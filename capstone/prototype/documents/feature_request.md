Hier ist das **finale Feature-Request-Dokument** für die **Integration eines Multi-Agenten-Systems** (Orchestrator + Sub-Agents) auf Basis deines aktuellen Codes. Ich habe deinen gesamten Code gelesen und die Lösung so geplant, dass sie sich **minimal-invasiv** in deine bestehenden Klassen, Modelle und Tool-Laufzeit einfügt.

&#x20;      &#x20;

---

# Feature Request: Multi-Agent-Orchestrierung (Sub-Agents als Tools, Rückfragen Bubble-Up, Todo-Patches)

## 1) Ausgangslage (heute)

* Dein **ReActAgent** bildet bereits einen robusten Loop mit Plan-First, Tool-Calling (OpenAI Function Calling), deterministischem Status-Update, Metriken und State-Persistenz. Die Todo-Liste existiert strukturiert (Tasks + Open Questions) und wird deterministisch zu Markdown gerendert. Tool-Ausführung erfolgt über `ToolSpec`, Lookup-Index und Standard-Runner.&#x20;
* Der LLM-Provider kapselt `generate_response`, schema-validierte Antworten (`generate_structured_response`) und natives Tool-Calling (`call_tools`) – OpenAI unterstützt es, Anthropic liefert `None`.&#x20;
* Der **System-Prompt** definiert klare IDP-Workflows (Microservice, Library, Frontend) und Entscheidungslogik (ASK\_USER, Tool, COMPLETE, Error Handling).&#x20;
* **StateManager** persistiert und lädt Sessions (Pickle + aiofiles).&#x20;
* **Todo-Rendering** ist deterministisch (Markdown wird nur als View erzeugt). Es gibt auch die ältere LLM-MD-Edit-API, aber dein Agent nutzt bereits den deterministischen Renderer.&#x20;
* **Tool-Laufzeit**: `ToolSpec`, Normalisierung, Export der OpenAI-Tools, Ausführung mit Timeout/Async, Alias-Auflösung, Tool-Index.&#x20;
* **Builtin-Tools**: Repo, Template, CI/CD, Tests, KB-Guidelines etc. – real oder Stub – inklusive Timeouts und Schemas.&#x20;

> Konsequenz: Wir können Sub-Agents **nahtlos als „virtuelle Tools“** registrieren und über **denselben Ausführungspfad** wie echte Tools (Index, Timeout, Metriken) laufen lassen – ohne neue Laufzeit zu erfinden.&#x20;

---

## 2) Zielbild

* Ein **Orchestrator-Agent** (heutiger ReActAgent erweitert) kann **entweder echte Tools** oder **Sub-Agents** (als Tools) aufrufen.
* **Sub-Agents** besitzen eine begrenzte Tool-Whitelist und arbeiten an **Teilaufgaben**; sie liefern **strukturierte Patches** für die Master-Todo zurück.
* **Rückfragen** von Sub-Agents werden **nicht** direkt an den User gestellt, sondern als `need_user_input` an den Orchestrator „hochgebubbelt“, der die bestehende `ASK_USER`-Mechanik nutzt und anschließend einen **Resume-Call** mit Antworten ausführt.&#x20;
* Die **Master-Todo** bleibt **Single Source of Truth** im Orchestrator; Markdown ist View. Sub-Agents modifizieren die Master-Tasks **nicht direkt**, sondern über Patches.

---

## 3) Datenmodell-Erweiterungen (minimal)

Deine `PlanTask`/`PlanOutput` sind schon da (id, title, tool, params, status, depends\_on…). Für Multi-Agent Ownership & Merge schlagen wir zwei additive Felder vor:

1. **Task-Level**

   * `owner_agent: str | None` – Verantwortlicher Agent („orchestrator“ oder Sub-Agent-Name)
2. **Plan-Meta**

   * `version: int` – inkrementell bei jedem erfolgreichen Patch-Merge (optimistic concurrency)

