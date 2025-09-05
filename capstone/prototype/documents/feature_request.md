Got it—hier ist ein präzises Feature-Request-Dokument für deinen neuen Prompt-Mechanismus. Ich habe die aktuellen Stellen im Code referenziert, an denen wir ansetzen, und gebe konkrete Änderungs-/Migrationsschritte inkl. Akzeptanzkriterien.

# Feature Request: Komponierbarer SystemPrompt mit `<GenericAgentSection>`, `<Mission>`, `<Tools>`

## Ziel

Der Agent soll seinen finalen SystemPrompt deterministisch **zusammenbauen** aus drei klar getrennten Sektionen:

```
<GenericAgentSection>
  …Default-Verhaltensregeln & Arbeitsweise…
</GenericAgentSection>

<Mission>
  …spezifische Aufgabe/Scope für diesen Run…
</Mission>

<Tools>
  …automatisch generierte Tool-Beschreibung inkl. Required-Params…
</Tools>
```

Dabei sind **SystemPrompt (optional)** und **Mission (optional)** externe Parameter. Tools werden ohnehin als Liste übergeben. Fehlen externe Angaben, nutzt der Agent sinnvolle Defaults.

---

## Status Quo (Ist-Analyse & Anknüpfpunkte)

* `ReActAgent` erwartet aktuell einen kompletten `system_prompt` von außen und **appendet** eine dynamische TOOLS-Liste via `_compose_system_prompt()` (Regeln + Tools) (siehe `_compose_system_prompt` in `agent.py`) .
* Der CLI-Beispiel-Runner lädt den Prompt aus `system_prompt_git.txt` und reicht ihn direkt an Agent & Subagent (delegation) weiter ; der Text selbst enthält Scope/Verantwortlichkeiten/Allowed-Tools für die IDP-Demo .
* Tooling ist als `ToolSpec` definiert; Name, Description, `input_schema.required` sind verfügbar (Grundlage für `<Tools>`-Sektion) .
* Der LLM-Provider akzeptiert `system_prompt` dediziert in **allen** Pfaden (free-form, structured, tool-calling) – kompatibel zur neuen Prompt-Komposition .
* Sub-Agent wrapping existiert bereits (`to_tool(system_prompt_override=...)`), sodass wir Missions/Prompt-Overrides gezielt weiterreichen können .
* Todo-List-Erzeugung/Updates rufen den LLM ebenfalls mit `system_prompt` auf; funktionieren weiter, wenn wir denselben finalen Prompt reinschieben  .

---

## Umfang (Was wird gebaut)

1. **Neues Prompt-API am Agenten**

   * `ReActAgent(...)` akzeptiert zusätzlich:

     * `generic_system_prompt: Optional[str] = None`  (Default-Sektion)
     * `mission: Optional[str] = None`                 (Missions-Sektion)
     * `prompt_overrides: Optional[dict] = None`       (feinere Steuerung, s.u.)
   * Falls `system_prompt` (bisheriger Parameter) **weiterhin** mitgegeben wird, wird er als **Legacy-Override** behandelt (kompletter Prompt, gewinnt nur wenn `prompt_overrides={'mode':'legacy_full'}` gesetzt ist). Standardpfad ist die **Komposition** aus 3 Sektionen.

2. **Neue Prompt-Komposition**

   * Ersetze `_compose_system_prompt()` durch einen Builder, der:

     * `<GenericAgentSection>` aus `generic_system_prompt` nimmt oder einen projektsicheren Default (siehe **Default-Template** unten).
     * `<Mission>` aus `mission` rendert; wenn `None`, bleibt die Sektion leer, aber **vorhanden** (stabil für Prompts).
     * `<Tools>` automatisch aus `self.tools` erzeugt: `- <name>: <description> (required: a,b,c)` (nur wenn `required` nicht leer ist) – aktuell existiert bereits eine ähnliche Liste inkl. Regeln; jetzt in die formale `<Tools>`-Sektion überführen .
   * Schlussabschnitt **Usage Rules** wandert in `<GenericAgentSection>` (Default).

3. **Sub-Agent Missionsweitergabe**

   * `to_tool(...)` erweitert um optionale Argumente `mission_override: Optional[str] = None`, `generic_system_prompt_override: Optional[str] = None`.
   * Der Sub-Agent nutzt denselben Kompositionsmechanismus (gleiches Default-Generic + Mission + Tools).

4. **CLI/Example-Migration**

   * `run_idp_cli.py`: statt den kompletten Prompt aus `system_prompt_git.txt` als full `system_prompt` zu setzen, verwenden wir den Text fortan als **Mission** der Demo-App; `generic_system_prompt` kommt aus Default oder separater Datei (optional)  .

5. **Kompatibilität**

   * Bestehende Aufrufer, die weiter `system_prompt` übergeben, funktionieren unverändert, wenn `prompt_overrides={'mode':'legacy_full'}` gesetzt wird; ansonsten wird der neue Mechanismus genutzt (bei Konflikt gewinnt `prompt_overrides.mode`).

