"""
HybridAgent - Production-Ready AI Agent with Tool Execution
Combines specialized tools, code execution, and intelligent orchestration
"""

import os
import json
import asyncio
import subprocess
import inspect
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from abc import ABC, abstractmethod
from datetime import datetime
import logging
import re
from collections import defaultdict
import urllib.request
import urllib.error

# Optional imports (install if needed)
try:
    import aiohttp
except ImportError:
    aiohttp = None
    print("Warning: aiohttp not installed. Web tools will be limited.")

try:
    import openai
except ImportError:
    raise ImportError("openai package required. Install with: pip install openai")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================
# BASE TOOL INTERFACE
# ============================================

class Tool(ABC):
    """Base class for all tools"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        pass
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        """Override to provide custom parameter schema for OpenAI function calling"""
        return self._generate_schema_from_signature()
    
    def _generate_schema_from_signature(self) -> Dict[str, Any]:
        """Auto-generate parameter schema from execute method signature"""
        sig = inspect.signature(self.execute)
        properties = {}
        required = []
        
        for param_name, param in sig.parameters.items():
            if param_name in ['self', 'kwargs']:
                continue
            
            # Determine parameter type
            param_type = "string"  # Default
            param_desc = f"Parameter {param_name}"
            
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == int:
                    param_type = "integer"
                elif param.annotation == bool:
                    param_type = "boolean"
                elif param.annotation == float:
                    param_type = "number"
                elif param.annotation == Dict or param.annotation == dict:
                    param_type = "object"
                elif param.annotation == List or param.annotation == list:
                    param_type = "array"
            
            properties[param_name] = {
                "type": param_type,
                "description": param_desc
            }
            
            # Check if required
            if param.default == inspect.Parameter.empty:
                required.append(param_name)
        
        return {
            "type": "object",
            "properties": properties,
            "required": required
        }
    
    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        pass
    
    def validate_params(self, **kwargs) -> Tuple[bool, Optional[str]]:
        """Validate parameters before execution"""
        sig = inspect.signature(self.execute)
        
        for param_name, param in sig.parameters.items():
            if param_name in ['self', 'kwargs']:
                continue
            
            if param.default == inspect.Parameter.empty and param_name not in kwargs:
                return False, f"Missing required parameter: {param_name}"
        
        return True, None

# ============================================
# FILE SYSTEM TOOLS
# ============================================

class FileReadTool(Tool):
    """Safe file reading with size limits"""
    
    @property
    def name(self) -> str:
        return "file_read"
    
    @property
    def description(self) -> str:
        return "Read file contents safely with size limits and encoding detection"
    
    async def execute(self, path: str, encoding: str = "utf-8", max_size_mb: int = 10, **kwargs) -> Dict[str, Any]:
        try:
            file_path = Path(path)
            
            if not file_path.exists():
                return {"success": False, "error": f"File not found: {path}"}
            
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            if file_size_mb > max_size_mb:
                return {"success": False, "error": f"File too large: {file_size_mb:.2f}MB > {max_size_mb}MB"}
            
            content = file_path.read_text(encoding=encoding)
            return {
                "success": True,
                "content": content,
                "size": len(content),
                "path": str(file_path.absolute())
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

class FileWriteTool(Tool):
    """Safe file writing with backup option"""
    
    @property
    def name(self) -> str:
        return "file_write"
    
    @property
    def description(self) -> str:
        return "Write content to file with backup and safety checks"
    
    async def execute(self, path: str, content: str, backup: bool = True, **kwargs) -> Dict[str, Any]:
        try:
            file_path = Path(path)
            
            # Backup existing file
            if backup and file_path.exists():
                backup_path = file_path.with_suffix(file_path.suffix + ".bak")
                backup_path.write_text(file_path.read_text())
            
            # Create parent directories
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write content
            file_path.write_text(content)
            
            return {
                "success": True,
                "path": str(file_path.absolute()),
                "size": len(content),
                "backed_up": backup and file_path.exists()
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

# ============================================
# GIT TOOL
# ============================================

class GitTool(Tool):
    """Comprehensive Git operations"""
    
    @property
    def name(self) -> str:
        return "git"
    
    @property
    def description(self) -> str:
        return "Execute git operations (init, add, commit, push, status, clone, etc.)"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["init", "add", "commit", "push", "status", "clone", "remote"],
                    "description": "Git operation to perform"
                },
                "repo_path": {
                    "type": "string",
                    "description": "Repository path (default: current directory)"
                },
                "message": {
                    "type": "string",
                    "description": "Commit message (for commit operation)"
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Files to add (for add operation)"
                },
                "url": {
                    "type": "string",
                    "description": "Remote URL (for remote/clone operations)"
                },
                "branch": {
                    "type": "string",
                    "description": "Branch name"
                }
            },
            "required": ["operation"]
        }
    
    async def execute(self, operation: str, repo_path: str = ".", **kwargs) -> Dict[str, Any]:
        try:
            repo_path = Path(repo_path)
            
            # Build command based on operation
            if operation == "init":
                cmd = ["git", "init", "-b", kwargs.get("branch", "main")]
            elif operation == "add":
                files = kwargs.get("files", ["."])
                cmd = ["git", "add"] + files
            elif operation == "commit":
                message = kwargs.get("message", "Commit via HybridAgent")
                cmd = ["git", "commit", "-m", message]
            elif operation == "push":
                remote = kwargs.get("remote", "origin")
                branch = kwargs.get("branch", "main")
                cmd = ["git", "push", "-u", remote, branch]
            elif operation == "status":
                cmd = ["git", "status", "--short"]
            elif operation == "clone":
                url = kwargs.get("url")
                if not url:
                    return {"success": False, "error": "URL required for clone"}
                cmd = ["git", "clone", url, str(repo_path)]
            elif operation == "remote":
                action = kwargs.get("action", "add")
                if action == "add":
                    cmd = ["git", "remote", "add", kwargs.get("name", "origin"), kwargs["url"]]
                else:
                    cmd = ["git", "remote", "-v"]
            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}
            
            # Execute command
            result = subprocess.run(
                cmd,
                cwd=repo_path if operation != "clone" else ".",
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None,
                "command": " ".join(cmd)
            }
            
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}

# ============================================
# SHELL TOOL
# ============================================

class ShellTool(Tool):
    """Execute shell commands with safety limits"""
    
    @property
    def name(self) -> str:
        return "shell"
    
    @property
    def description(self) -> str:
        return "Execute shell commands with timeout and safety limits"
    
    async def execute(self, command: str, timeout: int = 30, cwd: str = None, **kwargs) -> Dict[str, Any]:
        try:
            # Safety check - block dangerous commands
            dangerous_patterns = [
                "rm -rf /", "rm -rf /*", 
                "dd if=/dev/zero", "dd if=/dev/random",
                "format c:", "del /f /s /q",
                ":(){ :|:& };:",  # Fork bomb
                "> /dev/sda",
                "mkfs.",
            ]
            
            if any(pattern in command.lower() for pattern in dangerous_patterns):
                return {"success": False, "error": "Command blocked for safety reasons"}
            
            # Execute command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
                
                return {
                    "success": process.returncode == 0,
                    "stdout": stdout.decode() if stdout else "",
                    "stderr": stderr.decode() if stderr else "",
                    "returncode": process.returncode,
                    "command": command
                }
            except asyncio.TimeoutError:
                process.kill()
                return {"success": False, "error": f"Command timed out after {timeout}s"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}

# ============================================
# PYTHON CODE EXECUTION TOOL
# ============================================

class PythonTool(Tool):
    """Execute Python code for complex operations"""
    
    @property
    def name(self) -> str:
        return "python"
    
    @property
    def description(self) -> str:
        return "Execute Python code for complex logic, data processing, and custom operations. Code should set 'result' variable."
    
    async def execute(self, code: str, context: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """
        Execute Python code in controlled namespace.
        Code has access to standard libraries and must set 'result' variable.
        """
        
        # Create safe namespace
        safe_namespace = {
            "__builtins__": {
                # Basic functions
                "print": print, "len": len, "range": range, "enumerate": enumerate,
                "str": str, "int": int, "float": float, "bool": bool,
                "list": list, "dict": dict, "set": set, "tuple": tuple,
                "sum": sum, "min": min, "max": max, "abs": abs,
                "round": round, "sorted": sorted, "reversed": reversed,
                "zip": zip, "map": map, "filter": filter,
                "any": any, "all": all, "isinstance": isinstance,
                "open": open,  # Use with caution
                "__import__": __import__,
            },
            "context": context or {},
        }
        
        # Import common libraries
        import_code = """
