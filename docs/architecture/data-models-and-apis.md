# Data Models and APIs

## Data Models

The system uses several data persistence patterns:

- **Session State**: See `prototype/statemanager.py` - Python objects serialized to pickle files in `./agent_states/`
- **Todo Lists**: See `prototype/todolist_md.py` - Structured markdown with YAML frontmatter in `./checklists/`
- **Feedback Data**: See `prototype/feedback_collector.py` - JSON files with timestamps in `./feedback/`
- **Tool Specifications**: See `prototype/tools.py` - Pydantic models with JSON schemas

## API Specifications

- **FastAPI Backend**: See `backend/app/main.py` and route modules
  - `/health` - Service health check
  - `/agent-systems` - Agent configuration CRUD
  - `/sessions` - Session management and lifecycle
  - `/sessions/{sid}/messages` - Message sending
  - `/sessions/{sid}/stream` - SSE event streaming
  - `/sessions/{sid}/state` - Session state inspection
  - `/sessions/{sid}/artifacts/todolist.md` - Todo list download
  - `/tools` - Tool inventory and schemas