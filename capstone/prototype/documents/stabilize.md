Du hast recht: der Agent „verheddert“ sich – und die Logs zeigen klar warum. Hier ist eine präzise Fehleranalyse plus konkrete Fixes (inkl. Code-Hinweisen), damit dein Flow stabil läuft und der echte Projektname an die Tools geht.

# Was konkret schief läuft (aus deinen Logs)

1. **Falscher Projektname an Tools**
   `validate_project_name_and_type` bekommt `project_name="service"` bzw. `"microservice"` statt `invoice-information-extraction`. Das ist kein Tool-Bug, sondern **falsche/fehlende Param-Befüllung** beim Funktionsaufruf via Tool-Calling. Exportierte Schemas erlauben zwar `project_name`, aber es wird vom LLM mit generischen Wörtern befüllt. (Siehe deine Tool-Definition/Exportpfad.)&#x20;

2. **Drift & Endlosschleifen in der Aktionswahl**
   Dein „Next-Item-First“-Guard ist angelegt, aber nicht vollständig – die Korrektur wird nicht durchgezogen, wenn das Modell ein anderes Tool auswählt. In `_determine_action()` vergleichst du `req` vs. `exp`, aber der Code bricht an der Stelle ab (kein Override/Rewrite der Entscheidung), dadurch entstehen Wiederholungen.&#x20;

3. **Checkliste bricht wegen Schemafehlern**
   Beim Erzeugen der Checkliste fehlen Felder wie `items` / `estimated_duration` → Pydantic-Validation schlägt fehl, danach Fallback-Checkliste (3 Items) und später nochmal (10 Items). Das erzeugt widersprüchlichen Status und Schritt-Drift. (Log: „ChecklistGeneration … Field required … items / estimated\_duration“)

4. **Tool-Schemas uneinheitlich/zu permissiv**
   Du hast zwar „strict overrides“ für kritische Tools, aber unterschiedliche Stellen exportieren teils **permissive** Schemas mit `additionalProperties: True` oder variierenden Keys (z. B. Alias-Schlüssel `project-validator` vs. `project_validator`). Das erhöht die Chance auf falsche Argumente. &#x20;

5. **Meta-Actions offen, auch wenn Checkliste existiert**
   Deine Meta-Funktionen (update\_checklist/ask\_user/…) bleiben immer „callable“ – ohne harte Guardrail, wodurch das Modell trotz existierender Checkliste dahin zurückspringen kann. In einer Code-Variante verschärfst du die Systemnachricht („…you must call the function for exactly that item’s tool…“), in anderen fehlt das. Konsistenz fehlt. &#x20;

---

# Quick Wins (sofort umsetzbar)

1. **Parameter-Normalisierung vor Tool-Dispatch**
   Implementiere eine Schicht, die Tool-Argumente **korrigiert/auffüllt**, bevor du sie aufrufst:

   * Falls `project_name` generisch aussieht (`"service"`, `"microservice"`), **überschreibe** aus deinem letzten User-Intent/Context State.
   * Setze Defaults (`programming_language`, `project_type`) falls leer.
   * Beispiel-Strategie: `normalize_tool_params(tool_name, params, state)` → gibt „harten“ `project_name` zurück.

   *Warum nötig?* Dein Export erlaubt `project_name`, aber das LLM füllt ohne Kontextbindung. Die Normalisierung behebt das deterministisch. (Siehe strikte Schemaabsicht)&#x20;

2. **„Next-Item-First“-Durchsetzung vervollständigen**
   Den begonnenen Vergleich `req != exp` **zu Ende implementieren**:

   * Wenn unterschiedlich → **force**: setze `decided.action_name = exp`, `decided.parameters = hydrate_from_checklist(exp)`; logge eine Warnung.
   * So verhinderst du, dass das Modell wieder „validate“ statt „create\_repo“ etc. triggert.&#x20;

3. **Einheitliche strikte Tool-Schemas erzwingen**
   Nutze **eine** Exportfunktion mit den „strict overrides“ (keine Duplikate mehr) und setze `additionalProperties: False` für **alle** kritischen Tools (inkl. Aliases!). Momentan sind in unterschiedlichen Blöcken verschiedene Varianten aktiv. Halte dich an die Variante mit `required` + `additionalProperties: False` für `validate_project_name_and_type`, `apply_template`, `setup_cicd_pipeline`. &#x20;

