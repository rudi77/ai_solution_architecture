#!/usr/bin/env python3
"""
Production-Ready IDP Copilot Implementation
Vollständig erweitert mit Priority 1, 2 und 3 Features
"""

import json
import time
import os
import asyncio
import pickle
import structlog
import concurrent.futures
from typing import Dict, List, Optional, Any, Tuple, AsyncGenerator, Union
from dataclasses import dataclass, asdict, field
from enum import Enum
from datetime import datetime
from pathlib import Path
from abc import ABC, abstractmethod
import hashlib
from collections import defaultdict
import re
from functools import partial
try:
    from .tools import ToolSpec, export_openai_tools, find_tool, execute_tool_by_name
    from .tools_builtin import BUILTIN_TOOLS
except Exception:
    from tools import ToolSpec, export_openai_tools, find_tool, execute_tool_by_name  # type: ignore
    from tools_builtin import BUILTIN_TOOLS  # type: ignore

# System prompt import
try:
    from .prompt import IDP_COPILOT_SYSTEM_PROMPT, IDP_COPILOT_SYSTEM_PROMPT_GIT
except Exception:
    from prompt import IDP_COPILOT_SYSTEM_PROMPT, IDP_COPILOT_SYSTEM_PROMPT_GIT  # type: ignore

# External dependencies (requirements.txt)
# pip install pydantic langchain openai anthropic structlog prometheus-client circuitbreaker aiofiles

from pydantic import BaseModel, Field, validator
from prometheus_client import Counter, Histogram, Gauge, start_http_server
from circuitbreaker import circuit
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Setup OpenTelemetry
provider = TracerProvider()
if os.getenv("IDP_ENABLE_OTEL_CONSOLE", "false").lower() in {"1", "true", "yes", "on"}:
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)
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
    UPDATE_CHECKLIST = "update_checklist"
    ERROR_RECOVERY = "error_recovery"

CHECKLIST_STATUS_PENDING = "⏳ Pending"
CHECKLIST_STATUS_IN_PROGRESS = "🔄 In Progress"
CHECKLIST_STATUS_COMPLETED = "✅ Completed"
CHECKLIST_STATUS_FAILED = "❌ Failed"
CHECKLIST_STATUS_BLOCKED = "🚫 Blocked"
CHECKLIST_STATUS_SKIPPED = "⏭️ Skipped"
CHECKLIST_STATUS_RETRYING = "🔁 Retrying"

## Legacy Checklist classes removed (Markdown-only flow)

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
            return ActionType(v.lower())
        return v

## Legacy structured output for checklist generation removed (Markdown-only flow)
    
class ProjectInfo(BaseModel):
    """Structured project information extraction"""
    project_name: str
    project_type: str
    programming_language: Optional[str] = None
    missing_info: List[str] = Field(default_factory=list)
    requirements: Dict[str, Any] = Field(default_factory=dict)

# ==================== LLM ABSTRACTION ====================

class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    async def generate_response(self, prompt: str, **kwargs) -> str:
        pass
    
    @abstractmethod
    async def generate_structured_response(self, prompt: str, response_model: BaseModel, **kwargs) -> BaseModel:
        pass

