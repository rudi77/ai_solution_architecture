Ja — trenne dein Webservice sauber in einen eigenen Ordner, z.B. `backend`. Unten ist eine **empfohlene Monorepo-Struktur**, die exakt zu deinem bestehenden Agent-Framework passt und die Stellen berücksichtigt, die dein Code bereits erwartet.

```text
capstone/
├─ prototype/                      # dein Agent-Framework (weiterverwenden)
│  ├─ __init__.py
│  ├─ agent.py
│  ├─ llm_provider.py
│  ├─ tools.py
│  ├─ tools_builtin.py
│  ├─ todolist_md.py
│  ├─ todolist_actions.py
│  ├─ statemanager.py
│  ├─ feedback_collector.py
│  └─ ...                         # (bestehende Module)
│
├─ backend/                        # NEU: Webservice (FastAPI)
│  ├─ app/
│  │  ├─ __init__.py
│  │  ├─ main.py                   # FastAPI-Entry (Health, /tools, /agent-systems, /sessions, /stream, /artifacts)
│  │  ├─ api/
│  │  │  ├─ __init__.py
│  │  │  ├─ agent_systems.py       # POST /agent-systems, GET /agent-systems/{id}
│  │  │  ├─ sessions.py            # POST /sessions, POST /messages, POST /answers, GET /state
│  │  │  ├─ stream.py              # GET /sessions/{sid}/stream (SSE/WebSocket)
│  │  │  └─ artifacts.py           # GET /sessions/{sid}/artifacts/todolist.md
│  │  ├─ core/
│  │  │  ├─ builder.py             # YAML→(Orchestrator+Sub-Agents+Tools) Builder
│  │  │  ├─ registry.py            # AgentSystemRegistry (Factories)
│  │  │  ├─ session_store.py       # {sid → agent instance + paths}
│  │  │  └─ sse.py                 # SSE-Helper (EventSourceResponse)
│  │  ├─ schemas/
│  │  │  ├─ __init__.py
│  │  │  ├─ agent_system.py        # Pydantic: YAML-Schema v1
│  │  │  ├─ session.py             # Session DTOs
│  │  │  ├─ message.py             # Message/Answer DTOs
│  │  │  └─ state.py               # State/Inspection DTOs
│  │  ├─ config.py                 # Env (OPENAI_API_KEY, GITHUB_TOKEN, etc.)
│  │  └─ security.py               # (optional) Auth/JWT
│  │
│  ├─ documents/
│  │  └─ guidelines/               # von search_knowledge_base_for_guidelines gelesen
│  ├─ tests/
│  │  └─ test_e2e.py
│  ├─ pyproject.toml (oder requirements.txt)
│  └─ Dockerfile
│
├─ examples/
│  └─ idp_pack/
│     ├─ prompts/
│     │  ├─ orchestrator.txt
│     │  └─ mission_git.txt
│     └─ idp_tools.py
│
├─ checklists/                     # Ausgabeordner für Todo-List Markdown (vom Agent genutzt)
├─ scripts/
│  └─ run_idp_cli.py               # deine CLI-Demo (kann hierhin)
├─ .env.example                    # OPENAI_API_KEY, GITHUB_TOKEN, …
└─ README.md
```

## Warum diese Struktur?

* **Agent bleibt in `prototype/`**
  Dein `ReActAgent` ist bereits eigenständig, streamt Schritt-Updates via `process_request(...)` (perfekt für SSE/WebSocket) und sollte unverändert als Library genutzt werden. Das Webservice importiert ihn einfach (z.B. `from capstone.prototype.agent import ReActAgent`).&#x20;

* **LLM-Provider-Abstraktion zentral**
  `OpenAIProvider` & Co. liegen weiterhin in `prototype/llm_provider.py` und werden im Backend via `config.py` instanziiert (pro Agent/Session konfigurierbar).&#x20;

* **Tools & ToolSpec wiederverwenden**
  `ToolSpec`, `build_tool_index`, `export_openai_tools` etc. bleiben in `prototype/tools.py` und werden im Backend unter `/tools` exponiert (UI kann damit Form-Validierung machen).&#x20;

* **Builtin-Tools & Knowledge-Scan-Pfade**
  Dein Tool `search_knowledge_base_for_guidelines` scannt u.a. `capstone/backend/documents/guidelines` – deshalb dieser Ordner im Backend. Alternativ funktioniert auch `capstone/documents/guidelines`.&#x20;

* **Todo-List Markdown-Ablage**
  Der deterministische Renderer schreibt standardmäßig nach `./checklists/todolist_<session>.md`. Lege den Ordner **einmal** auf Repo-Root an (oder setze später einen konfigurierbaren `base_dir`).&#x20;
  (Falls du den „LLM-Editor“-Weg nutzen willst, liegen die Wrapper in `todolist_actions.py`—optional.)&#x20;

* **Examples bleiben unter `examples/`**
  Deine CLI-Demo lädt Prompts/Tools aus `examples/idp_pack`. Das passt, solange der Importpfad (`capstone.examples.idp_pack...`) gleich bleibt.&#x20;

## Import- und Laufzeit-Hinweise

* **Pythons Paketname**: Stelle sicher, dass der Repo-Root als `capstone/`-Package dient, damit Importe wie `capstone.prototype.agent` überall funktionieren (Backend, CLI, Tests).
* **Working-Directory**: Starte den Server idealerweise im Repo-Root (`capstone/`), damit `./checklists` und die guideline-Pfade ohne Extras funktionieren. &#x20;
* **ENV**: `OPENAI_API_KEY` (für `OpenAIProvider`) und optional `GITHUB_TOKEN`/`GITHUB_ORG` (für Repo-Erstellung) in `.env.example` dokumentieren. &#x20;

## Minimaler Start (Backend)

* `backend/app/main.py` (FastAPI):

  * registriert Router (`/agent-systems`, `/sessions`, `/tools`, `/stream`, `/artifacts`)
  * lädt `.env`, konfiguriert Provider
  * **SSE**: gibt die Yields von `ReActAgent.process_request(...)` 1:1 weiter.&#x20;
* `backend/app/core/builder.py`: YAML→(Orchestrator+Sub-Agents) mit Whitelists; Sub-Agenten via `orchestrator.tools.append(sub_agent.to_tool(...))`.&#x20;
* `backend/app/core/registry.py`: hält Factories je `agent_system_id`.
* `backend/app/core/session_store.py`: `{sid → agent instance + state_dir}` (nutzt den Agent-`StateManager` implizit).&#x20;
