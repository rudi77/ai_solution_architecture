"""Project operations implementation."""

from __future__ import annotations
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import asyncio
import structlog
from ..common import get_working_directory, validate_path, get_relative_path, get_repos_directory
from ..common.execution_guard import validate_working_directory

logger = structlog.get_logger()


async def list_templates(project_type: str = None, **kwargs) -> Dict[str, Any]:
    """List available project templates."""
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
    """Apply a project template to a target directory."""
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


async def validate_project_name_and_type(
    project_name: str = None, project_type: str = None, programming_language: str = None, **kwargs
) -> Dict[str, Any]:
    """Validate project name and type according to standards."""
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
    """Search knowledge base for relevant guidelines and standards."""
    try:
        repo_root = get_working_directory()
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


async def discover_templates(template_dir: str = "./templates", **kwargs) -> Dict[str, Any]:
    """Discover available templates in the template directory.
    
    Args:
        template_dir: Directory containing template files
        
    Returns:
        Dict with success status and list of templates
    """
    logger.info("discover_templates_start", template_dir=template_dir)
    
    try:
        templates_path = Path(template_dir)
        
        if not templates_path.exists():
            return {
                "success": False,
                "error": f"Template directory does not exist: {template_dir}"
            }
        
        templates = []
        for template_file in templates_path.glob("*.md"):
            if template_file.name == "template-index.md":
                continue
                
            try:
                content = template_file.read_text(encoding="utf-8")
                # Extract template metadata from markdown
                name = template_file.stem
                description = ""
                architecture = ""
                keywords = []
                
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    line = line.strip()
                    if line.startswith("## Description"):
                        if i + 1 < len(lines):
                            description = lines[i + 1].strip()
                    elif line.startswith("## Architecture Pattern"):
                        # Extract architecture patterns
                        for j in range(i + 1, min(i + 5, len(lines))):
                            arch_line = lines[j].strip()
                            if arch_line.startswith("- "):
                                architecture += arch_line[2:] + " "
                
                # Generate keywords from filename and content
                name_parts = name.replace("-", " ").split()
                keywords.extend(name_parts)
                keywords.extend([part.lower() for part in name_parts])
                
                # Add common framework keywords
                if "fastapi" in name.lower():
                    keywords.extend(["api", "rest", "microservice", "async"])
                if "flask" in name.lower():
                    keywords.extend(["web", "wsgi", "orm"])
                if "csharp" in name.lower() or "dotnet" in name.lower():
                    keywords.extend(["api", "webapi", ".net", "c#"])
                
                templates.append({
                    "name": name,
                    "file": str(template_file),
                    "description": description,
                    "architecture": architecture.strip(),
                    "keywords": list(set(keywords))  # Remove duplicates
                })
                
            except Exception as e:
                logger.warning("Failed to parse template", file=str(template_file), error=str(e))
                continue
        
        logger.info("discover_templates_success", count=len(templates))
        return {
            "success": True,
            "templates": templates,
            "count": len(templates)
        }
        
    except Exception as e:
        error = f"Failed to discover templates: {str(e)}"
        logger.error("discover_templates_failed", error=error)
        return {"success": False, "error": error}


