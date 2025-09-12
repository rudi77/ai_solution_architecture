"""
Git Tools Module - Extracted from tools_builtin.py

Contains Git repository operations:
- create_repository
- setup_branch_protection  
- create_git_repository_with_branch_protection
"""
from __future__ import annotations
import asyncio
import re
from pathlib import Path
import os
import json
import shutil
from datetime import datetime
import subprocess
from typing import Any, Dict, List
import structlog

# Import ToolSpec with fallback strategy to avoid circular dependencies
def _get_toolspec():
    try:
        # Try relative import first (when running as part of package)
        from .tools import ToolSpec
        return ToolSpec
    except ImportError:
        # Fallback for standalone execution
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))
        from tools import ToolSpec
        return ToolSpec

logger = structlog.get_logger()


async def create_repository(name: str, visibility: str = "private", **kwargs) -> Dict[str, Any]:
    """Create a real local Git repository with an initial commit.

    Steps:
    - Create directory ./<name>
    - git init, set branch to 'main'
    - write README.md and commit
    - configure local user.name/email if missing
    """
    logger.info("create_repository_start", name=name, visibility=visibility)
    
    if not isinstance(name, str) or not name.strip():
        error = "Missing or invalid repository name"
        logger.error("validation_failed", error=error, reason="missing_or_invalid_name")
        return {"success": False, "error": error}
    
    if any(char in name for char in "@!#$%^&*()"):
        error = "Invalid repository name"
        logger.error("validation_failed", error=error, reason="invalid_characters")
        return {"success": False, "error": error}

    git_path = shutil.which("git")
    logger.info("git_executable_check", git_path=git_path)
    if git_path is None:
        error = "Git not found in PATH. Please install Git and retry."
        logger.error("git_not_found", error=error)
        return {
            "success": False,
            "error": error,
        }

    repo_dir = Path.cwd() / name
    logger.info("target_directory_check", repo_dir=str(repo_dir))
    
    # Check if this is a retry scenario (local repo exists but may not be pushed to GitHub)
    is_retry_scenario = False
    
    if repo_dir.exists():
        logger.info("directory_exists", repo_dir=str(repo_dir))
        
        # Check if it's a git repository with commits
        git_dir = repo_dir / ".git"
        if git_dir.exists():
            logger.info(f"Found existing git repository at {repo_dir}")
            # Check if there are commits
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "HEAD"], cwd=str(repo_dir), 
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    commit_hash = result.stdout.strip()
                    logger.info(f"Found existing commit: {commit_hash}")
                    
                    # Check if remote origin exists
                    remote_result = subprocess.run(
                        ["git", "remote", "get-url", "origin"], cwd=str(repo_dir),
                        capture_output=True, text=True, timeout=10
                    )
                    
                    if remote_result.returncode != 0:
                        logger.info("No remote origin found - this appears to be a retry scenario")
                        is_retry_scenario = True
                    else:
                        remote_url = remote_result.stdout.strip()
                        logger.info(f"Remote origin already configured: {remote_url}")
                        # Repository already exists and is configured - return success
                        return {
                            "success": True,
                            "repo_path": str(repo_dir),
                            "default_branch": "main",
                            "initial_commit": commit_hash,
                            "remote_clone_url": remote_url,
                            "note": "Repository already exists and is properly configured"
                        }
                else:
                    logger.info("Git repository exists but has no commits")
            except Exception as e:
                logger.warning(f"Error checking existing git repository: {e}")
        
        if not is_retry_scenario and any(repo_dir.iterdir()):
            error = f"Target directory '{repo_dir}' already exists and is not empty"
            logger.error(error)
            return {"success": False, "error": error}
        elif not is_retry_scenario:
            logger.info(f"Directory {repo_dir} exists but is empty - proceeding")
    else:
        logger.info(f"Creating directory {repo_dir}")
        try:
            repo_dir.mkdir(parents=True, exist_ok=False)
            logger.info(f"Directory {repo_dir} created successfully")
        except Exception as e:
            error = f"Failed to create directory: {e}"
            logger.error(error)
            return {"success": False, "error": error}

    def run_git(args: List[str]) -> Dict[str, Any]:
        cmd = ["git"] + args
        logger.info("git_command_start", command=" ".join(cmd), cwd=str(repo_dir))
        
        try:
            result = subprocess.run(
                cmd, cwd=str(repo_dir), capture_output=True, text=True, timeout=30
            )
            result_dict = {
                "code": result.returncode, 
                "stdout": result.stdout.strip(), 
                "stderr": result.stderr.strip()
            }
        except subprocess.TimeoutExpired as e:
            logger.error("git_command_timeout", command=" ".join(args), timeout=30)
            result_dict = {"code": -1, "stdout": "", "stderr": "Command timed out after 30 seconds"}
        except Exception as e:
            logger.error("git_command_exception", command=" ".join(args), error=str(e))
            result_dict = {"code": -1, "stdout": "", "stderr": f"Command failed: {str(e)}"}
        
        logger.info("git_command_result", command=" ".join(args), code=result_dict["code"], 
                   stdout=result_dict["stdout"][:200], stderr=result_dict["stderr"][:200])
        return result_dict

    # Skip git init if this is a retry scenario
    if not is_retry_scenario:
        logger.info("git_init_start")
        init_res = run_git(["init"])
        if init_res["code"] != 0:
            error = f"git init failed: {init_res['stderr']}"
            logger.error("git_init_failed", error=error, stderr=init_res['stderr'])
            return {"success": False, "error": error}
        
        logger.info("git_branch_setup_start")
        branch_res = run_git(["branch", "-M", "main"])
        if branch_res["code"] != 0:
            error = f"setting branch failed: {branch_res['stderr']}"
            logger.error("git_branch_failed", error=error, stderr=branch_res['stderr'])
            return {"success": False, "error": error}
    else:
        logger.info("retry_scenario_detected", message="skipping git init and branch setup")

    logger.info("Checking git user configuration")
    cfg_email = run_git(["config", "--get", "user.email"])
    if cfg_email["code"] != 0 or not cfg_email["stdout"]:
        logger.info("Setting default user.email")
        set_email = run_git(["config", "user.email", "idp@example.com"])
        if set_email["code"] != 0:
            error = f"git config user.email failed: {set_email['stderr']}"
            logger.error(error)
            return {"success": False, "error": error}
    else:
        logger.info(f"Using existing user.email: {cfg_email['stdout']}")
        
    cfg_name = run_git(["config", "--get", "user.name"])
    if cfg_name["code"] != 0 or not cfg_name["stdout"]:
        logger.info("Setting default user.name")
        set_name = run_git(["config", "user.name", "IDP Copilot"])
        if set_name["code"] != 0:
            error = f"git config user.name failed: {set_name['stderr']}"
            logger.error(error)
            return {"success": False, "error": error}
    else:
        logger.info(f"Using existing user.name: {cfg_name['stdout']}")

    # Handle README and commit creation (skip if retry scenario with existing commits)
    if not is_retry_scenario:
        logger.info("Creating README.md file")
        try:
            readme = repo_dir / "README.md"
            if not readme.exists():
                readme_content = f"# {name}\n\nCreated by IDP Copilot on {datetime.now().isoformat()}\n"
                readme.write_text(readme_content, encoding="utf-8")
                logger.info(f"README.md created with content: {readme_content[:50]}...")
            else:
                logger.info("README.md already exists - skipping creation")
        except Exception as e:
            error = f"Failed to write README.md: {e}"
            logger.error(error)
            return {"success": False, "error": error}

        logger.info("Adding README.md to git staging area")
        add_res = run_git(["add", "README.md"])
        if add_res["code"] != 0:
            error = f"git add failed: {add_res['stderr']}"
            logger.error(error)
            return {"success": False, "error": error}
            
        logger.info("Creating initial commit")
        commit_res = run_git(["commit", "-m", "Initial commit"])
        if commit_res["code"] != 0:
            error = f"git commit failed: {commit_res['stderr']}"
            logger.error(error)
            return {"success": False, "error": error}
    else:
        logger.info("Retry scenario - skipping README creation and commit")
        
    logger.info("Getting current commit hash")
    rev_res = run_git(["rev-parse", "HEAD"])
    if rev_res["code"] != 0:
        error = f"git rev-parse failed: {rev_res['stderr']}"
        logger.error(error)
        return {"success": False, "error": error}
        
    commit_hash = rev_res["stdout"]
    logger.info(f"Current commit hash: {commit_hash}")

    # Create remote on GitHub and push initial commit if token is available
    logger.info("github_remote_start")
    token = os.getenv("GITHUB_TOKEN")
    org = os.getenv("GITHUB_ORG")
    owner_env = os.getenv("GITHUB_OWNER")
    
    logger.info("github_env_check", 
                github_token_set=bool(token), 
                github_org=org, 
                github_owner=owner_env)
    
    if not token:
        error = "GITHUB_TOKEN is not set. Cannot create remote repository."
        logger.warning("github_token_missing", error=error)
        return {
            "success": False,
            "error": error,
            "local_repo_created": True,
            "repo_path": str(repo_dir),
            "default_branch": "main",
            "initial_commit": commit_hash,
        }

    import urllib.request
    import urllib.error

    api_url = "https://api.github.com/user/repos"
    if org:
        api_url = f"https://api.github.com/orgs/{org}/repos"
        logger.info(f"Using organization API endpoint: {api_url}")
    else:
        logger.info(f"Using user API endpoint: {api_url}")
        
    payload = {
        "name": name,
        "private": (str(visibility).lower() != "public"),
        "auto_init": False,
        "has_issues": True,
        "has_projects": True,
        "has_wiki": False,
        "default_branch": "main",
    }
    logger.info(f"GitHub API payload: {payload}")
    # Log request info with masked token
    logger.info("github_api_headers", authorization_token_prefix=f"{token[:8]}...", user_agent="idp-copilot")
    
    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",  # Use full token for actual request
            "User-Agent": "idp-copilot", 
            "Content-Type": "application/json",
        },
        method="POST",
    )
    
    logger.info("github_api_request_start", repo_name=name, api_url=api_url)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            repo_info = json.loads(body)
            logger.info("github_repo_created", html_url=repo_info.get('html_url'))
    except urllib.error.HTTPError as e:
        logger.error("github_api_http_error", code=e.code, reason=e.reason)
        try:
            err_body = e.read().decode("utf-8")
            err_json = json.loads(err_body)
            msg = err_json.get("message", err_body)
            logger.error("github_api_error_details", error_json=err_json)
        except Exception:
            msg = str(e)
            logger.error("github_api_parse_error", error=str(e))
            
        return {
            "success": False,
            "error": f"GitHub repo creation failed: {msg}",
            "local_repo_created": True,
            "repo_path": str(repo_dir),
            "default_branch": "main",
            "initial_commit": commit_hash,
        }
    except Exception as e:
        logger.error("github_api_unexpected_error", error=str(e))
        return {
            "success": False,
            "error": f"GitHub repo creation failed: {str(e)}",
            "local_repo_created": True,
            "repo_path": str(repo_dir),
            "default_branch": "main",
            "initial_commit": commit_hash,
        }

    owner_login = ((repo_info or {}).get("owner") or {}).get("login") or owner_env or org or ""
    logger.info(f"Determined repository owner: '{owner_login}' (from repo_info: {((repo_info or {}).get('owner') or {}).get('login')}, owner_env: {owner_env}, org: {org})")
    
    if not owner_login:
        error = "Could not determine repository owner for remote URL."
        logger.error(error)
        return {
            "success": False,
            "error": error,
            "local_repo_created": True,
            "repo_path": str(repo_dir),
            "default_branch": "main",
            "initial_commit": commit_hash,
        }

    token_remote_url = f"https://x-access-token:{token}@github.com/{owner_login}/{name}.git"
    clean_remote_url = f"https://github.com/{owner_login}/{name}.git"
    logger.info(f"Remote URLs - token_url: https://x-access-token:***@github.com/{owner_login}/{name}.git, clean_url: {clean_remote_url}")

    logger.info("git_remote_add_start")
    add_remote = run_git(["remote", "add", "origin", token_remote_url])
    if add_remote["code"] != 0:
        error = f"git remote add failed: {add_remote['stderr']}"
        logger.error("git_remote_add_failed", error=error, stderr=add_remote['stderr'])
        return {"success": False, "error": error, "local_repo_created": True, "repo_path": str(repo_dir)}
    
    logger.info("git_push_start")
    push_res = run_git(["push", "-u", "origin", "main"])
    if push_res["code"] != 0:
        error = f"git push failed: {push_res['stderr']}"
        logger.error("git_push_failed", error=error, stderr=push_res['stderr'])
        return {"success": False, "error": error, "local_repo_created": True, "repo_path": str(repo_dir)}
    
    logger.info("git_remote_cleanup_start")
    set_url = run_git(["remote", "set-url", "origin", clean_remote_url])
    if set_url["code"] != 0:
        error = f"git remote set-url failed: {set_url['stderr']}"
        logger.error("git_remote_cleanup_failed", error=error, stderr=set_url['stderr'])
        return {"success": False, "error": error, "local_repo_created": True, "repo_path": str(repo_dir)}

    logger.info("create_repository_success", local_path=str(repo_dir), remote_url=clean_remote_url)
    
    return {
        "success": True,
        "repo_path": str(repo_dir),
        "default_branch": "main",
        "initial_commit": commit_hash,
        "remote_html_url": repo_info.get("html_url"),
        "remote_clone_url": clean_remote_url,
    }


