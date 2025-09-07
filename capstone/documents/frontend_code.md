alles klar — hier ist der **Streamlit-Code** für deine Demo (zwei Dateien). Er nutzt genau deine bestehenden Endpunkte (`/agent-systems`, `/sessions`, `/sessions/{sid}/messages`, `/sessions/{sid}/stream`, `/sessions/{sid}/state`, `/sessions/{sid}/artifacts/todolist.md`, `/tools`) und passt zu deiner Projektkonfiguration. &#x20;

---

### `frontend/components/sse_chat.py`

```python
# frontend/components/sse_chat.py
import json
import requests
from sseclient import SSEClient


def stream_agent(base_url: str, sid: str):
    """
    Yields text chunks from the backend SSE endpoint /sessions/{sid}/stream.
    The backend emits Server-Sent Events in the form "data: <json-dumped-string>".
    """
    url = f"{base_url.rstrip('/')}/sessions/{sid}/stream"
    with requests.get(url, stream=True, timeout=300) as resp:
        resp.raise_for_status()
        client = SSEClient(resp)
        for event in client.events():
            if not event.data:
                continue
            try:
                payload = json.loads(event.data)  # backend dumps a string; we try to decode once
            except Exception:
                payload = event.data
            # Always yield a string for display
            yield str(payload)
```

---

### `frontend/streamlit_app.py`