4. **Checklisten-Bootstrap als harte Guardrail**
   In `_determine_action()`: Wenn **keine** Checkliste → immer `UPDATE_CHECKLIST(create_checklist)` zurückgeben (du hast das schon teilweise; konsistent in allen Codepfaden machen, inkl. „kein Tool-Call returned“).&#x20;

5. **Checklisten-Schema fixen (Pydantic)**
   Stelle sicher, dass dein `ChecklistGeneration` immer **`items[]` + `estimated_duration`** mitliefert (auch bei Minimal-Checklisten). Sonst nicht abschicken – oder ein lokales „Schema-Filler“ baut die Felder vor Validation. (Fehler ist in deinen Logs ersichtlich.)

6. **Meta-Actions nur anbieten, wenn sinnvoll**
   Beim Tool-Export: Meta-Actions **nicht** exportieren, sobald eine Checkliste existiert **und** ein ausführbarer Next-Step vorhanden ist; oder setze `tool_choice="none"` + *tool-forced call* via serverseitiger Entscheidung, damit das Modell gar nicht in Versuchung kommt. (In einer deiner Varianten verschärfst du schon die Systemnachricht; vereinheitlichen!)&#x20;

---

# Empfohlene Code-Änderungen (skizziert)

1. **Einheitlicher Tool-Export (strict)**

   * Nur **eine** `export_openai_tools()` Quelle behalten.
   * Für Aliases dieselben strict-Schemas mappen (Key exakt der exportierte Name, z. B. `"project-validator"`).
   * `additionalProperties: False` für alle kritischen Tools (`validate_project_name_and_type`, `apply_template`, `setup_cicd_pipeline`).&#x20;

2. **Parameter-Normalizer einhängen**

   * In `_determine_action()` **nach** dem Tool-Call des Modells, **vor** Ausführung:
     `params = normalize_tool_params(name, params, self.state)`
     Regeln: hartes Überschreiben des `project_name` aus Session/State/Checklist; String-Trim, Lower-Kebab, etc.

3. **Next-Step-Enforcer fertigstellen**

   * Abschnitt `if exp and req != exp:` →

     ```python
     decided.action_name = exp
     decided.parameters = self._build_params_for(exp)  # aus Checklist/State ableiten
     decided.reasoning += " | corrected to next checklist item"
     ```

     plus Telemetrie-Log.

4. **Checkliste robust erzeugen**

   * Vor `create_checklist` ein lokaler Builder, der bei fehlenden Feldern **immer** sensible Defaults vergibt:
     `estimated_duration`, `risk_level`, und pro Item `tool_action` + minimal `parameters`.

5. **Ein Prompt-Flag für KB-Ergebnis**

   * Wenn `KB` leer: `kb_guidelines_available=no` in den Kontext, **aber** niemals als Blocker behandeln. (Du hast bereits ein leichtes Handling im Code – konsequent weiterführen.)

---

# Warum das die zwei Kernprobleme löst

* **Falscher Projektname** verschwindet, weil du ihn **serverseitig setzt/überschreibst**, anstatt dem Modell zu vertrauen. (Deine Schemas geben die Erlaubnis, aber garantieren nicht die Richtigkeit; der Normalizer tut’s.)
* **Endlosschleife** endet, weil der „Next-Item-First“-Pfad den Tool-Namen **hart korrigiert** und Meta-Abzweige nicht mehr exportiert/zugelassen werden, sobald ein ausführbarer Schritt existiert.

---

# Bonus-Hinweise

* Prüfe, dass du **nicht** mehrere divergierende Implementationen von `_determine_action()`/`export_openai_tools()` im File hast. In den Ausschnitten sieht man leicht abweichende Blöcke – konsolidieren! &#x20;
* `validate_project_name_and_type` setzt selbst Defaults für `project_type`/`programming_language`; nutze das, aber **füttere** den richtigen `project_name`.&#x20;

---

Wenn du möchtest, übernehme ich diese Punkte gern gesammelt in deinen bestehenden Canvas-Report („Fix-Report: Stabilisierung des IDP Copilot Agenten“) als **„Addendum (Stand heute)“** – sag einfach kurz Bescheid.
