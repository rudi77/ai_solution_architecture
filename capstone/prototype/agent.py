# ==================== PRODUCTION REACT AGENT ====================

import asyncio
from datetime import datetime
from enum import Enum
import hashlib
import json
import time
from turtle import tracer
from typing import Any, AsyncGenerator, Dict, List, Optional

from prometheus_client import Counter, Gauge, Histogram
from pydantic import BaseModel, Field, validator
import structlog
from capstone.prototype.feedback_collector import FeedbackCollector
from capstone.prototype.llm_provider import LLMProvider
from capstone.prototype.statemanager import StateManager
from capstone.prototype.tools import ToolSpec, execute_tool_by_name, export_openai_tools, find_tool

from circuitbreaker import circuit
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

# ==================== ENUMS & DATA MODELS ====================

class ActionType(Enum):
    TOOL_CALL = "tool_call"
    ASK_USER = "ask_user"
    COMPLETE = "complete"
    UPDATE_TODOLIST = "update_todolist"
    ERROR_RECOVERY = "error_recovery"

CHECKLIST_STATUS_PENDING = "⏳ Pending"
CHECKLIST_STATUS_IN_PROGRESS = "🔄 In Progress"
CHECKLIST_STATUS_COMPLETED = "✅ Completed"
CHECKLIST_STATUS_FAILED = "❌ Failed"
CHECKLIST_STATUS_BLOCKED = "🚫 Blocked"
CHECKLIST_STATUS_SKIPPED = "⏭️ Skipped"
CHECKLIST_STATUS_RETRYING = "🔁 Retrying"

# ==================== PYDANTIC MODELS FOR STRUCTURED OUTPUT ====================

class ActionDecision(BaseModel):
    """Structured output for LLM action decisions"""
    action_type: ActionType
    action_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)
    
    @validator('action_type', pre=True)
    def validate_action_type(cls, v):
        if isinstance(v, str):
            # Back-compat: map old UPDATE_CHECKLIST string to UPDATE_TODOLIST
            norm = v.lower()
            if norm == "update_checklist":
                norm = "update_todolist"
            return ActionType(norm)
        return v

## Legacy structured output for checklist generation removed (Markdown-only flow)
    
class ProjectInfo(BaseModel):
    """Structured project information extraction"""
    project_name: str
    project_type: str
    programming_language: Optional[str] = None
    missing_info: List[str] = Field(default_factory=list)
    requirements: Dict[str, Any] = Field(default_factory=dict)



