# Epic: Transition zu "Lean ReAct" Architektur mit Planning-as-a-Tool - Brownfield Enhancement

## Epic Goal

Das Ziel dieses Epics ist die radikale Vereinfachung der `agent.py` (Core Domain Logic). Wir bewegen uns weg von einer starren, Code-basierten "Plan-and-Execute" Architektur hin zu einem dynamischen **"Lean ReAct"** Ansatz. Anstatt den Planungsstatus (TodoList) im Python-Code zu verwalten, geben wir dem Agenten ein **`PlannerTool`**. Damit delegieren wir die Verantwortung für das Aufgabenmanagement an das LLM selbst ("Planning as a Tool"). Dies reduziert den Wartungsaufwand, eliminiert Fragilität beim JSON-Parsing und ermöglicht ein flüssigeres Verhalten bei generischen Aufgaben.

## Epic Description

### Existing System Context

**Current relevant functionality:**
Der aktuelle Agent (`agent.py`) ist mit ca. 900 Zeilen Code unnötig komplex ("Over-Engineering").
- **Rigide Strukturen:** `TodoList`, `TodoItem`, `Router` und separate Pfade (`fast_path` vs `full_path`) machen Erweiterungen schwer.
- **Brüchiges Parsing:** Das manuelle Erzwingen von JSON-Output via Prompting und Regex (`_generate_thought`) ist fehleranfällig.
- **Status-Desynchronisation:** Wenn der Agent vom Plan abweichen will, muss der Code dies via `_replan` aufwendig erkennen und die `TodoList` umschreiben.

**Technology stack:**
- Python Agent Framework
- LLM (OpenAI/Anthropic)
- Custom Tool Implementations

**Integration points:**
- `agent.py` Core Logic
- `TodoListManager` (to be replaced/removed)
- System Prompts

### Enhancement Details

**What's being added/changed:**
Ein **Lean Agent** (< 200 Zeilen Code), der auf einer einzigen Schleife basiert:
- **Single Loop:** Keine Unterscheidung mehr zwischen Fast/Full Path.
- **Native Tool Calling:** Nutzung der robusten API-Features (OpenAI/Anthropic Tools) statt Regex-Parsing.
- **Selbstverwaltung:** Der Agent nutzt ein `PlannerTool`, um komplexe Aufgaben zu strukturieren, wenn *er* es für nötig hält.

**Architektur-Vergleich:**

| Feature | Alte Architektur (Plan-and-Execute) | Neue Architektur (Lean ReAct) |
| :--- | :--- | :--- |
| **Steuerung** | Python Code erzwingt TodoList | LLM entscheidet selbstständig |
| **Planung** | `TodoListManager` Klasse | `PlannerTool` (Werkzeug) |
| **Execution** | `while not plan_complete` | `while step < max_steps` |
| **Parsing** | Custom JSON Parser & Retry Logik | Native LLM Tool Calling API |
| **Komplexität** | Hoch (State Machine) | Niedrig (Chat Loop) |

**Technical Approach (Dynamic Context Injection):**
- **Dynamic System Prompt:** Kombination aus `GENERAL_AUTONOMOUS_KERNEL_PROMPT` (Kernel) und `WIKI_SYSTEM_PROMPT` (Specialist) sowie injiziertem Plan-Status.
- **PlannerTool Integration:** `planner.read_plan()` wird vor jedem LLM-Aufruf ausgeführt und das Ergebnis in den Prompt injiziert.

**Success criteria:**
- Code-Reduktion der `agent.py` um ca. 70-80%.
- Agent kann Plan selbstständig erstellen und verwalten.
- Robustheit gegen Parsing-Fehler durch Native Tool Calling.

## Stories

1. **Story 1: Implementierung des `PlannerTool`**
   Ein Werkzeug schaffen, mit dem das LLM seinen eigenen State verwalten kann.
   - Klasse `PlannerTool` implementieren (ToolProtocol).
   - Actions: `create_plan`, `mark_done`, `read_plan`, `update_plan`.
   - State-Persistenz im `state_manager`.

