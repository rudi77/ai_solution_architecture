# ==================== PRODUCTION REACT AGENT ====================

import asyncio
from datetime import datetime
from enum import Enum
import hashlib
import json
import time
import re  # CHANGED: for simple fact extraction (kebab-case)
from typing import Any, AsyncGenerator, Dict, List, Optional

from prometheus_client import Counter, Gauge, Histogram
from pydantic import BaseModel, Field
from pydantic import field_validator
import structlog

from capstone.prototype.feedback_collector import FeedbackCollector
from capstone.prototype.llm_provider import LLMProvider
from capstone.prototype.statemanager import StateManager
from capstone.prototype.todolist_md import update_todolist_md, create_todolist_md  # CHANGED: add create_todolist_md
from capstone.prototype.tools import ToolSpec, execute_tool_by_name, export_openai_tools, find_tool

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

# ============ Agent ============
class ReActAgent:
    def __init__(
        self,
        system_prompt: str,
        llm: LLMProvider,
        *,
        tools: List[ToolSpec] | None = None,
        max_steps: int = 50,
    ):
        """
        Initializes the ReActAgent with the given system prompt, LLM provider, tools, and maximum steps.
        Args:
            system_prompt: The system prompt for the LLM.
            llm: The LLM provider.
            tools: The tools to use.
            max_steps: The maximum number of steps to take.
        """
        self.system_prompt_base = system_prompt.strip()
        self.llm = llm
        self.tools: List[ToolSpec] = tools or []  # keine Default-Tools -> generisch
        self.max_steps = max_steps

        self.state = StateManager()
        self.feedback = FeedbackCollector()
        self.logger = structlog.get_logger()

        self.session_id: Optional[str] = None
        self.context: Dict[str, Any] = {}
        self.react_history: List[str] = []
        self.step = 0

        self.system_prompt = self._compose_system_prompt()

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
                self.context = {
                    "user_request": user_input,
                    "session_id": self.session_id,
                    "started_at": datetime.now().isoformat(),
                }
                self.context["recent_user_message"] = user_input
                # initial augmented = original
                self.context["user_request_augmented"] = self.context["user_request"]  # CHANGED
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

            thought = await self._generate_thought()
            yield f"💭 Thought:\n{thought}\n"

            decision = await self._decide_next_action()
            yield f"⚡ Aktion: {decision.action_type.value} — {decision.action_name}\n"
            yield f"   Grund: {decision.reasoning}\n"

            started = time.time()
            observation = await self._exec_with_retry(decision)
            step_duration.labels(step_type=decision.action_type.value).observe(time.time() - started)

            yield f"👀 Observation:\n{observation}\n"

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
        known = self.context.get("known_answers_text", "")
        facts = self.context.get("facts", {})

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
            f"Known answers:\n{known or '- none -'}\n\n"
            f"Facts (parsed):\n{json.dumps(facts, ensure_ascii=False, indent=2)}\n\n"
            f"Tools and required params:\n{json.dumps(required_by_tool, ensure_ascii=False, indent=2)}"
        )
        try:
            return await self.llm.generate_structured_response(prompt, BlockingQuestions, system_prompt=self.system_prompt)
        except Exception:
            return BlockingQuestions()

    async def _create_initial_plan(self, *, open_questions: List[str]):
        """
        Erstellt die Todo-Liste (Markdown) mit:
        - Tasks (atomar, jedes exekutierbare Item enthält `tool: <name>` als Klartext im Task-Text)
        - Sektion „Open Questions (awaiting user)“ mit nicht-kritischen Fragen

        Args:
            open_questions (List[str]): Eine Liste von Fragen, die vom Nutzer noch beantwortet werden müssen.
        """
        # CHANGED: use augmented request if available
        user_req = self.context.get("user_request_augmented") or self.context.get("user_request", "")
        guide = (
            "Create a concise, executable TODO plan in Markdown.\n"
            "- Sections: Title, Meta (created/last-updated), Tasks, Open Questions (awaiting user), Notes.\n"
            "- Tasks: checkbox list (- [ ]) with short descriptions; each executable task states `tool: <exact_tool_name>` inside the line.\n"
            "- Keep tasks atomic and verifiable.\n"
            "- If no open questions, include the section but keep it empty.\n"
        )
        md_prompt = f"{guide}\n\nContext/user request:\n{user_req}\n"
        path = await create_todolist_md(  # CHANGED: ensure wrapper is used
            llm=self.llm,
            user_request=md_prompt,
            system_prompt=self.system_prompt,
            session_id=self.session_id,
        )
        self.context["todolist_created"] = True
        self.context["todolist_file"] = path

        if open_questions:
            await update_todolist_md(
                llm=self.llm,
                instruction="Under 'Open Questions (awaiting user)', add these bullet points: "
                            + "; ".join(open_questions),
                system_prompt=self.system_prompt,
                session_id=self.session_id,
            )

    # ===== ReAct inner pieces =====
    async def _generate_thought(self) -> str:
        summary = self._summary_for_llm()
        prompt = (
            f"Context:\n{summary}\n\n"
            "Think step by step about the single next best move. Consider the Todo List, tool availability, and errors. "
            "Keep it short."
        )
        try:
            return await self.llm.generate_response(prompt, system_prompt=self.system_prompt)
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
            ]
            call = await self.llm.call_tools(
                system_prompt=self.system_prompt,
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
            dec = await self.llm.generate_structured_response(prompt, ActionDecision, system_prompt=self.system_prompt)
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
        if kind == ActionType.ASK_USER:
            return await self._handle_user_interaction(name, params)
        if kind == ActionType.ERROR_RECOVERY:
            return "Tried generic recovery (noop)."
        if kind == ActionType.COMPLETE:
            return params.get("summary", "OK")
        return f"Executed {kind.value}/{name}"

    # ===== TodoList handling (Markdown) =====
    async def _handle_todolist(self, action: str, params: Dict[str, Any]) -> str:
        act = action.lower().replace("-", "_").replace(" ", "_")
        if act in {"create_todolist", "create"}:
            # Re-generate from latest context (idempotent)
            await self._create_initial_plan(open_questions=[])
            return f"Todo List (re)created at {self.context.get('todolist_file')}"
        if act == "update_item_status":
            instr = params.get("instruction") or ""
            if not instr:
                return "No instruction provided."
            await update_todolist_md(self.llm, instruction=instr, system_prompt=self.system_prompt, session_id=self.session_id)
            return "Todo List updated."
        return f"Todo action '{action}' done"

    async def _handle_tool(self, tool_name: str, params: Dict[str, Any]) -> str:
        if not self.context.get("todolist_created"):
            await self._create_initial_plan(open_questions=[])
        norm = tool_name.strip().lower().replace("-", "_").replace(" ", "_")

        # IN_PROGRESS (best-effort)
        try:
            await update_todolist_md(
                self.llm,
                instruction=f"Find the task that corresponds to tool '{norm}' and mark it IN_PROGRESS.",
                system_prompt=self.system_prompt,
                session_id=self.session_id,
            )
        except Exception:
            pass

        result = await execute_tool_by_name(self.tools, norm, params)
        success = bool(result.get("success"))
        status = "COMPLETED" if success else "FAILED"
        result_text = json.dumps(result, ensure_ascii=False)

        try:
            await update_todolist_md(
                self.llm,
                instruction=(f"Find the task that corresponds to tool '{norm}' and set its status to {status}. "
                             f"Record result: {result_text}."),
                system_prompt=self.system_prompt,
                session_id=self.session_id,
            )
        except Exception:
            pass

        # Generische Blocker-Hinweise ins Context
        err = (result.get("error") or "").strip()
        if err:
            self.context["blocker"] = {
                "message": err,
                "suggestion": "Gib korrigierte Parameter oder weitere Hinweise; ansonsten anderes Tool wählen."
            }

        return f"{tool_name} -> {json.dumps(result, indent=2)}"

    # ===== ASK_USER =====
    async def _handle_user_interaction(self, action_name: str, params: Dict[str, Any]) -> str:
        questions = params.get("questions") or []
        ctx = params.get("context") or ""
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
        if self.context.get("todolist_file"):
            lines.append(f"Todo List File: {self.context['todolist_file']}")
        else:
            lines.append("Todo List: not created yet")
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

    async def _save(self):
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
            "- First, build a Todo List (plan). Critical clarifications must be asked BEFORE planning; minor ones go into 'Open Questions'.\n"
            "- After each tool run, update the Todo List status and record results.\n"
            "- If a blocking error occurs, ASK_USER with concrete suggestions."
        )
        return "\n".join(lines)
