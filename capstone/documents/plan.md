Alles klar — hier ist ein **konkreter Implementierungsplan** für deinen Webservice, der dein aktuelles Agentensystem (ReAct-Orchestrator + Sub-Agents + Tools) kapselt und später via Chat-Frontend nutzbar macht. Ich beziehe mich explizit auf deinen bestehenden Code und mappe jeden Schritt sauber darauf.

# Ziele (kurz)

* Deklaratives **AgentSystem** per YAML/JSON registrieren → Server baut daraus Orchestrator + Sub-Agents.
* **Sessions** erstellen und verwalten → Chat-Nachrichten senden, **SSE/WS-Stream** konsumieren.
* **ASK\_USER**-Runden beantworten.
* **Artefakte** (Todo-List Markdown) bereitstellen.
* **Tools/Capabilities** inspizierbar machen.

# Phase 0 – Grundlagen & Projektstruktur

1. **Tech-Stack**: FastAPI (REST), uvicorn, optional Starlette/EventSourceResponse (SSE) bzw. WebSocket; Pydantic v2.
2. **Module**:

   * `api/` (FastAPI-Router, Schemas, Auth)
   * `core/agents/` (Builder, Registry, SessionStore)
   * `core/yaml/` (Schema, Parser)
   * `adapters/` (Bridges auf deinen Code)
   * `runtime/` (Logs, Config, Secrets)
3. **Konfig**: `OPENAI_API_KEY`, `GITHUB_TOKEN` usw. als env-secrets an `OpenAIProvider` weiterreichen.&#x20;

# Phase 1 – OpenAPI-Skelett & Endpunkte

Implementiere die folgenden Routen (REST) + Streaming:

* `POST /agent-systems` – YAML/JSON registrieren (persistieren) und **bauen**.
* `GET /agent-systems/{id}` – Resolved Config (Agents, Tools, Modelle).
* `POST /sessions` – Session zu AgentSystem erstellen.
* `POST /sessions/{sid}/messages` – User-Input entgegennehmen, **Verarbeitung triggern**.
* `GET /sessions/{sid}/stream` – **SSE** (oder WebSocket) mit Live-Updates aus `process_request(...)`. Dein Agent liefert bereits einen **async Generator** mit Schritt-Updates → 1:1 streamen.&#x20;
* `POST /sessions/{sid}/answers` – Antworten, wenn der Agent in `ASK_USER` wartet (dein Kontextflag `awaiting_user_input`).&#x20;
* `GET /sessions/{sid}/state` – Zustandsinspektion (version, tasks, awaiting\_user\_input, blocker).&#x20;
* `GET /sessions/{sid}/artifacts/todolist.md` – Download der Markdown-Todo-Liste, die deterministisch gerendert wird.&#x20;
* `GET /tools` – Export der verfügbaren Tools + Schemas/Capabilities (aus `ToolSpec` bzw. `capabilities_provider`). &#x20;

# Phase 2 – YAML-Spezifikation & Validierung

1. **JSON-Schema** für deine YAML-Version `v1` definieren (Agents, Mission, Modell, Tools-Whitelist, Budgets).
2. Parser implementieren:

   * Orchestrator + Sub-Agents erzeugen:

     * Orchestrator: `ReActAgent(system_prompt=..., mission=..., tools=[...])`&#x20;
     * Sub-Agenten: jeweils `ReActAgent` mit ihrer Tool-Whitelist; via `to_tool(...)` als **ToolSpec** an Orchestrator binden (inkl. `mission_override`, `allowed_tools`, `budget`).&#x20;
   * Tool-Lookup: aus YAML `allow` gegen deine Toolbasis (`BUILTIN_TOOLS` / `ALL_TOOLS_WITH_AGENTS`) auflösen.&#x20;
3. **Fehlerbilder** (z. B. unbekanntes Tool) frühzeitig als 400 melden.

# Phase 3 – AgentSystem-Builder & Registry

1. **Builder**:

   * `build_tool_index(...)` + Aliasse für robuste Namensauflösung nutzen.&#x20;
   * Für Sub-Agenten: `sub_agent = ReActAgent(...)` erzeugen, dann `orchestrator.tools.append(sub_agent.to_tool(...))`.&#x20;
2. **Registry**:

   * `AgentSystemRegistry`: `{id -> factory}` (Factory baut frische Orchestrator-Instanz inkl. ToolIndex, Prompt-Composition).
   * Pro Build `final_system_prompt` wird zusammengesetzt (Generic + Mission + Tools).&#x20;

# Phase 4 – SessionStore & Lebenszyklus

1. `SessionStore`: `{sid -> {agent, created_at, last_activity}}`.
2. **Start**:

   * `POST /sessions`: Orchestrator-Instanz aus Registry bauen; `sid` erzeugen und ablegen.
3. **Verarbeitung**:

   * `POST /messages`: user\_input in `process_request(user_input, session_id=sid)` einspeisen; **nicht blockieren** — Streaming im parallelen SSE-Endpunkt.
   * `GET /stream`: `async for update in agent.process_request(...): yield 'data: ...'`. Genau deine Schleife liefert Thought/Action/Observation/ASK\_USER/COMPLETE.&#x20;
4. **ASK\_USER-Resume**:

   * Wenn `awaiting_user_input` im Kontext, legt dein Agent das bereits im State ab und pausiert. `POST /answers` ruft erneut `process_request(answer, session_id=sid)` auf → der **Resume-Zweig** in deiner ReAct-Loop verarbeitet das (inkl. Sub-Agent-Query).&#x20;
