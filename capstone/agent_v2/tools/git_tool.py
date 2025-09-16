# ============================================
# GIT TOOL
# ============================================

import json
import os
from pathlib import Path
import subprocess
from typing import Any, Optional, Dict, Tuple
import urllib

from capstone.agent_v2.tool import Tool


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
                try:
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        return resp.getcode(), resp.read().decode("utf-8")
                except urllib.error.HTTPError as e:
                    try:
                        detail = e.read().decode("utf-8")
                    except Exception:
                        detail = str(e)
                    return e.code, detail
                except urllib.error.URLError as e:
                    return 0, f"URLError: {e.reason}"
            
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
                error_msg = None
                if not ok:
                    # Surface useful validation errors (422) or auth issues
                    base_msg = payload.get("message") if isinstance(payload, dict) else None
                    errors = payload.get("errors") if isinstance(payload, dict) else None
                    if status == 422 and errors:
                        error_msg = f"Validation failed: {errors}"
                    elif status in (401, 403):
                        error_msg = base_msg or "Authentication/authorization failed. Check GITHUB_TOKEN scopes."
                    else:
                        error_msg = base_msg or text or f"HTTP {status}"
                return {
                    "success": ok,
                    "repo_name": repo_name,
                    "response_status": status,
                    "repo_full_name": payload.get("full_name") if isinstance(payload, dict) else None,
                    "repo_html_url": payload.get("html_url") if isinstance(payload, dict) else None,
                    "error": error_msg,
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
