# ==================== PRODUCTION REACT AGENT ====================

import asyncio
from datetime import datetime
from enum import Enum
import hashlib
import json
import time
import re  # CHANGED: for simple fact extraction (kebab-case)
from typing import Any, AsyncGenerator, Dict, List, Optional, ClassVar

from prometheus_client import Counter, Gauge, Histogram
from pydantic import BaseModel, Field
from pydantic import field_validator
import structlog

from capstone.prototype.feedback_collector import FeedbackCollector
from capstone.prototype.llm_provider import LLMProvider
from capstone.prototype.statemanager import StateManager
from capstone.prototype.todolist_md import (
    render_todolist_markdown,
)
from capstone.prototype.tools import (
    ToolSpec,
    export_openai_tools,
    build_tool_index,
    execute_tool_by_name_from_index,
)

# removed: from turtle import tracer  # CHANGED: conflicting with opentelemetry tracer
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

tracer = trace.get_tracer(__name__)

# Prometheus Metrics
workflow_counter = Counter('idp_workflows_started', 'Number of IDP workflows started')
workflow_success = Counter('idp_workflows_completed', 'Number of successful workflows')
workflow_failed = Counter('idp_workflows_failed', 'Number of failed workflows')
step_duration = Histogram('idp_step_duration_seconds', 'Duration of workflow steps', ['step_type'])
active_workflows = Gauge('idp_active_workflows', 'Number of currently active workflows')
tool_execution_time = Histogram('idp_tool_execution_seconds', 'Tool execution time', ['tool_name'])
tool_success_rate = Counter('idp_tool_success', 'Tool execution success', ['tool_name'])
tool_failure_rate = Counter('idp_tool_failure', 'Tool execution failures', ['tool_name'])

# ===== Default Generic Prompt (used in composed mode) =====
DEFAULT_GENERIC_PROMPT = (
    """
<GenericAgentSection>
You are a ReAct-style execution agent.

Operating principles:
- Plan-first: create/update a concise Todo List; clarify blocking questions first.
- Be deterministic, keep outputs minimal & actionable.
- After each tool call, update state; avoid loops; ask for help on blockers.

Decision policy:
- Prefer available tools; ask user only for truly blocking info.
- Stop when acceptance criteria for the mission are met.

Output style:
- Short, structured, CLI-friendly status lines.
</GenericAgentSection>
"""
).strip()

# ============ Action Space ============
class ActionType(Enum):
    TOOL_CALL = "tool_call"
    ASK_USER = "ask_user"
    COMPLETE = "complete"
    UPDATE_TODOLIST = "update_todolist"
    ERROR_RECOVERY = "error_recovery"

class ActionDecision(BaseModel):
    action_type: ActionType
    action_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    reasoning: str = ""
    confidence: float = Field(0.0, ge=0, le=1)

    @field_validator("action_type", mode="before")
    def _map_old_names(cls, v):
        if isinstance(v, str) and v.lower() == "update_checklist":
            return ActionType.UPDATE_TODOLIST
        return ActionType(v) if isinstance(v, str) else v

# Für die „Fragen zuerst?“-Heuristik lassen wir das LLM blocking Fragen strukturieren.
class BlockingQuestions(BaseModel):
    blocking: List[str] = Field(default_factory=list)
    optional: List[str] = Field(default_factory=list)


# ===== Structured Plan Models (Single Source of Truth) =====
class TaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class PlanTask(BaseModel):
    id: str
    title: str
    description: str | None = None
    tool: str | None = None
    executor_id: str | None = None
    action: str | None = None
    params: Dict[str, Any] | None = None
    status: TaskStatus = TaskStatus.PENDING
    depends_on: List[str] = Field(default_factory=list)
    priority: int | None = None
    notes: str | None = None
    owner_agent: str | None = None


class PlanOutput(BaseModel):
    tasks: List[PlanTask] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)