---

## Default-Template (Vorschlag)

**`DEFAULT_GENERIC_PROMPT`** (eingebettet in `agent.py` oder eigene Datei):

```
<GenericAgentSection>
You are a ReAct-style execution agent.

Operating principles:
- Plan-first: create/update a concise Todo List; clarify blocking questions first.
- Be deterministic, keep outputs minimal & actionable.
- After each tool call, update state; avoid loops; ask for help on blockers.

Decision policy:
- Prefer available tools; ask user only for truly blocking info.
- Stop when acceptance criteria for the mission are met.

Output style:
- Short, structured, CLI-friendly status lines.
</GenericAgentSection>
```

*(Die bestehenden „Usage rules“ aus `_compose_system_prompt()` ziehen in diesen Block um) .*

---

## Öffentliche API-Änderungen

### `ReActAgent.__init__`

**Neu:**

```python
def __init__(
    self,
    system_prompt: str | None,              # legacy_full (optional)
    llm: LLMProvider,
    *,
    tools: list[ToolSpec] | None = None,
    max_steps: int = 50,
    generic_system_prompt: str | None = None,
    mission: str | None = None,
    prompt_overrides: dict | None = None,   # e.g., {'mode':'compose'|'legacy_full'}
):
    ...
```

### Prompt-Builder

* `self._build_final_system_prompt()` ersetzt `self._compose_system_prompt()`.
* Modi:

  * **compose** (Default): `<GenericAgentSection>` + `<Mission>` + `<Tools>`.
  * **legacy\_full**: nutzt den gelieferten `system_prompt` 1:1 (heutiges Verhalten).

### `ReActAgent.to_tool(...)`

**Neu:**

```python
def to_tool(...,
    mission_override: str | None = None,
    generic_system_prompt_override: str | None = None,
):
    ...
    sub = ReActAgent(
        system_prompt=None,
        llm=self.llm,
        tools=tools_whitelist,
        max_steps=max_steps,
        generic_system_prompt=generic_system_prompt_override or self.generic_system_prompt_base,
        mission=mission_override,   # z.B. „Scaffold webservice …“
        prompt_overrides={'mode':'compose'},
    )
```

(Heute gibt es `system_prompt_override`, das wir deprecaten oder intern auf `mission_override` mappen) .

---

## Implementierungsdetails (konkrete Arbeitspakete)

1. **agent.py**

   * Felder ergänzen: `self.generic_system_prompt_base`, `self.mission_text`, `self.prompt_overrides`.
   * `_build_final_system_prompt()` implementieren:

     * Nimmt `generic_system_prompt_base` oder `DEFAULT_GENERIC_PROMPT`.
     * Rendert `<Mission>` mit `self.mission_text or ""`.
     * Generiert `<Tools>` aus `self.tools`:

       * Zeile pro Tool: `- {name}: {description}` + `required: ...` wenn vorhanden (aus `input_schema.required`) (Daten liegen vor) .
     * Liefert einen **einzigen String** in obigem Markup.
   * Alle LLM-Aufrufe verwenden **ausschließlich** `self.final_system_prompt` (heute `self.system_prompt`), d.h. bei `generate_response`, `generate_structured_response`, `call_tools` (Parameter unverändert, Provider ist bereits kompatibel) .
   * Deprecation-Hinweis (Kommentar) für `system_prompt_override` in `to_tool()`, stattdessen `mission_override`.

2. **run\_idp\_cli.py**

   * `system_prompt_git.txt` als **Mission** laden:

     ```python
     mission = load_text(prompt_path)      # previously: system_prompt
     generic = None                        # use default
     git_agent = ReActAgent(
         system_prompt=None,
         llm=provider,
         tools=git_tools,
         generic_system_prompt=generic,
         mission=mission,
     )
     orchestrator = ReActAgent(
         system_prompt=None,
         llm=provider,
         tools=[git_agent.to_tool(
             name="agent_git",
             description="Git sub-agent",
             allowed_tools=[t.name for t in git_tools],
             budget={"max_steps": 12},
             mission_override=mission
         )],
         mission="Delegate Git workflows to sub-agent and report concise results."
     )
     ```
   * Hintergrund: Der Content in `system_prompt_git.txt` beschreibt Aufgabe/Scope/Allowed-Tools → in die **Mission-Sektion** verschieben .

3. **tools\_builtin.py / tools.py**

   * Keine Codeänderung nötig; `<Tools>` wird aus bestehenden `ToolSpec`-Feldern gerendert (Name/Desc/Required) .

4. **todolist\_md.py / todolist\_actions.py**

   * Weitergeben des fertigen SystemPrompts ist bereits vorhanden (Parameter `system_prompt`) – keine Änderung nötig; sie profitieren automatisch vom neuen finalen Prompt  .