> Diese Felder landen in `self.context` (z. B. `context["version"] = 1`) und in den Task-Dicts (kompatibel mit deinem Renderer; der ignoriert unbekannte Keys). &#x20;

### Patch-Schema (Sub-Agent → Orchestrator)

```json
{
  "base_version": 12,
  "ops": [
    {"op":"update","task_id":"WS-1","fields":{"status":"IN_PROGRESS","notes":"…"}},
    {"op":"add_subtask","parent_id":"WS-1","task":{"id":"WS-1.c","title":"Smoke-Test","status":"PENDING"}}
  ]
}
```

* **Zulässige Ops**: `add`, `add_subtask`, `update`, `link_dep`, `unlink_dep`.
* **Merge-Regeln**:

  * **Ownership-Guard**: Ein Sub-Agent darf nur Tasks mit `owner_agent == <sein_name>` schreiben.
  * **Version-Check**: `base_version` muss zur aktuellen `version` passen – sonst `409 Conflict`, Orchestrator entscheidet (oder fragt den User).
  * Abhängigkeits-Links dürfen agent-übergreifend ergänzt werden (`link_dep`), Entfernen ist policy-gesteuert.

Die **Markdown-View** bleibt über `render_todolist_markdown` deterministisch; Gruppierung nach `owner_agent` kann optional ergänzt werden (UI-Schicht, nicht LLM).&#x20;

---

## 4) Sub-Agenten als Tools (Wrapper)

Wir registrieren Sub-Agents als **ToolSpec** in derselben Registry wie Builtins:

```python
# Beispiel-Signatur des Agent-Tools
ToolSpec(
  name="agent_scaffold_webservice",
  description="Sub-Agent: erzeugt ein Webservice-Gerüst",
  input_schema={
    "type": "object",
    "properties": {
      "task": {"type": "string"},
      "inputs": {"type": "object"},
      "shared_context": {"type": "object"},
      "allowed_tools": {"type": "array", "items":{"type":"string"}},
      "budget": {"type":"object"},
      "resume_token": {"type":"string"},
      "answers": {"type":"object"}
    },
    "required": ["task"],
    "additionalProperties": True
  },
  output_schema={"type": "object"},
  func=run_sub_agent,   # Wrapper-Funktion
  is_async=True,
  timeout=120
)
```

* **Wrapper-Pflichten**:

  1. Sub-Agent (interner `ReActAgent`) mit **Whitelist** bauen (`tools=…`, `max_steps`, `timeout`). Deine Tool-Fabrik/Index kann wiederverwendet werden. &#x20;
  2. `process_request` streamen und danach den **Sub-Agent-State** prüfen:

     * Wenn `awaiting_user_input` gesetzt → **keine** Userfrage senden, sondern `{"success":false,"need_user_input":{…},"state_token":…}` zurückgeben. (State als **opaque resume token** serialisieren.)&#x20;
     * Wenn fertig → `{"success":true,"patch":[…], "result":{…}, "new_facts":{…}}` liefern.
  3. Bei `resume_token` + `answers` → Sub-Agent-State restaurieren, Antworten in `context` mergen (kompatibel mit deiner `known_answers_text`/`facts`-Logik) und fortsetzen.&#x20;

> Vorteil: Keine neue Runtime nötig – wir nutzen **denselben** Tool-Runner (`execute_tool_by_name_from_index`), Prometheus-Metriken, Timeouts, Normalisierung. &#x20;

---

## 5) Orchestrator-Erweiterungen

### 5.1 Neue Meta-Action: `delegate_to_agent`

Der Orchestrator erhält eine zusätzliche „Function“ (analog zu `update_todolist`, `ask_user`, `complete`, `error_recovery`), die einen Sub-Agent als Tool aufruft.&#x20;

* **Schema** (LLM-sichtbar):

  * `agent_name: string`
  * `task: string`
  * `inputs: object`
  * `allowed_tools?: string[]`
  * `budget?: object`

