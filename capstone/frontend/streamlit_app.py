import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import streamlit as st
import yaml

from components.sse_chat import stream_agent


def get_default_base_url() -> str:
    """Return default backend base URL, reading from AGENT_API_BASE_URL if present."""
    return os.getenv("AGENT_API_BASE_URL", "http://localhost:8000")


def init_session_state() -> None:
    """Initialize Streamlit session state keys used by the app."""
    defaults: Dict[str, Any] = dict(
        agent_system_id=None,
        session_id=None,
        chat_history=[],
        last_state=None,
        todolist_md=None,
    )
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def post_agent_system(base_url: str, payload: Dict[str, Any]) -> Tuple[bool, Optional[str], str]:
    """POST /agent-systems and return (ok, id, error_text)."""
    try:
        url = f"{base_url.rstrip('/')}/agent-systems"
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code == 201:
            return True, resp.json().get("id"), ""
        return False, None, f"{resp.status_code}: {resp.text}"
    except Exception as exc:  # noqa: BLE001
        return False, None, str(exc)


def get_agent_system(base_url: str, system_id: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """GET /agent-systems/{id}."""
    try:
        url = f"{base_url.rstrip('/')}/agent-systems/{system_id}"
        resp = requests.get(url, timeout=15)
        if resp.ok:
            return True, resp.json(), ""
        return False, None, f"{resp.status_code}: {resp.text}"
    except Exception as exc:  # noqa: BLE001
        return False, None, str(exc)


def create_session(base_url: str, agent_system_id: str) -> Tuple[bool, Optional[str], str]:
    """POST /sessions with agent_system_id and return (ok, sid, err)."""
    try:
        url = f"{base_url.rstrip('/')}/sessions"
        body = {"agent_system_id": agent_system_id}
        resp = requests.post(url, json=body, timeout=15)
        if resp.status_code == 201:
            return True, resp.json().get("sid"), ""
        return False, None, f"{resp.status_code}: {resp.text}"
    except Exception as exc:  # noqa: BLE001
        return False, None, str(exc)


def post_message(base_url: str, session_id: str, text: str) -> Tuple[bool, str]:
    """POST /sessions/{sid}/messages and return (ok, err)."""
    try:
        url = f"{base_url.rstrip('/')}/sessions/{session_id}/messages"
        resp = requests.post(url, json={"text": text}, timeout=15)
        if resp.status_code in (200, 202):
            return True, ""
        return False, f"{resp.status_code}: {resp.text}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def get_state(base_url: str, session_id: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """GET /sessions/{sid}/state."""
    try:
        url = f"{base_url.rstrip('/')}/sessions/{session_id}/state"
        resp = requests.get(url, timeout=15)
        if resp.ok:
            return True, resp.json(), ""
        return False, None, f"{resp.status_code}: {resp.text}"
    except Exception as exc:  # noqa: BLE001
        return False, None, str(exc)


def get_todolist_md(base_url: str, session_id: str) -> Tuple[bool, Optional[str], str, int]:
    """GET /sessions/{sid}/artifacts/todolist.md returning (ok, text, err, status_code)."""
    try:
        url = f"{base_url.rstrip('/')}/sessions/{session_id}/artifacts/todolist.md"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            return True, resp.text, "", 200
        return False, None, resp.text, resp.status_code
    except Exception as exc:  # noqa: BLE001
        return False, None, str(exc), 0


def get_tools(base_url: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """GET /tools."""
    try:
        url = f"{base_url.rstrip('/')}/tools"
        resp = requests.get(url, timeout=15)
        if resp.ok:
            return True, resp.json(), ""
        return False, None, f"{resp.status_code}: {resp.text}"
    except Exception as exc:  # noqa: BLE001
        return False, None, str(exc)


def render_tab_agent_system(base_url: str) -> None:
    """Render the Agent System registration tab."""
    st.subheader("Agent System registrieren")
    st.caption("YAML ODER JSON einfügen. Wird direkt an POST /agent-systems gesendet.")

    def _read_prompt(rel_path: str, fallback: str) -> str:
        """Read prompt file relative to capstone root; return fallback on error."""
        try:
            root = Path(__file__).resolve().parents[1]
            text = (root / rel_path).read_text(encoding="utf-8")
            return text.strip()
        except Exception:
            return fallback.strip()

    def _indent_block(text: str, spaces: int = 6) -> str:
        """Indent every line of a multi-line string by N spaces for YAML literal blocks."""
        pad = " " * spaces
        return "\n".join(pad + line if line else pad for line in text.splitlines())

    system_text = _read_prompt(
        "examples/idp_pack/system_prompt_idp.txt",
        "You are an IDP agent that plans and executes using available tools.",
    )
    mission_text = _read_prompt(
        "examples/idp_pack/prompts/mission_template_git.txt",
        "Create a repository with AI-generated project templates locally and on GitHub; includes template selection and code generation.",
    )

    # Default YAML switched to single-agent configuration
    default_yaml = f"""
version: 1
system:
  name: idp-single-agent
agents:
  - id: idp_agent
    role: worker
    description: IDP agent that plans and executes with built-in tools
    system_prompt: |
{_indent_block(system_text)}

    mission: |
{_indent_block(mission_text)}

    max_steps: 40
    model:
      provider: openai
      model: gpt-4.1
      temperature: 0.1
    tools:
      allow:
        - validate_project_name_and_type
        - git_init_repo
        - discover_templates
        - select_template
        - apply_project_template
        - file_create
        - file_read
        - file_write
        - file_edit
        - file_delete
        - file_list_directory
        - git_add_files
        - git_commit
        - git_push
        - github_create_repo
        - git_set_remote
"""

    text = st.text_area("AgentSystem (YAML oder JSON)", value=default_yaml, height=320)

    col_a, col_b = st.columns([1, 1])
    with col_a:
        parse_as = st.radio("Format", ["YAML", "JSON"], horizontal=True)
    with col_b:
        register_btn = st.button("📥 Registrieren", type="primary")

    if register_btn:
        payload: Optional[Dict[str, Any]]
        try:
            if parse_as == "YAML":
                payload = yaml.safe_load(text)
            else:
                payload = json.loads(text)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Parsing-Fehler: {exc}")
            payload = None

        if payload is not None:
            ok, system_id, err = post_agent_system(base_url, payload)
            if ok and system_id:
                st.session_state.agent_system_id = system_id
                st.success(f"Registriert: {system_id}")
            else:
                st.error(f"Fehler {err}")

    if st.session_state.agent_system_id:
        with st.expander("📄 Resolved anzeigen (GET /agent-systems/{id})", expanded=False):
            ok, data, err = get_agent_system(base_url, st.session_state.agent_system_id)
            if ok and data is not None:
                st.json(data)
            else:
                st.warning(f"GET failed: {err}")


def render_tab_chat(base_url: str) -> None:
    """Render the Chat tab including session creation and SSE streaming."""
    st.subheader("Template-Based Project Creation")
    st.caption("Beschreibe dein gewünschtes Projekt und ich erstelle es mit der passenden Vorlage!")
    
    with st.expander("📋 Verfügbare Templates", expanded=False):
        st.markdown("""
        **Python FastAPI Hexagonal** - Microservice mit Hexagonal Architecture  
        *Beispiel: "Create Python FastAPI service named payment-api"*
        
        **Python Flask MVC** - Webanwendung mit MVC Pattern  
        *Beispiel: "Create Python web application named user-service"*
        
        **C# Web API Clean** - Enterprise API mit Clean Architecture + CQRS  
        *Beispiel: "Create C# Web API named order-service"*
        """)

    if not st.session_state.agent_system_id:
        st.info("Bitte zuerst ein Agent System registrieren (Tab „Agent System“).")
        return

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("🆕 Session erstellen"):
            ok, sid, err = create_session(base_url, st.session_state.agent_system_id)
            if ok and sid:
                st.session_state.session_id = sid
                st.session_state.chat_history = []
                st.success(f"Session: {sid}")
            else:
                st.error(f"Fehler: {err}")

    with col2:
        st.write(f"**Aktuelle Session:** `{st.session_state.session_id or '—'}`")

    user_msg = st.text_input(
        "Deine Nachricht",
        value=(
            "Create Python FastAPI service named payment-api"
        ),
        placeholder="Beschreibe dein Projekt (z.B. 'Create Python FastAPI service named user-api') …",
    )
    go = st.button("Senden & Streamen ▶", type="primary")

    st.divider()
    chat_box = st.container(border=True)
    for role, content in st.session_state.chat_history:
        chat_box.markdown(f"**{role}:** {content}")

    if go:
        if not st.session_state.session_id:
            st.warning("Bitte zuerst eine Session erstellen.")
            return

        ok, err = post_message(base_url, st.session_state.session_id, user_msg)
        if not ok:
            st.error(f"Post fehlgeschlagen: {err}")
            return

        st.session_state.chat_history.append(("Du", user_msg))

        with st.status("Agent arbeitet …", expanded=True) as status_box:
            stream_area = st.empty()
            acc: List[str] = []
            try:
                for chunk in stream_agent(base_url, st.session_state.session_id):
                    acc.append(chunk)
                    stream_area.markdown("".join(acc))
            except Exception as exc:  # noqa: BLE001
                st.error(f"SSE-Fehler: {exc}")
            else:
                full = "".join(acc)
                st.session_state.chat_history.append(("Agent", full))
                status_box.update(label="Fertig.", state="complete")


def render_tab_state_and_todo(base_url: str) -> None:
    """Render the session state and ToDo artifact tab."""
    st.subheader("Session State & ToDo List")
    if not st.session_state.session_id:
        st.info("Zuerst eine Session erstellen.")
        return

    cols = st.columns(3)
    with cols[0]:
        if st.button("🔄 State laden"):
            ok, data, err = get_state(base_url, st.session_state.session_id)
            if ok and data is not None:
                st.session_state.last_state = data
            else:
                st.error(f"Fehler: {err}")

    with cols[1]:
        if st.button("📥 ToDo Markdown laden"):
            ok, text, err, status = get_todolist_md(base_url, st.session_state.session_id)
            if ok and text is not None:
                st.session_state.todolist_md = text
                st.markdown(text)
            else:
                if status == 404:
                    st.warning("Noch kein ToDo-Artifact vorhanden.")
                else:
                    st.error(f"Fehler: {err}")

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


def render_tab_tools(base_url: str) -> None:
    """Render the tools listing tab."""
    st.subheader("Verfügbare Tools")
    if st.button("🔄 Tools laden"):
        ok, data, err = get_tools(base_url)
        if ok and data is not None:
            st.json(data)
        else:
            st.error(f"Fehler: {err}")


def main() -> None:
    """Main entrypoint rendering the Streamlit application."""
    st.set_page_config(page_title="Agent Demo", page_icon="🤖", layout="wide")

    st.sidebar.header("Backend")
    base_url = st.sidebar.text_input(
        "Base URL",
        value=get_default_base_url(),
        help="FastAPI Base URL, z. B. http://localhost:8000",
    )
    st.sidebar.caption(
        "Tipp: OPENAI_API_KEY im Backend setzen; ggf. GITHUB_TOKEN für Repo-Erstellung."
    )

    init_session_state()

    st.title("🚀 IDP Template-Based Project Creation")
    tab_sys, tab_chat, tab_state, tab_tools = st.tabs(
        ["⚙️ Agent System", "💬 Chat", "📋 State & ToDo", "🧰 Tools"]
    )

    with tab_sys:
        render_tab_agent_system(base_url)
    with tab_chat:
        render_tab_chat(base_url)
    with tab_state:
        render_tab_state_and_todo(base_url)
    with tab_tools:
        render_tab_tools(base_url)


if __name__ == "__main__":
    main()


