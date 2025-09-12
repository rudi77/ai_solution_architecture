# Quick Reference - Key Files and Entry Points

## Critical Files for Understanding the System

- **Main Entry Points**: 
  - `capstone/prototype/idp.py` - CLI entry point with Prometheus server (port 8070)
  - `capstone/backend/app/main.py` - FastAPI backend entry point
  - `capstone/frontend/streamlit_app.py` - Streamlit frontend application
- **Core Agent**: `capstone/prototype/agent.py` - ReAct agent with plan-first heuristic
- **Tool System**: `capstone/prototype/tools.py`, `capstone/prototype/tools_builtin.py`
- **Configuration**: `capstone/pyproject.toml`, `CLAUDE.md` (project instructions)
- **State Management**: `capstone/prototype/statemanager.py`
- **LLM Integration**: `capstone/prototype/llm_provider.py`

## Key Business Logic Areas

- **ReAct Agent Loop**: Plan → Tool Selection → Execution → Observation → Re-plan
- **Tool Ecosystem**: Repository creation, CI/CD, K8s deployment, documentation generation
- **State Persistence**: Session state (pickle), Todo lists (markdown), Feedback (JSON)