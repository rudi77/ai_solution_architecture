"""CI/CD tools specifications."""

from typing import List
from ...tools import ToolSpec
from .cicd_ops import setup_cicd, run_tests, setup_observability

CICD_TOOLS: List[ToolSpec] = [
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
]