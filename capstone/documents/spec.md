Super Idee! Du hast mit deinem ReAct-Agenten schon fast alles, was ein Webservice braucht:

* ein asynchroner Stream von Status-Updates über `process_request(...)` (perfekt für SSE/WebSocket),
* sub-Agenten als „Tools“ via `to_tool(...)`,
* eine klare Tool-Abstraktion (Schemas, Aliasse, Timeout),
* und deterministische Artefakte (Todo-List Markdown).
  Ich skizziere dir unten eine schlanke Web-API + YAML-Spez, die genau darauf aufsetzt, und zeige, wie sie auf deinen vorhandenen Code mapped.     &#x20;

# Zielbild (kurz)

* **Konfiguration**: Ein YAML beschreibt Agenten (Orchestrator + Sub-Agents), Mission/Prompts, Modelle, Tool-Whitelists, Budgets.
* **Lifecycle**: (1) Agent-System registrieren → (2) Session erstellen → (3) Chat-Nachrichten schicken + Stream konsumieren → (4) optional Antworten liefern, wenn der Agent etwas fragt → (5) Zustände/Artefakte abrufen.
* **Transport**: REST für CRUD, **SSE** oder **WebSocket** für Live-Streaming aus `process_request(...)` (dein Agent liefert bereits ein Async-Generator-Stream).&#x20;

---

# Ressourcenmodell

* **AgentSystem**: Deine deklarative YAML (siehe unten). Server baut daraus ReAct-Instanzen und verknüpft Sub-Agenten via `to_tool(...)`.&#x20;
* **Session**: Laufzeit-Kontext (StateManager), dem du Nachrichten schickst; streamt Agent-Updates live aus der ReAct-Loop.&#x20;
* **Message**: User-Eingaben / Agent-Ausgaben.
* **Artifacts**: z. B. generierte **Todo-List Markdown**, die dein Renderer deterministisch schreibt (Dateipfad je Session).&#x20;
* **Tools**: Werden aus `ToolSpec` geladen (Schemas/Timeouts/Aliasse). &#x20;

---

# YAML-Spezifikation (v1)

```yaml
version: 1
system:
  name: "idp-copilot"
  storage:
    checklist_dir: "./checklists"     # passt zu render_todolist_markdown
  default_model:
    provider: "openai"
    model: "gpt-4.1"
    temperature: 0.1

agents:
  - id: orchestrator
    role: "orchestrator"
    system_prompt: |-
      You are the orchestrator. Coordinate tools and sub-agents efficiently.
    mission: |-
      Create a new repo, scaffold service, set up CI/CD, deploy to staging.
    max_steps: 50
    # Tools direkt + Sub-Agenten (siehe unten)
    tools:
      allow: ["create_git_repository_with_branch_protection",
              "list_templates", "apply_template",
              "setup_cicd_pipeline", "deploy_to_staging",
              "search_knowledge_base_for_guidelines",
              "setup_observability", "generate_k8s_manifests",
              "generate_documentation",
              "agent_git"]   # Sub-Agent exposed as Tool
    model:
      provider: "openai"
      model: "gpt-4.1"
      temperature: 0.1

  - id: agent_git
    role: "sub-agent"
    description: "Git sub-agent"
    mission: |-
      Handle repository creation and branch protection policies.
    max_steps: 12
    tools:
      allow: ["create_repository", "setup_branch_protection",
              "validate_project_name_and_type"]
    model:
      provider: "openai"
      model: "gpt-4.1-mini"
```

**Mapping:**

* Orchestrator registriert Sub-Agenten via `to_tool(name="agent_git", allowed_tools=[...], mission_override=...)`. Das erzeugt ein Tool mit Sub-Agent-Semantik, inkl. Whitelist und Budget – genau so nutzt es dein CLI-Beispiel. &#x20;
* Tool-Namen/Schema kommen aus `ToolSpec`/`BUILTIN_TOOLS` (z. B. `create_repository`, `create_git_repository_with_branch_protection`, `validate_project_name_and_type`, …). &#x20;
* Modelle/API-Keys laufen über deinen `LLMProvider` (z. B. `OpenAIProvider`).&#x20;

---

# REST + Streaming API (OpenAPI-Skizze)

```yaml
openapi: 3.0.3
info: {title: Agent Orchestration API, version: 1.0}
paths:
  /agent-systems:
    post:
      summary: Register or update an AgentSystem from YAML/JSON
      requestBody: {content: {application/x-yaml: {schema: {type: string}},
                               application/json: {schema: {type: object}}}}
      responses: {201: {description: created}}

  /agent-systems/{id}:
    get: {summary: Get resolved config (agents, tools, models)}

  /sessions:
    post:
      summary: Create a chat session for an AgentSystem
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties: {agent_system_id: {type: string}, user_id: {type: string}}
              required: [agent_system_id]
      responses: {201: {description: created}}

  /sessions/{sid}/messages:
    post:
      summary: Send a user message and start processing
      requestBody:
        content:
          application/json:
            schema: {type: object, properties: {text: {type: string}}, required: [text]}
      responses: {202: {description: accepted}}

  /sessions/{sid}/stream:
    get:
      summary: Server-Sent Events stream of agent updates
      responses:
        '200':
          description: text/event-stream
          content: {text/event-stream: {}}

  /sessions/{sid}/answers:
    post:
      summary: Provide answers when agent asked questions (ASK_USER)
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties: {text: {type: string}}
              required: [text]
      responses: {202: {description: accepted}}

  /sessions/{sid}/state:
    get: {summary: Inspect current state (tasks, version, awaiting_user_input, blocker)}

  /sessions/{sid}/artifacts/todolist.md:
    get: {summary: Download rendered Todo List Markdown}

  /tools:
    get: {summary: List available tool specs (name, schema, aliases, timeouts)}
```