async def select_template(user_input: str, template_dir: str = "./templates", **kwargs) -> Dict[str, Any]:
    """Select the best matching template based on user input.
    
    Args:
        user_input: User's project description/request
        template_dir: Directory containing template files
        
    Returns:
        Dict with template selection result and any clarification needed
    """
    logger.info("select_template_start", user_input=user_input, template_dir=template_dir)
    
    try:
        # Discover available templates
        discovery_result = await discover_templates(template_dir)
        if not discovery_result["success"]:
            return discovery_result
        
        templates = discovery_result["templates"]
        if not templates:
            return {
                "success": False,
                "error": "No templates found in template directory"
            }
        
        # Normalize user input
        input_lower = user_input.lower()
        input_words = re.findall(r'\w+', input_lower)
        
        # Score templates based on keyword matches
        scored_templates = []
        for template in templates:
            score = 0
            matched_keywords = []
            
            for keyword in template["keywords"]:
                if keyword.lower() in input_lower:
                    score += 1
                    matched_keywords.append(keyword)
            
            # Bonus points for exact matches
            for word in input_words:
                if word in template["keywords"]:
                    score += 0.5
            
            if score > 0:
                scored_templates.append({
                    **template,
                    "score": score,
                    "matched_keywords": matched_keywords
                })
        
        # Sort by score (highest first)
        scored_templates.sort(key=lambda x: x["score"], reverse=True)
        
        if not scored_templates:
            return {
                "success": False,
                "error": f"No templates match the input: {user_input}",
                "available_templates": [t["name"] for t in templates]
            }
        
        # Check for clear winner vs need for clarification
        if len(scored_templates) == 1:
            # Single match - proceed
            selected = scored_templates[0]
            logger.info("template_selected", template=selected["name"], score=selected["score"])
            return {
                "success": True,
                "selected_template": selected,
                "needs_clarification": False,
                "message": f"Selected template: {selected['name']}"
            }
        
        # Multiple matches - check if top score is significantly higher
        top_score = scored_templates[0]["score"]
        second_score = scored_templates[1]["score"] if len(scored_templates) > 1 else 0
        
        if top_score > second_score + 1:  # Clear winner
            selected = scored_templates[0]
            logger.info("template_selected_clear_winner", template=selected["name"], score=selected["score"])
            return {
                "success": True,
                "selected_template": selected,
                "needs_clarification": False,
                "message": f"Selected template: {selected['name']} (best match)"
            }
        
        # Need clarification - return top matches
        top_matches = [t for t in scored_templates if t["score"] >= top_score - 0.5][:3]
        
        logger.info("template_clarification_needed", matches=len(top_matches))
        return {
            "success": True,
            "selected_template": None,
            "needs_clarification": True,
            "top_matches": top_matches,
            "message": f"Found {len(top_matches)} matching templates. Please clarify your preference.",
            "clarification_options": [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "architecture": t["architecture"]
                }
                for t in top_matches
            ]
        }
        
    except Exception as e:
        error = f"Failed to select template: {str(e)}"
        logger.error("select_template_failed", error=error)
        return {"success": False, "error": error}


@validate_working_directory
async def apply_project_template(template_file: str, target_dir: str, project_name: str, **kwargs) -> Dict[str, Any]:
    """Apply a template to create project structure and files.
    
    Args:
        template_file: Path to the template markdown file
        target_dir: Target directory for the project
        project_name: Name of the project
        
    Returns:
        Dict with success status and list of created files
    """
    logger.info("apply_project_template_start", template_file=template_file, target_dir=target_dir, project_name=project_name)
    
    try:
        template_path = Path(template_file)
        target_path = Path(target_dir)
        
        # Resolve/validate target path:
        # - If relative, validate within working directory
        # - If absolute and outside the working directory, redirect to repos/<project_name>
        if not target_path.is_absolute():
            try:
                target_path = validate_path(target_dir)
            except ValueError as e:
                return {"success": False, "error": str(e)}
        else:
            base_dir = get_working_directory().resolve()
            try:
                _ = target_path.resolve().relative_to(base_dir)
            except Exception:
                logger.warning(
                    "absolute_target_outside_base",
                    provided=str(target_path),
                    base=str(base_dir),
                    action="redirect_to_repos"
                )
                target_path = get_repos_directory() / project_name
        
        if not template_path.exists():
            return {
                "success": False,
                "error": f"Template file does not exist: {template_file}"
            }
        
        # Read template content
        template_content = template_path.read_text(encoding="utf-8")
        
        # Parse template to extract file contents
        created_files = []
        
        # Extract code blocks from markdown
        import re
        
        # Find all code blocks with file paths
        file_pattern = r'### (.+?)\n```(?:\w+)?\n(.*?)\n```'
        matches = re.findall(file_pattern, template_content, re.DOTALL)
        
        for file_path, file_content in matches:
            # Clean up file path
            file_path = file_path.strip()
            
            # Skip non-file entries (like titles or descriptions)
            if not ('.' in file_path or file_path.endswith('.py') or file_path.endswith('.cs') or 
                    file_path.endswith('.md') or file_path.endswith('.txt') or file_path.endswith('.json') or
                    file_path.endswith('.yml') or file_path.endswith('.yaml') or file_path.endswith('.dockerfile') or
                    'Dockerfile' in file_path or 'requirements.txt' in file_path or '.gitignore' in file_path):
                continue
            
            # Create full target path
            full_path = target_path / file_path
            
            # Ensure directory exists
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Replace placeholders in content
            processed_content = file_content.replace("{project_name}", project_name)
            processed_content = processed_content.replace("{PROJECT_NAME}", project_name.upper())
            processed_content = processed_content.replace("{Project_Name}", project_name.title())
            
            # Write file
            full_path.write_text(processed_content, encoding="utf-8")
            created_files.append(str(full_path))
            
            logger.info("file_created", path=str(full_path), size=len(processed_content))
        
        # Create additional structure files if needed (like __init__.py files)
        if any('python' in template_file.lower() for template_file in [template_file]):
            # Add __init__.py files to Python packages
            python_dirs = set()
            for file_path in created_files:
                if file_path.endswith('.py'):
                    dir_path = Path(file_path).parent
                    python_dirs.add(dir_path)
                    # Also add parent directories if they contain Python files
                    for parent in dir_path.parents:
                        if parent == target_path:
                            break
                        python_dirs.add(parent)
            
            for py_dir in python_dirs:
                init_file = py_dir / "__init__.py"
                if not init_file.exists():
                    init_file.write_text("", encoding="utf-8")
                    created_files.append(str(init_file))
        
        logger.info("apply_project_template_success", files_created=len(created_files))
        return {
            "success": True,
            "files_created": created_files,
            "project_path": str(target_path),
            "message": f"Project template applied successfully. Created {len(created_files)} files."
        }
        
    except Exception as e:
        error = f"Failed to apply template: {str(e)}"
        logger.error("apply_project_template_failed", error=error)
        return {"success": False, "error": error}