5. **llm\_provider.py**

   * Keine Änderung nötig; Provider nutzt `system_prompt` bereits in allen Pfaden (free-form, structured, tool calls) .

---

## Akzeptanzkriterien

1. **Komposition sichtbar:** Der an den Provider übergebene `system_prompt` enthält **alle drei Sektionen** exakt in der Reihenfolge `<GenericAgentSection>`, `<Mission>`, `<Tools>`.
2. **Optionalität:** Wird weder `system_prompt` noch `mission` übergeben, verwendet der Agent den Default-Generic-Text, eine **leere `<Mission>`** und die korrekt generierte `<Tools>`-Liste.
3. **Tool-Autogenerierung:** Jede im Agent registrierte `ToolSpec` erscheint in `<Tools>` inkl. `required`-Feldern (falls vorhanden).
4. **Sub-Agenten:** `to_tool(..., mission_override=...)` führt dazu, dass der Sub-Agent mit **derselben Generic-Sektion**, neuer Mission und eigener Tools-Liste startet; sein Verhalten ist damit enger fokussiert.
5. **Backward-Compat:** Setze `prompt_overrides={'mode':'legacy_full'}` und reiche einen alten, monolithischen Prompt → Ausgabe identisch zum bisherigen Verhalten.
6. **Determinismus:** Gleicher Tool-Satz & gleiche Mission ⇒ identische `<Tools>`/`<Mission>`-Sektionen; nur die Reihenfolge der Tools entspricht der Registrierreihenfolge.

---

## Tests (Beispiele)

* **Unit:**

  * `_build_final_system_prompt()` mit (a) nur Tools, (b) Mission + Tools, (c) Generic + Mission + Tools, (d) legacy\_full.
  * Tools mit/ohne `required` Feldern.
* **Int:**

  * `run_idp_cli.py` starten, Eingabe „create a service“ → LLM-Requests inspecten: Prompt enthält alle 3 Sektionen; Sub-Agent Prompt enthält `mission_override`.
* **Regression:**

  * Vor/Nach Vergleich mit `prompt_overrides={'mode':'legacy_full'}`: identischer Verlauf bis zum ersten Tool-Call.

---

## Risiken & Mitigation

* **Überlange Prompts:** Tools-Sektion kann lang werden. → Kompakte Formatierung, nur `name`, `description`, `required`.
* **Doppelte Regeln:** Regeln existierten zuvor in `_compose_system_prompt()`; jetzt in Generic-Sektion konsolidieren, damit es **keine** Duplikate gibt .
* **Sub-Agent-Drift:** Unterschiedliche Generic-Prompts für Orchestrator/Subagent? → Standard: Sub-Agent erbt denselben Generic-Prompt, sofern `generic_system_prompt_override` nicht gesetzt ist.

---

## Migrationsplan (Schritt-für-Schritt)

1. **`agent.py`**

   * `__init__`-Signatur erweitern; Felder speichern.
   * `_compose_system_prompt()` → `_build_final_system_prompt()` refactor.
   * Alle Stellen, die `self.system_prompt` referenzieren, auf `self.final_system_prompt` (neuer Name) umstellen.
   * `to_tool(...)` um `mission_override`, `generic_system_prompt_override` ergänzen; `system_prompt_override` intern auf `mission_override` mappen (Deprecation-Comment beilegen).

2. **`run_idp_cli.py`**

   * `system_prompt_git.txt` → `mission`; `generic_system_prompt=None`.
   * Konstruktion von Orchestrator/Sub-Agent aktualisieren (siehe Snippet oben).
     (Vorherige Nutzung des Files:  / Inhalt als Scope: )

3. **Review/Smoke Test**

   * Kurzlauf in der CLI; prüfen, dass `<Tools>` erwartete Einträge aus `BUILTIN_TOOLS_SIMPLIFIED` enthält (z.B. `create_repository`, `validate_project_name_and_type`)  .

4. **Docs/Examples**

   * README-Ausschnitt: Wie man `mission` setzt; Hinweis auf Legacy-Mode.

---

## Beispiel (Erwarteter finaler Prompt – gekürzt)

```
<GenericAgentSection>
You are a ReAct-style execution agent…
…(Usage rules, plan-first, loop-guard, ask-user-on-blockers)…
</GenericAgentSection>

<Mission>
You are an Internal Developer Platform (IDP) Copilot Agent focused on a minimal, reliable Git workflow…
(SCOPE / RESPONSIBILITIES / ALLOWED STEPS … aus system_prompt_git.txt)
</Mission>

<Tools>
- create_repository: Creates local Git repo and GitHub remote, pushes initial commit
  required: name
- validate_project_name_and_type: Validate project name and type
  required: project_name
</Tools>
```

*(Mission-Text stammt aus der bisherigen Datei) ; Tools aus ToolSpecs .*

---

Wenn du möchtest, erstelle ich dir direkt die Patch-Snippets (diff-Stil) für `agent.py` und `run_idp_cli.py` nach obigem Plan.