# ============ Agent ============
class ReActAgent:
    def __init__(
        self,
        system_prompt: str | None,
        llm: LLMProvider,
        *,
        tools: List[ToolSpec] | None = None,
        max_steps: int = 50,
        mission: str | None = None,
    ):
        """
        Initializes the ReActAgent with the given system prompt, LLM provider, tools, and maximum steps.
        Args:
            system_prompt: The system prompt for the LLM.
            llm: The LLM provider.            
            tools: The tools to use.
            max_steps: The maximum number of steps to take.
            mission: The mission for the agent.

        """
        self.system_prompt_base = (system_prompt or "").strip()
        self.llm = llm
        self.tools: List[ToolSpec] = tools or []  # keine Default-Tools -> generisch
        self.tool_index = build_tool_index(self.tools)
        self.max_steps = max_steps

        # New prompt composition fields
        self.mission_text: str | None = (mission or None)

        self.state = StateManager()
        self.feedback = FeedbackCollector()
        self.logger = structlog.get_logger()

        self.session_id: Optional[str] = None
        self.context: Dict[str, Any] = {}
        self.react_history: List[str] = []
        self.step = 0

        # Loop-Guard: keep recent action/observation signatures to detect repetition
        self._loop_signatures: List[str] = []
        # Duplicate-Action Guard: track executor/action/params hash and version
        self._duplicate_action_cache: Dict[str, int] = {}

        # Executor capabilities index (built from tools)
        self.executor_index: Dict[str, Dict[str, Any]] = {}

        # Build the final system prompt using the new builder (default: compose)
        self.final_system_prompt = self._build_final_system_prompt()
        try:
            self.logger.info(
                "final_system_prompt",
                prompt=self.final_system_prompt,
            )
        except Exception:
            # Logging must never break agent construction
            pass

        # Build executor capabilities index at construction
        try:
            self.executor_index = self._build_executor_index()
        except Exception:
            self.executor_index = {}

    async def process_request(self, user_input: str, session_id: Optional[str] = None) -> AsyncGenerator[str, None]:
        """
        Verarbeitet eine Benutzeranfrage und liefert schrittweise Status-Updates als asynchronen Generator.

        Diese Methode übernimmt die Steuerung des gesamten Agenten-Workflows für eine Session:
        - Initialisiert oder lädt den Session-Kontext (inkl. Wiederherstellung eines bestehenden Zustands)
        - Erkennt, ob auf eine Benutzereingabe gewartet wird, und verarbeitet ggf. die Antwort
        - Hält den aktuellen Stand der Benutzereingabe und des augmentierten Kontexts aktuell
        - Startet die eigentliche Verarbeitungsschleife (_react_loop), die die Aufgabenplanung, Tool-Aufrufe und Interaktionen mit dem LLM übernimmt
        - Gibt nach jedem Verarbeitungsschritt ein Update-String zurück, sodass der Aufrufer den Fortschritt verfolgen kann
        - Markiert den Workflow als erfolgreich oder fehlgeschlagen und gibt entsprechende Statusmeldungen aus
        - Sichert am Ende den aktuellen Zustand und spült gesammeltes Feedback asynchron auf die Festplatte

        Args:
            user_input (str): Die aktuelle Benutzereingabe, die verarbeitet werden soll.
            session_id (Optional[str]): Eine optionale Sitzungs-ID, um den Zustand zwischen Aufrufen zu persistieren.

        Returns:
            AsyncGenerator[str, None]: Ein asynchroner Generator, der Status- und Fortschrittsmeldungen als Strings liefert.
        """
        try:
            self.session_id = session_id or hashlib.md5(f"{user_input}{time.time()}".encode()).hexdigest()
            restored = await self.state.load_state(self.session_id)
            if restored:
                self._restore(restored)
                self.context["recent_user_message"] = user_input
                if self.context.get("awaiting_user_input"):
                    # Persist reply & extract simple facts
                    self._store_user_reply(user_input)  # CHANGED
                    # keep an augmented request blob for LLM prompts
                    base_req = self.context.get("user_request", "")
                    known = self.context.get("known_answers_text", "")
                    self.context["user_request_augmented"] = f"{base_req}\n\nKnown answers from user:\n{known}".strip()  # CHANGED
                    yield "📥 Danke! Ich mache weiter…\n"
            else:
                # Preserve any pre-seeded flags (e.g., suppress_markdown/ephemeral_state) from callers
                ctx_init = dict(self.context or {})
                ctx_init.update({
                    "user_request": user_input,
                    "session_id": self.session_id,
                    "started_at": datetime.now().isoformat(),
                })
                self.context = ctx_init
                self.context["recent_user_message"] = user_input
                # initial augmented = original
                self.context["user_request_augmented"] = self.context["user_request"]  # CHANGED
                # initialize plan version for optimistic concurrency (sub-agent patches)
                self.context["version"] = 1
                yield f"🚀 Neue Session: {self.session_id}\n"

            yield f"📝 Verarbeitung: {user_input}\n"
            async for update in self._react_loop():
                yield update

            # CHANGED: Only mark success if we're not waiting for user input
            if self.context.get("awaiting_user_input"):
                yield "\n⏸️ Warte auf deine Antwort …\n"
            else:
                workflow_success.inc()
                yield "\n✅ Fertig!\n"

        except Exception as e:
            workflow_failed.inc()
            self.logger.error("workflow_failed", error=str(e))
            yield f"\n❌ Fehler: {e}\n"
        finally:
            active_workflows.dec()
            await self._save()
            await self.feedback.flush_feedback()

    # ===== main ReAct loop =====
    async def _react_loop(self) -> AsyncGenerator[str, None]:
        """
        Die Hauptschleife des ReAct-Agenten steuert die gesamte Ausführung des Workflows. 
        Sie übernimmt folgende Aufgaben:
        
        1. Prüft zu Beginn, ob für die Erstellung eines initialen Plans (Todo-Liste) noch zwingend benötigte Informationen vom Nutzer fehlen. 
           Falls ja, werden diese Fragen gesammelt und dem Nutzer präsentiert, bevor der Plan erstellt wird.
        2. Erstellt, sofern alle Pflichtangaben vorliegen, eine initiale Todo-Liste und speichert diese im Kontext.
        3. Durchläuft anschließend einen iterativen ReAct-Zyklus, in dem für jeden Schritt:
            - Ein neuer Gedanke ("Thought") vom LLM generiert wird, der die aktuelle Situation bewertet.
            - Basierend darauf eine Aktionsentscheidung getroffen wird (z.B. Tool-Aufruf, Nutzerfrage, Abschluss).
            - Die gewählte Aktion ausgeführt und das Ergebnis ("Observation") gesammelt wird.
            - Der Kontext mit den neuen Informationen aktualisiert wird.
        4. Die Schleife endet, sobald entweder der Workflow abgeschlossen ist (COMPLETE) oder eine Nutzerinteraktion erforderlich wird (ASK_USER).
        5. Nach jeweils fünf Schritten wird der aktuelle Zustand persistiert.
        
        Die Methode liefert fortlaufend Status- und Fortschrittsmeldungen als asynchronen Generator zurück, die z.B. für eine UI oder ein Monitoring genutzt werden können.
        """

        # PLAN-FIRST: Ermittele blocking Fragen; wenn vorhanden -> erst ASK_USER
        if not self.context.get("todolist_created"):
            questions = await self._detect_blocking_questions()
            if questions.blocking:
                msg = await self._handle_user_interaction(
                    "ask_user",
                    {"questions": questions.blocking, "context": "Benötigte Angaben, um den Plan zu erstellen."},
                )
                yield f"❓ {msg}\n"
                return  # warte auf User

            # Todo-Liste erzeugen (Plan) – optional offene Fragen separat listen
            await self._create_initial_plan(open_questions=questions.optional)
            yield f"🗂️ Todo-Liste erstellt: {self.context.get('todolist_file')}\n"

        # Regelmäßiger ReAct-Zyklus
        while self.step < self.max_steps:
            self.step += 1
            yield f"\n--- Schritt {self.step} ---\n"

            # Phase 5: If we have a pending sub-agent question and now user inputs, attempt resume
            if self.context.get("pending_subagent_query") and self.context.get("user_inputs"):
                try:
                    pq = dict(self.context.get("pending_subagent_query") or {})
                    last_answer = str(self.context.get("user_inputs", [])[-1].get("answer") or "").strip()
                    if last_answer:
                        # Build a resume call to the same sub-agent tool
                        tool_name = str(pq.get("tool") or pq.get("agent_name") or "").strip()
                        state_token = pq.get("state_token")
                        params = {
                            "task": pq.get("task") or "Continue previous sub-agent task",
                            "inputs": {},
                            "shared_context": {
                                "session_id": self.session_id,
                                "version": int(self.context.get("version", 1)),
                                "facts": self.context.get("facts", {}),
                                "known_answers_text": self.context.get("known_answers_text", ""),
                                "user_inputs": self.context.get("user_inputs", []),
                                "tasks": self._get_tasks(),
                            },
                            "resume_token": state_token,
                            "answers": {"latest": last_answer},
                        }
                        obs = await self._handle_tool(tool_name, params)
                        yield f"🔁 Resume Sub-Agent: {obs}\n"
                        self.context.pop("pending_subagent_query", None)
                except Exception:
                    pass

            thought = await self._generate_thought()
            yield f"💭 Thought:\n{thought}\n"

            decision = await self._decide_next_action()
            yield f"⚡ Aktion: {decision.action_type.value} — {decision.action_name}\n"
            yield f"   Grund: {decision.reasoning}\n"

            started = time.time()
            observation = await self._exec_with_retry(decision)
            step_duration.labels(step_type=decision.action_type.value).observe(time.time() - started)

            yield f"👀 Observation:\n{observation}\n"

            # Loop-Guard: Detect three identical action/observation pairs in a row
            try:
                if self._record_and_check_loop(decision, observation, window_size=3):
                    if int(self.context.get("loop_guard_cooldown", 0)) <= 2:
                        msg = await self._handle_user_interaction(
                            "ask_user",
                            {
                                "questions": [
                                    "Ich erkenne wiederholte, wirkungslose Schritte. Hast du zusätzliche Informationen oder soll ich die Strategie ändern?"
                                ],
                                "context": "Loop-Guard: Drei identische Aktionen/Observations in Folge erkannt."
                            },
                        )
                        yield f"❓ {msg}\n"
                    else:
                        self.context["loop_guard_cooldown"] = 0
                        yield "⚠️ Loop erkannt → Strategie gewechselt (kein weiteres ask_user)."
                    break
            except Exception as e:
                self.logger.warning("loop_guard_failed", error=str(e))

            await self._update_context(decision, observation)
            if decision.action_type in {ActionType.COMPLETE, ActionType.ASK_USER}:
                break

            if self.step % 5 == 0:
                await self._save()

    # ===== Plan First =====
    async def _detect_blocking_questions(self) -> BlockingQuestions:
        """
        Lässt das LLM prüfen, ob wesentliche Pflichtinfos für ERSTE(n) Tool-Schritt(e) fehlen.
        Rückgabe trennt blocking (vor Plan) und optional (als Open Questions in den Plan).
        """
        # CHANGED: include augmented request + known answers + facts
        req = self.context.get("user_request_augmented") or self.context.get("user_request", "")
        last_msg = self.context.get("recent_user_message", "")
        facts = self.context.get("facts", {})
        user_inputs_struct = list(self.context.get("user_inputs", []))
        known_structured = "\n".join(
            f"- {str(ui.get('answer') or '').strip()}" for ui in user_inputs_struct if str(ui.get('answer') or '').strip()
        )
        known_legacy = self.context.get("known_answers_text", "")

        required_by_tool = []
        for spec in self.tools:
            reqs = list((spec.input_schema or {}).get("required", []))
            if reqs:
                required_by_tool.append({"tool": spec.name, "required": reqs})

        prompt = (
            "You are a planning assistant. Given the user's request, the available tools with their required "
            "parameters, and the known answers provided by the user, identify:\n"
            "1) blocking questions (without answers you cannot even start the first 1–2 steps)\n"
            "2) optional questions (nice-to-have refinements)\n\n"
            "IMPORTANT:\n"
            "- Do NOT include questions that are already answered by 'Known answers' or 'Facts'.\n"
            "- Prefer to proceed without questions when enough information is available to start.\n\n"
            f"User request:\n{req}\n\n"
            f"Recent user message:\n{last_msg}\n\n"
            f"Known answers (from structured inputs):\n{known_structured or known_legacy or '- none -'}\n\n"
            f"Facts (parsed):\n{json.dumps(facts, ensure_ascii=False, indent=2)}\n\n"
            f"User inputs (structured):\n{json.dumps(user_inputs_struct, ensure_ascii=False, indent=2)}\n\n"
            f"Tools and required params:\n{json.dumps(required_by_tool, ensure_ascii=False, indent=2)}"
        )
        try:
            return await self.llm.generate_structured_response(prompt, BlockingQuestions, system_prompt=self.final_system_prompt)
        except Exception:
            return BlockingQuestions()

    async def _create_initial_plan(self, *, open_questions: List[str]):
        """
        Erstellt den initialen Plan als strukturierte JSON-Struktur und rendert die Markdown-Ansicht deterministisch.

        Args:
            open_questions: Nicht-blockierende Fragen, die zusätzlich gelistet werden sollen.
        """
        user_req = self.context.get("user_request_augmented") or self.context.get("user_request", "")
        # Expose executor capabilities to the planner (with descriptions)
        exec_index = self.executor_index or {}
        visible_executors = [(eid, (exec_index[eid] or {}).get("label") or eid) for eid in exec_index.keys()]
        capabilities_map = {eid: [a.get("name") for a in (exec_index[eid].get("actions") or [])] for eid in exec_index.keys()}
        # Detailed map for the LLM with action descriptions and required params
        capabilities_detailed = {}
        for eid, cap in exec_index.items():
            actions_detailed = []
            for a in cap.get("actions", []) or []:
                params_schema = a.get("params_schema") or {}
                actions_detailed.append({
                    "name": a.get("name"),
                    "description": a.get("description") or "",
                    "required_params": list((params_schema.get("required") or [])),
                })
            capabilities_detailed[eid] = {
                "label": cap.get("label") or eid,
                "actions": actions_detailed,
            }
        prompt = (
            "Plan tasks for the user's request. Return JSON only, matching the schema.\n"
            "Guidelines:\n"
            "- Prefer 3–10 atomic, verifiable tasks.\n"
            "- Use only these executors and their actions.\n"
            "- Use action descriptions to decide scope: if one action can complete multiple subtasks, avoid splitting.\n"
            "- Avoid proposing tasks for unavailable executors/actions.\n"
            "- Prefer composite tools over manual multi-step sequences when available.\n"
            "- Avoid duplicate tasks (same executor_id + action + params).\n"
            "- Set executor_id from 'visible_executors' and action from 'capabilities_map[executor_id]'.\n"
            "- Include the exact tool name when applicable in field 'tool' (optional).\n"
            "- Provide stable 'id' (e.g., t1, t2), 'title', optional 'params', and initial 'status' = PENDING.\n"
            "- Fill 'open_questions' with clarifications that are nice-to-have (non-blocking).\n\n"
            f"User request:\n{user_req}\n\n"
            f"visible_executors = {json.dumps(visible_executors, ensure_ascii=False)}\n"
            f"capabilities_map = {json.dumps(capabilities_map, ensure_ascii=False)}\n"
            f"capabilities_detailed = {json.dumps(capabilities_detailed, ensure_ascii=False)}\n"
        )
        try:
            plan: PlanOutput = await self.llm.generate_structured_response(prompt, PlanOutput, system_prompt=self.final_system_prompt)
        except Exception:
            # Fallback to empty plan; we can proceed with tool decisions later
            plan = PlanOutput(tasks=[], open_questions=[])

        # Merge optional open questions detected earlier
        merged_oq = list((plan.open_questions or [])) + list(open_questions or [])
        # Ensure unique order-preserving
        seen = set()
        final_oq: List[str] = []
        for q in merged_oq:
            if q not in seen:
                final_oq.append(q)
                seen.add(q)

        # Reconcile, validate, and prune against capabilities
        tasks_dicts = [t.model_dump() for t in plan.tasks]
        try:
            tasks_dicts = self._reconcile_tasks_with_capabilities(tasks_dicts, self.executor_index)
            _ = self._validate_plan_against_capabilities(tasks_dicts, self.executor_index)
            tasks_dicts = self._prune_invalid_and_duplicate_tasks(tasks_dicts, self.executor_index)
        except Exception:
            pass

        # Persist authoritative state in context (as plain dicts for easy serialization)
        self.context["tasks"] = tasks_dicts
        self.context["open_questions"] = final_oq
        self.context["todolist_created"] = True

        # Render Markdown view unless suppressed (e.g., in sub-agent sandbox)
        if not self.context.get("suppress_markdown"):
            path = render_todolist_markdown(
                tasks=self.context["tasks"],
                open_questions=self.context.get("open_questions", []),
                session_id=self.session_id,
            )
            self.context["todolist_file"] = path

    # ===== ReAct inner pieces =====
    async def _generate_thought(self) -> str:
        summary = self._summary_for_llm()
        prompt = (
            f"Context:\n{summary}\n\n"
            "Think step by step about the single next best move. Consider the Todo List, tool availability, and errors. "
            "Keep it short."
        )
        try:
            return await self.llm.generate_response(prompt, system_prompt=self.final_system_prompt)
        except Exception:
            return "Analyze state and choose next safe, useful step."

    async def _decide_next_action(self) -> ActionDecision:
        summary = self._summary_for_llm()
        todostate = "created" if self.context.get("todolist_created") else "missing"

        # 1) Anbieter-Tool-Calling
        try:
            tools_fc = export_openai_tools(self.tools)
            meta = [
                {  # ✅ gültiges Schema: leeres Objekt erlaubt beliebige Felder
                "type": "function",
                "function": {
                    "name": "update_todolist",
                    "description": "Create or modify the Todo List",
                    "parameters": {
                        "type": "object",
                        "properties": {},               # <- wichtig
                        "additionalProperties": True
                    }
                }
                },
                {  # ✅ mit Properties
                "type": "function",
                "function": {
                    "name": "ask_user",
                    "description": "Ask user for information",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "questions": {"type": "array", "items": {"type": "string"}},
                            "context": {"type": "string"}
                        },
                        "required": ["questions"],
                        "additionalProperties": False
                    }
                }
                },
                {  # ✅ optionales summary
                "type": "function",
                "function": {
                    "name": "complete",
                    "description": "Finish the workflow",
                    "parameters": {
                        "type": "object",
                        "properties": { "summary": {"type": "string"} },
                        "additionalProperties": False
                    }
                }
                },
                {  # ✅ generisches Objekt
                "type": "function",
                "function": {
                    "name": "error_recovery",
                    "description": "Attempt generic error recovery",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": True
                    }
                }
                },
                {  # ✅ delegate_to_agent meta
                "type": "function",
                "function": {
                    "name": "delegate_to_agent",
                    "description": "Delegate a sub-task to a specialized sub-agent (registered as a tool)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "agent_name": {"type": "string"},
                            "task": {"type": "string"},
                            "inputs": {"type": "object"},
                            "allowed_tools": {"type": "array", "items": {"type": "string"}},
                            "budget": {"type": "object"}
                        },
                        "required": ["agent_name", "task"],
                        "additionalProperties": True
                    }
                }
                },
            ]
            call = await self.llm.call_tools(
                system_prompt=self.final_system_prompt,
                tools=tools_fc + meta,
                messages=[{
                    "role": "user",
                    "content": f"Context:\n{summary}\n\nTodoList: {todostate}\n"
                               "Call exactly one function for the next action."
                }],
            )
            if call:
                name = (call.get("name") or "").lower().strip()
                params = call.get("arguments") or {}
                if name == "update_todolist":
                    return ActionDecision(action_type=ActionType.UPDATE_TODOLIST, action_name="create_todolist", parameters=params, reasoning="Need to (re)generate or adjust the plan", confidence=0.9)
                if name == "ask_user":
                    return ActionDecision(action_type=ActionType.ASK_USER, action_name="ask_user", parameters=params, reasoning="Need user input", confidence=0.9)
                if name == "complete":
                    return ActionDecision(action_type=ActionType.COMPLETE, action_name="complete", parameters=params, reasoning="Done", confidence=0.9)
                if name == "error_recovery":
                    return ActionDecision(action_type=ActionType.ERROR_RECOVERY, action_name="retry_failed", parameters=params, reasoning="Try to recover", confidence=0.7)
                if name == "delegate_to_agent":
                    agent_name = str(params.get("agent_name") or "").strip()
                    tool_name = f"agent_{self._normalize_name(agent_name)}" if agent_name else ""
                    tool_params = {
                        "task": params.get("task"),
                        "inputs": params.get("inputs") or {},
                        "shared_context": {
                            "session_id": self.session_id,
                            "version": int(self.context.get("version", 1)),
                            "facts": self.context.get("facts", {}),
                            "known_answers_text": self.context.get("known_answers_text", ""),
                        },
                        "allowed_tools": params.get("allowed_tools") or [],
                        "budget": params.get("budget") or {},
                    }
                    return ActionDecision(action_type=ActionType.TOOL_CALL, action_name=tool_name, parameters=tool_params, reasoning="Delegate to sub-agent tool", confidence=0.85)
                return ActionDecision(action_type=ActionType.TOOL_CALL, action_name=name, parameters=params, reasoning="Execute tool", confidence=0.8)
        except Exception as e:
            self.logger.warning("tool_calling_failed", error=str(e))

        # 2) Fallback: strukturierte Entscheidung
        prompt = (
            f"Context:\n{summary}\n\n"
            "Available actions: UPDATE_TODOLIST | TOOL_CALL | ASK_USER | ERROR_RECOVERY | COMPLETE\n"
            "Return the best next action."
        )
        try:
            dec = await self.llm.generate_structured_response(prompt, ActionDecision, system_prompt=self.final_system_prompt)
            # If we detect completion condition, force COMPLETE unless ASK_USER
            if dec.action_type != ActionType.ASK_USER and self._all_tasks_completed():
                return ActionDecision(action_type=ActionType.COMPLETE, action_name="complete", parameters={"summary": "All tasks completed."}, reasoning="All tasks done", confidence=0.95)
            if dec.action_type != ActionType.ASK_USER and not self.context.get("todolist_created"):
                return ActionDecision(action_type=ActionType.UPDATE_TODOLIST, action_name="create_todolist", parameters={}, reasoning="Bootstrap the plan", confidence=dec.confidence)
            return dec
        except Exception:
            return ActionDecision(action_type=ActionType.ERROR_RECOVERY, action_name="analyze", parameters={}, reasoning="Could not decide", confidence=0.5)

    async def _exec_with_retry(self, decision: ActionDecision, max_retries: int = 3) -> str:
        for attempt in range(1, max_retries + 1):
            try:
                res = await self._execute(decision.action_type, decision.action_name, decision.parameters)
                await self.feedback.collect_feedback(self.session_id, feedback_type=decision.action_type.value, success=True, details={"action": decision.action_name, "attempt": attempt})
                return res
            except Exception as e:
                self.logger.warning("action_failed", action=decision.action_name, attempt=attempt, error=str(e))
                if attempt == max_retries:
                    await self.feedback.collect_feedback(self.session_id, feedback_type=decision.action_type.value, success=False, details={"action": decision.action_name, "error": str(e)})
                    return f"Action '{decision.action_name}' failed after {max_retries} attempts: {e}"
                await asyncio.sleep(2 ** (attempt - 1))

    async def _execute(self, kind: ActionType, name: str, params: Dict[str, Any]) -> str:
        if kind == ActionType.UPDATE_TODOLIST:
            return await self._handle_todolist(name, params)
        if kind == ActionType.TOOL_CALL:
            return await self._handle_tool(name, params)
        # NOTE: delegate_to_agent will be routed as TOOL_CALL to agent_* tool names by LLM meta function
        if kind == ActionType.ASK_USER:
            return await self._handle_user_interaction(name, params)
        if kind == ActionType.ERROR_RECOVERY:
            return "Tried generic recovery (noop)."
        if kind == ActionType.COMPLETE:
            return params.get("summary", "OK")
        return f"Executed {kind.value}/{name}"

    # ===== TodoList handling (no LLM edits; Markdown is a view) =====
    async def _handle_todolist(self, action: str, params: Dict[str, Any]) -> str:
        act = action.lower().replace("-", "_").replace(" ", "_")
        if act in {"create_todolist", "create"}:
            # If a Todo List already exists, do NOT re-generate the plan to avoid overwriting state.
            # Only re-render the Markdown view from the authoritative in-memory state.
            if self.context.get("todolist_created"):
                self._render_markdown_view()
                return f"Todo List already exists at {self.context.get('todolist_file')}; skipped re-create."
            # Otherwise, create the initial plan
            await self._create_initial_plan(open_questions=[])
            return f"Todo List created at {self.context.get('todolist_file')}"
        if act == "update_item_status":
            # Back-compat: allow structured params {item_id,status,notes}
            item_id = params.get("item_id")
            status_text = str(params.get("status", "")).upper() or "PENDING"
            notes = params.get("notes")
            if not item_id:
                return "No item_id provided."
            updated = self._update_task_by_id(item_id, status_text, notes)
            if not updated:
                return f"Task '{item_id}' not found."
            self._render_markdown_view()
            return "Todo List updated."
        return f"Todo action '{action}' done"

    async def _handle_tool(self, tool_name: str, params: Dict[str, Any]) -> str:
        if not self.context.get("todolist_created"):
            await self._create_initial_plan(open_questions=[])
        norm = self._normalize_name(tool_name)

        # Instrumentation: execution time start (must be available for all paths)
        started_at = time.time()

        # Log which tool is about to be executed and acting agent identity
        try:
            agent_identity = str(self.context.get("agent_name") or "orchestrator").strip()
            self.logger.info(
                "tool_call_start",
                agent=agent_identity,
                tool=norm,
                raw_tool_name=str(tool_name),
                params_preview=list(sorted((params or {}).keys()))[:8],
            )
        except Exception:
            pass

        # Duplicate-Action Guard: skip if same executor/action/params caused no change previously
        try:
            exec_id = self._executor_id_for_tool(norm)
            action_name = self._action_for_tool(norm)
            params_hash = hashlib.md5(json.dumps(params, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
            sig = f"{exec_id}|{action_name}|{params_hash}"
            last_version = self._duplicate_action_cache.get(sig)
            if last_version is not None and int(self.context.get("version", 1)) == last_version:
                msg = await self._handle_user_interaction(
                    "ask_user",
                    {
                        "questions": [
                            "Gleiche Aktion mit identischen Parametern ohne Zustandsänderung erkannt. Zusätzliche Hinweise oder Strategie ändern?"
                        ],
                        "context": f"executor={exec_id}, action={action_name}",
                    },
                )
                # Ensure matching end-log even when we early-return due to duplicate guard
                try:
                    self.logger.info(
                        "tool_call_end",
                        tool=norm,
                        success=True,
                        duration_ms=int((time.time() - started_at) * 1000),
                    )
                except Exception:
                    pass
                return f"⏭️ Duplicate action guarded. {msg}"
        except Exception:
            pass

        # Deterministic status update: IN_PROGRESS only if not already COMPLETED
        try:
            idx_for_tool = self._find_task_for_tool(norm)
            if idx_for_tool is not None:
                cur_status = str(self._get_tasks()[idx_for_tool].get("status", "PENDING")).upper()
                if cur_status != TaskStatus.COMPLETED.value:
                    self._mark_task_for_tool(norm, TaskStatus.IN_PROGRESS)
                    self._render_markdown_view()
        except Exception:
            # Never fail the execution due to status pre-checks
            self._mark_task_for_tool(norm, TaskStatus.IN_PROGRESS)
            self._render_markdown_view()

        # Instrumentation: success/failure counters
        # Build tool params from decision without injecting non-serializable objects
        tool_params = dict(params or {})
        # If the target tool declares 'shared_context' in its schema, provide it by default
        try:
            spec = self.tool_index.get(self._normalize_name(tool_name))
            props = dict((spec.input_schema or {}).get("properties") or {}) if spec else {}
            if ("shared_context" in props):
                # Merge or create shared_context with tasks and target_task_id
                sc = dict(tool_params.get("shared_context") or {})
                sc.setdefault("session_id", self.session_id)
                sc.setdefault("version", int(self.context.get("version", 1)))
                sc.setdefault("facts", self.context.get("facts", {}))
                sc.setdefault("known_answers_text", self.context.get("known_answers_text", ""))
                sc.setdefault("user_inputs", self.context.get("user_inputs", []))
                # expose master tasks mapping and the current target task id for deterministic patching
                sc["tasks"] = self._get_tasks()
                try:
                    current_idx = self._find_task_for_tool(norm)
                    if current_idx is not None:
                        sc["target_task_id"] = str(self._get_tasks()[current_idx].get("id"))
                except Exception:
                    pass
                tool_params["shared_context"] = sc
        except Exception:
            pass
        before_version = int(self.context.get("version", 1))
        result = await execute_tool_by_name_from_index(self.tool_index, norm, tool_params)
        duration = time.time() - started_at
        try:
            tool_execution_time.labels(tool_name=norm).observe(duration)
            if bool(result.get("success")):
                tool_success_rate.labels(tool_name=norm).inc()
            else:
                tool_failure_rate.labels(tool_name=norm).inc()
        except Exception:
            # Metrics must never break the agent
            pass
        success = bool(result.get("success"))
        status = "COMPLETED" if success else "FAILED"
        result_text = json.dumps(result, ensure_ascii=False)

        # Log end of tool call with status
        try:
            self.logger.info(
                "tool_call_end",
                tool=norm,
                success=success,
                duration_ms=int(duration * 1000),
            )
        except Exception:
            pass

        # Special handling for sub-agent contract (generic; independent of tool name)
        # Bubble-up need_user_input without marking task failed
        if not success and result.get("need_user_input"):
            need = result.get("need_user_input") or {}
            self.context["pending_subagent_query"] = {
                "tool": tool_name,
                "state_token": result.get("state_token"),
                "questions": need.get("questions") or [],
                "context": need.get("context") or "",
                "task": params.get("task"),
                # propagate the sub-agent's identity if present in result or params
                "agent_name": str(need.get("agent_name") or params.get("agent_name") or tool_name),
            }
            _ = await self._handle_user_interaction(
                "ask_user",
                {
                    "questions": list(need.get("questions") or []),
                    "context": need.get("context") or "Sub-Agent requires additional information.",
                    "agent_name": str(need.get("agent_name") or params.get("agent_name") or tool_name),
                },
            )
            self._mark_task_for_tool(norm, TaskStatus.IN_PROGRESS, notes=result_text)
            self._render_markdown_view()
            # Ensure end log before returning to wait for user input
            try:
                self.logger.info(
                    "tool_call_end",
                    tool=norm,
                    success=False,
                    duration_ms=int((time.time() - started_at) * 1000),
                )
            except Exception:
                pass
            return "Sub-agent requires user input; awaiting response."

        # If sub-agent returned a patch, apply it
        patch = result.get("patch")
        if success and isinstance(patch, dict):
            merge_res = self._apply_patch(patch)
            result_text = json.dumps({"subagent_result": result, "merge": merge_res}, ensure_ascii=False)
            # Retry once on no-op applied=0: refresh capabilities, reconcile+revalidate, retry
            if merge_res.get("success") and int(merge_res.get("applied", 0)) == 0 and not merge_res.get("error"):
                # Retry once after reconciling tasks with current capabilities
                self.executor_index = self._build_executor_index()
                try:
                    tasks = self._reconcile_tasks_with_capabilities(self._get_tasks(), self.executor_index)
                    _ = self._validate_plan_against_capabilities(tasks, self.executor_index)
                    self._set_tasks(tasks)
                except Exception:
                    pass
                merge_res_retry = self._apply_patch(patch)
                result_text = json.dumps({"subagent_result": result, "merge": merge_res_retry}, ensure_ascii=False)
                if int(merge_res_retry.get("applied", 0)) == 0:
                    # Treat as no-op but successful sub-agent run; mark current task completed and continue
                    self._mark_task_for_tool(norm, TaskStatus.COMPLETED, notes=result_text)
                    self._render_markdown_view()
                    # Ensure we always emit a tool_call_end for this successful no-op path
                    try:
                        self.logger.info(
                            "tool_call_end",
                            tool=norm,
                            success=True,
                            duration_ms=int((time.time() - started_at) * 1000),
                        )
                    except Exception:
                        pass
                    return "No-Op patch: marked task completed"

            # On conflict (e.g., 409 or ownership issues), ask user instead of completing
            if (not bool(merge_res.get("success"))) or merge_res.get("error"):
                self._mark_task_for_tool(norm, TaskStatus.IN_PROGRESS, notes=result_text)
                self._render_markdown_view()
                msg = await self._handle_user_interaction(
                    "ask_user",
                    {
                        "questions": [
                            "Konflikt bei Sub-Agent-Patch (Version/Ownership). Wie fortfahren?"
                        ],
                        "context": str(merge_res),
                    },
                )
                # Emit end log for conflict path as well
                try:
                    self.logger.info(
                        "tool_call_end",
                        tool=norm,
                        success=False,
                        duration_ms=int((time.time() - started_at) * 1000),
                    )
                except Exception:
                    pass
                return f"⚠️ Patch-Konflikt: {msg}"
            self._mark_task_for_tool(norm, TaskStatus.COMPLETED, notes=result_text)
            self._render_markdown_view()
            return f"Applied sub-agent patch: {json.dumps(merge_res)}"

        # Deterministic status update after execution (generic tools)
        # Never downgrade a COMPLETED task back to IN_PROGRESS/FAILED due to noisy results
        try:
            idx_for_tool = self._find_task_for_tool(norm)
            if idx_for_tool is not None:
                cur_status = str(self._get_tasks()[idx_for_tool].get("status", "PENDING")).upper()
                next_status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
                if cur_status == TaskStatus.COMPLETED.value and next_status != TaskStatus.COMPLETED:
                    # keep completed; just append notes
                    tasks = self._get_tasks()
                    if result_text:
                        tasks[idx_for_tool]["notes"] = result_text
                        self._set_tasks(tasks)
                        self._render_markdown_view()
                else:
                    self._mark_task_for_tool(norm, next_status, notes=result_text)
                    self._render_markdown_view()
            else:
                self._mark_task_for_tool(norm, TaskStatus.COMPLETED if success else TaskStatus.FAILED, notes=result_text)
                self._render_markdown_view()
        except Exception:
            self._mark_task_for_tool(norm, TaskStatus.COMPLETED if success else TaskStatus.FAILED, notes=result_text)
            self._render_markdown_view()

        # Generische Blocker-Hinweise ins Context
        err = (result.get("error") or "").strip()
        if err:
            self.context["blocker"] = {
                "message": err,
                "suggestion": "Gib korrigierte Parameter oder weitere Hinweise; ansonsten anderes Tool wählen."
            }

        # If all tasks are completed, hint to COMPLETE
        if self._all_tasks_completed():
            self.context["suggest_complete"] = True

        # Record duplicate-action guard signature if no version change occurred
        try:
            after_version = int(self.context.get("version", 1))
            if after_version == before_version:
                exec_id = self._executor_id_for_tool(norm)
                action_name = self._action_for_tool(norm)
                params_hash = hashlib.md5(json.dumps(params, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
                sig = f"{exec_id}|{action_name}|{params_hash}"
                self._duplicate_action_cache[sig] = after_version
        except Exception:
            pass

        return f"{tool_name} -> {json.dumps(result, indent=2)}"

    # ===== Sub-agent as ToolSpec factory =====
    def to_tool(
        self,
        *,
        name: str,
        description: str,
        allowed_tools: Optional[List[str]] = None,
        budget: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = 120.0,
        aliases: Optional[List[str]] = None,
        system_prompt_override: Optional[str] = None,  # deprecated: mapped to mission_override
        mission_override: Optional[str] = None,
    ) -> ToolSpec:
        """Return a ToolSpec that wraps this agent as a sub-agent tool.

        The wrapper runs a fresh ReActAgent instance with the same LLM and a tool whitelist.
        Inputs follow the sub-agent schema: task, inputs, shared_context, budget, resume_token, answers.
        """
        async def _subagent_tool(
            *,
            task: str,
            inputs: Optional[Dict[str, Any]] = None,
            shared_context: Optional[Dict[str, Any]] = None,
            budget: Optional[Dict[str, Any]] = None,
            resume_token: Optional[str] = None,
            answers: Optional[Dict[str, Any]] = None,
            **kwargs: Any,
        ) -> Dict[str, Any]:
            names = set(allowed_tools or [])
            tools_whitelist = [t for t in self.tools if not names or t.name in names]
            effective_mission = mission_override or system_prompt_override or None

            # --- snapshot original agent config
            _orig_tools = self.tools
            _orig_index = self.tool_index
            _orig_max_steps = self.max_steps
            _orig_mission = self.mission_text
            _orig_prompt = self.final_system_prompt
            _orig_session = self.session_id
            _orig_context = dict(self.context or {})

            sub_awaiting: Optional[Dict[str, Any]] = None
            sub_tasks_snapshot: List[Dict[str, Any]] = []
            try:
                # sandbox apply
                self.tools = tools_whitelist
                self.tool_index = build_tool_index(self.tools)
                if budget and "max_steps" in budget:
                    try:
                        self.max_steps = int(budget["max_steps"])
                    except Exception:
                        pass
                if effective_mission is not None:
                    self.mission_text = effective_mission
                    self.final_system_prompt = self._build_final_system_prompt()

                parent_sid = (shared_context or {}).get("session_id") or "no-session"
                self.session_id = f"{parent_sid}:sub:{name}"
                self.context = {
                    "user_request": task,
                    "known_answers_text": (shared_context or {}).get("known_answers_text", ""),
                    "user_inputs": (shared_context or {}).get("user_inputs", []),
                    "facts": (shared_context or {}).get("facts", {}),
                    "version": int((shared_context or {}).get("version", 1)),
                    "suppress_markdown": True,
                    "ephemeral_state": True,
                    "no_user_prompts": True,
                    "agent_name": name,
                }

                transcript: List[str] = []
                async for chunk in self.process_request(task, session_id=self.session_id):
                    transcript.append(chunk)
                # capture sub-agent state before rollback
                try:
                    sub_awaiting = self.context.get("awaiting_user_input")
                except Exception:
                    sub_awaiting = None
                try:
                    sub_tasks_snapshot = list(self.context.get("tasks", []))
                except Exception:
                    sub_tasks_snapshot = []
            finally:
                # rollback sandbox
                self.tools = _orig_tools
                self.tool_index = _orig_index
                self.max_steps = _orig_max_steps
                self.mission_text = _orig_mission
                self.final_system_prompt = _orig_prompt
                self.session_id = _orig_session
                self.context = _orig_context

            if sub_awaiting:
                return {
                    "success": False,
                    "need_user_input": sub_awaiting,
                    "state_token": "opaque",
                }

            # Build patch as update-only against master tasks to avoid duplicates and regressions
            master_tasks = list((shared_context or {}).get("tasks", []))
            target_task_id = str((shared_context or {}).get("target_task_id") or "").strip() or None
            wrapper_norm = name.strip().lower().replace("-", "_").replace(" ", "_")
            def _norm(s: str) -> str:
                return s.strip().lower().replace("-", "_").replace(" ", "_")
            def _find_master_task_id_by_tool(tool_name: str) -> Optional[str]:
                # 0) If orchestrator provided a target_task_id, use it deterministically
                if target_task_id:
                    return target_task_id
                norm = _norm(tool_name)
                # 1) Direct match on tool field
                for mt in master_tasks:
                    ttool = _norm(str(mt.get("tool") or ""))
                    if ttool and ttool == norm:
                        return str(mt.get("id"))
                # 2) Match on prefixed tool name (e.g., agent_git.create_repository)
                for mt in master_tasks:
                    ttool = _norm(str(mt.get("tool") or ""))
                    if ttool and ttool == f"{wrapper_norm}.{norm}":
                        return str(mt.get("id"))
                # 3) Fallback: match by executor_id + action
                for mt in master_tasks:
                    exec_id = _norm(str(mt.get("executor_id") or ""))
                    action = _norm(str(mt.get("action") or ""))
                    if action == norm and (not exec_id or exec_id == wrapper_norm):
                        return str(mt.get("id"))
                return None

            ops: list[dict] = []
            for t in sub_tasks_snapshot:
                tool_name = str(t.get("tool") or "").strip()
                status = str(t.get("status") or "").upper()
                if not tool_name:
                    continue
                if status not in {"IN_PROGRESS", "COMPLETED"}:
                    continue
                tid = _find_master_task_id_by_tool(tool_name)
                if not tid:
                    continue
                ops.append({
                    "op": "update",
                    "task_id": tid,
                    "fields": {"status": status}
                })

            patch = {
                "base_version": int((shared_context or {}).get("version", 1)),
                "agent_name": name,
                "ops": ops,
            }

            return {"success": True, "patch": patch, "result": {"transcript": "".join(transcript)}}

        schema = {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "inputs": {"type": "object"},
                "shared_context": {"type": "object"},
                "budget": {"type": "object"},
                "resume_token": {"type": "string"},
                "answers": {"type": "object"},
            },
            "required": ["task"],
            "additionalProperties": True,
        }

        # Capabilities provider advertises sub-agent actions based on its internal tool whitelist
        def _caps_provider() -> Dict[str, Any]:
            names = set(allowed_tools or [])
            tools_whitelist = [t for t in self.tools if not names or t.name in names]
            actions = []
            for t in tools_whitelist:
                try:
                    actions.append({
                        "name": self._normalize_name(t.name),
                        "description": t.description,
                        "params_schema": t.input_schema or {"type": "object"},
                        "acceptance": None
                    })
                except Exception:
                    continue
            return {
                "executor_id": self._normalize_name(name),
                "label": description or name,
                "version": "cap-v1",
                "actions": actions,
            }

        return ToolSpec(
            name=name,
            description=description,
            input_schema=schema,
            output_schema={"type": "object"},
            func=_subagent_tool,
            is_async=True,
            timeout=timeout,
            aliases=aliases or [],
            capabilities_provider=_caps_provider,
        )

    # ===== Prompt Builder (new) =====
    def _build_final_system_prompt(self) -> str:
        """Compose the final system prompt in three sections or use legacy_full as requested.

        Modes:
          - compose (default): <GenericAgentSection> + <Mission> + <Tools>
          - legacy_full: use self.system_prompt_base 1:1 (back-compat path)
        """
        # Generic section
        generic = (self.system_prompt_base or DEFAULT_GENERIC_PROMPT).strip()

        # Mission section (always present, may be empty)
        mission = (self.mission_text or "").strip()

        # Tools section from ToolSpec list
        tool_lines: List[str] = []
        for spec in self.tools:
            req = list((spec.input_schema or {}).get("required", []))
            tool_lines.append(f"- {spec.name}: {spec.description}")
            if req:
                tool_lines.append(f"  required: {', '.join(req)}")

        parts = [
            "<GenericAgentSection>",
            generic,
            "</GenericAgentSection>",
            "",
            "<Mission>",
            mission,
            "</Mission>",
            "",
            "<Tools>",
            "\n".join(tool_lines) if tool_lines else "",
            "</Tools>",
        ]
        return "\n".join(parts).strip()

    # ===== ASK_USER =====
    async def _handle_user_interaction(self, action_name: str, params: Dict[str, Any]) -> str:
        # Block user prompts entirely for sub-agents when flagged
        if self.context.get("no_user_prompts"):
            return "Sub-agent: user prompts disabled"
        questions = params.get("questions") or []
        ctx = params.get("context") or ""
        try:
            # Improve observability: include agent identity and session in logs
            agent_name = str(self.context.get("agent_name") or params.get("agent_name") or "").strip() or None
            self.logger.info(
                "ask_user_triggered",
                agent=agent_name,
                session_id=self.session_id,
                action=action_name,
                num_questions=len(questions),
            )
        except Exception:
            pass
        self.context["awaiting_user_input"] = {
            "action": action_name,
            "questions": questions,
            "context": ctx,
            "requested_at": datetime.now().isoformat()
        }
        await self._save()
        lines = ["User input needed:", f"Context: {ctx}"]
        if questions:
            lines.append("Questions:")
            for i, q in enumerate(questions, 1):
                lines.append(f"  {i}. {q}")
        lines.append("\nBitte antworte frei-form.")
        return "\n".join(lines)

    # ===== helpers =====
    def _store_user_reply(self, msg: str):
        awaiting = self.context.get("awaiting_user_input") or {}
        entry = {
            "answer": msg,
            "for_action": awaiting.get("action"),
            "questions": awaiting.get("questions", []),
            "provided_at": datetime.now().isoformat(),
        }
        self.context.setdefault("user_inputs", []).append(entry)
        self.context.pop("awaiting_user_input", None)

        # CHANGED: keep known answers text blob for prompts
        answers_text = self.context.get("known_answers_text", "")
        answers_text += f"\n- {msg}"
        self.context["known_answers_text"] = answers_text.strip()

        # CHANGED: simple fact extraction (kebab-case -> project_name)
        m = re.search(r"\b([a-z0-9]+(?:-[a-z0-9]+)+)\b", msg)
        if m:
            self.context.setdefault("facts", {})["project_name"] = m.group(1)

    def _summary_for_llm(self) -> str:
        lines = [
            f"Session: {self.session_id}",
            f"User Request: {self.context.get('user_request','')}",
            f"Step: {self.step}/{self.max_steps}",
        ]
        if self.context.get("recent_user_message"):
            lines.append(f"Recent User Message: {self.context['recent_user_message']}")
        tasks = self.context.get("tasks")
        if tasks:
            lines.append(f"Tasks: {len(tasks)} total")
            # Show up to first 5 tasks with minimal info for planning
            for t in tasks[:5]:
                tid = t.get("id")
                title = t.get("title")
                status = t.get("status")
                tool = t.get("tool") or "-"
                lines.append(f"  - {tid}: {title} [{status}] (tool: {tool})")
        else:
            lines.append("Tasks: none yet")
        if self.context.get("todolist_file"):
            lines.append(f"Todo List File: {self.context['todolist_file']}")
        if self.react_history:
            lines.append("Recent Actions:")
            for a in self.react_history[-8:]:
                lines.append("  - " + a)
        if self.context.get("blocker"):
            lines.append(f"Blocker: {self.context['blocker']}")
        if self.context.get("known_answers_text"):  # CHANGED: add known answers to summary context
            lines.append("Known Answers:")
            lines.append(self.context["known_answers_text"])
        if self.context.get("facts"):  # CHANGED: add parsed facts
            lines.append(f"Facts: {self.context['facts']}")
        return "\n".join(lines)

    async def _update_context(self, decision: ActionDecision, observation: str):
        self.context["last_action"] = {
            "type": decision.action_type.value, "name": decision.action_name,
            "result": observation, "timestamp": datetime.now().isoformat()
        }
        self.react_history.append(f"{decision.action_name} -> {observation[:100]}")
        if len(self.react_history) > 32:
            self.react_history = self.react_history[-32:]

    def _record_and_check_loop(self, decision: ActionDecision, observation: str, *, window_size: int = 3) -> bool:
        """
        Record a normalized signature of the (action, observation) pair and
        return True if the last `window_size` signatures are identical.
        """
        sig = self._signature_for_loop(decision, observation)
        self._loop_signatures.append(sig)
        if len(self._loop_signatures) > window_size:
            self._loop_signatures = self._loop_signatures[-window_size:]
        if len(self._loop_signatures) == window_size and len(set(self._loop_signatures)) == 1:
            self.context["loop_guard_cooldown"] = int(self.context.get("loop_guard_cooldown", 0)) + 1
            return True
        return False

    def _signature_for_loop(self, decision: ActionDecision, observation: str) -> str:
        # Normalize observation to reduce noise and truncate to a stable prefix
        obs = observation.strip().lower()
        obs = re.sub(r"\s+", " ", obs)
        obs = obs[:160]
        return f"{decision.action_type.value}|{decision.action_name.lower()}|{obs}"

    async def _save(self):
        if self.context.get("ephemeral_state"):
            return
        await self.state.save_state(self.session_id, {
            "context": self.context,
            "react_history": self.react_history,
            "step": self.step,
        })

    def _restore(self, s: Dict[str, Any]):
        self.context = s.get("context", {})
        self.react_history = s.get("react_history", [])
        self.step = s.get("step", 0)

    def _compose_system_prompt(self) -> str:
        lines = [self.system_prompt_base, "\n## TOOLS (dynamic)\n"]
        for spec in self.tools:
            req = list((spec.input_schema or {}).get("required", []))
            lines.append(f"- {spec.name}: {spec.description}")
            if req: lines.append(f"  required: {', '.join(req)}")
        lines.append(
            "\nUsage rules:\n"
            "- Use only listed tools.\n"
            "- First, build a Todo List (plan) as structured JSON; minor clarifications go into 'Open Questions'.\n"
            "- After each tool run, status is updated deterministically; Markdown is a view only.\n"
            "- If a blocking error occurs, ASK_USER with concrete suggestions."
        )
        return "\n".join(lines)

    # ===== Structured Task helpers =====
    def _normalize_name(self, name: str) -> str:
        return name.strip().lower().replace("-", "_").replace(" ", "_")

    # ===== Capabilities & Planning helpers =====
    def _build_executor_index(self) -> Dict[str, Dict[str, Any]]:
        """Build executor capabilities from registered tools.

        For tools without explicit capabilities, synthesize a single action using the tool name.
        Returns a map executor_id -> capabilities dict with keys: executor_id, label, version, actions[].
        """
        index: Dict[str, Dict[str, Any]] = {}
        for spec in self.tools:
            try:
                cap: Dict[str, Any]
                # If tool provides its own capabilities
                if getattr(spec, "capabilities_provider", None):
                    cap = spec.capabilities_provider()  # type: ignore[misc]
                    eid = str(cap.get("executor_id") or self._normalize_name(spec.name))
                    cap["executor_id"] = eid
                    index[eid] = cap
                else:
                    eid = self._normalize_name(spec.name)
                    cap = {
                        "executor_id": eid,
                        "label": spec.name,
                        "version": "cap-v1",
                        "actions": [
                            {
                                "name": self._normalize_name(spec.name),
                                "description": getattr(spec, "description", spec.name),
                                "params_schema": spec.input_schema or {"type": "object"},
                                "acceptance": None,
                            }
                        ],
                    }
                    index[eid] = cap
                try:
                    # Structured capability log per executor
                    self.logger.info(
                        "executor_capabilities",
                        executor_id=index[eid]["executor_id"],
                        label=index[eid].get("label"),
                        version=index[eid].get("version"),
                        actions=[a.get("name") for a in index[eid].get("actions", [])],
                    )
                except Exception:
                    pass
            except Exception:
                continue
        # Keep in context for prompts/visibility
        self.context["executor_index"] = index
        return index

    def _executor_id_for_tool(self, tool_norm: str) -> str:
        # Prefer matching synthesized eid equal to tool name
        eid = self._normalize_name(tool_norm)
        if eid in self.executor_index:
            return eid
        # Fallback: first executor containing an action matching tool name
        for k, cap in (self.executor_index or {}).items():
            for a in cap.get("actions", []) or []:
                if self._normalize_name(a.get("name", "")) == tool_norm:
                    return k
        return eid

    def _action_for_tool(self, tool_norm: str) -> str:
        # Default action name equals normalized tool name for synthesized capabilities
        return self._normalize_name(tool_norm)

    def _validate_plan_against_capabilities(self, tasks: List[Dict[str, Any]], executor_index: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Validate tasks against capability index. Marks invalid tasks with status ERROR and notes.
        Returns a report dict; tasks are mutated in place with notes when invalid.
        """
        report = {"invalid": 0}
        for t in tasks:
            eid = t.get("executor_id")
            act = t.get("action")
            if not eid or eid not in executor_index:
                t["status"] = TaskStatus.FAILED.value
                t["notes"] = (t.get("notes") or "") + "; invalid executor_id"
                report["invalid"] += 1
                continue
            actions = [a.get("name") for a in executor_index[eid].get("actions", [])]
            if not act or self._normalize_name(act) not in [self._normalize_name(a) for a in actions]:
                t["status"] = TaskStatus.FAILED.value
                t["notes"] = (t.get("notes") or "") + "; invalid action"
                report["invalid"] += 1
        return report

    def _reconcile_tasks_with_capabilities(self, tasks: List[Dict[str, Any]], executor_index: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fill missing executor_id/action when determinable without domain knowledge."""
        # If only one executor, set missing executor_id
        visible = list(executor_index.keys())
        single_executor = visible[0] if len(visible) == 1 else None
        for t in tasks:
            # Derive executor_id from tool name if missing
            if not t.get("executor_id"):
                tool = (t.get("tool") or "").strip()
                if tool:
                    t["executor_id"] = self._executor_id_for_tool(self._normalize_name(tool))
                elif single_executor:
                    t["executor_id"] = single_executor
            # Derive action if missing or invalid and executor has single action
            eid = t.get("executor_id")
            if eid and eid in executor_index:
                actions = executor_index[eid].get("actions", [])
                if not t.get("action"):
                    if len(actions) == 1:
                        t["action"] = actions[0].get("name")
                    else:
                        # Try to match tool to action
                        tool = (t.get("tool") or "").strip()
                        cand = self._normalize_name(tool) if tool else None
                        for a in actions:
                            if cand and self._normalize_name(a.get("name", "")) == cand:
                                t["action"] = a.get("name")
                                break
        return tasks

    def _prune_invalid_and_duplicate_tasks(self, tasks: List[Dict[str, Any]], executor_index: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove tasks that reference non-existent executors/actions and collapse duplicates.

        Duplicate criteria: same normalized (executor_id, action, json.dumps(params, sort_keys=True)).
        """
        pruned: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for t in tasks:
            eid = t.get("executor_id")
            act = t.get("action")
            if not eid or eid not in executor_index:
                continue
            actions = [self._normalize_name(a.get("name")) for a in executor_index[eid].get("actions", [])]
            if not act or self._normalize_name(act) not in actions:
                continue
            try:
                params = t.get("params") or {}
                key = json.dumps({
                    "eid": self._normalize_name(eid),
                    "act": self._normalize_name(act),
                    "params": params,
                }, sort_keys=True, ensure_ascii=False)
            except Exception:
                key = f"{self._normalize_name(eid)}|{self._normalize_name(act)}"
            if key in seen:
                continue
            seen.add(key)
            pruned.append(t)
        # reassign stable ids t1..tn if missing or duplicate ids present
        assigned_ids: set[str] = set()
        for i, t in enumerate(pruned, start=1):
            tid = str(t.get("id") or "").strip()
            if not tid or tid in assigned_ids:
                t["id"] = f"t{i}"
            assigned_ids.add(str(t.get("id")))
        return pruned

    def _get_tasks(self) -> List[Dict[str, Any]]:
        return list(self.context.get("tasks", []))

    def _set_tasks(self, tasks: List[Dict[str, Any]]):
        self.context["tasks"] = tasks

    def _render_markdown_view(self):
        # Allow disabling Markdown rendering (e.g., for sub-agents)
        if self.context.get("suppress_markdown"):
            return
        try:
            # Ensure we never downgrade statuses while rendering; normalize first
            tasks = self._get_tasks()
            for t in tasks:
                t["status"] = self._normalize_status_value(t.get("status"))
            path = render_todolist_markdown(
                tasks=tasks,
                open_questions=self.context.get("open_questions", []),
                session_id=self.session_id,
            )
            self.context["todolist_file"] = path
        except Exception:
            # Rendering must not break execution
            pass

    def _find_task_for_tool(self, tool_norm: str) -> Optional[int]:
        tasks = self._get_tasks()
        # Prefer first task matching tool name that is not COMPLETED
        for idx, t in enumerate(tasks):
            t_tool = str(t.get("tool") or "").strip()
            status = str(t.get("status", "PENDING")).upper()
            if t_tool and self._normalize_name(t_tool) == tool_norm and status != TaskStatus.COMPLETED.value:
                return idx
        # Fallback: first PENDING/IN_PROGRESS task
        for idx, t in enumerate(tasks):
            status = str(t.get("status", "PENDING")).upper()
            if status in {TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value}:
                return idx
        return None

    def _mark_task_for_tool(self, tool_norm: str, status: TaskStatus, *, notes: str | None = None):
        idx = self._find_task_for_tool(tool_norm)
        if idx is None:
            return
        tasks = self._get_tasks()
        tasks[idx]["status"] = status.value
        if notes:
            tasks[idx]["notes"] = notes
        self._set_tasks(tasks)

    def _update_task_by_id(self, item_id: str, status_text: str, notes: Optional[str]) -> bool:
        tasks = self._get_tasks()
        for i, t in enumerate(tasks):
            if str(t.get("id")) == str(item_id):
                tasks[i]["status"] = status_text
                if notes:
                    tasks[i]["notes"] = notes
                self._set_tasks(tasks)
                return True
        return False

    # ===== Patch Engine (Sub-Agent -> Orchestrator) =====
    def _find_task_index_by_id(self, task_id: str) -> Optional[int]:
        tasks = self._get_tasks()
        for i, t in enumerate(tasks):
            if str(t.get("id")) == str(task_id):
                return i
        return None

    def _normalize_status_value(self, value: Any) -> str:
        """Normalize status values to uppercase strings like 'PENDING'/'COMPLETED'."""
        try:
            if isinstance(value, TaskStatus):
                return value.value
            s = str(value).strip()
            if "." in s and s.upper().startswith("TASKSTATUS"):
                s = s.split(".")[-1]
            return s.upper() or TaskStatus.PENDING.value
        except Exception:
            return TaskStatus.PENDING.value

    def _all_tasks_completed(self) -> bool:
        tasks = self._get_tasks()
        if not tasks:
            return False
        for t in tasks:
            if str(t.get("status", "")).upper() != TaskStatus.COMPLETED.value:
                return False
        return True

    def _apply_patch(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        """Apply a sub-agent patch with version/ownership guards.

        Patch format:
          {"base_version": int, "agent_name": str, "ops": [ ... ]}

        Supported ops:
          - {"op":"update", "task_id": str, "fields": {...}}
          - {"op":"add", "task": {...}}
          - {"op":"add_subtask", "parent_id": str, "task": {...}}
          - {"op":"link_dep", "task_id": str, "depends_on": [str,...]}
          - {"op":"unlink_dep", "task_id": str, "depends_on": [str,...]}
          - {"op":"set_status", "task_id": str, "value": "COMPLETED"}
          - {"op":"set_field", "task_id": str, "path": "notes", "value": "..."}
          - {"op":"append_task", "task": Task}
          - {"op":"remove_task", "task_id": str}
          - {"op":"replace_task", "task_id": str, "task": Task}
        """
        current_version = int(self.context.get("version", 1))
        base_version = int(patch.get("base_version") or patch.get("applied_to_plan_version") or current_version)
        agent_name = str(patch.get("agent_name") or "").strip() or None

        if base_version != current_version:
            return {"success": False, "error": f"409 Conflict: base_version {base_version} != current {current_version}"}

        tasks = self._get_tasks()
        applied: int = 0
        denied: list[str] = []

        for op in patch.get("ops", []) or []:
            try:
                kind = str(op.get("op") or "").lower()
                if kind == "update":
                    tid = op.get("task_id")
                    fields = dict(op.get("fields") or {})
                    idx = self._find_task_index_by_id(str(tid)) if tid else None
                    if idx is None:
                        denied.append(f"update:{tid}:not_found")
                        continue
                    owner = tasks[idx].get("owner_agent")
                    if owner and agent_name and owner != agent_name:
                        denied.append(f"update:{tid}:owner_mismatch")
                        continue
                    # allow updating standard fields only; ignore unknowns
                    for k in ["title", "description", "tool", "params", "status", "notes", "priority"]:
                        if k in fields:
                            if k == "status":
                                tasks[idx][k] = self._normalize_status_value(fields[k])
                            else:
                                tasks[idx][k] = fields[k]
                    applied += 1

                elif kind == "annotate":
                    tid = op.get("task_id")
                    note = str(op.get("note") or "").strip()
                    idx = self._find_task_index_by_id(str(tid)) if tid else None
                    if idx is None:
                        denied.append(f"annotate:{tid}:not_found")
                        continue
                    owner = tasks[idx].get("owner_agent")
                    if owner and agent_name and owner != agent_name:
                        denied.append(f"annotate:{tid}:owner_mismatch")
                        continue
                    cur = str(tasks[idx].get("notes") or "").strip()
                    tasks[idx]["notes"] = (cur + ("; " if cur and note else "") + note).strip()
                    applied += 1

                elif kind == "add":
                    t = dict(op.get("task") or {})
                    if agent_name:
                        t.setdefault("owner_agent", agent_name)
                    # default fields
                    t["status"] = self._normalize_status_value(t.get("status", TaskStatus.PENDING.value))
                    t.setdefault("id", f"t{len(tasks)+1}")
                    # de-duplicate by id: if exists, merge instead of append
                    exist_idx = self._find_task_index_by_id(str(t.get("id")))
                    if exist_idx is not None:
                        owner = tasks[exist_idx].get("owner_agent")
                        if owner and agent_name and owner != agent_name:
                            denied.append(f"add:{t.get('id')}:owner_mismatch")
                        else:
                            for k in ["title", "description", "tool", "params", "status", "notes", "priority", "owner_agent", "depends_on"]:
                                if k in t:
                                    if k == "status":
                                        tasks[exist_idx][k] = self._normalize_status_value(t[k])
                                    else:
                                        tasks[exist_idx][k] = t[k]
                            applied += 1
                    else:
                        tasks.append(t)
                        applied += 1

                elif kind == "add_subtask":
                    parent_id = op.get("parent_id")
                    t = dict(op.get("task") or {})
                    if agent_name:
                        t.setdefault("owner_agent", agent_name)
                    # mark relation in notes and depends_on
                    notes = (t.get("notes") or "").strip()
                    rel_note = f"subtask_of:{parent_id}"
                    t["notes"] = (notes + ("; " if notes else "") + rel_note).strip()
                    deps = list(t.get("depends_on") or [])
                    if parent_id:
                        deps.append(str(parent_id))
                    t["depends_on"] = sorted(set(map(str, deps)))
                    t["status"] = self._normalize_status_value(t.get("status", TaskStatus.PENDING.value))
                    t.setdefault("id", f"t{len(tasks)+1}")
                    # de-duplicate by id
                    exist_idx = self._find_task_index_by_id(str(t.get("id")))
                    if exist_idx is not None:
                        owner = tasks[exist_idx].get("owner_agent")
                        if owner and agent_name and owner != agent_name:
                            denied.append(f"add_subtask:{t.get('id')}:owner_mismatch")
                        else:
                            for k in ["title", "description", "tool", "params", "status", "notes", "priority", "owner_agent", "depends_on"]:
                                if k in t:
                                    if k == "status":
                                        tasks[exist_idx][k] = self._normalize_status_value(t[k])
                                    else:
                                        tasks[exist_idx][k] = t[k]
                            applied += 1
                    else:
                        tasks.append(t)
                        applied += 1

                elif kind == "link_dep":
                    tid = op.get("task_id")
                    links = [str(x) for x in (op.get("depends_on") or [])]
                    idx = self._find_task_index_by_id(str(tid)) if tid else None
                    if idx is None:
                        denied.append(f"link_dep:{tid}:not_found")
                        continue
                    owner = tasks[idx].get("owner_agent")
                    if owner and agent_name and owner != agent_name:
                        denied.append(f"link_dep:{tid}:owner_mismatch")
                        continue
                    cur = set(map(str, tasks[idx].get("depends_on") or []))
                    cur.update(links)
                    tasks[idx]["depends_on"] = sorted(cur)
                    applied += 1

                elif kind == "unlink_dep":
                    tid = op.get("task_id")
                    unlink = set(map(str, (op.get("depends_on") or [])))
                elif kind == "set_status":
                    tid = op.get("task_id")
                    value = op.get("value")
                    idx = self._find_task_index_by_id(str(tid)) if tid else None
                    if idx is None:
                        denied.append(f"set_status:{tid}:not_found")
                        continue
                    owner = tasks[idx].get("owner_agent")
                    if owner and agent_name and owner != agent_name:
                        denied.append(f"set_status:{tid}:owner_mismatch")
                        continue
                    tasks[idx]["status"] = self._normalize_status_value(value)
                    applied += 1

                elif kind == "set_field":
                    tid = op.get("task_id")
                    path = str(op.get("path") or "").strip()
                    value = op.get("value")
                    idx = self._find_task_index_by_id(str(tid)) if tid else None
                    if idx is None or not path:
                        denied.append(f"set_field:{tid}:invalid")
                        continue
                    owner = tasks[idx].get("owner_agent")
                    if owner and agent_name and owner != agent_name:
                        denied.append(f"set_field:{tid}:owner_mismatch")
                        continue
                    # Only allow top-level safe fields
                    if path in {"title","description","tool","params","status","notes","priority","executor_id","action"}:
                        if path == "status":
                            tasks[idx][path] = self._normalize_status_value(value)
                        else:
                            tasks[idx][path] = value
                        applied += 1
                    else:
                        denied.append(f"set_field:{tid}:path_not_allowed")

                elif kind == "append_task":
                    t = dict(op.get("task") or {})
                    if agent_name:
                        t.setdefault("owner_agent", agent_name)
                    t["status"] = self._normalize_status_value(t.get("status", TaskStatus.PENDING.value))
                    t.setdefault("id", f"t{len(tasks)+1}")
                    exist_idx = self._find_task_index_by_id(str(t.get("id")))
                    if exist_idx is not None:
                        denied.append(f"append_task:{t.get('id')}:exists")
                    else:
                        tasks.append(t)
                        applied += 1

                elif kind == "remove_task":
                    tid = op.get("task_id")
                    idx = self._find_task_index_by_id(str(tid)) if tid else None
                    if idx is None:
                        denied.append(f"remove_task:{tid}:not_found")
                        continue
                    owner = tasks[idx].get("owner_agent")
                    if owner and agent_name and owner != agent_name:
                        denied.append(f"remove_task:{tid}:owner_mismatch")
                        continue
                    tasks.pop(idx)
                    applied += 1

                elif kind == "replace_task":
                    tid = op.get("task_id")
                    new_t = dict(op.get("task") or {})
                    idx = self._find_task_index_by_id(str(tid)) if tid else None
                    if idx is None:
                        denied.append(f"replace_task:{tid}:not_found")
                        continue
                    owner = tasks[idx].get("owner_agent")
                    if owner and agent_name and owner != agent_name:
                        denied.append(f"replace_task:{tid}:owner_mismatch")
                        continue
                    # preserve id unless explicitly set
                    new_t.setdefault("id", tasks[idx].get("id"))
                    new_t["status"] = self._normalize_status_value(new_t.get("status", TaskStatus.PENDING.value))
                    tasks[idx] = new_t
                    applied += 1
                    idx = self._find_task_index_by_id(str(tid)) if tid else None
                    if idx is None:
                        denied.append(f"unlink_dep:{tid}:not_found")
                        continue
                    owner = tasks[idx].get("owner_agent")
                    if owner and agent_name and owner != agent_name:
                        denied.append(f"unlink_dep:{tid}:owner_mismatch")
                        continue
                    cur = set(map(str, tasks[idx].get("depends_on") or []))
                    tasks[idx]["depends_on"] = sorted(cur - unlink)
                    applied += 1

                else:
                    denied.append(f"{kind}:unsupported")
            except Exception as e:
                denied.append(f"{op.get('op')}:error:{e}")

        # Persist changes if any op applied
        if applied > 0:
            self._set_tasks(tasks)
            self.context["version"] = int(self.context.get("version", current_version)) + 1
            self._render_markdown_view()

        return {"success": True, "applied": applied, "denied": denied, "new_version": int(self.context.get("version", current_version))}
