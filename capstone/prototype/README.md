# IDP Copilot Prototype (ReAct Agent)

Ein produktionsnaher, generischer ReAct-Agent zur Unterstützung interner Developer-Plattform-Workflows (IDP). Der Agent plant Aufgaben als Todo-Liste, führt Tools aus, persistiert Zustand, sammelt Feedback und liefert Metriken für Observability.

## Highlights

- ReAct-Loop mit plan-first-Heuristik und Loop-Guard gegen Endlosschleifen
- Persistenter Zustand je Session in `./agent_states` (Wiederaufnahme möglich)
- Ausführbare Todo-Liste als Markdown in `./checklists` (Plan, Status, Ergebnisse)
- Tool-Ökosystem mit einheitlichem Schema und Alias-/Lookup-Index
- Telemetrie: Prometheus-Metriken (Standard: `http://localhost:8070`) und optional OpenTelemetry-Traces
- Feedback-Sammlung als JSON-Dateien in `./feedback`
- LLM-Provider-Abstraktion (OpenAI, optional Anthropic)

## Verzeichnisstruktur (Ausschnitt)

- `agent.py` — ReAct-Agent mit Plan-First, Tool-Calling, Retry/Backoff, Loop-Guard
- `tools.py` — Tool-Spezifikation, Normalisierung, Ausführung, Index
- `tools_builtin.py` — Beispielhafte Built-in-Tools (Repo-Erstellung, CI/CD, K8s, u.a.)
- `todolist_md.py` — Erstellen/Aktualisieren der Markdown-Todo-Liste
- `todolist_actions.py` — Kompatibilitätshilfen für Todo-Listen-Operationen
- `statemanager.py` — Persistenz von Agenten-Sessionzustand
- `feedback_collector.py` — Pufferung und persistente Ablage von Feedback
- `llm_provider.py` — Abstraktion + Provider (OpenAI, Anthropic)
- `prompt.py` — System-Prompts (Guides für Agentenverhalten)
- `idp.py` — Startbarer CLI-Einstieg (interaktive Session, Prometheus-Server)

## Voraussetzungen

- Windows PowerShell (dieses Projekt setzt Windows voraus)
- Git (für Tools wie Repository-Erstellung)
- Python 3.10+ empfohlen
- uv als Python-Paket- und Projektmanagement-Tool

### uv installieren (PowerShell)

```powershell
iwr https://astral.sh/uv/install.ps1 -UseBasicParsing | iex
```

Überprüfen:

```powershell
uv --version
```

## Installation

Im Projektstamm arbeiten: `C:\Users\rudi\source\ai_solution_architecture`.

```powershell
# In den Projektordner wechseln
Set-Location C:\Users\rudi\source\ai_solution_architecture

# Virtuelle Umgebung anlegen
uv venv .venv

# Aktivieren (PowerShell)
. .\.venv\Scripts\Activate.ps1

# Abhängigkeiten installieren
uv pip install -r .\capstone\prototype\requirements.txt
```

## Konfiguration (Umgebungsvariablen)

- `OPENAI_API_KEY` — erforderlich für OpenAI-Provider
- `GITHUB_TOKEN` — optional, für Remote-Repo-Erstellung auf GitHub (via Tools)
- `GITHUB_ORG` / `GITHUB_OWNER` — optional, Zielorganisation/-konto für GitHub-Repo
- `IDP_ENABLE_OTEL_CONSOLE` — optional (`true`/`false`), aktiviert Console-Exporter für OpenTelemetry

PowerShell-Beispiele:

```powershell
# Für die aktuelle Session
$env:OPENAI_API_KEY = "sk-..."
$env:GITHUB_TOKEN = "ghp_..."
$env:GITHUB_ORG = "my-org"
$env:IDP_ENABLE_OTEL_CONSOLE = "true"

# Dauerhaft (neue Sessions), danach neues Terminal öffnen
setx OPENAI_API_KEY "sk-..."
setx GITHUB_TOKEN "ghp_..."
setx GITHUB_ORG "my-org"
setx IDP_ENABLE_OTEL_CONSOLE "true"
```