2. **Story 2: Refactoring der `agent.py` (The Big Cut)**
   Den Ballast abwerfen und den Core Loop neu schreiben.
   - Entferne `TodoListManager`, `QueryRouter`, `ReplanStrategy`.
   - Implementiere `LeanAgent` Klasse: nur eine `execute` Methode, `PlannerTool` im Konstruktor, Entfernen manueller JSON-Prompts.
   - Implementierung der Dynamic Prompt Assembly (Kernel + Specialist + Plan).

3. **Story 3: Integration von Native Tool Calling & Dynamic Context Injection**
   Robustheit erhöhen und dem Agenten den Plan "ins Gedächtnis rufen".
   - Anpassung `LLMProviderProtocol` für native `tools`.
   - Implementierung des Loops: Check auf `tool_calls`, Execute Tools, Append Result.
   - Context Injection: `planner.execute("read_plan")` vor jedem Call in den System Prompt injizieren.

## Compatibility Requirements

- [x] Existing APIs remain unchanged (CLI Interface)
- [x] Database schema changes are backward compatible (State persistence format changes handled)
- [x] UI changes follow existing patterns (CLI Output)
- [x] Performance impact is minimal (Reduced overhead)

## Risk Mitigation

- **Primary Risk:** Das Modell nutzt das `PlannerTool` nicht zuverlässig.
  - **Mitigation:** Tuning des System-Prompts und Hinzufügen von "Few-Shot" Beispielen (Beispiele für gute Plan-Nutzung) in den Prompt.
- **Primary Risk:** Endlosschleifen.
  - **Mitigation:** Hard-Limit für `MAX_STEPS` (z.B. 20) beibehalten.

## Definition of Done

- [ ] **Code-Reduktion:** Die Datei `agent.py` hat weniger als 250 Zeilen Code.
- [ ] **No-Plan Default:** Einfache Fragen ("Wie ist das Wetter?") führen zu **keinem** Aufruf des `PlannerTool` (0 Overhead).
- [ ] **Complex Planning:** Eine Multi-Step-Anfrage ("Recherchiere X, dann Y, dann vergleiche") führt dazu, dass der Agent selbstständig einen Plan erstellt und abarbeitet.
- [ ] **Resilience:** Wenn eine Suche fehlschlägt, stürzt der Agent nicht ab, sondern probiert eine Alternative.
- [ ] **Persistence:** Der Agent kann mitten im Plan gestoppt und später fortgesetzt werden, ohne den Plan zu vergessen.

## Validation Checklist

**Scope Validation:**
- [x] Epic can be completed in 1-3 stories maximum (3 Stories defined)
- [x] No architectural documentation is required (Architecture is simplified, captured in Epic)
- [x] Enhancement follows existing patterns (Tool Protocol)
- [x] Integration complexity is manageable

**Risk Assessment:**
- [x] Risk to existing system is low (Refactoring Core, but covered by tests)
- [x] Rollback plan is feasible (Git)
- [x] Testing approach covers existing functionality
- [x] Team has sufficient knowledge of integration points

**Completeness Check:**
- [x] Epic goal is clear and achievable
- [x] Stories are properly scoped
- [x] Success criteria are measurable
- [x] Dependencies are identified

## Handoff to Story Manager

---

**Story Manager Handoff:**

"Please develop detailed user stories for this brownfield epic. Key considerations:

- This is an enhancement to an existing system running Python/Agent Framework.
- Integration points: `agent.py`, `LLMProvider`, `System Prompts`.
- Existing patterns to follow: `ToolProtocol`, `ReAct Loop`.
- Critical compatibility requirements: CLI behavior must remain stable.
- Each story must include verification that existing functionality remains intact (or is improved).

The epic should maintain system integrity while delivering a simplified, robust 'Lean ReAct' architecture."

---