```python
# frontend/streamlit_app.py
import os
import json
import yaml
import requests
import streamlit as st

from components.sse_chat import stream_agent

st.set_page_config(page_title="Agent Demo", page_icon="🤖", layout="wide")

# ---------------------------
# Sidebar / Config
# ---------------------------
DEFAULT_BASE_URL = os.getenv("AGENT_API_BASE_URL", "http://localhost:8000")
st.sidebar.header("Backend")
base_url = st.sidebar.text_input(
    "Base URL",
    value=DEFAULT_BASE_URL,
    help="FastAPI Base URL, z. B. http://localhost:8000",
)
st.sidebar.caption("Tipp: OPENAI_API_KEY im Backend setzen; ggf. GITHUB_TOKEN für Repo-Erstellung.")

# ---------------------------
# Session State (init)
# ---------------------------
for k, v in dict(
    agent_system_id=None,
    session_id=None,
    chat_history=[],
    last_state=None,
    todolist_md=None,
).items():
    st.session_state.setdefault(k, v)

st.title("🤖 Agent Orchestration Demo")

tab_sys, tab_chat, tab_state, tab_tools = st.tabs(
    ["⚙️ Agent System", "💬 Chat", "📋 State & ToDo", "🧰 Tools"]
)

# ===========================================================
# TAB 1: Agent System registrieren
# ===========================================================
with tab_sys:
    st.subheader("Agent System registrieren")
    st.caption("YAML ODER JSON einfügen. Wird direkt an POST /agent-systems gesendet.")

    default_yaml = """\
version: 1
system:
  name: idp-orchestrator
agents:
  - id: orchestrator
    role: orchestrator
    description: Main orchestrator
    system_prompt: |
      You are the Orchestrator Agent...
    mission: |
      Coordinate sub-agents to accomplish the task.
    max_steps: 40
    model:
      provider: openai
      model: gpt-4.1
      temperature: 0.1
    tools:
      allow:
        - agent_git
        - validate_project_name_and_type
        - create_repository
  - id: agent_git
    role: worker
    description: Git worker
    system_prompt: |
      You are a Git-focused worker agent...
    mission: |
      Create repo and push initial commit.
    max_steps: 12
    model:
      provider: openai
      model: gpt-4.1
      temperature: 0.1
    tools:
      allow:
        - validate_project_name_and_type
        - create_repository
"""
    text = st.text_area("AgentSystem (YAML oder JSON)", value=default_yaml, height=320)

    colA, colB = st.columns([1, 1])
    with colA:
        parse_as = st.radio("Format", ["YAML", "JSON"], horizontal=True)
    with colB:
        register_btn = st.button("📥 Registrieren", type="primary")

    if register_btn:
        # 1) parse
        try:
            if parse_as == "YAML":
                payload = yaml.safe_load(text)
            else:
                payload = json.loads(text)
        except Exception as e:
            st.error(f"Parsing-Fehler: {e}")
            payload = None

        # 2) POST /agent-systems
        if payload is not None:
            try:
                url = f"{base_url.rstrip('/')}/agent-systems"
                resp = requests.post(url, json=payload, timeout=30)
                if resp.status_code == 201:
                    data = resp.json()
                    st.session_state.agent_system_id = data["id"]
                    st.success(f"Registriert: {data['id']}")
                else:
                    st.error(f"Fehler {resp.status_code}: {resp.text}")
            except Exception as e:
                st.error(f"Request-Fehler: {e}")

    if st.session_state.agent_system_id:
        with st.expander("📄 Resolved anzeigen (GET /agent-systems/{id})", expanded=False):
            try:
                url = f"{base_url.rstrip('/')}/agent-systems/{st.session_state.agent_system_id}"
                res = requests.get(url, timeout=15)
                if res.ok:
                    st.json(res.json())
                else:
                    st.warning(f"GET failed: {res.status_code} {res.text}")
            except Exception as e:
                st.error(f"Fehler: {e}")

# ===========================================================
# TAB 2: Chatten / Stream
# ===========================================================
with tab_chat:
    st.subheader("Chat mit Orchestrator")

    if not st.session_state.agent_system_id:
        st.info("Bitte zuerst ein Agent System registrieren (Tab „Agent System“).")
    else:
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("🆕 Session erstellen"):
                try:
                    url = f"{base_url.rstrip('/')}/sessions"
                    body = {"agent_system_id": st.session_state.agent_system_id}
                    r = requests.post(url, json=body, timeout=15)
                    if r.status_code == 201:
                        st.session_state.session_id = r.json()["sid"]
                        st.session_state.chat_history = []
                        st.success(f"Session: {st.session_state.session_id}")
                    else:
                        st.error(f"Fehler: {r.status_code} {r.text}")
                except Exception as e:
                    st.error(f"Fehler: {e}")
        with col2:
            st.write(f"**Aktuelle Session:** `{st.session_state.session_id or '—'}`")

        user_msg = st.text_input(
            "Deine Nachricht",
            value="Erzeuge ein neues Service-Repo 'awesome-svc' und pushe initialen Commit.",
            placeholder="Nachricht für den Orchestrator …",
        )
        go = st.button("Senden & Streamen ▶", type="primary")

        st.divider()
        chat_box = st.container(border=True)
        for role, content in st.session_state.chat_history:
            chat_box.markdown(f"**{role}:** {content}")

        if go:
            if not st.session_state.session_id:
                st.warning("Bitte zuerst eine Session erstellen.")
            else:
                try:
                    # POST /sessions/{sid}/messages (202)
                    url_post = f"{base_url.rstrip('/')}/sessions/{st.session_state.session_id}/messages"
                    r = requests.post(url_post, json={"text": user_msg}, timeout=15)
                    if r.status_code not in (200, 202):
                        st.error(f"Post fehlgeschlagen: {r.status_code} {r.text}")
                    else:
                        st.session_state.chat_history.append(("Du", user_msg))

                        # SSE-Stream starten
                        with st.status("Agent arbeitet …", expanded=True) as s:
                            stream_area = st.empty()
                            acc = []
                            try:
                                for chunk in stream_agent(base_url, st.session_state.session_id):
                                    acc.append(chunk)
                                    # kleiner Schutz gegen zu schnelles Re-Rendern
                                    stream_area.markdown("".join(acc))
                            except Exception as e:
                                st.error(f"SSE-Fehler: {e}")
                            else:
                                full = "".join(acc)
                                st.session_state.chat_history.append(("Agent", full))
                                s.update(label="Fertig.", state="complete")

                except Exception as e:
                    st.error(f"Fehler: {e}")

# ===========================================================
# TAB 3: State & ToDo
# ===========================================================
with tab_state:
    st.subheader("Session State & ToDo List")
    if not st.session_state.session_id:
        st.info("Zuerst eine Session erstellen.")
    else:
        cols = st.columns(3)
        with cols[0]:
            if st.button("🔄 State laden"):
                try:
                    url = f"{base_url.rstrip('/')}/sessions/{st.session_state.session_id}/state"
                    r = requests.get(url, timeout=15)
                    if r.ok:
                        st.session_state.last_state = r.json()
                    else:
                        st.error(f"Fehler: {r.status_code} {r.text}")
                except Exception as e:
                    st.error(f"Fehler: {e}")

        with cols[1]:
            if st.button("📥 ToDo Markdown laden"):
                try:
                    url = f"{base_url.rstrip('/')}/sessions/{st.session_state.session_id}/artifacts/todolist.md"
                    r = requests.get(url, timeout=15)
                    if r.status_code == 200:
                        st.session_state.todolist_md = r.text
                        st.markdown(r.text)
                    else:
                        st.warning("Noch kein ToDo-Artifact vorhanden.")
                except Exception as e:
                    st.error(f"Fehler: {e}")

        with cols[2]:
            if st.button("🔎 Raw ToDo als Link anzeigen"):
                url = f"{base_url.rstrip('/')}/sessions/{st.session_state.session_id}/artifacts/todolist.md"
                st.write(url)

        st.divider()
        st.write("Letzter State:")
        st.json(st.session_state.last_state or {})

        if st.session_state.todolist_md:
            st.divider()
            st.write("ToDo Markdown:")
            st.markdown(st.session_state.todolist_md)

# ===========================================================
# TAB 4: Tools
# ===========================================================
with tab_tools:
    st.subheader("Verfügbare Tools")
    if st.button("🔄 Tools laden"):
        try:
            url = f"{base_url.rstrip('/')}/tools"
            r = requests.get(url, timeout=15)
            if r.ok:
                st.json(r.json())
            else:
                st.error(f"Fehler: {r.status_code} {r.text}")
        except Exception as e:
            st.error(f"Fehler: {e}")
```

---

### Start-Hinweise

```bash
# Backend (deins)
uv run uvicorn backend.app.main:app --reload --port 8000

# Frontend
uv run streamlit run frontend/streamlit_app.py
```

Wenn du magst, ergänze ich dir gleich noch Datei-Upload für AgentSystem (YAML) oder einen einfachen Session-Picker.