## Schnellstart (CLI)

Der Einstiegspunkt `idp.py` startet den Prometheus-Metrikserver auf Port 8070 und eine interaktive Konsole.

```powershell
# Aktivierte venv vorausgesetzt
python .\capstone\prototype\idp.py
```

- Beenden: `exit` oder `quit`
- Metriken: im Browser `http://localhost:8070`

Hinweis: Ohne `OPENAI_API_KEY` bricht der Start mit einem Fehler ab.

## Agent und Tools verwenden

Der CLI startet einen generischen Agenten ohne vordefinierte Tools. Für Automationen können die Built-in-Tools aus `tools_builtin.py` übergeben werden.

### Tool-Schnittstelle (Kurzüberblick)

- Definition via `ToolSpec`:
  - `name`, `description`
  - `input_schema` (JSON-Schema), `output_schema`
  - `func` (async empfohlen), optionale `aliases`
- Der Agent ruft Tools über Vendor-Function-Calling oder über strukturierte Entscheidungen auf.
- Ergebnisse werden in der Todo-Liste festgehalten und als Feedback/Metriken erfasst.

### Built-in-Tools (Auswahl)

- `create_repository` — Lokales Git-Repo + optional GitHub-Remote anlegen und pushen
- `validate_project_name_and_type` — Validierung auf kebab-case und erlaubte Typen
- `create_git_repository_with_branch_protection` — Repo + Standard-Branchregeln
- `apply_template`, `list_templates` — Templates aufsetzen
- `setup_cicd_pipeline` — Beispielhafte CI/CD-Konfiguration
- `generate_k8s_manifests`, `create_k8s_namespace`, `deploy_to_staging` — K8s-Workflows (Demo)
- `search_knowledge_base_for_guidelines` — Lokale Richtlinien durchsuchen
- `setup_observability`, `generate_documentation` — Observability/Dokumentation (Demo)

## Todo-Liste, Zustand, Feedback

- Todo-Liste: Markdown-Dateien unter `./checklists` mit Sektionen: Title, Meta, Tasks, Open Questions, Notes
- Zustand: Serialisiert pro Session in `./agent_states/<session_id>.pkl`
- Feedback: Gesammelte Einträge als JSON in `./feedback/feedback_YYYYMMDD_HHMMSS.json`

Der Agent erzeugt initial eine Todo-Liste (Plan) und aktualisiert sie nach jedem Tool-Lauf (Status, Resultate). Bei Blockern stellt er gezielte Rückfragen an den Nutzer.

## Observability

- Prometheus: Histogramme/Zähler zur Workflow- und Tool-Performance, automatisch via `idp.py` auf Port 8070
- OpenTelemetry: Aktivierbar über `IDP_ENABLE_OTEL_CONSOLE=true` (Konsolenexporter)

## Typische Fehler und Abhilfe

- Fehlende API Keys: Setzen von `OPENAI_API_KEY` erforderlich
- Git nicht installiert: Tools wie `create_repository` schlagen fehl → Git installieren und in den `PATH` aufnehmen
- GitHub ohne Token: Remote-Repo-Erstellung schlägt fehl; lokales Repo wird dennoch angelegt
- Tool nicht gefunden: Toolname/alias prüfen; Normalisierung nutzt Kleinschreibung und ersetzt Leerzeichen/Bindestriche mit Unterstrich

## Entwicklung und Erweiterung

- Neue Tools: Als `ToolSpec` definieren und dem Agenten beim Erzeugen übergeben
- Prompts: In `prompt.py` anpassbar (z. B. fokussierte Git-Workflows)
- LLM-Provider: `llm_provider.py` bietet OpenAI und Anthropic; Konfiguration über Konstruktorparameter und Env-Variablen

## Tests

Es sind keine Tests hinterlegt; die Testtools sind vorhanden. Beispiel:

```powershell
uv run pytest -q
```

## Lizenz

Sofern nicht anders angegeben, intern verwendbar. Bitte organisationsspezifische Lizenzierung ergänzen.