import os, sys, json, re, pathlib, shutil
import subprocess, datetime, time, random
import base64, hashlib, tempfile, csv
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
"""
        
        try:
            # Execute imports
            exec(import_code, safe_namespace)
            
            # Execute user code
            exec(code, safe_namespace)
            
            # Extract result
            result_value = safe_namespace.get('result', None)
            
            # Get all user-defined variables
            user_vars = {
                k: v for k, v in safe_namespace.items()
                if not k.startswith('_') 
                and k not in ['os', 'sys', 'json', 're', 'pathlib', 'shutil',
                             'subprocess', 'datetime', 'time', 'random',
                             'base64', 'hashlib', 'tempfile', 'csv', 'Path',
                             'timedelta', 'Dict', 'List', 'Any', 'Optional', 'context']
            }
            
            return {
                "success": True,
                "result": result_value,
                "variables": user_vars,
                "context_updated": safe_namespace.get('context', {})
            }
            
        except Exception as e:
            import traceback
            return {
                "success": False,
                "error": str(e),
                "type": type(e).__name__,
                "traceback": traceback.format_exc()
            }

# ============================================
# WEB TOOLS
# ============================================

class WebSearchTool(Tool):
    """Web search using DuckDuckGo (no API key required)"""
    
    @property
    def name(self) -> str:
        return "web_search"
    
    @property
    def description(self) -> str:
        return "Search the web using DuckDuckGo"
    
    async def execute(self, query: str, num_results: int = 5, **kwargs) -> Dict[str, Any]:
        if not aiohttp:
            return {"success": False, "error": "aiohttp not installed"}
        
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    "q": query,
                    "format": "json",
                    "no_html": "1",
                    "skip_disambig": "1"
                }
                
                async with session.get(
                    "https://api.duckduckgo.com/",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    data = await response.json()
                    
                    results = []
                    
                    # Extract abstract if available
                    if data.get("Abstract"):
                        results.append({
                            "title": data.get("Heading", ""),
                            "snippet": data["Abstract"],
                            "url": data.get("AbstractURL", "")
                        })
                    
                    # Extract related topics
                    for topic in data.get("RelatedTopics", [])[:num_results]:
                        if isinstance(topic, dict) and "Text" in topic:
                            results.append({
                                "title": topic.get("Text", "").split(" - ")[0][:50],
                                "snippet": topic.get("Text", ""),
                                "url": topic.get("FirstURL", "")
                            })
                    
                    return {
                        "success": True,
                        "query": query,
                        "results": results[:num_results],
                        "count": len(results)
                    }
                    
        except Exception as e:
            return {"success": False, "error": str(e)}

class WebFetchTool(Tool):
    """Fetch content from URLs"""
    
    @property
    def name(self) -> str:
        return "web_fetch"
    
    @property
    def description(self) -> str:
        return "Fetch and extract content from a URL"
    
    async def execute(self, url: str, **kwargs) -> Dict[str, Any]:
        if not aiohttp:
            return {"success": False, "error": "aiohttp not installed"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    content = await response.text()
                    
                    # Simple HTML extraction
                    if "text/html" in response.headers.get("Content-Type", ""):
                        # Remove HTML tags (basic)
                        text = re.sub('<script[^>]*>.*?</script>', '', content, flags=re.DOTALL)
                        text = re.sub('<style[^>]*>.*?</style>', '', content, flags=re.DOTALL)
                        text = re.sub('<[^>]+>', '', text)
                        text = ' '.join(text.split())[:5000]  # Limit size
                    else:
                        text = content[:5000]
                    
                    return {
                        "success": True,
                        "url": url,
                        "status": response.status,
                        "content": text,
                        "content_type": response.headers.get("Content-Type", ""),
                        "length": len(content)
                    }
                    
        except asyncio.TimeoutError:
            return {"success": False, "error": "Request timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}

# ============================================
# GITHUB TOOL
# ============================================

class GitHubTool(Tool):
    """GitHub operations using GitHub REST API (requires GITHUB_TOKEN)"""
    
    @property
    def name(self) -> str:
        return "github"
    
    @property
    def description(self) -> str:
        return "GitHub operations (create/list/delete repos) using REST API. Requires GITHUB_TOKEN."
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create_repo", "list_repos", "delete_repo"],
                    "description": "GitHub action to perform"
                },
                "name": {
                    "type": "string",
                    "description": "Repository name"
                },
                "private": {
                    "type": "boolean",
                    "description": "Make repository private"
                },
                "description": {
                    "type": "string",
                    "description": "Repository description"
                }
            },
            "required": ["action"]
        }
    
    async def execute(self, action: str, **kwargs) -> Dict[str, Any]:
        try:
            token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
            if not token:
                return {"success": False, "error": "GITHUB_TOKEN environment variable is not set"}
            
            api_base = "https://api.github.com"
            
            def request(method: str, url: str, body: Optional[Dict[str, Any]] = None) -> Tuple[int, str]:
                headers = {
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {token}",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "User-Agent": "HybridAgent"
                }
                data_bytes = None
                if body is not None:
                    data_bytes = json.dumps(body).encode("utf-8")
                    headers["Content-Type"] = "application/json"
                req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return resp.getcode(), resp.read().decode("utf-8")
            
            if action == "create_repo":
                repo_name = kwargs.get("name")
                if not repo_name:
                    return {"success": False, "error": "Repository name required"}
                body = {
                    "name": repo_name,
                    "private": bool(kwargs.get("private", False)),
                    "description": kwargs.get("description") or ""
                }
                status, text = request("POST", f"{api_base}/user/repos", body)
                ok = status in (200, 201)
                payload = {}
                try:
                    payload = json.loads(text) if text else {}
                except Exception:
                    payload = {"raw": text}
                return {
                    "success": ok,
                    "repo_name": repo_name,
                    "response_status": status,
                    "repo_full_name": payload.get("full_name"),
                    "repo_html_url": payload.get("html_url"),
                    "error": None if ok else payload.get("message", text)
                }
            
            elif action == "list_repos":
                status, text = request("GET", f"{api_base}/user/repos?per_page=20")
                ok = status == 200
                repos = []
                try:
                    data = json.loads(text) if text else []
                    repos = [item.get("full_name") for item in data if isinstance(item, dict)]
                except Exception:
                    repos = []
                return {
                    "success": ok,
                    "repos": repos,
                    "response_status": status,
                    "error": None if ok else text
                }
            
            elif action == "delete_repo":
                full_name = kwargs.get("name")
                if not full_name or "/" not in full_name:
                    return {"success": False, "error": "Repository name must be in 'owner/repo' format"}
                status, text = request("DELETE", f"{api_base}/repos/{full_name}")
                ok = status in (200, 202, 204)
                return {
                    "success": ok,
                    "repo_name": full_name,
                    "response_status": status,
                    "error": None if ok else text
                }
            
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode("utf-8")
            except Exception:
                detail = str(e)
            return {"success": False, "error": f"HTTPError {e.code}: {detail}"}
        except urllib.error.URLError as e:
            return {"success": False, "error": f"URLError: {e.reason}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

# ============================================
# ORCHESTRATION COMPONENTS
# ============================================

@dataclass
class TaskResult:
    """Result of a task execution"""
    task_id: str
    tool: str
    success: bool
    result: Dict[str, Any]
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    retries: int = 0

@dataclass
class ExecutionMemory:
    """Stores execution history for context"""
    goal: str
    summary: str
    results: List[TaskResult]
    timestamp: datetime = field(default_factory=datetime.now)

# ============================================
# MAIN HYBRID AGENT
# ============================================

class HybridAgent:
    """
    Production-ready agent combining:
    - Specialized tools for common operations
    - Code execution for complex logic
    - Intelligent tool selection via LLM
    - Error recovery and retry logic
    - Memory and context management
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4.1",
        max_retries: int = 3,
        enable_memory: bool = True
    ):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self.max_retries = max_retries
        self.enable_memory = enable_memory
        
        # Tool registry
        self.tools: Dict[str, Tool] = {}
        self._register_default_tools()
        
        # Execution context and memory
        self.context: Dict[str, Any] = {}
        self.memory: List[ExecutionMemory] = []
        self.max_memory_size = 10
        
        # Statistics
        self.stats = defaultdict(int)
        
    def _register_default_tools(self):
        """Register the default tool set"""
        default_tools = [
            # File operations
            FileReadTool(),
            FileWriteTool(),
            
            # Git operations
            GitTool(),
            
            # System operations
            ShellTool(),
            
            # Code execution
            PythonTool(),
            
            # Web operations
            WebSearchTool(),
            WebFetchTool(),
            
            # GitHub operations
            GitHubTool(),
        ]
        
        for tool in default_tools:
            self.register_tool(tool)
            
    def register_tool(self, tool: Tool):
        """Register a new tool"""
        self.tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")
    
    def get_tools_schema(self) -> List[Dict]:
        """Generate OpenAI function calling schema for all tools"""
        schemas = []
        
        for name, tool in self.tools.items():
            schema = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.description,
                    "parameters": tool.parameters_schema
                }
            }
            schemas.append(schema)
            
        return schemas
    
    def _get_memory_context(self, limit: int = 3) -> str:
        """Get relevant memory context"""
        if not self.enable_memory or not self.memory:
            return ""
        
        recent_memory = self.memory[-limit:]
        context_parts = []
        
        for mem in recent_memory:
            success_rate = sum(1 for r in mem.results if r.success) / len(mem.results) * 100
            context_parts.append(
                f"Previous task: {mem.goal[:100]}\n"
                f"Summary: {mem.summary}\n"
                f"Success rate: {success_rate:.0f}%"
            )
        
        return "\n\n".join(context_parts)
    
    async def _execute_tool_with_retry(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        task_id: str = None
    ) -> TaskResult:
        """Execute a tool with retry logic"""
        tool = self.tools.get(tool_name)
        if not tool:
            return TaskResult(
                task_id=task_id or f"task_{datetime.now().timestamp()}",
                tool=tool_name,
                success=False,
                result={},
                error=f"Tool '{tool_name}' not found"
            )
        
        # Validate parameters
        valid, error = tool.validate_params(**parameters)
        if not valid:
            return TaskResult(
                task_id=task_id or f"task_{datetime.now().timestamp()}",
                tool=tool_name,
                success=False,
                result={},
                error=error
            )
        
        # Try execution with retries
        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Add context for Python tool
                if tool_name == "python":
                    parameters["context"] = self.context
                
                # Execute tool
                result = await tool.execute(**parameters)
                
                # Update statistics
                self.stats[f"{tool_name}_calls"] += 1
                
                if result.get("success"):
                    self.stats[f"{tool_name}_success"] += 1
                    return TaskResult(
                        task_id=task_id or f"task_{datetime.now().timestamp()}",
                        tool=tool_name,
                        success=True,
                        result=result,
                        retries=attempt
                    )
                
                last_error = result.get("error", "Unknown error")
                
                # Try to fix parameters if we have more attempts
                if attempt < self.max_retries - 1:
                    fixed_params = await self._fix_parameters(
                        tool_name, parameters, last_error
                    )
                    if fixed_params:
                        # Merge to preserve required args like 'action'
                        merged = dict(parameters)
                        merged.update(fixed_params)
                        parameters = merged
                        logger.info(f"Retrying {tool_name} with fixed parameters")
                
            except Exception as e:
                last_error = str(e)
                logger.error(f"Tool execution failed: {e}")
        
        self.stats[f"{tool_name}_failures"] += 1
        return TaskResult(
            task_id=task_id or f"task_{datetime.now().timestamp()}",
            tool=tool_name,
            success=False,
            result={},
            error=last_error,
            retries=self.max_retries
        )
    
    async def _fix_parameters(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        error: str
    ) -> Optional[Dict[str, Any]]:
        """Use LLM to fix parameters based on error"""
        prompt = f"""
        Tool '{tool_name}' failed with error:
        {error}
        
        Original parameters:
        {json.dumps(parameters, indent=2)}
        
        Suggest corrected parameters that might fix this error.
        Return ONLY valid JSON with the corrected parameters.
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a debugging assistant. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"Failed to fix parameters: {e}")
            return None
    
    async def execute_with_function_calling(
        self,
        goal: str,
        max_iterations: int = 10
    ) -> Dict[str, Any]:
        """Execute goal using OpenAI function calling for tool selection"""
        
        # Initialize conversation with memory context
        memory_context = self._get_memory_context()
        
        system_prompt = """You are an AI assistant that uses tools to complete tasks.
