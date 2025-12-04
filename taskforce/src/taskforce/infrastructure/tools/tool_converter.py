"""
Tool Converter - Converts ToolProtocol instances to OpenAI function calling format.

This module provides utilities for converting internal tool definitions
to the format required by OpenAI's native function calling API.
"""

from typing import Any

from taskforce.core.interfaces.tools import ToolProtocol


def tools_to_openai_format(tools: dict[str, ToolProtocol]) -> list[dict[str, Any]]:
    """
    Convert internal tool definitions to OpenAI function calling format.

    This function transforms ToolProtocol instances into the JSON Schema
    format required by the OpenAI API's native function calling feature.

    Args:
        tools: Dictionary mapping tool names to ToolProtocol instances

    Returns:
        List of tool definitions in OpenAI format:
        [
            {
                "type": "function",
                "function": {
                    "name": "tool_name",
                    "description": "Tool description",
                    "parameters": { JSON Schema }
                }
            },
            ...
        ]

    Example:
        >>> from taskforce.infrastructure.tools.native.file_tools import FileReadTool
        >>> tools = {"file_read": FileReadTool()}
        >>> openai_tools = tools_to_openai_format(tools)
        >>> print(openai_tools[0]["function"]["name"])
        'file_read'
    """
    openai_tools = []

    for tool in tools.values():
        openai_tool = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters_schema,
            },
        }
        openai_tools.append(openai_tool)

    return openai_tools


def tool_result_to_message(
    tool_call_id: str, tool_name: str, result: dict[str, Any]
) -> dict[str, Any]:
    """
    Convert a tool execution result to an OpenAI tool message format.

    After executing a tool, the result must be added to the message history
    in the specific format expected by the OpenAI API.

    Args:
        tool_call_id: The unique ID from the tool_call request
        tool_name: Name of the executed tool
        result: Result dictionary from tool.execute()

    Returns:
        Message dict in OpenAI tool response format:
        {
            "role": "tool",
            "tool_call_id": "...",
            "name": "tool_name",
            "content": "JSON string of result"
        }

    Example:
        >>> result = {"success": True, "output": "File contents..."}
        >>> msg = tool_result_to_message("call_abc123", "file_read", result)
        >>> print(msg["role"])
        'tool'
    """
    import json

    # Serialize result to JSON string for the message content
    content = json.dumps(result, ensure_ascii=False, default=str)

    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "name": tool_name,
        "content": content,
    }


def assistant_tool_calls_to_message(tool_calls: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Create an assistant message with tool calls for message history.

    When the LLM returns tool_calls, we need to add the assistant's
    response (with tool_calls) to the message history before adding
    the tool results.

    Args:
        tool_calls: List of tool calls from LLM response

    Returns:
        Assistant message dict with tool_calls:
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [...]
        }
    """
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": tool_calls,
    }

