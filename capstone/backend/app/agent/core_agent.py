"""Core ADK-native agent for IDP Copilot."""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional

from app.agent.events import (
    AgentEvent, AgentEventType, create_agent_event, AgentToolCall, 
    AgentToolResult, AgentThinking, AgentClarification, AgentMessage
)
from app.agent.memory import PersistentMemory, AgentInteraction
from app.mcp.toolsets.git_operations import GitOperationsToolset
from app.mcp.toolsets.filesystem_ops import FilesystemToolset
from app.mcp.toolsets.template_engine import TemplateEngineToolset
from app.mcp.toolsets.cicd_generator import CICDToolset
from app.rag import chroma_store
from app.settings import settings


class IDPAgent:
    """Core ADK-native agent for IDP Copilot.
    
    This agent serves as the primary conversation controller and orchestrator
    for the IDP Copilot system. It manages conversation state, executes tools,
    and provides intelligent responses for service creation workflows.
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.memory = PersistentMemory(db_path)
        
        # Initialize toolsets
        self.git_ops = GitOperationsToolset()
        self.filesystem = FilesystemToolset()
        self.template_engine = TemplateEngineToolset()
        self.cicd_generator = CICDToolset()
        
        # ADK agent instance (lazy loaded)
        self._adk_agent = None
        self._adk_available = self._check_adk_availability()
        
        # System instruction for the agent
        self.system_instruction = self._build_system_instruction()
    
    def _check_adk_availability(self) -> bool:
        """Check if Google ADK is available."""
        try:
            __import__("google.adk")
            return True
        except ImportError:
            return False
    
    def _build_system_instruction(self) -> str:
        """Build comprehensive system instruction for the ADK agent."""
        return """You are an expert DevOps engineer and IDP (Internal Developer Platform) assistant. 
Your role is to help developers create software services quickly and according to best practices.

AVAILABLE TOOLS:
- git_ops: Create repositories, manage branches, commits, and repository operations
- filesystem: Read/write files, manage directory structures, copy files
- template_engine: Generate language-specific scaffolding (Go, Python, Node.js, etc.)
- cicd_generator: Create CI/CD pipelines (GitHub Actions, GitLab CI, Azure Pipelines)
- rag_search: Query company guidelines and best practices (when available)

CORE WORKFLOW:
1. UNDERSTAND user requirements through clarifying questions
2. SEARCH company guidelines for relevant standards and apply them
3. PLAN step-by-step service creation approach based on guidelines
4. EXECUTE tools in logical sequence with clear progress updates
5. VERIFY results and adapt plan if needed

CLARIFICATION RULES:
- Always ask for missing critical information before proceeding
- Required fields: repository_name, language, framework (if applicable)
- Optional but recommended: deployment_target, features, ci_provider

EXECUTION PRINCIPLES:
- Explain your reasoning before taking actions
- Show progress clearly with status updates
- Handle tool failures gracefully with alternative approaches
- Ask for confirmation before destructive operations
- Provide helpful error messages and next steps

RESPONSE FORMAT:
- Use clear, actionable language
- Provide progress updates during tool execution
- Explain what each tool does and why you're using it
- Show file structures and configurations clearly
- End with next steps or completion summary

