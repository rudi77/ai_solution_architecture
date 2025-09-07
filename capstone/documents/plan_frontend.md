Perfekt! Hier ist ein knackiger, umsetzbarer **Implementierungsplan** für dein Streamlit-Frontend auf Basis deines aktuellen Backends.

# Ziel

Eine minimalistische Demo-UI (Streamlit) zum:

* Agent-System registrieren
* Session anlegen
* Chatten mit Live-SSE-Stream
* State & ToDo-Markdown anzeigen
* Tools listen

(Die benötigten API-Endpunkte sind bereits vorhanden: `/agent-systems`, `/sessions`, `/sessions/{sid}/messages`, `/sessions/{sid}/stream`, `/sessions/{sid}/state`, `/sessions/{sid}/artifacts/todolist.md`, `/tools`. )

---

# 1) Paketabhängigkeiten (nur `pyproject.toml`)

**Aufgabe:** In `[project].dependencies` ergänzen: `streamlit`, `requests`, `sseclient-py`, `pyyaml`.
**Akzeptanzkriterium:** `uv run python -c "import streamlit,requests,yaml"` läuft ohne Fehler.
**Hinweis:** Du hast bereits ein `pyproject.toml` im Repo; wir erweitern nur die Dependencies, keine neue `requirements.txt`. (Stand heute enthält es ausschließlich Backend-Pakete. )

---

# 2) Projektstruktur (Frontend)

```
frontend/
├─ streamlit_app.py               # Haupt-UI
└─ components/
   └─ sse_chat.py                 # SSE-Streaming-Helper
```

**Aufgabe:** Ordner & Dateien anlegen.

**Akzeptanzkriterium:** `streamlit run frontend/streamlit_app.py` startet eine leere App ohne Exceptions.

---

# 3) UI-Funktionalität umsetzen

## 3.1 Sidebar – Backend-Konfiguration

* **Feature:** Eingabefeld „Base URL“ (Default aus `AGENT_API_BASE_URL`, sonst `http://localhost:8000`).
* **Akzeptanzkriterium:** Alle API-Calls verwenden die im Sidebar gesetzte Base-URL.

## 3.2 Tab „⚙️ Agent System“

* **Features:**

  * Textarea für AgentSystem **(YAML oder JSON)**.
  * Button „Registrieren“ → `POST /agent-systems` (201, `{"id": ...}`).
  * Optional: „Resolved anzeigen“ → `GET /agent-systems/{id}`.
* **Akzeptanzkriterien:**

  * Erfolgreiche Registrierung zeigt `id`.
  * Fehlerhafte Eingaben liefern klaren Fehler (Statuscode + Body).
    (Endpunkte siehe Backend. )

## 3.3 Tab „💬 Chat“

* **Features:**

  * „🆕 Session erstellen“ → `POST /sessions` (201, `{"sid": ...}`).
  * Eingabefeld Nachricht → `POST /sessions/{sid}/messages` (202).
  * **Live-Stream** via `GET /sessions/{sid}/stream` (SSE); Anzeige der Chunks in Echtzeit.
* **Akzeptanzkriterien:**

  * Nach dem Senden wird gestreamt, bis Generator endet.
  * Netzwerk-/SSE-Fehler werden nicht-blockierend angezeigt.
    (SSE-Medientyp `text/event-stream`. )

## 3.4 Tab „📋 State & ToDo“

* **Features:**

  * „🔄 State laden“ → `GET /sessions/{sid}/state` (zeigt JSON).
  * „📥 ToDo Markdown laden“ → `GET /sessions/{sid}/artifacts/todolist.md` (Markdown rendern).
* **Akzeptanzkriterien:**

  * Bei 404 für `todolist.md` dezente Info „noch nicht vorhanden“.&#x20;

## 3.5 Tab „🧰 Tools“

* **Feature:** „🔄 Tools laden“ → `GET /tools` (Kompaktliste: Name, Beschreibung, Parameter-Schema).
* **Akzeptanzkriterium:** Liste wird als JSON-Viewer dargestellt.&#x20;

---

# 4) Technische Umsetzungsschritte (konkret)

1. **SSE-Client** (`frontend/components/sse_chat.py`)

   * `requests.get(url, stream=True)` und `sseclient.SSEClient` nutzen.
   * Iterator, der `event.data` JSON-decoded (falls möglich) und als String zurückgibt.
   * **Done-Definition:** Robust bei leeren Events, Netzwerkfehlern, Timeouts.

