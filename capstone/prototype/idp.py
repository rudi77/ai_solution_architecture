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

# External dependencies (requirements.txt)
# pip install pydantic langchain openai anthropic structlog prometheus-client circuitbreaker aiofiles

from pydantic import BaseModel, Field, validator
from prometheus_client import Counter, Histogram, Gauge, start_http_server
from circuitbreaker import circuit
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

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
trace.set_tracer_provider(TracerProvider())
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

class ChecklistItemStatus(Enum):
    PENDING = "⏳ Pending"
    IN_PROGRESS = "🔄 In Progress"
    COMPLETED = "✅ Completed"
    FAILED = "❌ Failed"
    BLOCKED = "🚫 Blocked"
    SKIPPED = "⏭️ Skipped"
    RETRYING = "🔁 Retrying"

@dataclass
class ChecklistItem:
    id: str
    title: str
    description: str
    dependencies: List[str]
    tool_action: Optional[str] = None
    tool_params: Optional[Dict] = None
    status: ChecklistItemStatus = ChecklistItemStatus.PENDING
    result: Optional[str] = None
    notes: Optional[str] = None
    updated_at: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    error_details: Optional[Dict] = None

@dataclass
class ProjectChecklist:
    project_name: str
    project_type: str
    user_request: str
    created_at: str
    items: List[ChecklistItem]
    current_step: int = 0
    session_id: str = field(default_factory=lambda: hashlib.md5(str(time.time()).encode()).hexdigest())
    
    def to_markdown(self) -> str:
        """Konvertiert zu Markdown"""
        completed = sum(1 for item in self.items if item.status == ChecklistItemStatus.COMPLETED)
        total = len(self.items)
        progress_chars = "█" * completed + "░" * (total - completed)
        
        md = f"""# IDP Copilot Checklist: {self.project_name}

**Session ID:** {self.session_id}
**Project Type:** {self.project_type}
**Created:** {self.created_at}
**User Request:** "{self.user_request}"
**Progress:** [{progress_chars}] {completed}/{total} ({completed/total*100:.1f}%)

## Checklist Items

"""
        for item in self.items:
            deps = f" (requires: {', '.join(item.dependencies)})" if item.dependencies else ""
            md += f"""### {item.status.value} {item.id}. {item.title}

{item.description}{deps}

"""
            if item.tool_action:
                md += f"**Tool:** `{item.tool_action}`\n"
            if item.result:
                md += f"**Result:** {item.result}\n"
            if item.notes:
                md += f"**Notes:** {item.notes}\n"
            if item.retry_count > 0:
                md += f"**Retries:** {item.retry_count}/{item.max_retries}\n"
            if item.error_details:
                md += f"**Last Error:** {item.error_details.get('error', 'Unknown')}\n"
            md += "\n---\n"
        
        return md

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

class ChecklistGeneration(BaseModel):
    """Structured output for checklist generation"""
    items: List[Dict[str, Any]]
    estimated_duration: int  # in minutes
    risk_level: str = Field(default="low", pattern="^(low|medium|high)$")
    
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
        
        schema = response_model.schema()
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
            return response_model(**data)
        except Exception as e:
            self.logger.error("anthropic_structured_failed", error=str(e))
            raise

# ==================== ENHANCED TOOL REGISTRY WITH CIRCUIT BREAKER ====================