Remember: You are creating production-ready services that follow industry best practices.
Focus on creating maintainable, testable, and deployable code structures."""
    
    def _get_adk_agent(self):
        """Get or create ADK agent instance."""
        if not self._adk_available:
            return None
            
        if self._adk_agent is None:
            try:
                from google.adk.agents import Agent
                
                # Collect MCP toolsets
                mcp_tools = []
                for toolset in [self.git_ops, self.filesystem, self.template_engine, self.cicd_generator]:
                    mcp_tool = toolset.create_mcp_toolset()
                    if mcp_tool:
                        mcp_tools.append(mcp_tool)
                
                self._adk_agent = Agent(
                    name="idp_copilot",
                    model=getattr(settings, "adk_model", "gemini-2.0-flash"),
                    instruction=self.system_instruction,
                    description="IDP Copilot agent for automated service creation",
                    tools=mcp_tools
                )
            except Exception as e:
                print(f"Failed to initialize ADK agent: {e}")
                return None
        
        return self._adk_agent
    
    async def process_message(
        self, 
        conversation_id: str, 
        message: str,
        run_id: Optional[str] = None
    ) -> AsyncIterator[AgentEvent]:
        """Process a user message and stream agent responses.
        
        Args:
            conversation_id: Unique conversation identifier
            message: User message to process
            run_id: Optional run identifier for tracking
            
        Yields:
            AgentEvent: Stream of agent events
        """
        if run_id is None:
            run_id = f"run_{uuid.uuid4().hex[:8]}"
        
        # Load conversation context
        try:
            context = await self.memory.load_context(conversation_id)
            context_text = self.memory.format_context_for_agent(context)
        except Exception as e:
            context_text = ""
            yield create_agent_event(
                AgentEventType.ERROR,
                f"Failed to load conversation context: {e}",
                run_id=run_id,
                conversation_id=conversation_id
            )
        
        # Check if we need clarification first
        clarification_result = self._check_for_clarifications(message)
        if clarification_result["needs_clarification"]:
            yield AgentClarification(
                id=f"clarification_{uuid.uuid4().hex[:8]}",
                message="I need some additional information to proceed",
                question=clarification_result["question"],
                required_fields=clarification_result["missing_fields"],
                context=clarification_result.get("context", {}),
                run_id=run_id,
                conversation_id=conversation_id
            )
            return
        
        # Process with ADK if available, otherwise use fallback
        if self._adk_available:
            async for event in self._process_with_adk(conversation_id, message, context_text, run_id):
                yield event
        else:
            async for event in self._process_with_fallback(conversation_id, message, run_id):
                yield event
    
    async def handle_clarification(
        self, 
        conversation_id: str, 
        response: str,
        original_message: str,
        run_id: Optional[str] = None
    ) -> AsyncIterator[AgentEvent]:
        """Handle clarification response and continue conversation.
        
        Args:
            conversation_id: Unique conversation identifier
            response: User's clarification response
            original_message: Original user message
            run_id: Optional run identifier for tracking
            
        Yields:
            AgentEvent: Stream of agent events
        """
        if run_id is None:
            run_id = f"run_{uuid.uuid4().hex[:8]}"
        
        # Combine original message with clarification
        combined_message = f"Original request: {original_message}\nClarification: {response}"
        
        # Process the clarified message
        async for event in self.process_message(conversation_id, combined_message, run_id):
            yield event
    
    async def _process_with_adk(
        self, 
        conversation_id: str, 
        message: str, 
        context: str,
        run_id: str
    ) -> AsyncIterator[AgentEvent]:
        """Process message using ADK agent."""
        agent = self._get_adk_agent()
        if not agent:
            async for event in self._process_with_fallback(conversation_id, message, run_id):
                yield event
            return
        
        yield create_agent_event(
            AgentEventType.THINKING,
            "Analyzing your request...",
            run_id=run_id,
            conversation_id=conversation_id,
            reasoning="Using ADK agent to process service creation request"
        )
        
        try:
            # Prepare full context for agent
            full_prompt = f"""
{context}

## Current User Request
{message}