class ReActAgent:
    """Production-ready ReAct Agent with all enhancements"""
    
    def __init__(self, system_prompt: str, llm_provider: LLMProvider, tools: Optional[List[ToolSpec]] = None):
        self.system_prompt = system_prompt
        self.llm = llm_provider
        # Do not default to built-in tools; require explicit tools list
        self.tools: List[ToolSpec] = tools or []
        self.state_manager = StateManager()
        self.feedback_collector = FeedbackCollector()
        
        self.context = {}
        # Markdown-only checklist flow; no in-memory checklist object
        self.react_history = []
        self.step_counter = 0
        self.max_steps = 50
        self.session_id = None
        
        self.logger = structlog.get_logger()
        # Compose dynamic tools documentation into the system prompt for better LLM guidance
        self.system_prompt_full = self._compose_system_prompt(system_prompt)
    
    async def process_request(self, user_input: str, session_id: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Process user request with streaming progress"""
        
        # Track workflow start
        workflow_counter.inc()
        active_workflows.inc()
        
        try:
            self.session_id = session_id or hashlib.md5(f"{user_input}{time.time()}".encode()).hexdigest()
            
            # Try to restore previous state
            restored_state = await self.state_manager.load_state(self.session_id)
            if restored_state:
                yield f"🔄 Restoring previous session {self.session_id}\n"
                self._restore_from_state(restored_state)
                # Capture latest user message for reasoning context
                self.context["recent_user_message"] = user_input
                # If we were waiting for user input, consume this message as the answer and clear the flag
                if self.context.get("awaiting_user_input"):
                    awaiting = self.context.get("awaiting_user_input") or {}
                    self.context.setdefault("user_inputs", []).append({
                        "answer": user_input,
                        "for_action": awaiting.get("action"),
                        "questions": awaiting.get("questions", []),
                        "provided_at": datetime.now().isoformat(),
                    })
                    # Clear awaiting flag and persist immediately
                    self.context.pop("awaiting_user_input", None)
                    await self._save_current_state()
                    yield "📥 Received your input. Continuing with the workflow...\n"
            else:
                yield f"🚀 Starting new workflow (Session: {self.session_id})\n"
                self.context = {
                    "user_request": user_input,
                    "session_id": self.session_id,
                    "started_at": datetime.now().isoformat()
                }
                # Capture latest user message for reasoning context
                self.context["recent_user_message"] = user_input
            
            yield f"📝 Processing: {user_input}\n\n"
            
            # Execute ReAct loop with streaming
            async for update in self._react_loop_streaming():
                yield update
            
            workflow_success.inc()
            yield "\n✅ Workflow completed successfully!\n"
            
        except Exception as e:
            workflow_failed.inc()
            self.logger.error("workflow_failed", error=str(e), session_id=self.session_id)
            yield f"\n❌ Workflow failed: {str(e)}\n"
            
            # Collect failure feedback
            await self.feedback_collector.collect_feedback(
                self.session_id, "workflow_failure", False, {"error": str(e)}
            )
        
        finally:
            active_workflows.dec()
            # Save final state
            await self._save_current_state()
            # Flush feedback
            await self.feedback_collector.flush_feedback()
    
    async def _react_loop_streaming(self) -> AsyncGenerator[str, None]:
        """ReAct loop with streaming updates"""
        
        while self.step_counter < self.max_steps:
            self.step_counter += 1
            
            yield f"\n--- Step {self.step_counter} ---\n"
            
            with tracer.start_as_current_span(f"react_step_{self.step_counter}"):
                step_start = time.time()
                
                # Generate thought
                thought = await self._generate_thought()
                yield f"💭 Thinking: {thought}\n"
                # Make thought available to action selection
                self.context["last_thought"] = thought
                
                # Determine action
                action_decision = await self._determine_action()
                yield f"⚡ Action: {action_decision.action_type.value} - {action_decision.action_name}\n"
                yield f"   Reasoning: {action_decision.reasoning}\n"
                
                # Execute action with retry logic
                observation = await self._execute_action_with_retry(action_decision)
                yield f"👀 Observation: {observation}\n"
                
                # Track metrics
                step_duration.labels(step_type=action_decision.action_type.value).observe(
                    time.time() - step_start
                )
                
                # Update context
                await self._update_context(action_decision, observation)
                
                # Save state periodically
                if self.step_counter % 5 == 0:
                    await self._save_current_state()
                
                # Check completion conditions
                if action_decision.action_type == ActionType.COMPLETE:
                    yield f"\n✨ Workflow completed: {observation}\n"
                    break
                
                if action_decision.action_type == ActionType.ASK_USER:
                    yield f"\n❓ User input required: {observation}\n"
                    break
    
    async def _generate_thought(self) -> str:
        """Generate reasoning with LLM"""
        context_summary = self._build_context_summary()
        
        prompt = f"""Current context:
{context_summary}

Based on the system instructions and current state, what should be the next logical step?
Think step by step about what needs to be done."""
        
        try:
            thought = await self.llm.generate_response(
                prompt, 
                system_prompt=self.system_prompt_full
            )
            return thought
        except Exception as e:
            self.logger.error("thought_generation_failed", error=str(e))
            return "I need to analyze the current situation and determine the best next step."
    
    async def _determine_action(self) -> ActionDecision:
        """Determine next action using vendor function-calling when available, otherwise schema JSON."""
        context_summary = self._build_context_summary()
        checklist_status = self._get_checklist_status()

        # Note: We allow ASK_USER even when no checklist exists to keep the CLI interactive.
        # We'll prefer creating a checklist later if the model doesn't ask the user explicitly.

        # 1) Try provider tool-calling: expose all tools and meta-actions via provider
        try:
            tools = export_openai_tools(self.tools)
            meta_actions = [
                {"type": "function", "function": {"name": "update_todolist", "description": "Create or modify the workflow Todo List.", "parameters": {"type": "object", "properties": {}, "additionalProperties": True}}},
                {"type": "function", "function": {"name": "ask_user", "description": "Request information from the user.", "parameters": {"type": "object", "properties": {"questions": {"type": "array", "items": {"type": "string"}}, "context": {"type": "string"}}, "additionalProperties": True}}},
                {"type": "function", "function": {"name": "error_recovery", "description": "Handle errors and retry failed operations.", "parameters": {"type": "object", "properties": {}, "additionalProperties": True}}},
                {"type": "function", "function": {"name": "complete", "description": "Finish the workflow with an optional summary.", "parameters": {"type": "object", "properties": {"summary": {"type": "string"}}, "additionalProperties": True}}},
            ]
            all_tools = tools + meta_actions
            tool_decision = await self.llm.call_tools(
                system_prompt=self.system_prompt_full,
                messages=[
                    {"role": "user", "content": f"Context:\n{context_summary}\n\nTodo List status: {checklist_status}\nRecent reasoning: {self.context.get('last_thought', '')}\nDecide the next action and call exactly one function. If a Todo List exists and a next executable item is available, you must call the function for exactly that item's tool. Do not select any other tool."}
                ],
                tools=all_tools,
            )
            if tool_decision:
                name = (tool_decision.get("name") or "").strip().lower()
                params = tool_decision.get("arguments") or {}
                if name == "update_todolist":
                    return ActionDecision(action_type=ActionType.UPDATE_TODOLIST, action_name="create_todolist", parameters=params, reasoning="Provider called update_todolist", confidence=0.9)
                if name == "ask_user":
                    return ActionDecision(action_type=ActionType.ASK_USER, action_name="ask_user", parameters=params, reasoning="Provider called ask_user", confidence=0.9)
                if name == "error_recovery":
                    return ActionDecision(action_type=ActionType.ERROR_RECOVERY, action_name="retry_failed_items", parameters=params, reasoning="Provider called error_recovery", confidence=0.9)
                if name == "complete":
                    return ActionDecision(action_type=ActionType.COMPLETE, action_name="complete", parameters=params, reasoning="Provider called complete", confidence=0.9)
                decided = ActionDecision(action_type=ActionType.TOOL_CALL, action_name=name, parameters=params, reasoning="Provider called tool", confidence=0.9)
                if isinstance(self.context.get("blocker"), dict):
                    return ActionDecision(
                        action_type=ActionType.ASK_USER,
                        action_name="ask_user",
                        parameters={
                            "questions": [
                                f"{self.context['blocker'].get('message', 'A blocking issue occurred.')}",
                                f"{self.context['blocker'].get('suggestion', 'Please advise next steps.')}",
                            ],
                            "context": "Blocking error encountered. Provide next steps."
                        },
                        reasoning="Blocking error present; asking user instead of retrying tools",
                        confidence=0.9,
                    )
                if not self.context.get("checklist_created") and not self.context.get("todolist_created"):
                    return ActionDecision(
                        action_type=ActionType.UPDATE_TODOLIST,
                        action_name="create_todolist",
                        parameters={},
                        reasoning="No Todo List yet; create it before executing tools",
                        confidence=0.9,
                    )
                return decided
            if not self.context.get("checklist_created") and not self.context.get("todolist_created"):
                return ActionDecision(
                    action_type=ActionType.UPDATE_TODOLIST,
                    action_name="create_todolist",
                    parameters={},
                    reasoning="No function call returned; bootstrap Todo List",
                    confidence=0.8,
                )
            return ActionDecision(
                action_type=ActionType.ASK_USER,
                action_name="ask_user",
                parameters={"questions": ["What should we do next?"], "context": "No decisive action from model."},
                reasoning="No function call returned; Todo List exists",
                confidence=0.6,
            )
        except Exception as e:
            self.logger.warning("provider_action_selection_failed", error=str(e))

        # 2) Fallback to schema-guided JSON decision
        context_summary = self._build_context_summary()
        checklist_status = self._get_checklist_status()
        prompt = f"""Current context:
{context_summary}

Todo List status: {checklist_status}

Recent reasoning: {self.context.get('last_thought', '')}

Available actions:
- UPDATE_TODOLIST: Create or modify the workflow Todo List
- TOOL_CALL: Execute a specific tool
- ASK_USER: Request information from the user
- ERROR_RECOVERY: Handle errors and retry failed operations
- COMPLETE: Finish the workflow

Determine the most appropriate next action with clear reasoning."""
        try:
            action_decision = await self.llm.generate_structured_response(
                prompt,
                ActionDecision,
                system_prompt=self.system_prompt_full
            )
            # Respect ASK_USER; otherwise, if no Todo List exists (Markdown flag), create it first
            if action_decision.action_type != ActionType.ASK_USER and not self.context.get("checklist_created") and not self.context.get("todolist_created"):
                return ActionDecision(
                    action_type=ActionType.UPDATE_TODOLIST,
                    action_name="create_todolist",
                    parameters={},
                    reasoning="No Todo List yet; create it before proceeding",
                    confidence=action_decision.confidence,
                )
            return action_decision
        except Exception as e:
            self.logger.error("action_determination_failed", error=str(e))
            return ActionDecision(
                action_type=ActionType.ERROR_RECOVERY,
                action_name="analyze_situation",
                parameters={},
                reasoning="Failed to determine action, analyzing situation",
                confidence=0.5
            )
    
    async def _execute_action_with_retry(self, action_decision: ActionDecision, 
                                        max_retries: int = 3) -> str:
        """Execute action with retry logic"""
        # Limit retries for repository creation in Git iteration
        if action_decision.action_type == ActionType.TOOL_CALL and action_decision.action_name:
            name_norm = action_decision.action_name.strip().lower().replace("-", "_").replace(" ", "_")
            if name_norm == "create_repository":
                max_retries = 1

        for attempt in range(max_retries):
            try:
                result = await self._execute_action(
                    action_decision.action_type,
                    action_decision.action_name,
                    action_decision.parameters
                )
                
                # Collect success feedback
                await self.feedback_collector.collect_feedback(
                    self.session_id,
                    "action_execution",
                    True,
                    {
                        "action": action_decision.action_name,
                        "attempt": attempt + 1
                    }
                )
                
                return result
                
            except Exception as e:
                self.logger.warning("action_execution_failed",
                                  action=action_decision.action_name,
                                  attempt=attempt + 1,
                                  error=str(e))
                
                if attempt == max_retries - 1:
                    # Final attempt failed
                    await self.feedback_collector.collect_feedback(
                        self.session_id,
                        "action_execution",
                        False,
                        {
                            "action": action_decision.action_name,
                            "error": str(e),
                            "attempts": max_retries
                        }
                    )
                    
                    # Markdown mode: no in-memory item to mark failed
                    
                    return f"Action failed after {max_retries} attempts: {e}"
                
                # Exponential backoff
                await asyncio.sleep(2 ** attempt)
    
    async def _execute_action(self, action_type: ActionType, action_name: str, 
                             parameters: Dict) -> str:
        """Execute the determined action"""
        
        if action_type == ActionType.UPDATE_TODOLIST:
            return await self._handle_todolist_action(action_name, parameters)
        
        elif action_type == ActionType.TOOL_CALL:
            return await self._execute_tool_call(action_name, parameters)
        
        elif action_type == ActionType.ASK_USER:
            return await self._handle_user_interaction(action_name, parameters)
        
        elif action_type == ActionType.ERROR_RECOVERY:
            return await self._handle_error_recovery(action_name, parameters)
        
        elif action_type == ActionType.COMPLETE:
            return await self._complete_workflow(parameters)
        
        return f"Executed {action_type.value}: {action_name}"
    
    async def _handle_todolist_action(self, action_name: str, parameters: Dict) -> str:
        """Handle todolist-related actions by delegating to focused helpers."""
        try:
            from .todolist_actions import (
                normalize_todolist_action_name,
                create_todolist,
                update_item_status,
                get_next_executable_item,
            )  # type: ignore
        except Exception:
            from todolist_actions import (  # type: ignore
                normalize_todolist_action_name,
                create_todolist,
                update_item_status,
                get_next_executable_item,
            )

        action = normalize_todolist_action_name(action_name)

        if action == "create_todolist":
            return await create_todolist(
                llm=self.llm,
                context=self.context,
                system_prompt=self.system_prompt_full,
                session_id=self.session_id,
                extract_project_info=self._extract_project_info,
                logger=self.logger,
            )

        if action == "update_item_status":
            return await update_item_status(
                llm=self.llm,
                context=self.context,
                system_prompt=self.system_prompt_full,
                session_id=self.session_id,
                parameters=parameters,
                extract_project_info=self._extract_project_info,
            )

        if action == "get_next_executable_item":
            return get_next_executable_item(context=self.context)

        return f"Todo List action '{action}' completed"
    
    async def _execute_tool_call(self, tool_name: str, parameters: Dict) -> str:
        """Execute tool and update checklist"""
        
        # Hard guard (Markdown flow): ensure a todolist file exists before tool execution
        if not self.context.get("todolist_created") and not self.context.get("checklist_created"):
            checklist_msg = await self._handle_todolist_action("create_todolist", {})
            return f"Todo List was missing. {checklist_msg}\nWill proceed with tool execution next."

        # Normalize tool name and resolve via ToolSpec list
        normalized_tool_name = tool_name.strip().lower().replace("-", "_").replace(" ", "_")
        requested_spec = find_tool(self.tools, normalized_tool_name)
        
        # Find corresponding checklist item (exact or normalized match)
        current_item = None  # Markdown-only flow: we no longer track items in memory
        
        # Mark item as in progress in Markdown (best-effort)
        if current_item:
            try:
                from .todolist_md import update_todolist_md  # type: ignore
            except Exception:
                from todolist_md import update_todolist_md  # type: ignore
            try:
                project_name = self.context.get("project_name")
                if project_name:
                    await update_todolist_md(
                        self.llm,
                        project_name=project_name,
                        instruction=f"Set task {current_item.id} status to IN_PROGRESS.",
                        system_prompt=self.system_prompt_full,
                        session_id=self.session_id,
                    )
            except Exception:
                pass
        else:
            # No in-memory item; best-effort by tool name
            try:
                try:
                    from .todolist_md import update_todolist_md  # type: ignore
                except Exception:
                    from todolist_md import update_todolist_md  # type: ignore
                project_name = self.context.get("project_name")
                if project_name:
                    await update_todolist_md(
                        self.llm,
                        project_name=project_name,
                        instruction=f"Find the task that corresponds to tool '{normalized_tool_name}' and mark it IN_PROGRESS.",
                        system_prompt=self.system_prompt_full,
                        session_id=self.session_id,
                    )
            except Exception:
                pass

        # Enforce executing the current checklist item's tool if there is a mismatch
        if current_item and current_item.tool_action:
            expected_tool = (current_item.tool_action or "").strip().lower().replace("-", "_").replace(" ", "_")
            expected_spec = find_tool(self.tools, expected_tool)
            if expected_spec and (not requested_spec or requested_spec.name != expected_spec.name):
                normalized_tool_name = expected_tool
                requested_spec = expected_spec
        
        # Enhance parameters with context
        enhanced_params = self._enhance_tool_parameters(normalized_tool_name, parameters)
        
        # Execute tool
        result = await execute_tool_by_name(self.tools, normalized_tool_name, enhanced_params)
        if not result.get("success") and isinstance(result.get("error"), str) and "not found" in result.get("error", ""):
            result = await execute_tool_by_name(self.tools, tool_name, enhanced_params)

        # Knowledge Base handling: empty matches are non-blocker; set context flag
        try:
            if requested_spec and requested_spec.name in {"search_knowledge_base_for_guidelines", "search_knowledge_base"}:
                matches = []
                if isinstance(result, dict):
                    matches = (result.get("result", {}) or {}).get("matches", []) or []
                self.context["kb_guidelines_available"] = "yes" if matches else "no"
        except Exception:
            self.context["kb_guidelines_available"] = "no"
        
        # Update checklist based on result in Markdown
        if current_item:
            try:
                from .todolist_md import update_todolist_md  # type: ignore
            except Exception:
                from todolist_md import update_todolist_md  # type: ignore
            success = bool(result.get("success"))
            status_text = "COMPLETED" if success else "RETRYING"
            if not success:
                # If it repeatedly fails, mark as FAILED; we don't track retry_count in Markdown, so keep it simple
                status_text = "FAILED"
            try:
                project_name = self.context.get("project_name")
                if project_name:
                    result_text = json.dumps(result, ensure_ascii=False) if success else (result.get("error", "Unknown error"))
                    await update_todolist_md(
                        self.llm,
                        project_name=project_name,
                        instruction=(
                            f"Set task {current_item.id} status to {status_text}. "
                            f"Record result for task {current_item.id}: {result_text}."
                        ),
                        system_prompt=self.system_prompt_full,
                        session_id=self.session_id,
                    )
            except Exception:
                pass
        else:
            # No in-memory item; update by tool name
            try:
                try:
                    from .todolist_md import update_todolist_md  # type: ignore
                except Exception:
                    from todolist_md import update_todolist_md  # type: ignore
                project_name = self.context.get("project_name")
                if project_name:
                    success = bool(result.get("success"))
                    status_text = "COMPLETED" if success else "FAILED"
                    result_text = json.dumps(result, ensure_ascii=False) if success else (result.get("error", "Unknown error"))
                    await update_todolist_md(
                        self.llm,
                        project_name=project_name,
                        instruction=(
                            f"Find the task that corresponds to tool '{normalized_tool_name}' and set its status to {status_text}. "
                            f"Record result: {result_text}."
                        ),
                        system_prompt=self.system_prompt_full,
                        session_id=self.session_id,
                    )
            except Exception:
                pass

        # Detect blocking errors generically and set context to steer next step to ASK_USER
        try:
            err_text = str(result.get("error", "")).strip()
            if err_text:
                suggestion = "Review the error and provide next steps or corrected parameters."
                if "not found" in err_text.lower():
                    suggestion = "Verify tool availability and parameters; consider selecting a different tool."
                if "permission" in err_text.lower() or "unauthorized" in err_text.lower():
                    suggestion = "Check credentials/permissions and retry after fixing access."
                if "already exists" in err_text.lower():
                    suggestion = "Choose a different name or remove/empty the existing target."
                self.context["blocker"] = {
                    "message": err_text,
                    "suggestion": suggestion,
                }
        except Exception:
            pass
        
        return f"Tool '{tool_name}' execution: {json.dumps(result, indent=2)}"
    
    async def _handle_user_interaction(self, action_name: str, parameters: Dict) -> str:
        """Handle user interaction requests"""
        
        questions = parameters.get("questions", [])
        context = parameters.get("context", "")
        
        interaction_msg = f"User input needed for {action_name}:\n"
        interaction_msg += f"Context: {context}\n"
        
        if questions:
            interaction_msg += "Questions:\n"
            for i, q in enumerate(questions, 1):
                interaction_msg += f"  {i}. {q}\n"
        
        # In production, this would trigger UI interaction
        # For CLI: Save state, then the next user message to process_request() will be consumed as the answer
        self.context["awaiting_user_input"] = {
            "action": action_name,
            "questions": questions,
            "requested_at": datetime.now().isoformat()
        }
        # Once we ask the user, clear any blocker to avoid re-triggering forced ASK_USER
        self.context.pop("blocker", None)
        
        await self._save_current_state()
        
        interaction_msg += "\nPlease type your answers (free-form).\n"
        return interaction_msg
    
    async def _handle_error_recovery(self, action_name: str, parameters: Dict) -> str:
        """Handle error recovery strategies"""
        
        if action_name == "retry_failed_items":
            # Markdown-only flow: instruct LLM to mark the first FAILED task as RETRYING
            try:
                try:
                    from .todolist_md import update_todolist_md  # type: ignore
                except Exception:
                    from todolist_md import update_todolist_md  # type: ignore
                project_name = self.context.get("project_name")
                if not project_name:
                    info = await self._extract_project_info()
                    project_name = info.project_name
                filepath = await update_todolist_md(
                    self.llm,
                    project_name=project_name,
                    instruction="Find the first FAILED task and set its status to RETRYING (increment attempt if present).",
                    system_prompt=self.system_prompt_full,
                    session_id=self.session_id,
                )
                self.context["checklist_file"] = filepath
                return "Retrying first failed task"
            except Exception:
                return "No failed items available for retry"
        
        elif action_name == "skip_blocked_items":
            # Markdown flow: emit instruction to mark blocked items as skipped
            try:
                try:
                    from .todolist_md import update_todolist_md  # type: ignore
                except Exception:
                    from todolist_md import update_todolist_md  # type: ignore
                project_name = self.context.get("project_name")
                if not project_name:
                    info = await self._extract_project_info()
                    project_name = info.project_name
                filepath = await update_todolist_md(
                    self.llm,
                    project_name=project_name,
                    instruction="Mark all tasks that are blocked due to unmet dependencies as SKIPPED and add note 'Skipped due to dependency failure'.",
                    system_prompt=self.system_prompt_full,
                    session_id=self.session_id,
                )
                self.context["checklist_file"] = filepath
                return "Skipped blocked items in checklist"
            except Exception:
                return "No blocked items to skip"
        
        return f"Error recovery action '{action_name}' completed"
    
    async def _complete_workflow(self, parameters: Dict) -> str:
        """Complete the workflow"""
        
        summary = parameters.get("summary", "Workflow completed successfully")
        
        if self.context.get("checklist_created") or self.context.get("todolist_created"):
            return f"Workflow completed. Summary: {summary}"
        
        return summary
    
    async def _extract_project_info(self) -> ProjectInfo:
        """Extract project information from user request"""
        
        prompt = f"""Analyze the following user request and extract project information:

User Request: {self.context.get('user_request', '')}

Extract:
1. Project name (kebab-case)
2. Project type (microservice/library/application/etc)
3. Programming language (if specified)
4. Any specific requirements
5. Missing information that should be clarified"""
        
        try:
            project_info = await self.llm.generate_structured_response(
                prompt,
                ProjectInfo,
                system_prompt=self.system_prompt
            )
            return project_info
            
        except Exception as e:
            self.logger.error("project_info_extraction_failed", error=str(e))
            # Return default
            return ProjectInfo(
                project_name="unnamed-project",
                project_type="generic",
                missing_info=["project_name", "project_type"]
            )
    
    ## Legacy builder removed (Markdown-only flow)
    
    def _build_context_summary(self) -> str:
        """Build context summary for LLM"""
        
        summary = f"Session: {self.session_id}\n"
        summary += f"User Request: {self.context.get('user_request', 'None')}\n"
        if self.context.get("recent_user_message"):
            summary += f"Recent User Message: {self.context.get('recent_user_message')}\n"
        summary += f"Step: {self.step_counter}/{self.max_steps}\n"
        
        kb = self.context.get("kb_guidelines_available")
        if kb:
            summary += f"KB Guidelines: {kb}\n"
        
        if self.context.get("todolist_file") or self.context.get("checklist_file"):
            summary += f"Todo List File: {self.context.get('todolist_file') or self.context.get('checklist_file')}\n"
        else:
            summary += "Todo List: Not created yet\n"
        
        # Recent history
        if self.react_history:
            summary += f"Recent Actions (last 10):\n"
            for action in self.react_history[-10:]:
                summary += f"  - {action}\n"
        
        return summary
    
    def _get_checklist_status(self) -> str:
        """Get current Todo List status (back-compat name)."""
        
        if not self.context.get("checklist_created") and not self.context.get("todolist_created"):
            return "No Todo List created"
        
        # When using Markdown-only checklist, we cannot compute next item reliably here.
        # Provide a generic status based on existence of the file.
        if self.context.get("todolist_file") or self.context.get("checklist_file"):
            return f"Todo List ready at {self.context.get('todolist_file') or self.context.get('checklist_file')}"
        
        # No deeper introspection in Markdown-only mode

        return "Waiting for next action"

    def _compose_system_prompt(self, base_prompt: str) -> str:
        """Append dynamic tools documentation to the base system prompt."""
        try:
            lines = [base_prompt.strip(), "\n## TOOLS (dynamic)\nList of available tools with input requirements:\n"]
            for spec in self.tools:
                # Derive required keys from input_schema
                required = []
                try:
                    required = list((spec.input_schema or {}).get("required", []))
                except Exception:
                    required = []
                lines.append(f"- {spec.name}: {spec.description}")
                if required:
                    lines.append(f"  required: {', '.join(required)}")
            lines.append("\nUsage rules:\n- Use only listed tools.\n- After each tool run, update the Todo List with status/result.\n- If a blocking error occurs, consider ASK_USER with suggested next steps.")
            return "\n".join(lines)
        except Exception:
            return base_prompt
    
    ## Legacy next-executable resolver removed (Markdown-only flow)
    
    def _enhance_tool_parameters(self, tool_name: str, parameters: Dict) -> Dict:
        """No-op: keep agent generic by not auto-modifying tool parameters."""
        return parameters if isinstance(parameters, dict) else {}
    
    async def _update_context(self, action_decision: ActionDecision, observation: str):
        """Update context after action execution"""
        
        self.context["last_action"] = {
            "type": action_decision.action_type.value,
            "name": action_decision.action_name,
            "result": observation,
            "timestamp": datetime.now().isoformat()
        }
        
        # Add to history
        self.react_history.append(f"{action_decision.action_name} -> {observation[:100]}")
        
        # Keep history size manageable
        if len(self.react_history) > 20:
            self.react_history = self.react_history[-20:]
    
    async def _save_current_state(self):
        """Save current agent state"""
        
        state_data = {
            "context": self.context,
            "react_history": self.react_history,
            "step_counter": self.step_counter
        }
        
        await self.state_manager.save_state(self.session_id, state_data)
    
    def _restore_from_state(self, state_data: Dict):
        """Restore agent from saved state"""
        
        self.context = state_data.get("context", {})
        self.react_history = state_data.get("react_history", [])
        self.step_counter = state_data.get("step_counter", 0)
        
        self.logger.info("state_restored",
                        session_id=self.session_id,
                        step=self.step_counter)
    
    ## Legacy mark-current-item-failed removed (Markdown-only flow)