class EnhancedToolRegistry:
    """Production-ready tool registry with timeout and circuit breaker"""
    
    def __init__(self):
        self.tools = {}
        self.tool_aliases: Dict[str, str] = {}
        self.logger = structlog.get_logger()
        self._register_default_tools()
    
    def register_tool(self, name: str, func: callable, description: str = "", timeout: int = 30):
        """Registriert Tool mit Timeout"""
        self.tools[name] = {
            "func": func,
            "description": description,
            "timeout": timeout
        }
        self.logger.info("tool_registered", tool_name=name)
    
    def register_alias(self, alias_name: str, target_name: str):
        """Register a human-friendly alias that maps to an existing tool name."""
        normalized_alias = alias_name.strip().lower().replace("-", "_").replace(" ", "_")
        self.tool_aliases[normalized_alias] = target_name
        self.logger.info("tool_alias_registered", alias=normalized_alias, target=target_name)
    
    @circuit(failure_threshold=5, recovery_timeout=60, expected_exception=Exception)
    async def execute_tool_async(self, name: str, params: Dict) -> Dict:
        """Async tool execution with circuit breaker"""
        resolved_name = self.resolve_tool_name(name)
        if resolved_name not in self.tools:
            return {"success": False, "error": f"Tool '{name}' not found"}
        
        tool_info = self.tools[resolved_name]
        start_time = time.time()
        
        try:
            with tracer.start_as_current_span(f"tool_execution_{resolved_name}"):
                # Execute with timeout
                result = await self._execute_with_timeout(
                    tool_info["func"],
                    params,
                    tool_info["timeout"]
                )
                
                duration = time.time() - start_time
                tool_execution_time.labels(tool_name=resolved_name).observe(duration)
                tool_success_rate.labels(tool_name=resolved_name).inc()
                
                self.logger.info("tool_executed", 
                               tool_name=resolved_name, 
                               duration=duration,
                               success=result.get("success", True))
                
                return result
                
        except asyncio.TimeoutError:
            tool_failure_rate.labels(tool_name=resolved_name).inc()
            error_msg = f"Tool '{resolved_name}' timed out after {tool_info['timeout']}s"
            self.logger.error("tool_timeout", tool_name=resolved_name, timeout=tool_info["timeout"])
            return {"success": False, "error": error_msg}
            
        except Exception as e:
            tool_failure_rate.labels(tool_name=resolved_name).inc()
            self.logger.error("tool_execution_failed", tool_name=resolved_name, error=str(e))
            return {"success": False, "error": str(e)}
    
    def resolve_tool_name(self, name: str) -> str:
        """Resolve alias or normalized variants to a registered tool name."""
        normalized = name.strip().lower().replace("-", "_").replace(" ", "_")
        if normalized in self.tools:
            return normalized
        if normalized in self.tool_aliases:
            return self.tool_aliases[normalized]
        return name
    
    async def _execute_with_timeout(self, func: callable, params: Dict, timeout: int):
        """Execute function with timeout"""
        loop = asyncio.get_event_loop()
        
        # If function is async, await it directly
        if asyncio.iscoroutinefunction(func):
            return await asyncio.wait_for(func(**params), timeout=timeout)
        
        # For sync functions, run in executor
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = loop.run_in_executor(executor, func, **params)
            return await asyncio.wait_for(future, timeout=timeout)
    
    def _register_default_tools(self):
        """Register default IDP tools"""
        # GitHub Tools
        self.register_tool("create_repository", self._create_repository, "Creates GitHub repository", 10)
        self.register_tool("setup_branch_protection", self._setup_branch_protection, "Setup branch rules", 5)
        # Wrapper for convenience
        self.register_tool(
            "create_git_repository_with_branch_protection",
            self._create_git_repository_with_branch_protection,
            "Create repo then apply standard branch protection",
            20,
        )
        # Validation Tools
        self.register_tool("validate_project_name_and_type", self._validate_project_name_and_type, "Validate project name and type", 5)
        
        # Template Tools
        self.register_tool("list_templates", self._list_templates, "List available templates", 5)
        self.register_tool("apply_template", self._apply_template, "Apply project template", 15)
        
        # CI/CD Tools
        self.register_tool("setup_cicd_pipeline", self._setup_cicd, "Setup CI/CD pipeline", 20)
        self.register_tool("run_initial_tests", self._run_tests, "Run initial test suite", 30)
        
        # Infrastructure Tools
        self.register_tool("create_k8s_namespace", self._create_k8s_namespace, "Create K8s namespace", 10)
        self.register_tool("deploy_to_staging", self._deploy_staging, "Deploy to staging", 45)

        # Knowledge Base Tools (aliases included for robustness)
        self.register_tool(
            "search_knowledge_base_for_guidelines",
            self._search_knowledge_base_for_guidelines,
            "Searches local knowledge base for guidelines relevant to the project",
            10,
        )
        self.register_tool(
            "search_knowledge_base",
            self._search_knowledge_base_for_guidelines,
            "Alias of search_knowledge_base_for_guidelines",
            10,
        )

        # Observability/Docs/K8s artifacts (lightweight stubs for workflow continuity)
        self.register_tool("setup_observability", self._setup_observability, "Setup monitoring & logging", 10)
        self.register_tool("generate_k8s_manifests", self._generate_k8s_manifests, "Generate K8s manifests", 10)
        self.register_tool("generate_documentation", self._generate_documentation, "Generate documentation", 10)

        # Aliases to match checklist/tool naming variants
        self.register_alias("project-validator", "validate_project_name_and_type")
        self.register_alias("kb-search", "search_knowledge_base_for_guidelines")
        self.register_alias("search-guidelines", "search_knowledge_base_for_guidelines")
        self.register_alias("git-repo-creator", "create_git_repository_with_branch_protection")
        self.register_alias("create-git-repo", "create_git_repository_with_branch_protection")
        self.register_alias("template-applier", "apply_template")
        self.register_alias("ci-cd-configurator", "setup_cicd_pipeline")
        self.register_alias("observability-integrator", "setup_observability")
        self.register_alias("k8s-manifest-generator", "generate_k8s_manifests")
        self.register_alias("k8s-deployer", "deploy_to_staging")
        self.register_alias("test-runner", "run_initial_tests")
        self.register_alias("doc-generator", "generate_documentation")

    def export_openai_tools(self) -> List[Dict[str, Any]]:
        """Export registered tools as OpenAI tool definitions.
        
        Note: Parameter schemas are approximated from call signatures. Types default to string when unknown.
        """
        import inspect
        tools: List[Dict[str, Any]] = []
        def build_def(name: str, func: callable, description: str) -> Dict[str, Any]:
            # Build a permissive JSON schema for parameters
            properties: Dict[str, Any] = {}
            required: List[str] = []
            try:
                sig = inspect.signature(func)
                for param_name, param in sig.parameters.items():
                    if param_name == "self":
                        continue
                    # Heuristic typing: keep simple and robust
                    properties[param_name] = {"type": "string"}
                    if param.default is inspect._empty:
                        required.append(param_name)
            except Exception:
                properties = {}
                required = []
            parameters_schema: Dict[str, Any] = {
                "type": "object",
                "properties": properties,
                "additionalProperties": True,
            }
            if required:
                parameters_schema["required"] = required
            return {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters_schema,
                },
            }

        # Real tools
        for name, info in self.tools.items():
            tools.append(build_def(name, info.get("func"), info.get("description", "")))

        # Aliases exported as separate callable names
        for alias, target in self.tool_aliases.items():
            if target in self.tools:
                func = self.tools[target]["func"]
                description = f"Alias of {target}"
                tools.append(build_def(alias, func, description))
        return tools
    
    # Async tool implementations
    async def _create_repository(self, name: str, visibility: str = "private", **kwargs) -> Dict:
        """Creates GitHub repository (async)"""
        await asyncio.sleep(2)  # Simulate API call
        
        if any(char in name for char in "@!#$%^&*()"):
            return {"success": False, "error": "Invalid repository name"}
        
        return {
            "success": True,
            "repo_url": f"https://github.com/company/{name}",
            "clone_url": f"git@github.com:company/{name}.git"
        }

    async def _create_git_repository_with_branch_protection(self, repo_name: str = None, visibility: str = "private", **kwargs) -> Dict:
        """Create repository and apply branch protection rules in one step."""
        name = repo_name or kwargs.get("name") or kwargs.get("project_name") or "unnamed"
        create = await self._create_repository(name=name, visibility=visibility, **kwargs)
        if not create.get("success"):
            return create
        protection = await self._setup_branch_protection(repo_name=name, **kwargs)
        if not protection.get("success"):
            return protection
        return {
            "success": True,
            "repo": create,
            "branch_protection": protection,
        }
    
    async def _setup_branch_protection(self, repo_name: str, **kwargs) -> Dict:
        await asyncio.sleep(1)
        return {
            "success": True,
            "rules": ["require-pr-reviews", "dismiss-stale-reviews", "require-status-checks"]
        }
    
    async def _list_templates(self, project_type: str = None, **kwargs) -> Dict:
        await asyncio.sleep(0.5)
        templates = {
            "microservice": ["fastapi-microservice", "spring-boot-service", "go-microservice"],
            "library": ["python-library", "typescript-library", "java-library"],
            "frontend": ["nextjs-app", "react-spa", "vue-app"]
        }
        
        if project_type and project_type in templates:
            return {"success": True, "templates": templates[project_type]}
        
        return {"success": True, "templates": list(templates.values())}
    
    async def _apply_template(self, template: str, target_path: str, **kwargs) -> Dict:
        await asyncio.sleep(3)
        return {
            "success": True,
            "files_created": ["src/main.py", "tests/test_main.py", "README.md", "Dockerfile"],
            "next_steps": ["Configure environment variables", "Update README"]
        }
    
    async def _setup_cicd(self, repo_path: str, pipeline_type: str = "github-actions", **kwargs) -> Dict:
        await asyncio.sleep(2)
        return {
            "success": True,
            "pipeline_file": f".github/workflows/ci.yml",
            "stages": ["lint", "test", "build", "security-scan"]
        }

    async def _setup_observability(self, project_name: str = None, **kwargs) -> Dict:
        await asyncio.sleep(1)
        return {
            "success": True,
            "stack": ["prometheus", "grafana", "otel"],
            "notes": "Integrated default dashboards and traces",
        }
    
    async def _run_tests(self, project_path: str, **kwargs) -> Dict:
        await asyncio.sleep(5)
        return {
            "success": True,
            "tests_run": 42,
            "tests_passed": 42,
            "coverage": "87%"
        }

    async def _generate_k8s_manifests(self, service_name: str = None, **kwargs) -> Dict:
        await asyncio.sleep(1)
        name = service_name or kwargs.get("project_name") or "service"
        return {
            "success": True,
            "files": [
                f"k8s/{name}-deployment.yaml",
                f"k8s/{name}-service.yaml",
                f"k8s/{name}-configmap.yaml",
            ],
        }
    
    async def _create_k8s_namespace(self, name: str, **kwargs) -> Dict:
        await asyncio.sleep(1)
        return {
            "success": True,
            "namespace": name,
            "resources": ["namespace", "resource-quota", "network-policy"]
        }
    
    async def _deploy_staging(self, project: str, version: str = "latest", **kwargs) -> Dict:
        await asyncio.sleep(8)
        return {
            "success": True,
            "environment": "staging",
            "url": f"https://{project}-staging.company.io",
            "version": version
        }

    async def _generate_documentation(self, project_name: str = None, **kwargs) -> Dict:
        await asyncio.sleep(1)
        name = project_name or "project"
        return {
            "success": True,
            "artifacts": [f"docs/{name}-api.md", f"docs/{name}-operations.md"],
        }

    async def _validate_project_name_and_type(self, project_name: str = None, project_type: str = None,
                                             programming_language: str = None, **kwargs) -> Dict:
        """Validate project name and type against simple conventions."""
        await asyncio.sleep(0)  # keep async signature predictable

        if not project_name or not isinstance(project_name, str):
            return {"success": False, "error": "Missing required parameter: project_name"}

        # kebab-case, lowercase letters, numbers and single dashes between segments
        name_pattern = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
        if not name_pattern.match(project_name):
            return {"success": False, "error": "Invalid project name. Use kebab-case: lowercase letters, numbers, and single dashes."}

        allowed_types = {"microservice", "library", "application", "frontend", "backend", "generic"}
        if project_type and project_type not in allowed_types:
            return {"success": False, "error": f"Unsupported project_type '{project_type}'. Allowed: {sorted(allowed_types)}"}

        details = {
            "project_name": project_name,
            "project_type": project_type or "microservice",
            "programming_language": programming_language or "python",
            "policy_checks": ["kebab-case", "allowed_type"],
        }
        return {"success": True, "result": details}

    async def _search_knowledge_base_for_guidelines(self, project_type: str = None, language: str = None,
                                                    project_name: str = None, **kwargs) -> Dict:
        """Search simple local knowledge base for relevant guidelines.

        Minimal, dependency-free implementation that scans known docs directories
        for markdown files and returns matches based on project_type/language.
        """
        try:
            # Resolve relative to repo root if possible
            repo_root = Path.cwd()
            base_paths = [
                repo_root / "capstone" / "backend" / "documents" / "guidelines",
                repo_root / "capstone" / "documents" / "guidelines",
                repo_root / "capstone" / "backend" / "documents",
            ]

            keywords: List[str] = []
            if project_type:
                keywords.append(str(project_type).lower())
            if language:
                keywords.append(str(language).lower())
            if project_name:
                # project name is often too specific; include but low priority
                keywords.append(str(project_name).lower())
            # broaden
            keywords.extend(["service", "microservice", "standards", "guidelines", "ci/cd", "cicd"])

            matched: List[Dict[str, Any]] = []
            scanned_files: List[str] = []

            for base in base_paths:
                if not base.exists() or not base.is_dir():
                    continue
                for file in base.glob("**/*.md"):
                    scanned_files.append(str(file))
                    try:
                        text = file.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        continue

                    text_lower = text.lower()
                    filename_lower = file.name.lower()
                    score = 0
                    for kw in keywords:
                        if kw and (kw in text_lower or kw in filename_lower):
                            score += 1

                    # Extract first heading as title, and up to 2 relevant lines
                    title = None
                    for line in text.splitlines():
                        if line.strip().startswith("#"):
                            title = line.strip().lstrip("# ")
                            break
                    if score > 0 or (not keywords and title):
                        # pick small snippets containing keywords
                        snippets: List[str] = []
                        if keywords:
                            for line in text.splitlines():
                                line_l = line.lower()
                                if any(kw in line_l for kw in keywords) and line.strip():
                                    snippets.append(line.strip())
                                    if len(snippets) >= 3:
                                        break
                        matched.append({
                            "file": str(file),
                            "title": title or file.name,
                            "score": score,
                            "snippets": snippets,
                        })

            # Sort by score descending, then title
            matched.sort(key=lambda m: (-m.get("score", 0), m.get("title") or ""))

            # Fallback: if nothing matched, return top-level known guidelines if present
            if not matched:
                defaults = []
                for default_name in [
                    "python-service-standards.md",
                    "cicd-pipeline-standards.md",
                    "go-service-standards.md",
                ]:
                    for base in base_paths:
                        candidate = base / default_name
                        if candidate.exists():
                            defaults.append({
                                "file": str(candidate),
                                "title": default_name.replace("-", " ").replace(".md", "").title(),
                                "score": 0,
                                "snippets": [],
                            })
                matched = defaults

            return {
                "success": True,
                "result": {
                    "searched_files": scanned_files,
                    "matches": matched[:10],
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

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

# ==================== ENHANCED CHECKLIST MANAGER ====================

class EnhancedChecklistManager:
    """Enhanced checklist manager with async operations"""
    
    def __init__(self, checklist_dir: str = "./checklists"):
        self.checklist_dir = Path(checklist_dir)
        self.checklist_dir.mkdir(exist_ok=True)
        self.logger = structlog.get_logger()
    
    async def save_checklist(self, checklist: ProjectChecklist) -> str:
        """Save checklist asynchronously"""
        filename = f"{checklist.project_name}_{checklist.session_id}.md"
        filepath = self.checklist_dir / filename
        
        try:
            import aiofiles
            async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
                await f.write(checklist.to_markdown())
            
            self.logger.info("checklist_saved", 
                           project=checklist.project_name,
                           session_id=checklist.session_id)
            return str(filepath)
            
        except Exception as e:
            self.logger.error("checklist_save_failed", error=str(e))
            raise
    
    async def update_item_status(self, checklist: ProjectChecklist, item_id: str,
                                status: ChecklistItemStatus, result: str = None, 
                                notes: str = None, error_details: Dict = None):
        """Update checklist item status"""
        for item in checklist.items:
            if item.id == item_id:
                item.status = status
                item.updated_at = datetime.now().isoformat()
                
                if result:
                    item.result = result
                if notes:
                    item.notes = notes
                if error_details:
                    item.error_details = error_details
                
                self.logger.info("checklist_item_updated",
                               item_id=item_id,
                               status=status.value)
                break
        
        await self.save_checklist(checklist)
    
    async def mark_dependent_items_blocked(self, checklist: ProjectChecklist, failed_item_id: str):
        """Mark items that depend on failed item as blocked"""
        for item in checklist.items:
            if failed_item_id in item.dependencies and item.status == ChecklistItemStatus.PENDING:
                item.status = ChecklistItemStatus.BLOCKED
                item.notes = f"Blocked due to failure of item {failed_item_id}"
                
                self.logger.info("item_blocked",
                               item_id=item.id,
                               blocked_by=failed_item_id)
        
        await self.save_checklist(checklist)

# ==================== PRODUCTION REACT AGENT ====================

class ProductionReActAgent:
    """Production-ready ReAct Agent with all enhancements"""
    
    def __init__(self, system_prompt: str, llm_provider: LLMProvider):
        self.system_prompt = system_prompt
        self.llm = llm_provider
        self.tools = EnhancedToolRegistry()
        self.checklist_manager = EnhancedChecklistManager()
        self.state_manager = StateManager()
        self.feedback_collector = FeedbackCollector()
        
        self.context = {}
        self.current_checklist: Optional[ProjectChecklist] = None
        self.react_history = []
        self.step_counter = 0
        self.max_steps = 50
        self.session_id = None
        
        self.logger = structlog.get_logger()
    
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
                system_prompt=self.system_prompt
            )
            return thought
        except Exception as e:
            self.logger.error("thought_generation_failed", error=str(e))
            return "I need to analyze the current situation and determine the best next step."
    
    async def _determine_action(self) -> ActionDecision:
        """Determine next action using vendor function-calling when available, otherwise schema JSON."""
        context_summary = self._build_context_summary()
        checklist_status = self._get_checklist_status()

        # 1) Try vendor function-calling: expose all tools and meta-actions as callable functions
        try:
            from openai import APIConnectionError  # type: ignore
            # Only attempt if our LLM provider supports OpenAI function calling
            if isinstance(self.llm, OpenAIProvider):
                tools = self.tools.export_openai_tools()
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
                            "parameters": {"type": "object", "properties": {"questions": {"type": "array", "items": {"type": "string"}}}, "additionalProperties": True},
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
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": f"Context:\n{context_summary}\n\nChecklist status: {checklist_status}\nDecide the next action and call exactly one function."},
                    ],
                    tools=all_tools,
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
                    return ActionDecision(action_type=ActionType.TOOL_CALL, action_name=name, parameters=params, reasoning="Vendor function-called tool", confidence=0.9)
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
                system_prompt=self.system_prompt
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
                    
                    # Mark checklist item as failed if applicable
                    if self.current_checklist:
                        await self._mark_current_item_failed(str(e))
                    
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
            
            # Generate checklist using LLM
            checklist_prompt = f"""Create a detailed implementation checklist for:
Project Type: {project_info.project_type}
Project Name: {project_info.project_name}
Requirements: {json.dumps(project_info.requirements)}

Generate a comprehensive checklist with all necessary steps, dependencies, and required tools."""
            
            try:
                checklist_data = await self.llm.generate_structured_response(
                    checklist_prompt,
                    ChecklistGeneration,
                    system_prompt=self.system_prompt
                )
                
                # Build checklist object
                self.current_checklist = await self._build_checklist(project_info, checklist_data)
                
                # Save checklist
                filepath = await self.checklist_manager.save_checklist(self.current_checklist)
                
                self.context["checklist_created"] = True
                self.context["checklist_file"] = filepath
                
                return f"Created checklist with {len(self.current_checklist.items)} items (saved to {filepath})"
                
            except Exception as e:
                self.logger.error("checklist_creation_failed", error=str(e))
                # Fallback: create a minimal viable checklist so the workflow can proceed
                try:
                    fallback_data = ChecklistGeneration(
                        items=[
                            {
                                "title": "Create Repository",
                                "description": "Create GitHub repository",
                                "dependencies": [],
                                "tool": "create_repository"
                            },
                            {
                                "title": "Apply Template",
                                "description": "Apply microservice template",
                                "dependencies": ["1"],
                                "tool": "apply_template"
                            },
                            {
                                "title": "Setup CI/CD",
                                "description": "Configure pipeline",
                                "dependencies": ["2"],
                                "tool": "setup_cicd_pipeline"
                            }
                        ],
                        estimated_duration=30,
                        risk_level="low"
                    )
                    self.current_checklist = await self._build_checklist(project_info, fallback_data)
                    filepath = await self.checklist_manager.save_checklist(self.current_checklist)
                    self.context["checklist_created"] = True
                    self.context["checklist_file"] = filepath
                    return (
                        f"Created checklist with {len(self.current_checklist.items)} items using fallback "
                        f"(saved to {filepath}). Original error: {e}"
                    )
                except Exception as inner_e:
                    self.logger.error("checklist_fallback_failed", error=str(inner_e))
                    return f"Failed to create checklist: {e}"
        
        elif action_name == "update_item_status":
            if not self.current_checklist:
                return "No active checklist to update"
            
            item_id = parameters.get("item_id")
            status = ChecklistItemStatus(parameters.get("status"))
            
            await self.checklist_manager.update_item_status(
                self.current_checklist,
                item_id,
                status,
                parameters.get("result"),
                parameters.get("notes")
            )
            
            return f"Updated item {item_id} to {status.value}"
        
        elif action_name == "get_next_executable_item":
            next_item = self._get_next_executable_item()
            if next_item:
                return f"Next item: {next_item.id} - {next_item.title}"
            return "No executable items available"
        
        return f"Checklist action '{action_name}' completed"
    
    async def _execute_tool_call(self, tool_name: str, parameters: Dict) -> str:
        """Execute tool and update checklist"""
        
        # Normalize tool name to improve robustness
        normalized_tool_name = tool_name.strip().lower().replace("-", "_").replace(" ", "_")
        
        # Find corresponding checklist item (exact or normalized match)
        current_item = None
        if self.current_checklist:
            for item in self.current_checklist.items:
                if item.status not in [ChecklistItemStatus.PENDING, ChecklistItemStatus.RETRYING]:
                    continue
                item_name_normalized = (item.tool_action or "").strip().lower().replace("-", "_").replace(" ", "_")
                if item.tool_action == tool_name or item_name_normalized == normalized_tool_name:
                    current_item = item
                    break
        
        # Mark item as in progress
        if current_item:
            await self.checklist_manager.update_item_status(
                self.current_checklist,
                current_item.id,
                ChecklistItemStatus.IN_PROGRESS
            )
        
        # Enhance parameters with context
        enhanced_params = self._enhance_tool_parameters(normalized_tool_name, parameters)
        
        # Execute tool
        result = await self.tools.execute_tool_async(normalized_tool_name, enhanced_params)
        # If not found, try original name as fallback (defensive)
        if not result.get("success") and isinstance(result.get("error"), str) and "not found" in result.get("error", ""):
            result = await self.tools.execute_tool_async(tool_name, enhanced_params)
        
        # Update checklist based on result
        if current_item:
            if result.get("success"):
                status = ChecklistItemStatus.COMPLETED
                result_text = json.dumps(result.get("result", {}))
            else:
                current_item.retry_count += 1
                if current_item.retry_count < current_item.max_retries:
                    status = ChecklistItemStatus.RETRYING
                else:
                    status = ChecklistItemStatus.FAILED
                    # Mark dependent items as blocked
                    await self.checklist_manager.mark_dependent_items_blocked(
                        self.current_checklist,
                        current_item.id
                    )
                result_text = result.get("error", "Unknown error")
            
            await self.checklist_manager.update_item_status(
                self.current_checklist,
                current_item.id,
                status,
                result_text,
                error_details={"error": result.get("error")} if not result.get("success") else None
            )
        
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
        # For now, we'll save state and return message
        self.context["awaiting_user_input"] = {
            "action": action_name,
            "questions": questions,
            "requested_at": datetime.now().isoformat()
        }
        
        await self._save_current_state()
        
        return interaction_msg
    
    async def _handle_error_recovery(self, action_name: str, parameters: Dict) -> str:
        """Handle error recovery strategies"""
        
        if action_name == "retry_failed_items":
            # Find failed items that can be retried
            failed_items = [
                item for item in self.current_checklist.items
                if item.status == ChecklistItemStatus.FAILED and item.retry_count < item.max_retries
            ]
            
            if failed_items:
                # Reset first failed item for retry
                item = failed_items[0]
                item.status = ChecklistItemStatus.RETRYING
                item.retry_count += 1
                
                await self.checklist_manager.save_checklist(self.current_checklist)
                
                return f"Retrying failed item: {item.id} - {item.title} (attempt {item.retry_count})"
            
            return "No failed items available for retry"
        
        elif action_name == "skip_blocked_items":
            # Mark blocked items as skipped
            blocked_items = [
                item for item in self.current_checklist.items
                if item.status == ChecklistItemStatus.BLOCKED
            ]
            
            for item in blocked_items:
                item.status = ChecklistItemStatus.SKIPPED
                item.notes = "Skipped due to dependency failure"
            
            if blocked_items:
                await self.checklist_manager.save_checklist(self.current_checklist)
                return f"Skipped {len(blocked_items)} blocked items"
            
            return "No blocked items to skip"
        
        return f"Error recovery action '{action_name}' completed"
    
    async def _complete_workflow(self, parameters: Dict) -> str:
        """Complete the workflow"""
        
        summary = parameters.get("summary", "Workflow completed successfully")
        
        if self.current_checklist:
            # Generate completion report
            completed = sum(1 for item in self.current_checklist.items 
                          if item.status == ChecklistItemStatus.COMPLETED)
            failed = sum(1 for item in self.current_checklist.items 
                       if item.status == ChecklistItemStatus.FAILED)
            skipped = sum(1 for item in self.current_checklist.items 
                        if item.status == ChecklistItemStatus.SKIPPED)
            
            report = f"""
Workflow Completion Report:
- Total Items: {len(self.current_checklist.items)}
- Completed: {completed}
- Failed: {failed}
- Skipped: {skipped}
- Success Rate: {completed/len(self.current_checklist.items)*100:.1f}%

Summary: {summary}
"""
            
            # Save final checklist state
            await self.checklist_manager.save_checklist(self.current_checklist)
            
            return report
        
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
    
    async def _build_checklist(self, project_info: ProjectInfo, 
                              checklist_data: ChecklistGeneration) -> ProjectChecklist:
        """Build checklist from LLM response"""
        
        items = []
        for idx, item_data in enumerate(checklist_data.items, 1):
            items.append(ChecklistItem(
                id=str(idx),
                title=item_data.get("title", f"Step {idx}"),
                description=item_data.get("description", ""),
                dependencies=[str(d) for d in item_data.get("dependencies", [])],
                tool_action=item_data.get("tool"),
                tool_params=item_data.get("params", {})
            ))
        
        return ProjectChecklist(
            project_name=project_info.project_name,
            project_type=project_info.project_type,
            user_request=self.context.get("user_request", ""),
            created_at=datetime.now().isoformat(),
            items=items,
            session_id=self.session_id
        )
    
    def _build_context_summary(self) -> str:
        """Build context summary for LLM"""
        
        summary = f"Session: {self.session_id}\n"
        summary += f"User Request: {self.context.get('user_request', 'None')}\n"
        if self.context.get("recent_user_message"):
            summary += f"Recent User Message: {self.context.get('recent_user_message')}\n"
        summary += f"Step: {self.step_counter}/{self.max_steps}\n"
        
        if self.current_checklist:
            status_counts = defaultdict(int)
            for item in self.current_checklist.items:
                status_counts[item.status.value] += 1
            
            summary += f"Checklist Status:\n"
            for status, count in status_counts.items():
                summary += f"  - {status}: {count}\n"
            
            # Current/next item
            next_item = self._get_next_executable_item()
            if next_item:
                summary += f"Next Item: {next_item.id} - {next_item.title}\n"
        else:
            summary += "Checklist: Not created yet\n"
        
        # Recent history
        if self.react_history:
            summary += f"Recent Actions:\n"
            for action in self.react_history[-3:]:
                summary += f"  - {action}\n"
        
        return summary
    
    def _get_checklist_status(self) -> str:
        """Get current checklist status"""
        
        if not self.current_checklist:
            return "No checklist created"
        
        next_item = self._get_next_executable_item()
        if next_item:
            return f"Ready to execute: {next_item.id} - {next_item.title}"
        
        # Check for completion
        all_done = all(
            item.status in [ChecklistItemStatus.COMPLETED, ChecklistItemStatus.SKIPPED]
            for item in self.current_checklist.items
        )
        
        if all_done:
            return "All items completed or skipped"
        
        # Check for blocked items
        has_blocked = any(
            item.status == ChecklistItemStatus.BLOCKED
            for item in self.current_checklist.items
        )
        
        if has_blocked:
            return "Items blocked due to dependencies"
        
        # Check for failed items
        has_failed = any(
            item.status == ChecklistItemStatus.FAILED
            for item in self.current_checklist.items
        )
        
        if has_failed:
            return "Has failed items that need attention"
        
        return "Waiting for next action"
    
    def _get_next_executable_item(self) -> Optional[ChecklistItem]:
        """Get next item that can be executed"""
        
        if not self.current_checklist:
            return None
        
        for item in self.current_checklist.items:
            # Skip non-pending items
            if item.status != ChecklistItemStatus.PENDING:
                continue
            
            # Check dependencies
            deps_satisfied = all(
                any(dep_item.id == dep_id and 
                   dep_item.status == ChecklistItemStatus.COMPLETED
                   for dep_item in self.current_checklist.items)
                for dep_id in item.dependencies
            )
            
            if deps_satisfied:
                return item
        
        return None
    
    def _enhance_tool_parameters(self, tool_name: str, parameters: Dict) -> Dict:
        """Enhance tool parameters with context"""
        
        enhanced = parameters.copy()
        
        if self.current_checklist:
            # Add project context
            enhanced["project_name"] = self.current_checklist.project_name
            enhanced["project_type"] = self.current_checklist.project_type
            enhanced["session_id"] = self.session_id
        
        # Tool-specific enhancements
        if tool_name == "create_repository" and "name" not in enhanced:
            enhanced["name"] = self.current_checklist.project_name if self.current_checklist else "unnamed"
        
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
            "checklist": self.current_checklist,
            "react_history": self.react_history,
            "step_counter": self.step_counter
        }
        
        await self.state_manager.save_state(self.session_id, state_data)
    
    def _restore_from_state(self, state_data: Dict):
        """Restore agent from saved state"""
        
        self.context = state_data.get("context", {})
        self.current_checklist = state_data.get("checklist")
        self.react_history = state_data.get("react_history", [])
        self.step_counter = state_data.get("step_counter", 0)
        
        self.logger.info("state_restored",
                        session_id=self.session_id,
                        step=self.step_counter)
    
    async def _mark_current_item_failed(self, error: str):
        """Mark current in-progress item as failed"""
        
        if not self.current_checklist:
            return
        
        for item in self.current_checklist.items:
            if item.status == ChecklistItemStatus.IN_PROGRESS:
                await self.checklist_manager.update_item_status(
                    self.current_checklist,
                    item.id,
                    ChecklistItemStatus.FAILED,
                    result=f"Failed: {error}",
                    error_details={"error": error}
                )
                break

