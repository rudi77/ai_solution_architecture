"""Documentation tools specifications."""

from typing import List
from ...tools import ToolSpec
from .docs_ops import generate_documentation

DOCS_TOOLS: List[ToolSpec] = [
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