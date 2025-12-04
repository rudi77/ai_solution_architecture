# Epic 6: Transition zu "Lean ReAct" Architektur mit Planning-as-a-Tool

**Status:** Draft
**Priorität:** Hoch
**Owner:** Development Team
**Geschätzter Aufwand:** M (Medium) - Reduktion der Codebasis um ca. 70-80%

## 1. Executive Summary

Das Ziel dieses Epics ist die radikale Vereinfachung der `agent.py` (Core Domain Logic). Wir bewegen uns weg von einer starren, Code-basierten "Plan-and-Execute" Architektur hin zu einem dynamischen **"Lean ReAct"** Ansatz.

Anstatt den Planungsstatus (TodoList) im Python-Code zu verwalten, geben wir dem Agenten ein **`PlannerTool`**. Damit delegieren wir die Verantwortung für das Aufgabenmanagement an das LLM selbst ("Planning as a Tool"). Dies reduziert den Wartungsaufwand, eliminiert Fragilität beim JSON-Parsing und ermöglicht ein flüssigeres Verhalten bei generischen Aufgaben.

## 2. Problemstellung (Ist-Zustand)

Der aktuelle Agent (`agent.py`) ist mit ca. 1800 Zeilen Code unnötig komplex ("Over-Engineering"):

* **Rigide Strukturen:** `TodoList`, `TodoItem`, `Router` und separate Pfade (`fast_path` vs `full_path`) machen Erweiterungen schwer.
* **Brüchiges Parsing:** Das manuelle Erzwingen von JSON-Output via Prompting und Regex (`_generate_thought`) ist fehleranfällig.
* **Status-Desynchronisation:** Wenn der Agent vom Plan abweichen will, muss der Code dies via `_replan` aufwendig erkennen und die `TodoList` umschreiben.

## 3. Zielbild (Soll-Zustand)

Ein **Lean Agent** (< 250 Zeilen Core Logic), der auf einer einzigen Schleife basiert:

* **Single Loop:** Keine Unterscheidung mehr zwischen Fast/Full Path.
* **Native Tool Calling:** Nutzung der robusten API-Features (OpenAI/Anthropic Tools) statt Regex-Parsing.
* **Selbstverwaltung:** Der Agent nutzt ein `PlannerTool`, um komplexe Aufgaben zu strukturieren, wenn *er* es für nötig hält.

### Architektur-Vergleich

| Feature | Alte Architektur (Plan-and-Execute) | Neue Architektur (Lean ReAct) |
| :--- | :--- | :--- |
| **Steuerung** | Python Code erzwingt TodoList | LLM entscheidet selbstständig |
| **Planung** | `TodoListManager` Klasse | `PlannerTool` (Werkzeug) |
| **Execution** | `while not plan_complete` | `while step < max_steps` |
| **Parsing** | Custom JSON Parser & Retry Logik | Native LLM Tool Calling API |
| **Komplexität** | Hoch (State Machine) | Niedrig (Chat Loop) |

## 4. Implementierungs-Schritte (User Stories)

### Story 1: Implementierung des `PlannerTool`

**Ziel:** Ein Werkzeug schaffen, mit dem das LLM seinen eigenen State verwalten kann.

* Erstelle eine Klasse `PlannerTool` (implementiert `ToolProtocol`).
* **Actions:**
    * `create_plan(tasks: List[str])`: Überschreibt den aktuellen Plan.
    * `mark_done(step_index: int)`: Setzt einen Haken.
    * `read_plan()`: Gibt den formatierten Plan als String zurück.
    * `update_plan(...)`: Optional, um Schritte hinzuzufügen/zu löschen.
* **State:** Der Plan muss im `state_manager` persistierbar sein (Teil der Session).

### Story 2: Refactoring der `agent.py` (The Big Cut)

**Ziel:** Den Ballast abwerfen und den Core Loop neu schreiben.

* Entferne `TodoListManager`, `QueryRouter`, `ReplanStrategy`.
* Implementiere `LeanAgent` Klasse:
    * Nur noch **eine** `execute(mission)` Methode.
    * Initialisierung des `PlannerTool` im Konstruktor.
    * Entfernen der manuellen JSON-Prompt-Templates.

### Story 3: Integration von Native Tool Calling

**Ziel:** Robustheit erhöhen.

* Anpassung des `LLMProviderProtocol`, um `tools` und `tool_choice` Parameter nativ zu unterstützen.
* Im `execute`-Loop:
    * Check: Hat die LLM-Antwort `tool_calls`?
    * Falls JA: Iteriere über Calls -> Execute Tool -> Append Result to History.
    * Falls NEIN: Return Content as Final Answer.

