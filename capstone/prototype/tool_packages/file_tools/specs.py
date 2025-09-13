"""File tools specifications."""

from __future__ import annotations
from typing import List

from ...tools import ToolSpec
from .file_ops import (
    file_create,
    file_read,
    file_write,
    file_edit,
    file_delete,
    file_list_directory,
)


FILE_TOOLS: List[ToolSpec] = [
    ToolSpec(
        name="file_create",
        description="Create a new file with specified content",
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to create"
                },
                "content": {
                    "type": "string",
                    "description": "File content to write"
                }
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "path": {"type": "string"},
                "size": {"type": "integer"},
                "message": {"type": "string"},
                "error": {"type": "string"}
            }
        },
        func=file_create,
        is_async=True,
        timeout=30,
        aliases=["create_file"],
    ),
    
    ToolSpec(
        name="file_read",
        description="Read content from a file",
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to read"
                }
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "path": {"type": "string"},
                "content": {"type": "string"},
                "size": {"type": "integer"},
                "error": {"type": "string"}
            }
        },
        func=file_read,
        is_async=True,
        timeout=30,
        aliases=["read_file"],
    ),
    
    ToolSpec(
        name="file_write",
        description="Write content to a file (overwrites existing content)",
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to write"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write"
                }
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "path": {"type": "string"},
                "size": {"type": "integer"},
                "message": {"type": "string"},
                "error": {"type": "string"}
            }
        },
        func=file_write,
        is_async=True,
        timeout=30,
        aliases=["write_file"],
    ),
    
    ToolSpec(
        name="file_edit",
        description="Edit a file by replacing old_content with new_content",
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to edit"
                },
                "old_content": {
                    "type": "string",
                    "description": "Content to replace"
                },
                "new_content": {
                    "type": "string",
                    "description": "Replacement content"
                }
            },
            "required": ["path", "old_content", "new_content"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "path": {"type": "string"},
                "old_size": {"type": "integer"},
                "new_size": {"type": "integer"},
                "message": {"type": "string"},
                "error": {"type": "string"}
            }
        },
        func=file_edit,
        is_async=True,
        timeout=30,
        aliases=["edit_file"],
    ),
    
    ToolSpec(
        name="file_delete",
        description="Delete a file",
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to delete"
                }
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "path": {"type": "string"},
                "message": {"type": "string"},
                "error": {"type": "string"}
            }
        },
        func=file_delete,
        is_async=True,
        timeout=30,
        aliases=["delete_file"],
    ),
    
    ToolSpec(
        name="file_list_directory",
        description="List directory contents with metadata. Returns list of tuples: (name, type, size) where type is 'File' or 'Directory' and size is bytes for files or None for directories",
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list"
                }
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "path": {"type": "string"},
                "entries": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": [
                            {"type": "string"},  # name
                            {"type": "string"},  # type
                            {"type": ["integer", "null"]}  # size
                        ]
                    }
                },
                "count": {"type": "integer"},
                "error": {"type": "string"}
            }
        },
        func=file_list_directory,
        is_async=True,
        timeout=30,
        aliases=["list_directory", "ls"],
    ),
]