# ==================== SYSTEM PROMPTS ====================

IDP_COPILOT_SYSTEM_PROMPT = """You are an advanced Internal Developer Platform (IDP) Copilot Agent with production-grade capabilities.

## CORE RESPONSIBILITIES:
1. Analyze developer requests for creating development projects (microservices, libraries, applications)
2. Create detailed, executable checklists with proper dependency management
3. Execute automation tools with retry logic and error handling
4. Maintain persistent state for workflow recovery
5. Provide real-time progress updates and handle failures gracefully

## WORKFLOW PRINCIPLES:
- **Reliability First**: Always handle errors gracefully and provide recovery options
- **Transparency**: Keep users informed of progress and any issues
- **Automation**: Maximize automation while maintaining quality
- **Best Practices**: Apply industry standards and organizational guidelines
- **Idempotency**: Ensure operations can be safely retried

## PROJECT TYPE WORKFLOWS:

### Microservice:
1. Validate project requirements and naming
2. Search knowledge base for guidelines
3. Create Git repository with branch protection
4. Apply microservice template
5. Configure CI/CD pipeline
6. Set up monitoring and logging
7. Create Kubernetes manifests
8. Deploy to staging environment
9. Run integration tests
10. Generate documentation

### Library:
1. Validate library name and purpose
2. Create repository with library template
3. Set up package configuration
4. Configure testing framework
5. Set up publishing pipeline
6. Create example usage
7. Generate API documentation

### Frontend Application:
1. Validate application requirements
2. Create repository
3. Apply frontend framework template
4. Set up build system
5. Configure CDN and deployment
6. Set up E2E testing
7. Create staging deployment

## DECISION FRAMEWORK:
- Missing critical information → ASK_USER with specific questions
- No checklist exists → CREATE_CHECKLIST based on project type
- Checklist has executable items → TOOL_CALL for next item
- Tool execution failed → ERROR_RECOVERY with retry or skip
- All items complete/skipped → COMPLETE with summary

## ERROR HANDLING STRATEGY:
1. **Retry with backoff**: For transient failures (network, timeouts)
2. **Parameter adjustment**: For validation failures (invalid names, missing params)
3. **Skip and continue**: For non-critical failures with blocked dependencies
4. **Escalate to user**: For critical failures requiring manual intervention

## TOOL INTERACTION:
- Always validate tool parameters before execution
- Use appropriate timeouts based on operation type
- Collect structured feedback for continuous improvement
- Update checklist status after every tool execution

Remember: You are a production system. Prioritize reliability, observability, and user experience."""

