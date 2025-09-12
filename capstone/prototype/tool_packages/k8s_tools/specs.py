"""Kubernetes tools specifications."""

from typing import List
from ...tools import ToolSpec
from .k8s_ops import (
    generate_k8s_manifests,
    create_k8s_namespace,
    deploy_to_staging,
)

K8S_TOOLS: List[ToolSpec] = [
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
]