async def apply_template_and_commit(
    template_file: str, 
    target_dir: str, 
    project_name: str, 
    commit_message: str = "Apply template: generate project structure",
    **kwargs
) -> Dict[str, Any]:
    """Apply template and automatically commit all generated files with proper path handling.
    
    This is a wrapper function that combines template application with git operations,
    handling the file path conversion that was causing issues in the agent workflow.
    
    Args:
        template_file: Path to the template markdown file
        target_dir: Target directory for the project (should be a git repository)
        project_name: Name of the project
        commit_message: Git commit message
        
    Returns:
        Dict with success status, commit info, and file details
    """
    logger.info("apply_template_and_commit_start", 
                template_file=template_file, 
                target_dir=target_dir, 
                project_name=project_name)
    
    try:
        from pathlib import Path
        
        # Step 1: Apply the template
        template_result = await apply_project_template(
            template_file=template_file,
            target_dir=target_dir,
            project_name=project_name
        )
        
        if not template_result["success"]:
            return template_result
        
        created_files = template_result["files_created"]
        logger.info("template_applied_successfully", files_count=len(created_files))
        
        # Step 2: Convert absolute paths to relative paths for git
        repo_path_obj = Path(target_dir)
        relative_files = []
        
        for file_path in created_files:
            path_obj = Path(file_path)
            if path_obj.is_absolute():
                try:
                    rel_path = path_obj.relative_to(repo_path_obj)
                    relative_files.append(str(rel_path))
                except ValueError:
                    # File is not within repo_path, use original path
                    relative_files.append(file_path)
            else:
                relative_files.append(file_path)
        
        logger.info("file_paths_converted", 
                   absolute_count=len(created_files),
                   relative_count=len(relative_files))
        
        # Step 3: Add files to git staging area
        from ..git_tools.git_ops import git_add_files, git_commit
        
        add_result = await git_add_files(repo_path=target_dir, files=relative_files)
        if not add_result["success"]:
            return {
                "success": False,
                "error": f"Failed to add files to git: {add_result.get('error')}",
                "template_applied": True,
                "files_created": created_files
            }
        
        logger.info("files_added_to_git", files_count=len(relative_files))
        
        # Step 4: Commit the changes
        commit_result = await git_commit(repo_path=target_dir, message=commit_message)
        if not commit_result["success"]:
            return {
                "success": False,
                "error": f"Failed to commit changes: {commit_result.get('error')}",
                "template_applied": True,
                "files_created": created_files,
                "files_added": True
            }
        
        logger.info("template_and_commit_success", 
                   commit_hash=commit_result.get("commit_hash"),
                   files_count=len(created_files))
        
        return {
            "success": True,
            "files_created": created_files,
            "relative_files": relative_files,
            "project_path": str(repo_path_obj),
            "commit_hash": commit_result.get("commit_hash"),
            "commit_message": commit_message,
            "message": f"Template applied and committed successfully. Created {len(created_files)} files."
        }
        
    except Exception as e:
        error = f"Failed to apply template and commit: {str(e)}"
        logger.error("apply_template_and_commit_failed", error=error)
        return {"success": False, "error": error}