* **Handler** (intern):

  * Sub-Agent-Toolname aus `agent_name` ableiten (z. B. `agent_scaffold_webservice`) und via `execute_tool_by_name_from_index` aufrufen.&#x20;
  * Antwort behandeln:

    * `patch` → **Merge** gegen Master-Todo (Ownership, Versioning), anschließend **Markdown neu rendern**.&#x20;
    * `need_user_input` → Orchestrator nutzt **bestehende** `ASK_USER`-Mechanik und speichert `state_token`; auf Antwort folgt **Resume-Call** mit `resume_token` + `answers`.&#x20;
    * `result/new_facts/suggested_next_action` → in `context` & Tasks speichern.

### 5.2 Orchestrator-Loop bleibt unverändert robust

* Plan-First mit `_detect_blocking_questions` und `_create_initial_plan` bleibt erhalten.&#x20;
* Tool-Calls markieren deterministisch IN\_PROGRESS/COMPLETED/FAILED, inkl. Metriken.&#x20;
* Loop-Guard/ASK\_USER/State-Persistenz funktionieren wie gehabt. &#x20;

---

## 6) Rückfragen-Protokoll (Bubble-Up & Resume)

* **Sub-Agent → Orchestrator**:
  `{"success": false, "need_user_input": {"questions":[…], "context":"…", "proposed_defaults":{…}}, "state_token": "…"}`

* **Orchestrator**:

  1. Stellt **eine** konsolidierte Frage mit vorhandener `ASK_USER`-Funktion und setzt `awaiting_user_input`.&#x20;
  2. Speichert `state_token` in `context["pending_subagent_queries"]`.
  3. Bei Antwort → `resume_token=state_token`, `answers={…}` an denselben Sub-Agent-Toolspec übergeben.

* **Antwort-Validierung**: Orchestrator validiert Antworten gegen erwartete Keys des Sub-Agents (z. B. Pflichtfelder für seine nächsten Tool-Schritte). Fehlende Felder → erneute `ASK_USER`.

> Der Flow nutzt **deine bestehende ASK/Resume-Fähigkeit** (Kontextschlüssel `awaiting_user_input`, `known_answers_text`, `facts`), nur vermittelt über den Orchestrator statt direkt.&#x20;

---

## 7) Sicherheit, Budget, Guards

* **Tool-Whitelist** je Sub-Agent (nur explizit erlaubte Builtins).&#x20;
* **Hop-Limit** (max. Delegations-Tiefe, z. B. 2) im Wrapper erzwingen.
* **Timeout/Steps-Budget** (Wrapper übergibt `max_steps`, `timeout` an internen `ReActAgent`).&#x20;
* **Ownership-Guard** im Patch-Merge (kein Fremd-Task-Write).
* **Optimistic Concurrency** via `version`/`base_version`.

---

## 8) Observability & Feedback

* Sub-Agent-Calls sind **Tools** → vorhandene **Prometheus-Metriken** greifen: `idp_tool_execution_seconds`, `idp_tool_success/failure`. Optional Label `subagent="<name>"`.&#x20;
* **FeedbackCollector** erfasst bereits Erfolge/Fehler pro Schritt; Sub-Agent-Wrapper kann zusätzliche Details (agent\_name, patch\_ops) in `details` mitschicken.&#x20;

---

## 9) Schrittweise Umsetzung

1. **Model-Add-ons**

   * `owner_agent` in Tasks (Optional-Feld).
   * `context["version"] = 1` initialisieren; bei jedem Merge erhöhen.&#x20;

2. **PatchEngine** (kleines Modul oder Methode im Orchestrator)

   * `apply_patch(master: dict, patch: dict) -> MergeResult`
   * Prüft `base_version`, Ownership, führt Ops aus, erhöht Version.
   * Danach `render_todolist_markdown()` aufrufen.&#x20;