5. **Persistenz**:

   * Dein `StateManager` wird von `process_request/_save()` genutzt; Sessions geben `session_id` weiter → persistenter Zustand out-of-the-box.&#x20;

# Phase 5 – Artefakte & Todo-List (deterministisch)

1. **Determinische Ansicht**: Die Markdown-Todo wird aus dem **autoritativen State** gerendert (`render_todolist_markdown(...)`) — kein LLM nötig. Route gibt die Datei aus `get_todolist_path(session_id)` zurück.&#x20;
2. Optional: Legacy-Modus (LLM-Editor) via `create_todolist_md/update_todolist_md` für freie Edit-Ops; standardmäßig aber **renderer-first** nutzen. &#x20;

# Phase 6 – Tools & Capabilities-Inspektion

1. **Auflisten**:

   * `export_openai_tools(...)` gibt Name/Description/Parameters je Tool; das kann das Frontend zur Formular-Validierung nutzen.&#x20;
   * Sub-Agenten liefern über `capabilities_provider` eine **Executor-Capabilities**-Liste mit Actions/ParamSchemas.&#x20;
2. **Ausführung**:

   * Alle Tool-Aufrufe laufen ohnehin über deine Orchestrator-Logik (`execute_tool_by_name_from_index`), inklusive Timeout/Fehler-Normierung.&#x20;

# Phase 7 – Sicherheit & Governance

* **Auth**: Bearer-Token/JWT auf allen Routen; optional **per-Tenant** Schlüsselräume (LLM-Keys, GitHub-Token).
* **Rate Limits & Quotas** pro Session/System.
* **Audit-Trail**: SSE-Stream serverseitig mitschreiben; deine Logs enthalten Tool-Start/-Ende, Erfolg, Dauer, usw. (Prometheus-Metriken sind bereits vorhanden).&#x20;
* **Sandboxing**: Sub-Agenten laufen mit `suppress_markdown`, `ephemeral_state`, **Tool-Whitelist** und `max_steps`-Budget (im Wrapper/`to_tool`).&#x20;

# Phase 8 – Teststrategie

1. **Unit-Tests**:

   * Builder: YAML → Agents/Tools korrekt verdrahtet (inkl. Aliasse).
   * Tool-Pfad: `execute_tool_by_name_from_index` mit valid/invalid Parametern.&#x20;
2. **Integration**:

   * End-to-End Flow: `/agent-systems` → `/sessions` → `/messages` + `/stream` → `/answers`.
   * **ASK\_USER**-Pfad: verifizieren, dass `awaiting_user_input` gesetzt wird und Resume klappt (Sub-Agent-Query).&#x20;
   * Artefakte: Markdown unter `./checklists/todolist_<sid>.md` erzeugt.&#x20;
3. **CLI-Parität**:

   * Deine bestehende CLI-Demo (`run_idp_cli.py`) als Referenz-Flow; gleiche Mission/Tools, aber über Web-API.&#x20;

# Phase 9 – Deployment

* Container (uvicorn, workers 2–4; ein Worker für SSE reicht oft).
* Health/Readiness Probes.
* Volumes/Paths für `./checklists` persistieren (Artefakte).&#x20;
* Prometheus-Scrape für Metriken aktivieren (du exportierst bereits Counter/Gauge/Histogram).&#x20;

# Akzeptanzkriterien (DoD)

* **Konfiguration**: `POST /agent-systems` lädt YAML, baut Orchestrator + Sub-Agents (mit Tool-Whitelist) erfolgreich. &#x20;
* **Chat-Lauf**: Für eine Session werden Thought/Action/Observation live gestreamt; bei `ASK_USER` pausiert der Lauf und `/answers` setzt ihn fort.&#x20;
* **Artefakte**: `GET /sessions/{sid}/artifacts/todolist.md` liefert das deterministische Markdown.&#x20;
* **Tool-Inspektion**: `GET /tools` listet Tools & Parameter/Capabilities. &#x20;
* **Safety**: Sub-Agenten sind auf erlaubte Tools + Budget begrenzt; Duplicate-Action-Guard & Loop-Guard greifen.&#x20;

# Implementierungs-Hinweise (Mapping auf deinen Code)

* **ReAct-Loop/Streaming**: `ReActAgent.process_request(...)` ist bereits als **async Generator** implementiert; ideal für SSE/WS.&#x20;
* **Sub-Agent als Tool**: `to_tool(...)` verpackt einen Agenten als `ToolSpec`; Whitelists/Budget/Mission-Override inklusive.&#x20;
* **Tool-Layer**: `ToolSpec`, `build_tool_index`, `execute_tool_by_name_from_index` stellen sauberes Routing, Timeouts, Fehlerbild her.&#x20;
* **Builtin-Tooling**: Git-Repo, Templates, CI/CD, K8s, Doku etc. stehen über `BUILTIN_TOOLS` bereit.&#x20;
* **Markdown/Todo**: Deterministischer Renderer `render_todolist_markdown` + Pfadlogik `get_todolist_path(session_id)`; Editor-Pfad optional via `create_todolist_md/update_todolist_md`. &#x20;
* **LLM-Abstraktion**: `OpenAIProvider` deckt **Tool-Calling** & **Structured Output** ab; je Agent konfigurierbar (Model/Temperature).&#x20;
