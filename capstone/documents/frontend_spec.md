Alles klar — ich liefere dir (A) die **konkreten Änderungen** für dein `pyproject.toml` und (B) ein **Frontend-Spec als Fließtext** (kein YAML).

---

# A) Änderungen an `pyproject.toml`

Füge die vier UI-Pakete in `[project].dependencies` hinzu (keine neue `requirements.txt`). Sonst nichts anfassen.

```toml
[project]
# … (unverändert)
dependencies = [
  "aiofiles==23.2.1",
  "anthropic==0.30.0",
  "circuitbreaker==2.0.0",
  "fastapi==0.111.0",
  "httpx==0.26.0",
  "ipython==8.25.0",
  "kubernetes==30.1.0",
  "langchain==0.2.5",
  "openai>=1.40.0",
  "opentelemetry-api==1.25.0",
  "opentelemetry-sdk==1.25.0",
  "prometheus-client==0.20.0",
  "pydantic==2.7.4",
  "pygithub==2.3.0",
  "redis==5.0.6",
  "structlog==24.2.0",
  "uvicorn[standard]==0.30.1",

  # --- Frontend (neu) ---
  "streamlit>=1.33",
  "requests>=2.31",
  "sseclient-py>=1.8",
  "pyyaml>=6.0.1",
]
```

(Hintergrund: Dein Backend stellt bereits u. a. `/agent-systems`, `/sessions`, `/sessions/{sid}/messages`, `/sessions/{sid}/stream`, `/sessions/{sid}/state`, `/sessions/{sid}/artifacts/todolist.md`, `/tools` bereit, die das Frontend konsumiert. )
(Die vorhandene Projekt- und Tool-Struktur in `pyproject.toml` bleibt gleich. )

---

# B) Frontend Specification (Textform)

## Ziel & Kontext

Das Frontend dient als **Demo-UI** für dein Agenten-System: Agent-Systeme registrieren, Sessions anlegen, mit dem Orchestrator chatten (Live-Stream via SSE), State & ToDo-Markdown einsehen sowie verfügbare Tools listen. Grundlage ist dein bestehendes FastAPI-Backend.&#x20;

## Tech-Stack & Laufzeit

* **Framework:** Streamlit (Single-Page UI, schnelle Demo-Iterationen).
* **HTTP-Client:** `requests` für REST-Calls.
* **Streaming:** `sseclient-py` für Server-Sent Events des Chat-Streams (`text/event-stream`).
* **Konfiguration:** `pyyaml` für das Einlesen/Validieren von Agent-System-Definitionen (YAML/JSON).
* **Python:** 3.11+.
* **Start:** `streamlit run frontend/streamlit_app.py` (Base-URL per ENV `AGENT_API_BASE_URL`, Default `http://localhost:8000`).&#x20;

## Kern-Userflows (End-to-End)

1. **Agent-System registrieren**

   * Eingabe: YAML/JSON gemäß `AgentSystem`-Schema.
   * Request: `POST /agent-systems` → Response enthält `id`.
   * Optional: `GET /agent-systems/{id}` zur Anzeige der „resolved“ Ansicht.&#x20;

2. **Session erstellen**

   * Eingabe: `agent_system_id`.
   * Request: `POST /sessions` → Response `sid`.&#x20;

3. **Chat / Live-Stream**

   * `POST /sessions/{sid}/messages` mit `{"text": "<user msg>"}` (202 Accepted).
   * Direkt danach `GET /sessions/{sid}/stream` (SSE) lesen und tokenweise anzeigen.
   * Erwartung: Event-Payloads als `data: "<json string>"`.&#x20;

4. **State & Artefakte**

   * `GET /sessions/{sid}/state` zeigt u. a. `version`, `awaiting_user_input`, `tasks`, `blocker`.
   * `GET /sessions/{sid}/artifacts/todolist.md` lädt das Markdown der ToDo-Liste (404, falls noch nicht erzeugt).&#x20;

5. **Tools sichten**

   * `GET /tools` liefert normalisierte Tool-Infos (Name, Beschreibung, Parameterschema) für UI-Anzeige.&#x20;

## UI-Struktur

* **Sidebar (Konfiguration):**

  * Base-URL (Textfeld), Default aus `AGENT_API_BASE_URL`.
* **Tabs:**

  1. **⚙️ Agent System**
     Textarea (YAML/JSON), Button „Registrieren“, optional „Resolved anzeigen“.
  2. **💬 Chat**
     Button „Session erstellen“, Eingabezeile, Button „Senden & Streamen“, Live-Log.
  3. **📋 State & ToDo**
     Buttons „State laden“, „ToDo laden“; JSON-Viewer; Markdown-Render.
  4. **🧰 Tools**
     Button „Tools laden“, JSON-Viewer.

## Fehlerbehandlung & UX-Prinzipien

* **Robustheit:**

  * 4xx/5xx Responses klar anzeigen (Statuscode + Body-Text).
  * Bei SSE-Fehlern sauberes Abbrechen mit Fehlermeldung.
  * Für 404 bei `todolist.md`: dezenter Hinweis („noch nicht vorhanden“).&#x20;
* **Leistung:**

  * Streaming als Einweg-Fluss, UI inkrementell updaten.
  * Keine Client-Polling-Schleifen; nur SSE.
* **Usability:**

  * Klarer „Happy-Path“ (Registrieren → Session → Prompt → Stream).
  * Minimalistische Statusmeldungen, kein visueller Lärm.

## Nicht-funktionale Anforderungen

* **Portabilität:** Keine system-spezifischen Pfade; Start über Standard-Streamlit.
* **Security (Demo):**

  * CORS ist im Backend offen; Frontend speichert keine Secrets.
  * Später leicht auf Bearer/JWT erweiterbar.&#x20;
* **Observability:**

  * Frontend zeigt nur UI-Status; Metriken/Tracing laufen im Backend (Prometheus/OpenTelemetry).&#x20;

## Annahmen & Schnittstellenvertrag

* **API-Kontrakte** (gekürzt):

  * `POST /agent-systems` → `201 { "id": "<system_id>" }`
  * `GET /agent-systems/{id}` → `200 { resolved: {...} }`
  * `POST /sessions` → `201 { "sid": "<uuid>" }`
  * `POST /sessions/{sid}/messages` → `202 { "status": "accepted" }`
  * `GET /sessions/{sid}/stream` → `text/event-stream` (SSE, Felder über `data:`)
  * `GET /sessions/{sid}/state` → `200 { version, awaiting_user_input, tasks, blocker }`
  * `GET /sessions/{sid}/artifacts/todolist.md` → `200 text/markdown` oder `404`
  * `GET /tools` → `200 { "tools": [ {name, description, parameters}, ... ] }`&#x20;

## Erweiterungen (optional, nach MVP)

* Datei-Upload (YAML), Session-Picker, dedizierter **Tool-Playground** (gezielter Tool-Call mit Parametern), einfache **Run-Presets** (vordefinierte Prompts).

---

Wenn du möchtest, schreibe ich dir das kurze `frontend/streamlit_app.py` passend zu diesem Spec direkt als Dateiinhalt — sag einfach „mach“.
