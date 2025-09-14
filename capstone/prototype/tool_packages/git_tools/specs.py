"""Git tools specifications."""

from typing import List
from ...tools import ToolSpec
from .git_ops import (
    git_init_repo,
    github_create_repo,
    git_set_remote,
    create_repository,
    setup_branch_protection,
    create_git_repository_with_branch_protection,
    git_commit,
    git_push,
    git_add_files,
)

GIT_TOOLS: List[ToolSpec] = [
    ToolSpec(
        name="git_init_repo",
        description="Initialize a local git repository under repos/ without commits or remotes",
        input_schema={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "repo_path": {"type": "string"},
                "default_branch": {"type": "string"},
                "error": {"type": "string"},
            },
        },
        func=git_init_repo,
        is_async=True,
        timeout=10,
        aliases=[],
    ),
    ToolSpec(
        name="github_create_repo",
        description="Create a GitHub repository via API only (no local git side-effects)",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "visibility": {"type": "string", "enum": ["private", "public"]},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "html_url": {"type": "string"},
                "clone_url": {"type": "string"},
                "owner": {"type": "string"},
                "error": {"type": "string"},
            },
        },
        func=github_create_repo,
        is_async=True,
        timeout=20,
        aliases=[],
    ),
    ToolSpec(
        name="git_set_remote",
        description="Add or update a git remote for a repository",
        input_schema={
            "type": "object",
            "properties": {
                "repo_path": {"type": "string"},
                "remote_url": {"type": "string"},
                "name": {"type": "string", "default": "origin"},
            },
            "required": ["repo_path", "remote_url"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "message": {"type": "string"},
                "error": {"type": "string"},
            },
        },
        func=git_set_remote,
        is_async=True,
        timeout=10,
        aliases=["set_remote"],
    ),
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
    ToolSpec(
        name="git_commit",
        description="Create a Git commit in the specified repository",
        input_schema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the Git repository"
                },
                "message": {
                    "type": "string",
                    "description": "Commit message"
                }
            },
            "required": ["repo_path", "message"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "repo_path": {"type": "string"},
                "commit_hash": {"type": ["string", "null"]},
                "message": {"type": "string"},
                "error": {"type": "string"}
            }
        },
        func=git_commit,
        is_async=True,
        timeout=30,
        aliases=["commit"],
    ),
    ToolSpec(
        name="git_push",
        description="Push changes to remote repository",
        input_schema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the Git repository"
                },
                "remote": {
                    "type": "string",
                    "description": "Remote name (default: origin)",
                    "default": "origin"
                },
                "branch": {
                    "type": "string",
                    "description": "Branch name (default: main)",
                    "default": "main"
                }
            },
            "required": ["repo_path"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "repo_path": {"type": "string"},
                "remote": {"type": "string"},
                "branch": {"type": "string"},
                "message": {"type": "string"},
                "error": {"type": "string"}
            }
        },
        func=git_push,
        is_async=True,
        timeout=60,
        aliases=["push"],
    ),
    ToolSpec(
        name="git_add_files",
        description="Add files to Git staging area",
        input_schema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the Git repository"
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of file paths to add"
                }
            },
            "required": ["repo_path", "files"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "repo_path": {"type": "string"},
                "files": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "message": {"type": "string"},
                "error": {"type": "string"}
            }
        },
        func=git_add_files,
        is_async=True,
        timeout=30,
        aliases=["add_files"],
    ),
]