class OpenAIProvider(LLMProvider):
    """OpenAI/GPT implementation using official OpenAI SDK (no langchain)."""
    
    def __init__(self, api_key: str, model: str = "gpt-4.1", temperature: float = 0.1):
        from openai import AsyncOpenAI
        
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.logger = structlog.get_logger()
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        system_prompt = kwargs.get('system_prompt', '')
        try:
            completion = await self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
            )
            return completion.choices[0].message.content or ""
        except Exception as e:
            self.logger.error("llm_generation_failed", error=str(e))
            raise
    
    async def generate_structured_response(self, prompt: str, response_model: BaseModel, **kwargs) -> BaseModel:
        import json as _json
        
        # Support both model class and instance
        model_cls = response_model if isinstance(response_model, type) else response_model.__class__
        if hasattr(model_cls, 'model_json_schema'):
            schema = model_cls.model_json_schema()
        else:
            # Fallback for environments exposing .schema()
            schema = model_cls.schema()  # type: ignore[attr-defined]
        
        # 1) Preferred path: Vendor function-calling to force a validated JSON return
        # We expose a single function whose parameters are exactly the target schema.
        try:
            completion = await self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": kwargs.get('system_prompt', '')},
                    {"role": "user", "content": prompt},
                ],
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "return_structured",
                            "description": f"Return a JSON object that matches the provided schema for {model_cls.__name__}.",
                            "parameters": schema,
                        },
                    }
                ],
                tool_choice={"type": "function", "function": {"name": "return_structured"}},
            )
            choice = completion.choices[0]
            tool_calls = getattr(choice.message, "tool_calls", None)
            if tool_calls and len(tool_calls) > 0:
                args_str = tool_calls[0].function.arguments
                data = _json.loads(args_str)
                return model_cls(**data)
        except Exception as e:
            # Fall through to schema-guided JSON prompting
            self.logger.warning("openai_function_calling_failed", error=str(e), model=model_cls.__name__)
        
        # 2) Fallback: Schema-guided prompting with plain JSON response
        structured_prompt = f"""{prompt}
\nRespond with valid JSON matching this schema:
{_json.dumps(schema, indent=2)}
\nJSON Response:"""
        try:
            text = await self.generate_response(structured_prompt, **kwargs)
            json_str = text.strip()
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]
            data = _json.loads(json_str.strip())
            return model_cls(**data)
        except Exception as e:
            self.logger.error("structured_generation_failed", error=str(e), model=model_cls.__name__)
            raise

class AnthropicProvider(LLMProvider):
    """Anthropic/Claude implementation"""
    
    def __init__(self, api_key: str, model: str = "claude-3-opus-20240229", temperature: float = 0.1):
        import anthropic
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.logger = structlog.get_logger()
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=self.temperature,
                system=kwargs.get('system_prompt', ''),
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            self.logger.error("anthropic_generation_failed", error=str(e))
            raise
    
    async def generate_structured_response(self, prompt: str, response_model: BaseModel, **kwargs) -> BaseModel:
        import json
        
        model_cls = response_model if isinstance(response_model, type) else response_model.__class__
        schema = model_cls.model_json_schema() if hasattr(model_cls, "model_json_schema") else model_cls.schema()  # type: ignore[attr-defined]
        structured_prompt = f"""{prompt}

Respond with valid JSON matching this schema:
{json.dumps(schema, indent=2)}

JSON Response:"""
        
        try:
            response = await self.generate_response(structured_prompt, **kwargs)
            # Extract JSON from response
            json_str = response.strip()
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]
            
            data = json.loads(json_str.strip())
            return model_cls(**data)
        except Exception as e:
            self.logger.error("anthropic_structured_failed", error=str(e))
            raise

# ==================== STATE MANAGEMENT ====================