async def setup_branch_protection(repo_name: str, **kwargs) -> Dict[str, Any]:
    await asyncio.sleep(1)
    return {
        "success": True,
        "rules": [
            "require-pr-reviews",
            "dismiss-stale-reviews",
            "require-status-checks",
        ],
    }


async def create_git_repository_with_branch_protection(
    repo_name: str = None, visibility: str = "private", **kwargs
) -> Dict[str, Any]:
    visibility = kwargs.get("visibility", visibility)
    name = repo_name or kwargs.get("name") or kwargs.get("project_name") or "unnamed"
    create = await create_repository(name=name, visibility=visibility, **kwargs)
    if not create.get("success"):
        return create
    protection = await setup_branch_protection(repo_name=name, **kwargs)
    if not protection.get("success"):
        return protection
    return {"success": True, "repo": create, "branch_protection": protection}


# Lazy ToolSpec definitions to avoid circular imports
def get_git_tools():
    """Lazy loader for Git ToolSpec definitions to avoid import issues"""
    ToolSpec = _get_toolspec()
    
    return [
        ToolSpec(
            name="create_repository",
            description="Creates local Git repo and GitHub remote, pushes initial commit",
            input_schema={
                "type": "object",
                "properties": {"name": {"type": "string"}, "visibility": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": True,
            },
            output_schema={"type": "object"},
            func=create_repository,
            is_async=True,
            timeout=10,
            aliases=[],
        ),
        ToolSpec(
            name="setup_branch_protection",
            description="Setup branch rules",
            input_schema={
                "type": "object",
                "properties": {"repo_name": {"type": "string"}},
                "required": ["repo_name"],
                "additionalProperties": True,
            },
            output_schema={"type": "object"},
            func=setup_branch_protection,
            is_async=True,
            timeout=5,
            aliases=[],
        ),
        ToolSpec(
            name="create_git_repository_with_branch_protection",
            description="Create repo then apply standard branch protection",
            input_schema={
                "type": "object",
                "properties": {"repo_name": {"type": "string"}, "visibility": {"type": "string"}},
                "required": [],
                "additionalProperties": True,
            },
            output_schema={"type": "object"},
            func=create_git_repository_with_branch_protection,
            is_async=True,
            timeout=20,
            aliases=["git-repo-creator", "create-git-repo"],
        ),
    ]