2. **Streamlit App** (`frontend/streamlit_app.py`)

   * `st.set_page_config(layout="wide")`.
   * **Session State Keys:** `agent_system_id`, `session_id`, `chat_history`, `last_state`.
   * **Tabs** gemäß Abschnitt 3 implementieren.
   * **Fehlerbehandlung:** HTTP-Status & `resp.text` sichtbar; für 404 bei ToDo: Hinweis.
   * **SSE-Anzeige:** Während des Streams mittels `st.status()` + `st.empty()` inkrementell rendern.
   * **Done-Definition:** Alle CRUD-Pfadfunktionen gegen die Backend-Routen lauffähig (siehe Code/Signaturen im Backend).&#x20;

3. **Konfiguration**

   * ENV `AGENT_API_BASE_URL` unterstützen.
   * Fallback: `http://localhost:8000`.
   * **Done-Definition:** Base-URL änderbar in Sidebar; UI ruft sofort gegen neue URL.

---

# 5) Lokales Starten & Smoke-Tests

## 5.1 Backend lokal

```bash
uv run uvicorn backend.app.main:app --reload --port 8000
```

**Smoke-Test:** `GET /health` → `{ "status": "ok" }`. (Middleware/CORS ist bereits aktiv. )

## 5.2 Frontend lokal

```bash
uv run streamlit run frontend/streamlit_app.py
```

## 5.3 Manuelle End-to-End-Checks

1. **Registrierung**

   * YAML/JSON einfügen → „Registrieren“ → erhält `id`; „Resolved anzeigen“ gibt Agents zurück.&#x20;
2. **Session**

   * „🆕 Session erstellen“ → `sid` sichtbar.
3. **Chat**

   * Nachricht senden → 202 → Stream startet; Chunks laufen ein.
4. **State/ToDo**

   * „🔄 State laden“ zeigt JSON-State.
   * „📥 ToDo Markdown laden“ zeigt Markdown oder „noch nicht vorhanden“.&#x20;
5. **Tools**

   * „🔄 Tools laden“ zeigt normalisierte Tools.&#x20;

---

# 6) Qualitäts-Checkliste (DoD)

* [ ] **Installierbar** via `uv sync`/`pip install -e .` (neue Deps sind in `pyproject.toml`).&#x20;
* [ ] **CORS/Netzwerk**: Aufruf aus Streamlit zum FastAPI-Backend ohne CORS-Fehler.&#x20;
* [ ] **SSE stabil**: Abbruch/Fehler werden abgefangen (UI bleibt bedienbar).
* [ ] **UX**: Klare Statusanzeigen (Processing/Done), verständliche Fehlertexte.
* [ ] **API-Vertrag**: Responses entsprechen den im Backend implementierten Schemas.&#x20;
* [ ] **Demo-Script**: Standard-Happy-Path funktioniert reproduzierbar.

---

# 7) Demo-Drehbuch (Pitch)

1. **Intro (15s):** „Wir registrieren jetzt ein Agent-System (YAML)…“
2. **Register (30s):** AgentSystem posten → `id` erscheint.
3. **Session (10s):** Session erstellen → `sid` erscheint.
4. **Chat (60–90s):** Prompt senden → Live-Stream anschauen (Delegation/Schritte).
5. **State/ToDo (30s):** JSON-State + ToDo-Markdown öffnen.
6. **Tools (15s):** Tool-Inventar anzeigen.

---

# 8) Risiken & Gegenmaßnahmen

* **SSE-Timeouts / Proxy-Issues:** `timeout` großzügig setzen; klare Fehlermeldung + Retry-Hinweis.
* **Fehlende `OPENAI_API_KEY`:** Backend gibt beim Registrieren/Verwenden Fehler; UI zeigt Ursache an. (Backend validiert Key beim Registrieren. )
* **404 bei ToDo:** Erwartetes Verhalten, freundlich kommunizieren.&#x20;

---

# 9) Erweiterungen (nach MVP)

* Datei-Upload für AgentSystem (YAML).
* Session-Picker (Dropdown mit bekannten `sid`s).
* Tool-Playground (gezielte Tool-Calls mit Parametern).
* Basic Auth/JWT (falls später nötig).

---

Wenn du willst, schreibe ich dir **jetzt** die beiden Dateien `frontend/streamlit_app.py` und `frontend/components/sse_chat.py` gemäß Plan — dann kannst du sofort loslegen.
