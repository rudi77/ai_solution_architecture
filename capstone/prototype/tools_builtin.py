from __future__ import annotations
import asyncio
import re
from pathlib import Path
import os
import json
import shutil
from datetime import datetime
import asyncio.subprocess as asp
from typing import Any, Dict, List

from .tools import ToolSpec
from .agent import ReActAgent
from .llm_provider import LLMProvider
from .tools import build_tool_index, execute_tool_by_name_from_index


# ==== Tool Implementations (migrated from idp.py methods) ====


async def create_repository(name: str, visibility: str = "private", **kwargs) -> Dict[str, Any]:
    """Create a real local Git repository with an initial commit.

    Steps:
    - Create directory ./<name>
    - git init, set branch to 'main'
    - write README.md and commit
    - configure local user.name/email if missing
    """
    if not isinstance(name, str) or not name.strip():
        return {"success": False, "error": "Missing or invalid repository name"}
    if any(char in name for char in "@!#$%^&*()"):
        return {"success": False, "error": "Invalid repository name"}

    if shutil.which("git") is None:
        return {
            "success": False,
            "error": "Git not found in PATH. Please install Git and retry.",
        }

    repo_dir = Path.cwd() / name
    if repo_dir.exists():
        if any(repo_dir.iterdir()):
            return {"success": False, "error": f"Target directory '{repo_dir}' already exists and is not empty"}
    else:
        try:
            repo_dir.mkdir(parents=True, exist_ok=False)
        except Exception as e:
            return {"success": False, "error": f"Failed to create directory: {e}"}

    async def run_git(args: List[str]) -> Dict[str, Any]:
        proc = await asp.create_subprocess_exec(
            "git", *args, cwd=str(repo_dir), stdout=asp.PIPE, stderr=asp.PIPE
        )
        out_b, err_b = await proc.communicate()
        return {"code": proc.returncode, "stdout": out_b.decode().strip(), "stderr": err_b.decode().strip()}

    init_res = await run_git(["init"])
    if init_res["code"] != 0:
        return {"success": False, "error": f"git init failed: {init_res['stderr']}"}

    branch_res = await run_git(["branch", "-M", "main"])
    if branch_res["code"] != 0:
        return {"success": False, "error": f"setting branch failed: {branch_res['stderr']}"}

    cfg_email = await run_git(["config", "--get", "user.email"])
    if cfg_email["code"] != 0 or not cfg_email["stdout"]:
        set_email = await run_git(["config", "user.email", "idp@example.com"])
        if set_email["code"] != 0:
            return {"success": False, "error": f"git config user.email failed: {set_email['stderr']}"}
    cfg_name = await run_git(["config", "--get", "user.name"])
    if cfg_name["code"] != 0 or not cfg_name["stdout"]:
        set_name = await run_git(["config", "user.name", "IDP Copilot"])
        if set_name["code"] != 0:
            return {"success": False, "error": f"git config user.name failed: {set_name['stderr']}"}

    try:
        readme = repo_dir / "README.md"
        if not readme.exists():
            readme.write_text(
                f"# {name}\n\nCreated by IDP Copilot on {datetime.now().isoformat()}\n",
                encoding="utf-8",
            )
    except Exception as e:
        return {"success": False, "error": f"Failed to write README.md: {e}"}

    add_res = await run_git(["add", "README.md"])
    if add_res["code"] != 0:
        return {"success": False, "error": f"git add failed: {add_res['stderr']}"}
    commit_res = await run_git(["commit", "-m", "Initial commit"])
    if commit_res["code"] != 0:
        return {"success": False, "error": f"git commit failed: {commit_res['stderr']}"}
    rev_res = await run_git(["rev-parse", "HEAD"])
    if rev_res["code"] != 0:
        return {"success": False, "error": f"git rev-parse failed: {rev_res['stderr']}"}

    # Create remote on GitHub and push initial commit if token is available
    token = os.getenv("GITHUB_TOKEN")
    org = os.getenv("GITHUB_ORG")
    owner_env = os.getenv("GITHUB_OWNER")
    if not token:
        return {
            "success": False,
            "error": "GITHUB_TOKEN is not set. Cannot create remote repository.",
            "local_repo_created": True,
            "repo_path": str(repo_dir),
            "default_branch": "main",
            "initial_commit": rev_res["stdout"],
        }

    import urllib.request
    import urllib.error

    api_url = f"https://api.github.com/user/repos"
    if org:
        api_url = f"https://api.github.com/orgs/{org}/repos"
    payload = {
        "name": name,
        "private": (str(visibility).lower() != "public"),
        "auto_init": False,
        "has_issues": True,
        "has_projects": True,
        "has_wiki": False,
        "default_branch": "main",
    }
    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "idp-copilot",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            repo_info = json.loads(body)
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
            err_json = json.loads(err_body)
            msg = err_json.get("message", err_body)
        except Exception:
            msg = str(e)
        return {
            "success": False,
            "error": f"GitHub repo creation failed: {msg}",
            "local_repo_created": True,
            "repo_path": str(repo_dir),
            "default_branch": "main",
            "initial_commit": rev_res["stdout"],
        }

    owner_login = ((repo_info or {}).get("owner") or {}).get("login") or owner_env or org or ""
    if not owner_login:
        return {
            "success": False,
            "error": "Could not determine repository owner for remote URL.",
            "local_repo_created": True,
            "repo_path": str(repo_dir),
            "default_branch": "main",
            "initial_commit": rev_res["stdout"],
        }

    token_remote_url = f"https://x-access-token:{token}@github.com/{owner_login}/{name}.git"
    clean_remote_url = f"https://github.com/{owner_login}/{name}.git"

    add_remote = await run_git(["remote", "add", "origin", token_remote_url])
    if add_remote["code"] != 0:
        return {"success": False, "error": f"git remote add failed: {add_remote['stderr']}", "local_repo_created": True, "repo_path": str(repo_dir)}
    push_res = await run_git(["push", "-u", "origin", "main"])
    if push_res["code"] != 0:
        return {"success": False, "error": f"git push failed: {push_res['stderr']}", "local_repo_created": True, "repo_path": str(repo_dir)}
    set_url = await run_git(["remote", "set-url", "origin", clean_remote_url])
    if set_url["code"] != 0:
        return {"success": False, "error": f"git remote set-url failed: {set_url['stderr']}", "local_repo_created": True, "repo_path": str(repo_dir)}

    return {
        "success": True,
        "repo_path": str(repo_dir),
        "default_branch": "main",
        "initial_commit": rev_res["stdout"],
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


async def list_templates(project_type: str = None, **kwargs) -> Dict[str, Any]:
    await asyncio.sleep(0.5)
    templates = {
        "microservice": ["fastapi-microservice", "spring-boot-service", "go-microservice"],
        "library": ["python-library", "typescript-library", "java-library"],
        "frontend": ["nextjs-app", "react-spa", "vue-app"],
    }
    if project_type and project_type in templates:
        return {"success": True, "templates": {project_type: templates[project_type]}}
    return {"success": True, "templates": templates}


async def apply_template(template: str, target_path: str, **kwargs) -> Dict[str, Any]:
    await asyncio.sleep(3)
    return {
        "success": True,
        "files_created": [
            "src/main.py",
            "tests/test_main.py",
            "README.md",
            "Dockerfile",
        ],
        "next_steps": ["Configure environment variables", "Update README"],
    }


async def setup_cicd(repo_path: str, pipeline_type: str = "github-actions", **kwargs) -> Dict[str, Any]:
    await asyncio.sleep(2)
    return {
        "success": True,
        "pipeline_file": f".github/workflows/ci.yml",
        "stages": ["lint", "test", "build", "security-scan"],
    }


async def setup_observability(project_name: str = None, **kwargs) -> Dict[str, Any]:
    await asyncio.sleep(1)
    return {
        "success": True,
        "stack": ["prometheus", "grafana", "otel"],
        "notes": "Integrated default dashboards and traces",
    }


async def run_tests(project_path: str, **kwargs) -> Dict[str, Any]:
    await asyncio.sleep(5)
    return {"success": True, "tests_run": 42, "tests_passed": 42, "coverage": "87%"}


async def generate_k8s_manifests(service_name: str = None, **kwargs) -> Dict[str, Any]:
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


async def create_k8s_namespace(name: str, **kwargs) -> Dict[str, Any]:
    await asyncio.sleep(1)
    return {
        "success": True,
        "namespace": name,
        "resources": ["namespace", "resource-quota", "network-policy"],
    }


async def deploy_to_staging(project: str, version: str = "latest", **kwargs) -> Dict[str, Any]:
    await asyncio.sleep(8)
    return {
        "success": True,
        "environment": "staging",
        "url": f"https://{project}-staging.company.io",
        "version": version,
    }


async def generate_documentation(project_name: str = None, **kwargs) -> Dict[str, Any]:
    await asyncio.sleep(1)
    name = project_name or "project"
    return {
        "success": True,
        "artifacts": [f"docs/{name}-api.md", f"docs/{name}-operations.md"],
    }


async def validate_project_name_and_type(
    project_name: str = None, project_type: str = None, programming_language: str = None, **kwargs
) -> Dict[str, Any]:
    await asyncio.sleep(0)
    if not project_name or not isinstance(project_name, str):
        return {"success": False, "error": "Missing required parameter: project_name"}
    name_pattern = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    if not name_pattern.match(project_name):
        return {
            "success": False,
            "error": "Invalid project name. Use kebab-case: lowercase letters, numbers, and single dashes.",
        }
    allowed_types = {"microservice", "library", "application", "frontend", "backend", "generic"}
    if project_type and project_type not in allowed_types:
        return {
            "success": False,
            "error": f"Unsupported project_type '{project_type}'. Allowed: {sorted(allowed_types)}",
        }
    details = {
        "project_name": project_name,
        "project_type": project_type or "microservice",
        "programming_language": programming_language or "python",
        "policy_checks": ["kebab-case", "allowed_type"],
    }
    return {"success": True, "result": details}


async def search_knowledge_base_for_guidelines(
    project_type: str = None, language: str = None, project_name: str = None, **kwargs
) -> Dict[str, Any]:
    try:
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
            keywords.append(str(project_name).lower())
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
                title = None
                for line in text.splitlines():
                    if line.strip().startswith("#"):
                        title = line.strip().lstrip("# ")
                        break
                if score > 0 or (not keywords and title):
                    snippets: List[str] = []
                    if keywords:
                        for line in text.splitlines():
                            line_l = line.lower()
                            if any(kw in line_l for kw in keywords) and line.strip():
                                snippets.append(line.strip())
                                if len(snippets) >= 3:
                                    break
                    matched.append(
                        {
                            "file": str(file),
                            "title": title or file.name,
                            "score": score,
                            "snippets": snippets,
                        }
                    )
        matched.sort(key=lambda m: (-m.get("score", 0), m.get("title") or ""))
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
                        defaults.append(
                            {
                                "file": str(candidate),
                                "title": default_name.replace("-", " ").replace(".md", "").title(),
                                "score": 0,
                                "snippets": [],
                            }
                        )
            matched = defaults
        return {"success": True, "result": {"searched_files": scanned_files, "matches": matched[:10]}}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==== Tool Specs ====


BUILTIN_TOOLS: List[ToolSpec] = [
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
        name="validate_project_name_and_type",
        description="Validate project name and type",
        input_schema={
            "type": "object",
            "properties": {
                "project_name": {"type": "string"},
                "project_type": {"type": "string"},
                "programming_language": {"type": "string"},
            },
            "required": ["project_name"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        func=validate_project_name_and_type,
        is_async=True,
        timeout=5,
        aliases=["project-validator"],
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
    
    ToolSpec(
        name="list_templates",
        description="List available templates",
        input_schema={
            "type": "object",
            "properties": {"project_type": {"type": "string"}},
            "required": [],
            "additionalProperties": True,
        },
        output_schema={"type": "object"},
        func=list_templates,
        is_async=True,
        timeout=5,
        aliases=[],
    ),
    ToolSpec(
        name="apply_template",
        description="Apply project template",
        input_schema={
            "type": "object",
            "properties": {"template": {"type": "string"}, "target_path": {"type": "string"}},
            "required": ["template", "target_path"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        func=apply_template,
        is_async=True,
        timeout=15,
        aliases=["template-applier"],
    ),
    ToolSpec(
        name="setup_cicd_pipeline",
        description="Setup CI/CD pipeline",
        input_schema={
            "type": "object",
            "properties": {"repo_path": {"type": "string"}, "pipeline_type": {"type": "string"}},
            "required": ["repo_path"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        func=setup_cicd,
        is_async=True,
        timeout=20,
        aliases=["ci-cd-configurator"],
    ),
    ToolSpec(
        name="run_initial_tests",
        description="Run initial test suite",
        input_schema={
            "type": "object",
            "properties": {"project_path": {"type": "string"}},
            "required": ["project_path"],
            "additionalProperties": True,
        },
        output_schema={"type": "object"},
        func=run_tests,
        is_async=True,
        timeout=30,
        aliases=["test-runner"],
    ),
    ToolSpec(
        name="create_k8s_namespace",
        description="Create K8s namespace",
        input_schema={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": True,
        },
        output_schema={"type": "object"},
        func=create_k8s_namespace,
        is_async=True,
        timeout=10,
        aliases=[],
    ),
    ToolSpec(
        name="deploy_to_staging",
        description="Deploy to staging",
        input_schema={
            "type": "object",
            "properties": {"project": {"type": "string"}, "version": {"type": "string"}},
            "required": ["project"],
            "additionalProperties": True,
        },
        output_schema={"type": "object"},
        func=deploy_to_staging,
        is_async=True,
        timeout=45,
        aliases=["k8s-deployer"],
    ),
    ToolSpec(
        name="search_knowledge_base_for_guidelines",
        description="Searches local knowledge base for guidelines relevant to the project",
        input_schema={
            "type": "object",
            "properties": {
                "project_type": {"type": "string"},
                "language": {"type": "string"},
                "project_name": {"type": "string"},
            },
            "required": [],
            "additionalProperties": True,
        },
        output_schema={"type": "object"},
        func=search_knowledge_base_for_guidelines,
        is_async=True,
        timeout=10,
        aliases=["search_knowledge_base", "kb-search", "search-guidelines"],
    ),
    ToolSpec(
        name="setup_observability",
        description="Setup monitoring & logging",
        input_schema={
            "type": "object",
            "properties": {"project_name": {"type": "string"}},
            "required": [],
            "additionalProperties": True,
        },
        output_schema={"type": "object"},
        func=setup_observability,
        is_async=True,
        timeout=10,
        aliases=["observability-integrator"],
    ),
    ToolSpec(
        name="generate_k8s_manifests",
        description="Generate K8s manifests",
        input_schema={
            "type": "object",
            "properties": {"service_name": {"type": "string"}},
            "required": [],
            "additionalProperties": True,
        },
        output_schema={"type": "object"},
        func=generate_k8s_manifests,
        is_async=True,
        timeout=10,
        aliases=["k8s-manifest-generator"],
    ),
    ToolSpec(
        name="generate_documentation",
        description="Generate documentation",
        input_schema={
            "type": "object",
            "properties": {"project_name": {"type": "string"}},
            "required": [],
            "additionalProperties": True,
        },
        output_schema={"type": "object"},
        func=generate_documentation,
        is_async=True,
        timeout=10,
        aliases=["doc-generator"],
    ),
]



BUILTIN_TOOLS_SIMPLIFIED: List[ToolSpec] = [
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
        name="validate_project_name_and_type",
        description="Validate project name and type",
        input_schema={
            "type": "object",
            "properties": {
                "project_name": {"type": "string"},
                "project_type": {"type": "string"},
                "programming_language": {"type": "string"},
            },
            "required": ["project_name"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        func=validate_project_name_and_type,
        is_async=True,
        timeout=5,
        aliases=["project-validator"],
    )
]

# Expose combined tool list for agent construction where needed
ALL_TOOLS: List[ToolSpec] = BUILTIN_TOOLS


# ===== Sub-Agent Wrapper(s) as Tools =====
async def run_sub_agent(
    *,
    task: str,
    inputs: Dict[str, Any] | None = None,
    shared_context: Dict[str, Any] | None = None,
    allowed_tools: List[str] | None = None,
    budget: Dict[str, Any] | None = None,
    resume_token: str | None = None,
    answers: Dict[str, Any] | None = None,
    agent_name: str | None = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Run a constrained sub-agent and return either a patch or need_user_input.

    This wrapper expects the hosting orchestrator to pass in the orchestrator's LLMProvider via kwargs['llm']
    and the base system prompt via kwargs['system_prompt'] for consistency.
    """
    llm: LLMProvider | None = kwargs.get("llm")
    system_prompt: str = kwargs.get("system_prompt") or ""
    if llm is None:
        return {"success": False, "error": "Missing llm provider for sub-agent"}

    # Construct tool whitelist index from BUILTIN_TOOLS
    allow = [t for t in BUILTIN_TOOLS if (not allowed_tools) or (t.name in allowed_tools)]
    subagent = ReActAgent(system_prompt=None, llm=llm, tools=allow, max_steps=int((budget or {}).get("max_steps", 12)), mission=system_prompt)

    # Seed minimal context (ephemeral + child-session) to avoid state collision
    parent_sid = (shared_context or {}).get("session_id") or "no-session"
    subagent.session_id = f"{parent_sid}:sub:{(agent_name or 'subagent')}"
    subagent.context = {
        "user_request": task,
        "known_answers_text": (shared_context or {}).get("known_answers_text", ""),
        "facts": (shared_context or {}).get("facts", {}),
        "version": int((shared_context or {}).get("version", 1)),
        "suppress_markdown": True,
        "ephemeral_state": True,
        # tag for logging and ownership
        "agent_name": agent_name or "subagent",
    }

    # Run a short loop
    transcript: List[str] = []
    async for chunk in subagent.process_request(task, session_id=subagent.session_id):
        transcript.append(chunk)

    # Inspect sub-agent state
    if subagent.context.get("awaiting_user_input"):
        return {
            "success": False,
            "need_user_input": subagent.context.get("awaiting_user_input"),
            "state_token": "opaque",  # kept simple for v1
        }

    # Build a minimal patch reflecting only status updates against master tasks
    patch = {
        "base_version": int((shared_context or {}).get("version", 1)),
        "agent_name": agent_name or "subagent",
        "ops": []
    }
    master_tasks = list((shared_context or {}).get("tasks", []))
    target_task_id = str((shared_context or {}).get("target_task_id") or "").strip() or None
    wrapper_norm = (agent_name or "subagent").strip().lower().replace("-", "_").replace(" ", "_")
    def _norm(s: str) -> str:
        return (s or "").strip().lower().replace("-", "_").replace(" ", "_")
    def _find_master_task_id_by_tool(tool_name: str) -> str | None:
        # 0) Deterministic: prefer explicitly given target_task_id
        if target_task_id:
            return target_task_id
        norm = _norm(tool_name)
        # 1) Direct tool match
        for mt in master_tasks:
            tt = _norm(mt.get("tool"))
            if tt and tt == norm:
                return str(mt.get("id"))
        # 2) Prefixed tool match: wrapper.action
        for mt in master_tasks:
            tt = _norm(mt.get("tool"))
            if tt and tt == f"{wrapper_norm}.{norm}":
                return str(mt.get("id"))
        # 3) Fallback: match by executor_id + action
        for mt in master_tasks:
            exec_id = _norm(mt.get("executor_id"))
            action = _norm(mt.get("action"))
            if action == norm and (not exec_id or exec_id == wrapper_norm):
                return str(mt.get("id"))
        return None
    for t in subagent.context.get("tasks", []):
        status = str(t.get("status","")).upper()
        tool_name = t.get("tool")
        if tool_name and status in {"IN_PROGRESS","COMPLETED"}:
            tid = _find_master_task_id_by_tool(tool_name)
            if tid:
                patch["ops"].append({"op":"update","task_id":tid,"fields":{"status":status}})

    return {"success": True, "patch": patch, "result": {"transcript": "".join(transcript)}}


# Example sub-agent ToolSpec (scaffolder)
AGENT_TOOLS: List[ToolSpec] = [
    ToolSpec(
        name="agent_scaffold_webservice",
        description="Sub-agent: scaffolds a webservice using whitelisted tools",
        input_schema={
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "inputs": {"type": "object"},
                "shared_context": {"type": "object"},
                "allowed_tools": {"type": "array", "items": {"type": "string"}},
                "budget": {"type": "object"},
                "resume_token": {"type": "string"},
                "answers": {"type": "object"},
            },
            "required": ["task"],
            "additionalProperties": True,
        },
        output_schema={"type": "object"},
        func=run_sub_agent,
        is_async=True,
        timeout=120,
        aliases=["agent_scaffold", "agent_webservice"],
    )
]

ALL_TOOLS_WITH_AGENTS: List[ToolSpec] = BUILTIN_TOOLS + AGENT_TOOLS