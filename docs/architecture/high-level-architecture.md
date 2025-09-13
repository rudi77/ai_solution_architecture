# High Level Architecture

## Technical Summary

The IDP Copilot is a **monolithic Python application** built around a ReAct agent pattern that automates developer platform workflows. The system follows a plan-first approach where the agent creates structured todo lists before executing tools, providing transparency and interruptability.

## Actual Tech Stack (from pyproject.toml)

| Category  | Technology | Version | Notes                      |
| --------- | ---------- | ------- | -------------------------- |
| Runtime   | Python    | 3.11+   | Windows PowerShell focus   |
| Package Mgmt | uv       | Latest  | Replaces pip/poetry       |
| Web Framework | FastAPI | 0.111.0 | Backend API services      |
| Frontend  | Streamlit | 1.33+   | Demo UI with SSE          |
| AI/LLM    | OpenAI    | 1.40.0+ | Primary LLM provider      |
| AI/LLM    | Anthropic | 0.30.0  | Secondary LLM provider    |
| Observability | Prometheus | 0.20.0 | Metrics (port 8070)    |
| Observability | OpenTelemetry | 1.25.0 | Tracing support       |
| Async Runtime | asyncio  | Built-in | Core async execution     |
| State Mgmt | Pickle   | Built-in | Session persistence      |
| Kubernetes | K8s Python | 30.1.0 | Cluster operations       |
| Git Integration | PyGithub | 2.3.0 | Repository automation   |

## Repository Structure Reality Check

- **Type**: Monorepo with multiple components
- **Package Manager**: uv (modern Python package management)
- **Notable**: Windows PowerShell-centric development environment