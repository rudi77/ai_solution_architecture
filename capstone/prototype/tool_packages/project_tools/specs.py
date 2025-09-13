"""Project tools specifications."""

from typing import List
from ...tools import ToolSpec
from .project_ops import (
    list_templates,
    apply_template,
    validate_project_name_and_type,
    search_knowledge_base_for_guidelines,
    discover_templates,
    select_template,
    apply_project_template,
)

PROJECT_TOOLS: List[ToolSpec] = [
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
        name="discover_templates",
        description="Discover available templates in the template directory",
        input_schema={
            "type": "object",
            "properties": {
                "template_dir": {
                    "type": "string",
                    "description": "Directory containing template files",
                    "default": "./templates"
                }
            },
            "required": [],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "templates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "file": {"type": "string"},
                            "description": {"type": "string"},
                            "architecture": {"type": "string"},
                            "keywords": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        }
                    }
                },
                "count": {"type": "integer"},
                "error": {"type": "string"}
            }
        },
        func=discover_templates,
        is_async=True,
        timeout=10,
        aliases=["find_templates"],
    ),
    ToolSpec(
        name="select_template",
        description="Select the best matching template based on user input with clarification support",
        input_schema={
            "type": "object",
            "properties": {
                "user_input": {
                    "type": "string",
                    "description": "User's project description/request"
                },
                "template_dir": {
                    "type": "string",
                    "description": "Directory containing template files",
                    "default": "./templates"
                }
            },
            "required": ["user_input"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "selected_template": {"type": ["object", "null"]},
                "needs_clarification": {"type": "boolean"},
                "top_matches": {
                    "type": "array",
                    "items": {"type": "object"}
                },
                "clarification_options": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                            "architecture": {"type": "string"}
                        }
                    }
                },
                "message": {"type": "string"},
                "error": {"type": "string"},
                "available_templates": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            }
        },
        func=select_template,
        is_async=True,
        timeout=15,
        aliases=["choose_template", "match_template"],
    ),
    ToolSpec(
        name="apply_project_template",
        description="Apply a template to create project structure and files",
        input_schema={
            "type": "object",
            "properties": {
                "template_file": {
                    "type": "string",
                    "description": "Path to the template markdown file"
                },
                "target_dir": {
                    "type": "string",
                    "description": "Target directory for the project"
                },
                "project_name": {
                    "type": "string",
                    "description": "Name of the project"
                }
            },
            "required": ["template_file", "target_dir", "project_name"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "files_created": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "project_path": {"type": "string"},
                "message": {"type": "string"},
                "error": {"type": "string"}
            }
        },
        func=apply_project_template,
        is_async=True,
        timeout=30,
        aliases=["create_from_template", "generate_project"],
    ),
]