3. **Agent-als-Tool Wrapper**

   * `run_sub_agent(...)` implementieren: Bau des internen `ReActAgent` mit Whitelist/MaxSteps, Stream konsumieren, `need_user_input`/`patch`/`result` sammeln. &#x20;

4. **Registry**

   * `ALL_TOOLS = BUILTIN_TOOLS + [AgentTools…]` und `build_tool_index(ALL_TOOLS)`. &#x20;

5. **Orchestrator-Meta**

   * `delegate_to_agent` als zusätzliche Function in `_decide_next_action` anbieten; im `_execute` behandeln (wie `TOOL_CALL`, nur mit Agent-Toolnamen).&#x20;

6. **Rückfragen & Resume**

   * `pending_subagent_queries` + Handler für Resume: wenn User antwortet, baue Params `{resume_token, answers}` und rufe den gleichen Agent-ToolSpec erneut.

---

## 10) Beispiele (End-to-End)

**Plan (Orchestrator)**
`t1: validate_project_name_and_type` → owner: orchestrator
`t2: scaffold webservice` → owner: agent\_scaffold\_webservice
`t3: setup_cicd_pipeline` → owner: orchestrator

**Delegation**
`delegate_to_agent(agent_name="scaffold_webservice", task="Erzeuge FastAPI-Service …", allowed_tools=["apply_template","setup_cicd_pipeline"])`

**Sub-Agent → Orchestrator**

* Fall A (Frage): `need_user_input` („Python-Version?“, `state_token`) → Orchestrator `ASK_USER` → Resume.
* Fall B (Patch): `update WS-1 -> IN_PROGRESS`, `add_subtask WS-1.c`, `result.artifacts=[…]` → Orchestrator merged & rendert Markdown.&#x20;

---

## 11) Akzeptanzkriterien

1. **Sub-Agents** als `ToolSpec` registriert und über denselben Runner aufrufbar (Index/Timeout/Async/Prom-Metriken).&#x20;
2. **Neue Meta-Action** `delegate_to_agent` vorhanden und funktionsfähig (Plan→Delegation→Antwortverarbeitung).&#x20;
3. **Rückfragen** laufen via `need_user_input` → Orchestrator `ASK_USER` → **Resume** mit `resume_token`.&#x20;
4. **Patch-Merge** mit Ownership-Guard & Versioning; Markdown-View wird danach deterministisch aktualisiert.&#x20;
5. **Budgets/Guards** (Hop-Limit, Steps/Timeout, Whitelist) aktiv.
6. **Telemetry** sichtbar: Sub-Agent-Calls in `idp_tool_*`-Metriken + optionales Label.&#x20;

---

## 12) Nicht-Ziele (v1)

* Kein verteiltes Scheduling; Sub-Agents laufen im selben Prozesskontext (Wrapper).
* Keine cross-Session-Koordination (jede Session hat ihren Master-Plan).
* Kein automatischer LLM-Edit am Markdown (bleibt deterministisch gerendert).&#x20;

---

## 13) Anmerkungen zur Kompatibilität

* Der Orchestrator verwendet **deine vorhandenen Prompts/Heuristiken** (Plan-First, Tool-Calling via `export_openai_tools`, Vendor Function Calling). &#x20;
* **LLMProvider**-Abstraktion bleibt unverändert; OpenAI liefert Tool-Calls, Anthropic kann ohne Tool-Calls via strukturiertem Fallback weiterarbeiten.&#x20;
* **FeedbackCollector** kann unverändert weiterlaufen; du kannst optional die Sub-Agent-Ergebnisse/Fehler detaillierter taggen.&#x20;

---

Wenn du willst, schreibe ich dir als Nächstes ein **PR-fähiges Patchset** mit:

* `subagents/agent_tooling.py` (Wrapper + Resume-Token-Serializer),
* Orchestrator-Patch (`delegate_to_agent`, PatchEngine, Ownership/Versioning),
* einem Beispiel-Sub-Agent `agent_scaffold_webservice` (Whitelist: `apply_template`, `setup_cicd_pipeline`).
