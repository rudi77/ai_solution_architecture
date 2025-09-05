Hier sind die Feature-Request-Dokumente für die sechs wichtigsten Punkte aus meiner Analyse deines Agenten-Codes. Ich habe sie im üblichen **Feature Request Template** aufgeschrieben – jeweils mit **Problem Statement**, **Proposed Solution**, **Benefits** und **Acceptance Criteria**.

---

## 1. Migration auf Pydantic v2 (`@field_validator`)

**Problem Statement**
Aktuell werden noch `@validator`-Dekoratoren genutzt. Diese sind seit Pydantic v2 deprecated und erzeugen Warnungen im Log. Künftig werden sie entfernt, was den Agenten brechen würde.

**Proposed Solution**

* Alle `@validator` durch `@field_validator(..., mode="before")` ersetzen.
* Mapping-Logik (`_map_old_names`) entsprechend migrieren.

**Benefits**

* Zukunftssichere Codebasis (kompatibel mit Pydantic v3).
* Keine störenden Deprecation-Warnungen mehr.

**Acceptance Criteria**

* Keine Pydantic-Deprecation-Warnungen im Log.
* Unit Tests laufen ohne Änderungen durch.
* Verhalten der Validierung ist identisch wie zuvor.

---

## 2. Tool-Metriken erfassen (Zeit, Erfolg, Fehler)

**Problem Statement**
Prometheus-Metriken `tool_execution_time`, `tool_success_rate`, `tool_failure_rate` sind zwar definiert, werden aber nicht inkrementiert/observiert. Damit fehlen Einblicke in Tool-Performance und Fehlerhäufigkeit.

**Proposed Solution**

* Im `_handle_tool` bzw. `execute_tool_by_name`:

  * Startzeit messen, Laufzeit in `tool_execution_time` eintragen.
  * Bei Erfolg `tool_success_rate.inc()` erhöhen.
  * Bei Fehler `tool_failure_rate.inc()` erhöhen.

**Benefits**

* Transparente Tool-Observability.
* Frühzeitige Erkennung fehlerhafter Tools.
* Basis für SLAs und Optimierungen.

**Acceptance Criteria**

* Jede Tool-Ausführung erzeugt einen Eintrag in den Prometheus-Metriken.
* Erfolge/Fehler sind korrekt gezählt.
* Laufzeiten sind im Histogram sichtbar.

---

## 3. Konsistente Tool-Namen (Lookup-Index)

**Problem Statement**
Toolnamen werden an verschiedenen Stellen normalisiert (`lower().replace("-", "_")`). Dabei kann es zu Inkonsistenzen kommen, sodass vorhandene Tools nicht gefunden werden.

**Proposed Solution**

* Beim Laden der Tools einmalig einen Lookup-Index erstellen: `{normalized_name -> ToolSpec}`.
* Alle weiteren Tool-Calls nur über diesen Index auflösen.

**Benefits**

* Stabile Zuordnung von Tool-Namen.
* Keine „Tool not found“-Fehler mehr.
* Einfachere Debugbarkeit.

**Acceptance Criteria**

* Tools mit `-`, `_` oder Leerzeichen werden zuverlässig gefunden.
* Kein Unterschied mehr zwischen verschiedenen Normalisierungen.
* Bestehende Tests laufen durch.

---

Super — ich ergänze den Feature Request zu **Punkt 4 (Strukturierte Task-Repräsentation)** mit allen Details zur LLM-Rolle, JSON-Schema, Renderlogik und Ablauf.

---

## 4. Strukturierte Task-Repräsentation (statt Markdown-Manipulation)

**Problem Statement**
Aktuell werden Tasks und Statusänderungen direkt per LLM in einer Markdown-Datei geändert. Das ist fehleranfällig: das LLM kann Aufgaben falsch parsen, falsche Statuswerte einsetzen oder gar den gesamten Plan überschreiben. Dadurch sind Zustand und Darstellung unzuverlässig.

---

**Proposed Solution**

1. **LLM bleibt Planner**

   * Das LLM erzeugt den initialen Plan **nicht als Markdown**, sondern als **valide JSON-Struktur** nach einem festen Schema.
   * Prompting erfolgt mit `generate_structured_response` / Function-Calling, `temperature≈0.2` und klarem JSON-Schema.
   * Das LLM liefert zusätzlich `open_questions` für unklare Eingaben.

2. **JSON-Schema für Tasks und Fragen**

```json
{
  "type": "object",
  "properties": {
    "tasks": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "title", "status"],
        "properties": {
          "id": { "type": "string" },
          "title": { "type": "string" },
          "description": { "type": "string" },
          "tool": { "type": "string" },
          "params": { "type": "object" },
          "status": { "type": "string", "enum": ["PENDING","IN_PROGRESS","COMPLETED","FAILED","SKIPPED"] },
          "depends_on": { "type": "array", "items": { "type": "string" } },
          "priority": { "type": "integer" },
          "notes": { "type": "string" }
        }
      }
    },
    "open_questions": { "type": "array", "items": { "type": "string" } }
  },
  "required": ["tasks","open_questions"],
  "additionalProperties": false
}
```