# ==================== MAIN EXECUTION ====================

async def main():
    """Main execution function"""
    
    # Start Prometheus metrics server
    start_http_server(8070)
    
    # Initialize LLM provider with fallback to mock if no API key
    openai_key = os.getenv("OPENAI_API_KEY")
    
    # For demo, using a mock provider if no key present
    class MockLLMProvider(LLMProvider):
        async def generate_response(self, prompt: str, **kwargs) -> str:
            await asyncio.sleep(0.2)
            return "I should analyze the request and create a microservice workflow."
        
        async def generate_structured_response(self, prompt: str, response_model: BaseModel, **kwargs):
            await asyncio.sleep(0.2)
            if response_model == ActionDecision:
                return ActionDecision(
                    action_type=ActionType.UPDATE_CHECKLIST,
                    action_name="create_checklist",
                    parameters={},
                    reasoning="Need to create initial checklist",
                    confidence=0.9
                )
            if response_model == ProjectInfo:
                return ProjectInfo(
                    project_name="payment-processor",
                    project_type="microservice",
                    programming_language="python"
                )
            if response_model == ChecklistGeneration:
                return ChecklistGeneration(
                    items=[
                        {"title": "Create Repository", "description": "Create GitHub repository", "dependencies": [], "tool": "create_repository"},
                        {"title": "Apply Template", "description": "Apply microservice template", "dependencies": ["1"], "tool": "apply_template"},
                        {"title": "Setup CI/CD", "description": "Configure pipeline", "dependencies": ["2"], "tool": "setup_cicd_pipeline"},
                    ],
                    estimated_duration=30,
                    risk_level="low",
                )
    
    if openai_key:
        llm_provider = OpenAIProvider(api_key=openai_key)
    else:
        llm_provider = MockLLMProvider()
    
    # Initialize agent
    agent = ProductionReActAgent(
        system_prompt=IDP_COPILOT_SYSTEM_PROMPT,
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
    print(f"Workflows Started: {workflow_counter._value._value}")
    print(f"Workflows Completed: {workflow_success._value._value}")
    print(f"Workflows Failed: {workflow_failed._value._value}")

if __name__ == "__main__":
    asyncio.run(main())