### Story 4: Dynamic Context Injection (Das Herzstück)

**Ziel:** Dem Agenten den Plan "ins Gedächtnis rufen".

* Vor jedem LLM-Aufruf in der Schleife:
    1. Rufe `planner.execute("read_plan")` intern auf.
    2. Wenn ein Plan existiert, füge ihn in den **System Prompt** ein.
    * *Beispiel:* `Current Status:\n[x] Step 1\n[ ] Step 2...`
* Dies stellt sicher, dass der Agent nie vergisst, wo er im Prozess steht.

## 5. Technische Spezifikation & Snippets

### 5.1 Das neue System-Prompt Template

Der System-Prompt wird dynamisch. Er besteht aus einem statischen Teil und dem injizierten Plan.

```text
ROLE:
Du bist ein autonomer, robuster KI-Agent für [Firmenname].

CAPABILITIES:
Du hast Zugriff auf Tools (Wiki, RAG, etc.). Nutze sie weise.

STRATEGY:
1. Für einfache Fragen: Antworte direkt.
2. Für komplexe Aufgaben: Nutze das 'manage_plan' Tool, um Aufgaben zu strukturieren.
3. Halte dich an deinen Plan, aber sei bereit ihn zu ändern, wenn du in eine Sackgasse gerätst.

[INJECTED_PLAN_SECTION]
{current_plan_string}
```

### 5.2 Der vereinfachte Loop (Pseudocode Logic)

```python
# Innerhalb von LeanAgent.execute()

history = load_history()
planner = self.get_tool("manage_plan")

while steps < MAX_STEPS:
    # 1. Plan-Status holen (readonly call)
    current_plan = planner.read_plan()
    
    # 2. System Prompt on-the-fly zusammenbauen
    current_system_prompt = BASE_PROMPT.replace("{plan}", current_plan)
    
    # 3. LLM Call (Stateless bzgl. Plan-Logik im Python Code)
    response = llm.chat(
        system=current_system_prompt, 
        history=history, 
        tools=self.tools
    )
    
    # 4. Standard ReAct Handling
    if response.has_tool_calls():
        results = execute_tools(response.tool_calls)
        history.append(response, results)
        
        # Wichtig: State speichern (inkl. Planner-Daten!)
        save_state(history, planner.data)
    else:
        return response.content
```

## 6. Akzeptanzkriterien (Definition of Done)

1. **Code-Reduktion:** Die Datei `agent.py` hat signifikant weniger Code (< 250 Zeilen Core Logic).
2. **No-Plan Default:** Einfache Fragen ("Wie ist das Wetter?") führen zu **keinem** Aufruf des `PlannerTool` (0 Overhead).
3. **Complex Planning:** Eine Multi-Step-Anfrage ("Recherchiere X, dann Y, dann vergleiche") führt dazu, dass der Agent selbstständig einen Plan erstellt und abarbeitet.
4. **Resilience:** Wenn eine Suche fehlschlägt, stürzt der Agent nicht ab, sondern probiert eine Alternative.
5. **Persistence:** Der Agent kann mitten im Plan gestoppt und später (durch Laden der Session) fortgesetzt werden, ohne den Plan zu vergessen.

## 7. Risiken & Mitigation

* **Risiko:** Das Modell nutzt das `PlannerTool` nicht zuverlässig.
    * *Mitigation:* Tuning des System-Prompts und Hinzufügen von "Few-Shot" Beispielen (Beispiele für gute Plan-Nutzung) in den Prompt.
* **Risiko:** Endlosschleifen.
    * *Mitigation:* Hard-Limit für `MAX_STEPS` (z.B. 20) beibehalten.

## 8. Validation Checklist

**Scope Validation:**
- [x] Epic can be completed in 1-3 stories maximum (4 Stories defined)
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

## 9. Story Manager Handoff

**Story Manager Handoff:**

"Please develop detailed user stories for this brownfield epic. Key considerations:

- This is an enhancement to an existing system running Python/Agent Framework.
- Integration points: `agent.py`, `LLMProvider`, `System Prompts`.
- Existing patterns to follow: `ToolProtocol`, `ReAct Loop`.
- Critical compatibility requirements: CLI behavior must remain stable.
- Each story must include verification that existing functionality remains intact (or is improved).

The epic should maintain system integrity while delivering a simplified, robust 'Lean ReAct' architecture."