**Beispieloutput vom LLM:**

```json
{
  "tasks": [
    {
      "id": "t1",
      "title": "Rechnungs-PDFs einlesen",
      "tool": "load_invoices",
      "params": {"path": "/data/invoices"},
      "status": "PENDING",
      "priority": 1
    },
    {
      "id": "t2",
      "title": "Merkmale extrahieren",
      "tool": "extract_features",
      "params": {"model": "gpt-4.1-mini"},
      "status": "PENDING",
      "depends_on": ["t1"],
      "priority": 2
    }
  ],
  "open_questions": [
    "Wo liegen die PDFs? (z. B. /data/invoices)",
    "Welches Zielformat für den Export? (CSV, Parquet)"
  ]
}
```

3. **Validierung & Reparatur**

   * JSON gegen Schema prüfen.
   * Falls ungültig → kurzer Repair-Prompt an das LLM mit Parserfehler.
   * Nach 1–2 Versuchen → `ASK_USER`.

4. **Persistenz im Agent**

   * `context["tasks"]` = Single Source of Truth (Liste von Dicts oder Pydantic-`Task`-Objekten).
   * `context["open_questions"]` = separate Liste.
   * Jede Statusänderung (z. B. Tool gestartet → `IN_PROGRESS`, erfolgreich → `COMPLETED`) erfolgt deterministisch im Code.

5. **Renderschicht (Markdown)**

   * Aus den Tasks wird Markdown generiert (View).
   * Statusänderungen updaten nur `tasks` → Markdown wird neu gerendert.
   * **Keine** LLM-Edits am Markdown mehr.

6. **Bei Tool Calls**

   * Passenden Task mit `tool == name` und `status==PENDING/IN_PROGRESS` finden.
   * Status auf `IN_PROGRESS` setzen.
   * Nach Erfolg/Fehler → Status `COMPLETED`/`FAILED`, Resultat speichern.

7. **Plan-Updates**

   * Wenn Nutzer neue Antworten liefert oder ein Tool-Fehler neue Informationen verlangt, darf das LLM den Plan erneut generieren (mit aktuellem Plan + neuen Infos als Input).
   * Der Agent merged deterministisch (IDs beibehalten, neue IDs generieren).


**Benefits**

* Robuste, testbare Zustandsführung.
* Markdown ist reine Präsentationsschicht, kein kritischer Speicher.
* Keine Halluzinationen beim Statuswechsel.
* Einfaches Debugging: `context["tasks"]` zeigt immer den aktuellen Stand.


**Acceptance Criteria**

* Initialer Plan wird ausschließlich als JSON erzeugt.
* `context["tasks"]` ist die einzige Quelle für den Taskstatus.
* Markdown ist jederzeit konsistent mit `tasks`.
* Statuswechsel/Resultate sind deterministisch und nachvollziehbar im Log.
* Ungültiges JSON wird repariert oder führt zu `ASK_USER`.

---

## 5. Retry-Strategie mit Fehlerklassifizierung

**Problem Statement**
Aktuell wird jede Exception in `_exec_with_retry` automatisch erneut ausgeführt, egal ob es sich um einen transienten Fehler oder um einen Benutzerfehler handelt.

**Proposed Solution**

* Fehlerarten unterscheiden:

  * `TransientError` → Retry mit Backoff.
  * `UserInputError` → sofort `ASK_USER`.
* Exceptions entsprechend taggen/werfen.

**Benefits**

* Weniger unnötige Retries.
* Bessere User Experience: Nutzer wird direkt gefragt, wenn Input fehlt/falsch ist.
* Schnellere Recovery bei echten Fehlern.

**Acceptance Criteria**

* Transiente Fehler werden retried.
* User Input Fehler führen zu einer `ASK_USER`-Aktion.
* Fehlerhandling ist in den Logs nachvollziehbar.

---

## 6. Loop-Guard gegen „im Kreis drehen“

**Problem Statement**
Der Agent kann in Loops geraten, wenn die letzten Aktionen/Observationen keine Fortschritte bringen. Dadurch dreht er sich im Kreis.

**Proposed Solution**

* Loop-Guard implementieren:

  * Wenn die letzten N Aktionen identisch oder wirkungslos waren → Abbruch.
  * Stattdessen automatische Aktion `ERROR_RECOVERY` oder `ASK_USER`.

**Benefits**

* Verhindert Endlosschleifen.
* Nutzer erhält klare Rückmeldung statt ewiger Wiederholung.
* Stabileres Verhalten in unklaren Situationen.

**Acceptance Criteria**

* Agent bricht ab, wenn 3 gleiche Observations/Aktionen hintereinander auftreten.
* Nutzer wird mit `ASK_USER` konfrontiert.
* Keine Endlosschleifen mehr im Log.

---

👉 Soll ich dir diese Feature Requests als **ein zusammenhängendes Dokument** (z. B. in Markdown oder DOCX) aufbereiten, damit du sie direkt ins Repo legen kannst?