Please analyze this request and create the appropriate software service. 
Follow the workflow outlined in your instructions.
"""
            
            # Execute ADK agent
            result = None
            for method_name in ("run", "execute", "invoke"):
                method = getattr(agent, method_name, None)
                if callable(method):
                    result = method(full_prompt)
                    break
            
            if result is not None:
                # Parse and stream ADK response
                response_text = str(result)
                
                yield AgentMessage(
                    id=f"response_{uuid.uuid4().hex[:8]}",
                    message="Processing complete",
                    content=response_text,
                    run_id=run_id,
                    conversation_id=conversation_id
                )
                
                # Store interaction in memory
                interaction = AgentInteraction(
                    id=f"interaction_{uuid.uuid4().hex[:8]}",
                    conversation_id=conversation_id,
                    user_message=message,
                    agent_response=response_text,
                    tool_calls=[],  # TODO: Extract from ADK response
                    tool_results=[],  # TODO: Extract from ADK response
                    reasoning="ADK agent processing",
                    timestamp=time.time()
                )
                
                await self.memory.store_interaction(conversation_id, interaction)
                
            else:
                yield create_agent_event(
                    AgentEventType.ERROR,
                    "ADK agent method not found",
                    run_id=run_id,
                    conversation_id=conversation_id
                )
                
        except Exception as e:
            yield create_agent_event(
                AgentEventType.ERROR,
                f"ADK processing failed: {e}",
                run_id=run_id,
                conversation_id=conversation_id
            )
            
            # Fallback to deterministic processing
            async for event in self._process_with_fallback(conversation_id, message, run_id):
                yield event
    
    async def _process_with_fallback(
        self, 
        conversation_id: str, 
        message: str,
        run_id: str
    ) -> AsyncIterator[AgentEvent]:
        """Fallback processing without ADK."""
        yield create_agent_event(
            AgentEventType.THINKING,
            "Processing with built-in logic...",
            run_id=run_id,
            conversation_id=conversation_id,
            reasoning="ADK not available, using fallback processing"
        )
        
        # Extract parameters from message
        params = self._extract_service_parameters(message)
        
        if not params.get("repository_name"):
            yield AgentClarification(
                id=f"clarification_{uuid.uuid4().hex[:8]}",
                message="I need a repository name to create the service",
                question="What should the repository be named?",
                required_fields=["repository_name"],
                run_id=run_id,
                conversation_id=conversation_id
            )
            return
        
        # Create service using deterministic workflow
        try:
            async for event in self._execute_service_creation_workflow(params, run_id, conversation_id):
                yield event
        except Exception as e:
            yield create_agent_event(
                AgentEventType.ERROR,
                f"Service creation failed: {e}",
                run_id=run_id,
                conversation_id=conversation_id
            )
    
    async def _execute_service_creation_workflow(
        self, 
        params: Dict[str, Any],
        run_id: str,
        conversation_id: str
    ) -> AsyncIterator[AgentEvent]:
        """Execute the service creation workflow using toolsets."""
        
        repo_name = params["repository_name"]
        language = params.get("language", "go")
        framework = params.get("framework")
        features = params.get("features", ["testing", "linting"])
        ci_provider = params.get("ci_provider", "github-actions")
        
        yield create_agent_event(
            AgentEventType.MESSAGE,
            f"Creating {language} service '{repo_name}' with {framework or 'default'} framework",
            run_id=run_id,
            conversation_id=conversation_id
        )
        
        # Step 0: Search for company guidelines
        yield create_agent_event(
            AgentEventType.THINKING,
            f"Searching company guidelines for {language} development standards...",
            run_id=run_id,
            conversation_id=conversation_id
        )
        
        guidelines_query = f"{language} service standards development guidelines"
        guidelines = await self._search_company_guidelines(guidelines_query, 5)
        guidelines_summary = self._extract_guidelines_summary(guidelines, language)
        
        # Apply guidelines to parameters
        original_params = params.copy()
        params = self._apply_guidelines_to_params(params, guidelines)
        
        if guidelines:
            changes = []
            if params.get("framework") != original_params.get("framework"):
                changes.append(f"framework: {params['framework']}")
            if params.get("ci_provider") != original_params.get("ci_provider"):
                changes.append(f"CI/CD: {params['ci_provider']}")
            if set(params.get("features", [])) != set(original_params.get("features", [])):
                new_features = set(params["features"]) - set(original_params.get("features", []))
                if new_features:
                    changes.append(f"added features: {', '.join(new_features)}")
            
            changes_text = f" (Applied: {', '.join(changes)})" if changes else ""
            yield create_agent_event(
                AgentEventType.MESSAGE,
                f"Found {len(guidelines)} relevant company guidelines. Applying standards...{changes_text}",
                run_id=run_id,
                conversation_id=conversation_id,
                data={"guidelines_summary": guidelines_summary}
            )
        else:
            yield create_agent_event(
                AgentEventType.MESSAGE,
                "No company guidelines found. Using industry best practices.",
                run_id=run_id,
                conversation_id=conversation_id
            )
        
        # Update variables with guidelines-adjusted values
        framework = params.get("framework")
        features = params.get("features", ["testing", "linting"])
        ci_provider = params.get("ci_provider", "github-actions")
        
        # Step 1: Initialize Git repository
        yield AgentToolCall(
            id=f"tool_call_{uuid.uuid4().hex[:8]}",
            message="Initializing Git repository",
            tool_name="git_ops.init_repository",
            parameters={"repo_name": repo_name, "description": f"Auto-generated {language} service"},
            run_id=run_id,
            conversation_id=conversation_id
        )
        
        git_result = self.git_ops.init_repository(repo_name, f"Auto-generated {language} service")
        
        yield AgentToolResult(
            id=f"tool_result_{uuid.uuid4().hex[:8]}",
            message="Git repository initialization complete",
            tool_name="git_ops.init_repository",
            result=git_result,
            success=git_result.get("success", False),
            error=git_result.get("error"),
            run_id=run_id,
            conversation_id=conversation_id
        )
        
        if not git_result.get("success"):
            return
        
        # Step 2: Generate template structure
        yield AgentToolCall(
            id=f"tool_call_{uuid.uuid4().hex[:8]}",
            message=f"Generating {language} service template",
            tool_name=f"template_engine.generate_{language}_service",
            parameters={"service_name": repo_name, "framework": framework, "features": features},
            run_id=run_id,
            conversation_id=conversation_id
        )
        
        if language.lower() == "go":
            template_result = self.template_engine.generate_go_service(repo_name, framework or "gin", features)
        elif language.lower() == "python":
            template_result = self.template_engine.generate_python_service(repo_name, framework or "fastapi", features)
        elif language.lower() in ["node", "typescript"]:
            template_result = self.template_engine.generate_node_service(repo_name, framework or "express", language, features)
        else:
            template_result = {"success": False, "error": f"Unsupported language: {language}"}
        
        yield AgentToolResult(
            id=f"tool_result_{uuid.uuid4().hex[:8]}",
            message="Template generation complete",
            tool_name=f"template_engine.generate_{language}_service",
            result=template_result,
            success=template_result.get("success", False),
            error=template_result.get("error"),
            run_id=run_id,
            conversation_id=conversation_id
        )
        
        if not template_result.get("success"):
            return
        
        # Step 3: Create file structure
        if "structure" in template_result:
            yield AgentToolCall(
                id=f"tool_call_{uuid.uuid4().hex[:8]}",
                message="Creating project file structure",
                tool_name="filesystem.create_directory_structure",
                parameters={"base_path": repo_name, "structure": template_result["structure"]},
                run_id=run_id,
                conversation_id=conversation_id
            )
            
            fs_result = self.filesystem.create_directory_structure(repo_name, template_result["structure"])
            
            yield AgentToolResult(
                id=f"tool_result_{uuid.uuid4().hex[:8]}",
                message="File structure creation complete",
                tool_name="filesystem.create_directory_structure",
                result=fs_result,
                success=fs_result.get("success", False),
                error=fs_result.get("error"),
                run_id=run_id,
                conversation_id=conversation_id
            )
        
        # Step 4: Generate CI/CD pipeline
        yield AgentToolCall(
            id=f"tool_call_{uuid.uuid4().hex[:8]}",
            message=f"Generating {ci_provider} CI/CD pipeline",
            tool_name="cicd_generator.generate_pipeline",
            parameters={"language": language, "framework": framework, "provider": ci_provider},
            run_id=run_id,
            conversation_id=conversation_id
        )
        
        if ci_provider == "github-actions":
            cicd_result = self.cicd_generator.generate_github_actions_workflow(language, framework, features)
        elif ci_provider == "gitlab-ci":
            cicd_result = self.cicd_generator.generate_gitlab_ci_config(language, framework, features)
        elif ci_provider == "azure-pipelines":
            cicd_result = self.cicd_generator.generate_azure_pipelines_config(language, framework, features)
        else:
            cicd_result = {"success": False, "error": f"Unsupported CI provider: {ci_provider}"}
        
        yield AgentToolResult(
            id=f"tool_result_{uuid.uuid4().hex[:8]}",
            message="CI/CD pipeline generation complete",
            tool_name="cicd_generator.generate_pipeline",
            result=cicd_result,
            success=cicd_result.get("success", False),
            error=cicd_result.get("error"),
            run_id=run_id,
            conversation_id=conversation_id
        )
        
        # Step 5: Create CI/CD files if successful
        if cicd_result.get("success") and "files" in cicd_result:
            for file_path, content in cicd_result["files"].items():
                full_path = f"{repo_name}/{file_path}"
                self.filesystem.create_file(full_path, content, overwrite=True)
        
        # Step 6: Commit initial structure
        yield AgentToolCall(
            id=f"tool_call_{uuid.uuid4().hex[:8]}",
            message="Committing initial project structure",
            tool_name="git_ops.commit_changes",
            parameters={"repo_path": repo_name, "message": "Initial project structure and CI/CD setup"},
            run_id=run_id,
            conversation_id=conversation_id
        )
        
        commit_result = self.git_ops.commit_changes(repo_name, "Initial project structure and CI/CD setup")
        
        yield AgentToolResult(
            id=f"tool_result_{uuid.uuid4().hex[:8]}",
            message="Initial commit complete",
            tool_name="git_ops.commit_changes",
            result=commit_result,
            success=commit_result.get("success", False),
            error=commit_result.get("error"),
            run_id=run_id,
            conversation_id=conversation_id
        )
        
        # Final completion message
        yield create_agent_event(
            AgentEventType.COMPLETED,
            f"Service '{repo_name}' created successfully! Ready for development.",
            run_id=run_id,
            conversation_id=conversation_id
        )
    
    def _check_for_clarifications(self, message: str) -> Dict[str, Any]:
        """Check if message requires clarification."""
        missing_fields = []
        context = {}
        
        # Check for repository name
        if not self._extract_repo_name(message):
            missing_fields.append("repository_name")
        
        # Check for language
        if not self._extract_language(message):
            missing_fields.append("language")
        
        if missing_fields:
            return {
                "needs_clarification": True,
                "missing_fields": missing_fields,
                "question": "I need some additional information: " + ", ".join(missing_fields),
                "context": context
            }
        
        return {"needs_clarification": False}
    
    def _extract_service_parameters(self, message: str) -> Dict[str, Any]:
        """Extract service creation parameters from message."""
        return {
            "repository_name": self._extract_repo_name(message),
            "language": self._extract_language(message),
            "framework": self._extract_framework(message),
            "features": self._extract_features(message),
            "ci_provider": self._extract_ci_provider(message)
        }
    
    def _extract_repo_name(self, message: str) -> Optional[str]:
        """Extract repository name from message."""
        import re
        
        # More specific patterns for different phrasings
        patterns = [
            r'repository\s+called\s+([a-z0-9][a-z0-9-_]*)',
            r'repo\s+called\s+([a-z0-9][a-z0-9-_]*)',
            r'repository\s+name\s*:\s*([a-z0-9][a-z0-9-_]*)',
            r'repo\s+name\s*:\s*([a-z0-9][a-z0-9-_]*)',
            r'name\s+(?:the\s+)?repo\s+([a-z0-9][a-z0-9-_]*)',
            r'called\s+([a-z0-9][a-z0-9-_]*)',
            # Look for obvious repo names with hyphens
            r'\b([a-z][a-z0-9]*(?:-[a-z0-9]+)+)\b'
        ]
        
        message_lower = message.lower()
        
        for pattern in patterns:
            match = re.search(pattern, message_lower)
            if match:
                candidate = match.group(1)
                # Filter out common words that aren't repo names
                if candidate not in {'service', 'api', 'app', 'application', 'project', 'repo', 'repository'}:
                    return candidate
        
        return None
    
    def _extract_language(self, message: str) -> Optional[str]:
        """Extract programming language from message."""
        languages = ["go", "python", "node", "typescript", "java", "rust", "csharp"]
        message_lower = message.lower()
        
        for lang in languages:
            if lang in message_lower:
                return lang
        
        # Check for alternative names
        if "javascript" in message_lower or "js" in message_lower:
            return "node"
        if "ts" in message_lower:
            return "typescript"
        if "c#" in message_lower or ".net" in message_lower:
            return "csharp"
        
        return None
    
    def _extract_framework(self, message: str) -> Optional[str]:
        """Extract framework from message."""
        frameworks = ["gin", "echo", "fastapi", "flask", "django", "express", "nestjs", "spring"]
        message_lower = message.lower()
        
        for framework in frameworks:
            if framework in message_lower:
                return framework
        
        return None
    
    def _extract_features(self, message: str) -> List[str]:
        """Extract features from message."""
        features = []
        message_lower = message.lower()
        
        feature_mapping = {
            "test": "testing",
            "tests": "testing",
            "testing": "testing",
            "lint": "linting",
            "linting": "linting",
            "security": "security",
            "metrics": "metrics",
            "monitoring": "metrics",
            "database": "database",
            "db": "database"
        }
        
        for keyword, feature in feature_mapping.items():
            if keyword in message_lower and feature not in features:
                features.append(feature)
        
        # Default features if none specified
        if not features:
            features = ["testing", "linting"]
        
        return features
    
    def _extract_ci_provider(self, message: str) -> Optional[str]:
        """Extract CI/CD provider from message."""
        message_lower = message.lower()
        
        if "github" in message_lower or "actions" in message_lower:
            return "github-actions"
        if "gitlab" in message_lower:
            return "gitlab-ci"
        if "azure" in message_lower:
            return "azure-pipelines"
        if "circleci" in message_lower or "circle" in message_lower:
            return "circleci"
        
        return "github-actions"  # Default
    
    async def _search_company_guidelines(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Search company guidelines using RAG."""
        try:
            if chroma_store.is_enabled():
                results = chroma_store.query(query, max_results)
                return [{"path": path, "content": snippet, "source": "rag"} for path, snippet in results]
            else:
                # Fallback to simple search if ChromaDB not available
                from app.rag.simple_store import search_documents
                results = search_documents(settings.documents_root, query, max_results)
                return [{"path": path, "content": snippet, "source": "simple"} for path, snippet in results]
        except Exception as e:
            # Return empty results on error, don't break the workflow
            return []
    
    def _extract_guidelines_summary(self, guidelines: List[Dict[str, Any]], language: str) -> str:
        """Extract relevant guidelines for the specified language."""
        if not guidelines:
            return "No specific company guidelines found. Using industry best practices."
        
        language_lower = language.lower()
        relevant_guidelines = []
        
        for guideline in guidelines:
            content = guideline["content"].lower()
            path = guideline["path"].lower()
            
            # Check if guideline is relevant to the language
            if (language_lower in content or language_lower in path or
                (language_lower == "python" and "fastapi" in content) or
                (language_lower == "go" and "gin" in content)):
                relevant_guidelines.append(guideline["content"])
        
        if relevant_guidelines:
            return f"Found {len(relevant_guidelines)} relevant company guidelines:\n\n" + "\n---\n".join(relevant_guidelines[:3])
        else:
            return f"Found {len(guidelines)} general guidelines that may apply."
    
    def _apply_guidelines_to_params(self, params: Dict[str, Any], guidelines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Apply company guidelines to service parameters."""
        if not guidelines:
            return params
        
        language = params.get("language", "").lower()
        updated_params = params.copy()
        
        # Extract framework preferences from guidelines
        if not params.get("framework"):
            for guideline in guidelines:
                content = guideline["content"].lower()
                if language == "python" and "fastapi" in content:
                    updated_params["framework"] = "fastapi"
                    break
                elif language == "go" and "gin" in content:
                    updated_params["framework"] = "gin"
                    break
                elif language in ["node", "typescript"] and "express" in content:
                    updated_params["framework"] = "express"
                    break
        
        # Extract CI/CD preferences from guidelines
        if not params.get("ci_provider") or params["ci_provider"] == "github-actions":
            for guideline in guidelines:
                content = guideline["content"].lower()
                if "github actions" in content:
                    updated_params["ci_provider"] = "github-actions"
                    break
                elif "gitlab" in content:
                    updated_params["ci_provider"] = "gitlab-ci"
                    break
                elif "azure pipelines" in content:
                    updated_params["ci_provider"] = "azure-pipelines"
                    break
        
        # Extract additional features from guidelines
        features = set(params.get("features", ["testing", "linting"]))
        for guideline in guidelines:
            content = guideline["content"].lower()
            if "security" in content:
                features.add("security")
            if "monitoring" in content or "metrics" in content:
                features.add("metrics")
            if "database" in content:
                features.add("database")
        
        updated_params["features"] = list(features)
        
        return updated_params