Be efficient and combine operations when possible using the python tool.
Previous context may be available to help guide your decisions."""
        
        if memory_context:
            system_prompt += f"\n\nPrevious execution context:\n{memory_context}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": goal}
        ]
        
        results = []
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            try:
                # Call LLM with function calling
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=self.get_tools_schema(),
                    tool_choice="auto",
                    temperature=0.7
                )
                
                message = response.choices[0].message
                messages.append(message.dict())
                
                # Check if we're done
                if not message.tool_calls:
                    logger.info("No more tool calls needed")
                    break
                
                # Execute tool calls
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    logger.info(f"Calling {tool_name} with args: {tool_args}")
                    
                    # Execute with retry
                    task_result = await self._execute_tool_with_retry(
                        tool_name,
                        tool_args,
                        task_id=tool_call.id
                    )
                    
                    results.append(task_result)
                    
                    # Update context
                    self.context[tool_call.id] = task_result.result
                    
                    # Add tool response to conversation
                    tool_response = {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(task_result.result)
                    }
                    messages.append(tool_response)
                    
                    # Stop if critical failure
                    if not task_result.success and "critical" in str(task_result.error).lower():
                        logger.error(f"Critical failure: {task_result.error}")
                        break
                        
            except Exception as e:
                logger.error(f"Iteration {iteration} failed: {e}")
                break
        
        # Store in memory
        if self.enable_memory and results:
            self._store_memory(goal, results)
        
        # Generate summary
        success_count = sum(1 for r in results if r.success)
        
        return {
            "success": success_count == len(results) if results else False,
            "goal": goal,
            "results": [
                {
                    "task_id": r.task_id,
                    "tool": r.tool,
                    "success": r.success,
                    "error": r.error,
                    "retries": r.retries
                }
                for r in results
            ],
            "summary": f"Executed {len(results)} tasks, {success_count} successful",
            "context": self.context,
            "iterations": iteration,
            "stats": dict(self.stats)
        }
    
    def _store_memory(self, goal: str, results: List[TaskResult]):
        """Store execution in memory"""
        summary = f"Completed {len(results)} tasks, " \
                 f"{sum(1 for r in results if r.success)} successful"
        
        memory_entry = ExecutionMemory(
            goal=goal[:200],  # Truncate long goals
            summary=summary,
            results=results
        )
        
        self.memory.append(memory_entry)
        
        # Limit memory size
        if len(self.memory) > self.max_memory_size:
            self.memory.pop(0)
    
    async def plan_and_execute(self, goal: str) -> Dict[str, Any]:
        """Create a plan first, then execute it"""
        
        # Create plan
        plan = await self._create_plan(goal)
        
        if not plan:
            return {
                "success": False,
                "error": "Failed to create execution plan"
            }
        
        logger.info(f"Created plan with {len(plan)} tasks")
        
        # Execute plan
        results = []
        for task in plan:
            logger.info(f"Executing task: {task.get('description', task['id'])}")
            
            task_result = await self._execute_tool_with_retry(
                task["tool"],
                task.get("parameters", {}),
                task_id=task["id"]
            )
            
            results.append(task_result)
            self.context[task["id"]] = task_result.result
            
            # Stop on critical failure
            if not task_result.success and task.get("required", False):
                logger.error(f"Required task failed: {task['id']}")
                break
        
        # Store in memory
        if self.enable_memory and results:
            self._store_memory(goal, results)
        
        return {
            "success": all(r.success for r in results),
            "goal": goal,
            "plan": plan,
            "results": [
                {
                    "task_id": r.task_id,
                    "tool": r.tool,
                    "success": r.success,
                    "error": r.error
                }
                for r in results
            ],
            "context": self.context
        }
    
    async def _create_plan(self, goal: str) -> List[Dict[str, Any]]:
        """Create an execution plan"""
        
        tools_desc = "\n".join([
            f"- {name}: {tool.description}"
            for name, tool in self.tools.items()
        ])
        
        prompt = f"""Create a detailed execution plan for this goal:
{goal}