class StateManager:
    """Manages agent state persistence and recovery"""
    
    def __init__(self, state_dir: str = "./agent_states"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(exist_ok=True)
        self.logger = structlog.get_logger()
    
    async def save_state(self, session_id: str, state_data: Dict) -> bool:
        """Save agent state asynchronously"""
        try:
            state_file = self.state_dir / f"{session_id}.pkl"
            
            state_to_save = {
                'session_id': session_id,
                'timestamp': datetime.now().isoformat(),
                'state_data': state_data
            }
            
            # Async file write
            import aiofiles
            async with aiofiles.open(state_file, 'wb') as f:
                await f.write(pickle.dumps(state_to_save))
            
            self.logger.info("state_saved", session_id=session_id)
            return True
            
        except Exception as e:
            self.logger.error("state_save_failed", session_id=session_id, error=str(e))
            return False
    
    async def load_state(self, session_id: str) -> Optional[Dict]:
        """Load agent state asynchronously"""
        try:
            state_file = self.state_dir / f"{session_id}.pkl"
            
            if not state_file.exists():
                return None
            
            import aiofiles
            async with aiofiles.open(state_file, 'rb') as f:
                content = await f.read()
                state = pickle.loads(content)
            
            self.logger.info("state_loaded", session_id=session_id)
            return state['state_data']
            
        except Exception as e:
            self.logger.error("state_load_failed", session_id=session_id, error=str(e))
            return None
    
    def cleanup_old_states(self, days: int = 7):
        """Remove states older than specified days"""
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        
        for state_file in self.state_dir.glob("*.pkl"):
            if state_file.stat().st_mtime < cutoff_time:
                state_file.unlink()
                self.logger.info("old_state_removed", file=state_file.name)

# ==================== FEEDBACK COLLECTOR ====================

class FeedbackCollector:
    """Collects and stores user feedback for continuous improvement"""
    
    def __init__(self, feedback_dir: str = "./feedback"):
        self.feedback_dir = Path(feedback_dir)
        self.feedback_dir.mkdir(exist_ok=True)
        self.feedback_buffer = []
        self.logger = structlog.get_logger()
    
    async def collect_feedback(self, session_id: str, feedback_type: str, 
                              success: bool, details: Dict) -> None:
        """Collect feedback asynchronously"""
        feedback_entry = {
            'session_id': session_id,
            'timestamp': datetime.now().isoformat(),
            'type': feedback_type,
            'success': success,
            'details': details
        }
        
        self.feedback_buffer.append(feedback_entry)
        
        # Flush buffer if it gets too large
        if len(self.feedback_buffer) >= 100:
            await self.flush_feedback()
    
    async def flush_feedback(self) -> None:
        """Write feedback buffer to disk"""
        if not self.feedback_buffer:
            return
        
        filename = f"feedback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.feedback_dir / filename
        
        try:
            import aiofiles
            async with aiofiles.open(filepath, 'w') as f:
                await f.write(json.dumps(self.feedback_buffer, indent=2))
            
            self.logger.info("feedback_flushed", count=len(self.feedback_buffer))
            self.feedback_buffer.clear()
            
        except Exception as e:
            self.logger.error("feedback_flush_failed", error=str(e))
    
    def analyze_feedback(self, days: int = 30) -> Dict:
        """Analyze recent feedback for patterns"""
        analysis = {
            'total_feedback': 0,
            'success_rate': 0,
            'common_failures': defaultdict(int),
            'tool_performance': defaultdict(lambda: {'success': 0, 'failure': 0})
        }
        
        cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
        
        for feedback_file in self.feedback_dir.glob("*.json"):
            if feedback_file.stat().st_mtime < cutoff_date:
                continue
            
            with open(feedback_file) as f:
                feedback_data = json.load(f)
                
                for entry in feedback_data:
                    analysis['total_feedback'] += 1
                    
                    if entry['success']:
                        analysis['success_rate'] += 1
                    
                    if not entry['success'] and 'error' in entry['details']:
                        analysis['common_failures'][entry['details']['error']] += 1
                    
                    if 'tool_name' in entry['details']:
                        tool = entry['details']['tool_name']
                        if entry['success']:
                            analysis['tool_performance'][tool]['success'] += 1
                        else:
                            analysis['tool_performance'][tool]['failure'] += 1
        
        if analysis['total_feedback'] > 0:
            analysis['success_rate'] = analysis['success_rate'] / analysis['total_feedback']
        
        return analysis

## Legacy EnhancedChecklistManager removed (Markdown-only flow)

# ==================== PRODUCTION REACT AGENT ====================

class ProductionReActAgent:
    """Production-ready ReAct Agent with all enhancements"""
    
    def __init__(self, system_prompt: str, llm_provider: LLMProvider, tools: Optional[List[ToolSpec]] = None):
        self.system_prompt = system_prompt
        self.llm = llm_provider
        self.tools: List[ToolSpec] = tools or BUILTIN_TOOLS
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

        # 1) Try vendor function-calling: expose all tools and meta-actions as callable functions
        try:
            from openai import APIConnectionError  # type: ignore
            # Only attempt if our LLM provider supports OpenAI function calling
            if isinstance(self.llm, OpenAIProvider):
                tools = export_openai_tools(self.tools)
                # Also expose meta-actions as functions with no/loose params
                meta_actions = [
                    {
                        "type": "function",
                        "function": {
                            "name": "update_checklist",
                            "description": "Create or modify the workflow checklist.",
                            "parameters": {"type": "object", "properties": {}, "additionalProperties": True},
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "ask_user",
                            "description": "Request information from the user.",
                            "parameters": {"type": "object", "properties": {"questions": {"type": "array", "items": {"type": "string"}}, "context": {"type": "string"}}, "additionalProperties": True},
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "error_recovery",
                            "description": "Handle errors and retry failed operations.",
                            "parameters": {"type": "object", "properties": {}, "additionalProperties": True},
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "complete",
                            "description": "Finish the workflow with an optional summary.",
                            "parameters": {"type": "object", "properties": {"summary": {"type": "string"}}, "additionalProperties": True},
                        },
                    },
                ]
                all_tools = tools + meta_actions
                completion = await self.llm.client.chat.completions.create(
                    model=self.llm.model,
                    temperature=self.llm.temperature,
                    messages=[
                        {"role": "system", "content": self.system_prompt_full},
                        {"role": "user", "content": f"Context:\n{context_summary}\n\nChecklist status: {checklist_status}\nDecide the next action and call exactly one function. If a checklist exists and a next executable item is available, you must call the function for exactly that item's tool. Do not select any other tool."},
                    ],
                    tools=all_tools,
                    tool_choice="auto",
                )
                choice = completion.choices[0]
                tool_calls = getattr(choice.message, "tool_calls", None)
                if tool_calls and len(tool_calls) > 0:
                    tool_call = tool_calls[0]
                    name = tool_call.function.name
                    import json as _json
                    params = {}
                    try:
                        params = _json.loads(tool_call.function.arguments or "{}")
                    except Exception:
                        params = {}

                    # Map meta-actions to ActionType, others are TOOL_CALL
                    name_norm = name.strip().lower()
                    if name_norm == "update_checklist":
                        return ActionDecision(action_type=ActionType.UPDATE_CHECKLIST, action_name="create_checklist", parameters=params, reasoning="Vendor function-called update_checklist", confidence=0.9)
                    if name_norm == "ask_user":
                        return ActionDecision(action_type=ActionType.ASK_USER, action_name="ask_user", parameters=params, reasoning="Vendor function-called ask_user", confidence=0.9)
                    if name_norm == "error_recovery":
                        return ActionDecision(action_type=ActionType.ERROR_RECOVERY, action_name="retry_failed_items", parameters=params, reasoning="Vendor function-called error_recovery", confidence=0.9)
                    if name_norm == "complete":
                        return ActionDecision(action_type=ActionType.COMPLETE, action_name="complete", parameters=params, reasoning="Vendor function-called complete", confidence=0.9)

                    # Otherwise treat as a tool call
                    decided = ActionDecision(action_type=ActionType.TOOL_CALL, action_name=name, parameters=params, reasoning="Vendor function-called tool", confidence=0.9)
                    # If a blocker exists in context, force ASK_USER to avoid loops
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
                    # If no checklist exists yet (Markdown flag) and the model didn't ask the user, prefer creating one first
                    if not self.context.get("checklist_created"):
                        return ActionDecision(
                            action_type=ActionType.UPDATE_CHECKLIST,
                            action_name="create_checklist",
                            parameters={},
                            reasoning="No checklist yet; create it before executing tools",
                            confidence=0.9,
                        )
                    # Markdown mode: we do not enforce next-item order based on in-memory checklist
                    return decided
                # If no tool call returned, bootstrap checklist if not created yet
                if not self.context.get("checklist_created"):
                    return ActionDecision(
                        action_type=ActionType.UPDATE_CHECKLIST,
                        action_name="create_checklist",
                        parameters={},
                        reasoning="No function call returned; bootstrap checklist",
                        confidence=0.8,
                    )
                # Otherwise, ask the user
                return ActionDecision(
                    action_type=ActionType.ASK_USER,
                    action_name="ask_user",
                    parameters={"questions": ["What should we do next?"], "context": "No decisive action from model."},
                    reasoning="No function call returned; checklist exists",
                    confidence=0.6,
                )
        except Exception as e:
            self.logger.warning("vendor_action_selection_failed", error=str(e))

        # 2) Fallback to schema-guided JSON decision
        context_summary = self._build_context_summary()
        checklist_status = self._get_checklist_status()
        prompt = f"""Current context:
{context_summary}

Checklist status: {checklist_status}

Available actions:
- UPDATE_CHECKLIST: Create or modify the workflow checklist
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
            # Respect ASK_USER; otherwise, if no checklist exists (Markdown flag), create it first
            if action_decision.action_type != ActionType.ASK_USER and not self.context.get("checklist_created"):
                return ActionDecision(
                    action_type=ActionType.UPDATE_CHECKLIST,
                    action_name="create_checklist",
                    parameters={},
                    reasoning="No checklist yet; create it before proceeding",
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
        
        if action_type == ActionType.UPDATE_CHECKLIST:
            return await self._handle_checklist_action(action_name, parameters)
        
        elif action_type == ActionType.TOOL_CALL:
            return await self._execute_tool_call(action_name, parameters)
        
        elif action_type == ActionType.ASK_USER:
            return await self._handle_user_interaction(action_name, parameters)
        
        elif action_type == ActionType.ERROR_RECOVERY:
            return await self._handle_error_recovery(action_name, parameters)
        
        elif action_type == ActionType.COMPLETE:
            return await self._complete_workflow(parameters)
        
        return f"Executed {action_type.value}: {action_name}"
    
    async def _handle_checklist_action(self, action_name: str, parameters: Dict) -> str:
        """Handle checklist-related actions"""
        
        # Normalize common variants from LLM outputs (e.g., "Create Microservice Checklist")
        normalized = action_name.strip().lower().replace("-", "_").replace(" ", "_")
        if normalized in ("create_checklist", "create_microservice_checklist", "create_a_microservice_checklist"):
            action_name = "create_checklist"

        if action_name == "create_checklist":
            # Extract project info first
            project_info = await self._extract_project_info()
            
            try:
                # New simple Markdown-based checklist generation
                try:
                    from .checklists_simple import create_checklist_md  # type: ignore
                except Exception:
                    from checklists_simple import create_checklist_md  # type: ignore
                filepath = await create_checklist_md(
                    self.llm,
                    project_name=project_info.project_name,
                    project_type=project_info.project_type,
                    user_request=self.context.get("user_request", ""),
                    requirements=project_info.requirements,
                    system_prompt=self.system_prompt_full,
                    session_id=self.session_id,
                )
                self.context["checklist_created"] = True
                self.context["checklist_file"] = filepath
                # Store project identification in context for later Markdown updates
                self.context["project_name"] = project_info.project_name
                self.context["project_type"] = project_info.project_type
                return f"Created checklist (saved to {filepath})"
                
            except Exception as e:
                self.logger.error("checklist_creation_failed", error=str(e))
                # Fallback: create a minimal viable checklist so the workflow can proceed
                try:
                    # Simple fallback: create a minimal Markdown checklist directly
                    try:
                        from .checklists_simple import create_checklist_md  # type: ignore
                    except Exception:
                        from checklists_simple import create_checklist_md  # type: ignore
                    filepath = await create_checklist_md(
                        self.llm,
                        project_name=project_info.project_name,
                        project_type=project_info.project_type,
                        user_request=self.context.get("user_request", ""),
                        requirements=project_info.requirements,
                        system_prompt=self.system_prompt_full,
                        session_id=self.session_id,
                    )
                    self.context["checklist_created"] = True
                    self.context["checklist_file"] = filepath
                    return (
                        f"Created minimal checklist (saved to {filepath}). Original error: {e}"
                    )
                except Exception as inner_e:
                    self.logger.error("checklist_fallback_failed", error=str(inner_e))
                    return f"Failed to create checklist: {e}"
        
        elif action_name == "update_item_status":
            # Update via Markdown helper using instruction text
            try:
                from .checklists_simple import update_checklist_md  # type: ignore
            except Exception:
                from checklists_simple import update_checklist_md  # type: ignore
            # Determine project_name for Markdown checklist
            project_name = self.context.get("project_name")
            if not project_name:
                info = await self._extract_project_info()
                project_name = info.project_name
            item_id = parameters.get("item_id")
            status_text = parameters.get("status")
            notes = parameters.get("notes")
            result_txt = parameters.get("result")
            instruction_parts = [f"Set task {item_id} status to {status_text}."]
            if notes:
                instruction_parts.append(f"Add note to task {item_id}: {notes}.")
            if result_txt:
                instruction_parts.append(f"Record result for task {item_id}: {result_txt}.")
            instruction = " ".join(instruction_parts)
            filepath = await update_checklist_md(
                self.llm,
                project_name=project_name,
                instruction=instruction,
                system_prompt=self.system_prompt_full,
                session_id=self.session_id,
            )
            self.context["checklist_file"] = filepath
            return f"Updated checklist (saved to {filepath})"
        
        elif action_name == "get_next_executable_item":
            # Markdown-only flow: cannot infer next item; guide via file reference
            path = self.context.get("checklist_file")
            return f"Open and follow the checklist: {path}" if path else "No checklist created"
        
        return f"Checklist action '{action_name}' completed"
    
    async def _execute_tool_call(self, tool_name: str, parameters: Dict) -> str:
        """Execute tool and update checklist"""
        
        # Hard guard (Markdown flow): ensure a checklist file exists before tool execution
        if not self.context.get("checklist_created"):
            checklist_msg = await self._handle_checklist_action("create_checklist", {})
            return f"Checklist was missing. {checklist_msg}\nWill proceed with tool execution next."

        # Normalize tool name and resolve via ToolSpec list
        normalized_tool_name = tool_name.strip().lower().replace("-", "_").replace(" ", "_")
        requested_spec = find_tool(self.tools, normalized_tool_name)
        
        # Find corresponding checklist item (exact or normalized match)
        current_item = None  # Markdown-only flow: we no longer track items in memory
        
        # Mark item as in progress in Markdown (best-effort)
        if current_item:
            try:
                from .checklists_simple import update_checklist_md  # type: ignore
            except Exception:
                from checklists_simple import update_checklist_md  # type: ignore
            try:
                project_name = self.context.get("project_name")
                if project_name:
                    await update_checklist_md(
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
                    from .checklists_simple import update_checklist_md  # type: ignore
                except Exception:
                    from checklists_simple import update_checklist_md  # type: ignore
                project_name = self.context.get("project_name")
                if project_name:
                    await update_checklist_md(
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
                from .checklists_simple import update_checklist_md  # type: ignore
            except Exception:
                from checklists_simple import update_checklist_md  # type: ignore
            success = bool(result.get("success"))
            status_text = "COMPLETED" if success else "RETRYING"
            if not success:
                # If it repeatedly fails, mark as FAILED; we don't track retry_count in Markdown, so keep it simple
                status_text = "FAILED"
            try:
                project_name = self.context.get("project_name")
                if project_name:
                    result_text = json.dumps(result, ensure_ascii=False) if success else (result.get("error", "Unknown error"))
                    await update_checklist_md(
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
                    from .checklists_simple import update_checklist_md  # type: ignore
                except Exception:
                    from checklists_simple import update_checklist_md  # type: ignore
                project_name = self.context.get("project_name")
                if project_name:
                    success = bool(result.get("success"))
                    status_text = "COMPLETED" if success else "FAILED"
                    result_text = json.dumps(result, ensure_ascii=False) if success else (result.get("error", "Unknown error"))
                    await update_checklist_md(
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

        # Detect blocking errors and set context flags to steer next step to ASK_USER
        try:
            err_text = str(result.get("error", ""))
            if "already exists and is not empty" in err_text.lower():
                self.context["blocker"] = {
                    "type": "dir_conflict",
                    "message": err_text,
                    "suggestion": "Choose a different project name or remove/empty the existing directory."
                }
            elif "github_token is not set" in err_text.lower():
                self.context["blocker"] = {
                    "type": "missing_github_token",
                    "message": err_text,
                    "suggestion": "Set GITHUB_TOKEN and optionally GITHUB_ORG/OWNER, then retry."
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
                    from .checklists_simple import update_checklist_md  # type: ignore
                except Exception:
                    from checklists_simple import update_checklist_md  # type: ignore
                project_name = self.context.get("project_name")
                if not project_name:
                    info = await self._extract_project_info()
                    project_name = info.project_name
                filepath = await update_checklist_md(
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
                    from .checklists_simple import update_checklist_md  # type: ignore
                except Exception:
                    from checklists_simple import update_checklist_md  # type: ignore
                project_name = self.context.get("project_name")
                if not project_name:
                    info = await self._extract_project_info()
                    project_name = info.project_name
                filepath = await update_checklist_md(
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
        
        if self.context.get("checklist_created"):
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
        
        if self.context.get("checklist_file"):
            summary += f"Checklist File: {self.context.get('checklist_file')}\n"
        else:
            summary += "Checklist: Not created yet\n"
        
        # Recent history
        if self.react_history:
            summary += f"Recent Actions (last 10):\n"
            for action in self.react_history[-10:]:
                summary += f"  - {action}\n"
        
        return summary
    
    def _get_checklist_status(self) -> str:
        """Get current checklist status"""
        
        if not self.context.get("checklist_created"):
            return "No checklist created"
        
        # When using Markdown-only checklist, we cannot compute next item reliably here.
        # Provide a generic status based on existence of the file.
        if self.context.get("checklist_file"):
            return f"Checklist ready at {self.context.get('checklist_file')}"
        
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
            lines.append("\nUsage rules:\n- Use only listed tools.\n- Checklist items must include 'tool' exactly matching a tool name.\n- After each tool run, update the checklist.\n- On blocking errors (directory conflict, missing GITHUB_TOKEN), ASK_USER with concrete next steps.\n- Limit retries for create_repository to 1.")
            return "\n".join(lines)
        except Exception:
            return base_prompt
    
    ## Legacy next-executable resolver removed (Markdown-only flow)
    
    def _enhance_tool_parameters(self, tool_name: str, parameters: Dict) -> Dict:
        """Enhance tool parameters with context"""
        
        enhanced = parameters.copy()
        
        # Add project context from Markdown-based context
        if self.context.get("project_name"):
            enhanced["project_name"] = self.context.get("project_name")
        if self.context.get("project_type"):
            enhanced["project_type"] = self.context.get("project_type")
        enhanced["session_id"] = self.session_id
        
        # Parameter normalization: detect swapped project_name/project_type and set sane defaults
        try:
            allowed_types = {"microservice", "library", "application", "frontend", "backend", "generic"}
            name_pattern = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
            pn = enhanced.get("project_name")
            pt = enhanced.get("project_type")

            # Helper: kebab-case normalization
            def _kebab_case(value: str) -> str:
                return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")

            # If project_name is missing or equals a known type, repair from checklist
            if (pn is None or (isinstance(pn, str) and pn.lower() in allowed_types)) and self.context.get("project_name"):
                enhanced["project_name"] = self.context.get("project_name")
                pn = enhanced["project_name"]

            # If project_type is missing, take from checklist
            if (pt is None or pt == "") and self.context.get("project_type"):
                enhanced["project_type"] = self.context.get("project_type")
                pt = enhanced["project_type"]

            # Detect swapped name/type
            if isinstance(pn, str) and isinstance(pt, str):
                looks_like_type = pn.lower() in allowed_types
                looks_like_name = bool(name_pattern.match(pt))
                if looks_like_type and looks_like_name:
                    enhanced["project_name"], enhanced["project_type"] = pt, pn
                    pn, pt = enhanced["project_name"], enhanced["project_type"]

            # Normalize kebab-case for project_name
            if isinstance(enhanced.get("project_name"), str):
                enhanced["project_name"] = _kebab_case(enhanced["project_name"]) or "unnamed"

            # Prevent generic placeholders from leaking to tools by repairing from checklist
            generic_names = {"service", "microservice", "application", "app", "project"}
            if isinstance(enhanced.get("project_name"), str) and enhanced["project_name"].lower() in generic_names:
                enhanced["project_name"] = self.context.get("project_name") or "unnamed"
        except Exception:
            pass

        if not enhanced.get("project_name"):
            enhanced["project_name"] = self.context.get("project_name") or "unnamed"

        # Tool-specific enhancements
        if tool_name == "create_repository":
            # Ensure repo name reflects resolved project_name
            enhanced["name"] = enhanced.get("name") or enhanced.get("project_name") or "unnamed"
        if tool_name in ("setup_cicd_pipeline", "setup_cicd") and "repo_path" not in enhanced:
            enhanced["repo_path"] = f"./{enhanced.get('project_name', 'project')}"
        if tool_name == "apply_template":
            if "target_path" not in enhanced:
                enhanced["target_path"] = f"./{enhanced.get('project_name', 'project')}"
            if "template" not in enhanced or not enhanced.get("template"):
                enhanced["template"] = "fastapi-microservice"
        if tool_name == "validate_project_name_and_type":
            # Ensure both fields present for robust validation
            if not enhanced.get("project_type"):
                enhanced["project_type"] = self.context.get("project_type")
        if tool_name == "generate_k8s_manifests" and "service_name" not in enhanced:
            enhanced["service_name"] = enhanced.get("project_name", "service")
        if tool_name == "setup_observability" and "project_name" not in enhanced:
            enhanced["project_name"] = enhanced.get("project_name", self.context.get("project_name", "project"))
        
        return enhanced
    
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

# ==================== SYSTEM PROMPTS ====================
# Imported from capstone/prototype/prompt.py

# ==================== MAIN EXECUTION ====================

async def main():
    """Main execution function"""
    
    # Start Prometheus metrics server
    start_http_server(8070)
    
    # Initialize LLM provider with fallback to mock if no API key
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if openai_key:
        llm_provider = OpenAIProvider(api_key=openai_key)
    else:
        raise ValueError("OPENAI_API_KEY is not set")
    
    # Initialize agent
    agent = ProductionReActAgent(
        system_prompt=IDP_COPILOT_SYSTEM_PROMPT_GIT,
        llm_provider=llm_provider,
    )
    
    # Interactive chat loop
    print("=" * 80)
    print("🚀 Production IDP Copilot - Interactive CLI")
    print("Type 'exit' to quit.")
    print("=" * 80)
    
    session_id: Optional[str] = None
    while True:
        try:
            user_msg = input("You: ").strip()
        except EOFError:
            break
        if user_msg.lower() in ("exit", "quit", "q", ""):
            break
        async for update in agent.process_request(user_msg, session_id=session_id):
            print(update, end="", flush=True)
        # Keep session across turns
        session_id = agent.session_id
        # If agent requested user input, continue loop to capture it
        if agent.context.get("awaiting_user_input"):
            continue
        print("")
    
    # Print simple metrics snapshot on exit
    print("\n" + "=" * 80)
    print("📊 Workflow Metrics:")
    print("=" * 80)
    print("Prometheus metrics available at http://localhost:8070")

if __name__ == "__main__":
    asyncio.run(main())