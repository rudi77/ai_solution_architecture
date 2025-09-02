from __future__ import annotations

from typing import List

try:
	from ...prototype.tools import ToolSpec  # type: ignore
	from ...prototype.tools_builtin import BUILTIN_TOOLS  # type: ignore
except Exception:  # pragma: no cover
	from capstone.prototype.tools import ToolSpec  # type: ignore
	from capstone.prototype.tools_builtin import BUILTIN_TOOLS  # type: ignore


def get_idp_tools() -> List["ToolSpec"]:
	"""Return the built-in IDP tools for example composition."""
	return BUILTIN_TOOLS