Available tools:
{tools_desc}

Guidelines:
- Use specialized tools for standard operations
- Use 'python' tool for complex logic or data processing
- Combine multiple operations in Python when efficient
- Each task should have a unique id

Return a JSON array of tasks:
[
  {{
    "id": "unique_task_id",
    "tool": "tool_name",
    "parameters": {{}},
    "description": "what this does",
    "required": true/false,
    "depends_on": ["other_task_id"]  // optional
  }}
]
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a task planning expert."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.5
            )
            
            plan_data = json.loads(response.choices[0].message.content)
            
            # Extract tasks array from various possible formats
            if isinstance(plan_data, list):
                return plan_data
            elif "tasks" in plan_data:
                return plan_data["tasks"]
            elif "plan" in plan_data:
                return plan_data["plan"]
            else:
                # Try to find any list in the response
                for value in plan_data.values():
                    if isinstance(value, list):
                        return value
                return []
                
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get execution statistics"""
        total_calls = sum(v for k, v in self.stats.items() if k.endswith("_calls"))
        total_success = sum(v for k, v in self.stats.items() if k.endswith("_success"))
        
        tool_stats = {}
        for tool_name in self.tools.keys():
            calls = self.stats.get(f"{tool_name}_calls", 0)
            success = self.stats.get(f"{tool_name}_success", 0)
            failures = self.stats.get(f"{tool_name}_failures", 0)
            
            if calls > 0:
                tool_stats[tool_name] = {
                    "calls": calls,
                    "success": success,
                    "failures": failures,
                    "success_rate": (success / calls) * 100
                }
        
        return {
            "total_calls": total_calls,
            "total_success": total_success,
            "overall_success_rate": (total_success / total_calls * 100) if total_calls > 0 else 0,
            "tools": tool_stats,
            "memory_entries": len(self.memory)
        }
    
    def clear_context(self):
        """Clear execution context"""
        self.context.clear()
        logger.info("Context cleared")
    
    def clear_memory(self):
        """Clear execution memory"""
        self.memory.clear()
        logger.info("Memory cleared")