**Warum passt das zu deinem Code?**

* **Streaming**: `process_request()` ist ein Async-Generator; SSE/WS können jeden `yield` direkt weiterreichen (Thought, Action, Observation,…).&#x20;
* **ASK\_USER-Flow**: Dein Agent persistiert `awaiting_user_input` und holt Antworten später wieder ab; `/answers` hängt genau hier ein.&#x20;
* **Artefakt-Ablage**: Die Markdown-Todo wird deterministisch je Session in `./checklists/todolist_<session>.md` gerendert → einfacher Download-Endpoint.&#x20;
* **Tools & Sub-Agents**: Tool-Schemas + Capabilities stammen aus `ToolSpec`/`build_tool_index`; Sub-Agenten werden als Tool exposed. &#x20;
* **LLM-Backend**: `OpenAIProvider` kapselt Models/Temperature/Tool-Calling. Pro Agent konfigurierbar.&#x20;

---

# Server-Implementierung (FastAPI-artig, grob)

* **Bootstrap**

  * Parse YAML → baue `ReActAgent`-Instanzen.
  * Für jeden Sub-Agent: `orchestrator.tools.append(sub_agent.to_tool(...))`.&#x20;
  * Tool-Pool: `BUILTIN_TOOLS` / `ALL_TOOLS_WITH_AGENTS` bereitstellen.&#x20;
* **Session Store**

  * Map `{sid → orchestrator_instance + state_dir}`. Dein Agent nutzt bereits `StateManager` und Versionszähler für Patches/Ownership. (Du kannst den vorhandenen Persist-Pfad behalten und nur Weg dorthin konfigurieren.)&#x20;
* **SSE-Endpoint**

  * `async for chunk in agent.process_request(text, session_id=sid): yield f"data: {chunk}\n\n"` – 1:1 aus deinem Stream.&#x20;
* **Antworten**

  * `/answers` ruft intern `process_request(answer, session_id=sid)` auf. Dein Code erkennt „awaiting“ und setzt fort (Resume-Logik inkl. Sub-Agent).&#x20;
* **Artifacts**

  * Reiche Datei aus `render_todolist_markdown(...)`/`get_todolist_path(...)` durch.&#x20;
* **Models/Keys**

  * Je Agent System env-secrets für `OpenAIProvider` etc. injizieren; Provider-Instanz je Agent anhand YAML.&#x20;

---

# Beispiel: Minimaler Aufruf-Flow

1. **System registrieren**
   `POST /agent-systems` (YAML oben)

2. **Session starten**
   `POST /sessions {agent_system_id:"idp-copilot"}` → `{sid}`

3. **Chat starten + Stream**

* `POST /sessions/{sid}/messages {text:"Erzeuge ein Service 'billing-service' und deploye auf staging"}`
* **SSE** an `/sessions/{sid}/stream` empfangen (z. B. Thought → Aktion: `create_git_repository_with_branch_protection` → Observation …).
  Das passt exakt zu deinem ReAct-Loop (Thought/Decision/Execute/Observation).&#x20;

4. **Wenn Fragen kommen** (ASK\_USER)
   `POST /sessions/{sid}/answers {text:"Repo soll private sein; Programmiersprache Go"}` → Loop setzt fort.&#x20;

5. **Todo-Liste abrufen**
   `GET /sessions/{sid}/artifacts/todolist.md` (wird deterministisch aus dem strukturierten State gerendert).&#x20;

---

# Wichtige Design-Details

* **Tool-Schemas 1:1 exponieren**
  Nutze `ToolSpec.input_schema` für eine `/tools`-Inspektion, damit dein Chat-Frontend Formular-Validierung bekommt (required-Felder, Types).&#x20;
* **Sub-Agenten sicher**
  Whitelist per `allowed_tools` und Budget `max_steps` (in YAML) – wird in `to_tool(...)`/Sub-Agent-Wrapper angewandt. &#x20;
* **Deterministische Patches**
  Deine Patch-Engine verhindert State-Konflikte (Version/Owner) und aktualisiert nur erlaubte Felder. Das bleibt serverseitig unverändert.&#x20;
* **Markdown nur als View**
  State ist führend; Markdown wird **deterministisch gerendert** (kein LLM nötig). Das ist goldrichtig für Web-APIs.&#x20;
* **LLM-Vendors**
  `LLMProvider` macht dich vendor-agnostisch. Für Tool-Calling nutzt dein OpenAI-Provider native Functions, fällt sonst auf Schema-Prompting zurück.&#x20;
* **Security**

  * Per-Tenant Secrets (OpenAI/GitHub Token),
  * Ratenlimits/Quota per Session,
  * Audit-Trail = Speichere den SSE-Stream als Log.

---

# Bonus: Minimaler FastAPI-Handler (Pseudocode)

```python
@app.post("/sessions/{sid}/messages")
async def send_message(sid: str, body: Msg):
    agent = sessions[sid].agent
    # fire-and-stream: client öffnet /stream
    asyncio.create_task(stream_runner(agent, body.text, sid))
    return {"status": "accepted"}

@app.get("/sessions/{sid}/stream")
async def stream(sid: str):
    agent = sessions[sid].agent
    async def eventgen():
        async for chunk in agent.process_request("", session_id=sid):
            yield f"data: {chunk}\n\n"  # passt exakt zu deinem async generator
    return EventSourceResponse(eventgen())
```

Der `stream_runner` ist optional, wenn du Post + Stream entkoppeln willst; ansonsten kann `/stream` direkt `process_request(text, sid)` starten. Die Kernidee: **nicht** neu erfinden – dein `process_request` liefert bereits die Sequenz.&#x20;
