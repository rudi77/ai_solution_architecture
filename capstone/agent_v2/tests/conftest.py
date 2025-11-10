"""Pytest configuration for agent_v2 tests."""

import sys
from pathlib import Path


# Add workspace root (ai_solution_architecture) to Python path for imports
# This allows importing from capstone.agent_v2.*
WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

