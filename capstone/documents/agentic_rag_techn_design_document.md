Absolut. Hier ist ein vollständiges, neues Design-Dokument, das Ihre Vision, die Architektur und die Anforderungen für ein multimodales Agentic-RAG-System detailliert beschreibt, wie wir es besprochen haben.

-----

# Technisches Design-Dokument:

# Agentic RAG für Multimodale Wissenssuche

## 1\. Vision & Executive Summary

**Problemstellung:** Unternehmenswissen ist oft in dichten, schwer durchsuchbaren Dokumenten (Handbüchern, Berichten, PDFs) gebunden. Standard-RAG-Systeme (Retrieval-Augmented Generation) sind reaktiv und liefern oft nur Text-Snippets, die den Benutzer zwingen, die Quelldokumente für den vollen Kontext (insb. Diagramme und Bilder) dennoch zu öffnen.

**Vision:** Wir schaffen ein **autonomes Agenten-System (Agentic RAG)**, das als proaktiver Wissensassistent fungiert. Das Systemziel ist die Bereitstellung einer **multimodalen User Experience (UX)**, die so umfassend und intuitiv ist, dass sie die Notwendigkeit eliminiert, die ursprünglichen Handbücher oder Quelldokumente zu konsultieren.

**Lösung:** Dieses Dokument beschreibt die Architektur eines solchen Systems. Es baut auf einem bestehenden, robusten **ReAct-Agenten-Framework** (basierend auf `Thought -> Action -> Observation`) auf, das eine deterministische Aufgabenplanung (via `TodoList`) ermöglicht.

Wir erweitern dieses Framework um spezialisierte RAG-Fähigkeiten, die auf **Azure AI Search** aufsetzen. Der Kern der Innovation liegt in drei Bereichen:

1.  **Multimodale Indizierung:** Wir behandeln Text und Bilder als semantisch durchsuchbare "Inhaltsblöcke".
2.  **Intelligente Synthese:** Der Agent wird angewiesen, relevante Bilder direkt und im Kontext in seine textuellen Antworten einzubetten.
3.  **Agenten-Intelligenz:** Die RAG-Logik wird nicht fest einkodiert, sondern dem generischen Agenten über ein spezialisiertes **System Prompt** injiziert.

## 2\. Anforderungen & Design-Prinzipien

### 2.1 Funktionale Anforderungen

  * **Multimodale Antworten:** Das System muss relevante Bilder, Diagramme und Schemata finden und sie direkt im Chat-Verlauf rendern, eingebettet in kontextuellen Text.
  * **Autonome Planung:** Der Agent muss komplexe, mehrstufige Anfragen verstehen und selbstständig in einen ausführbaren Plan (eine `TodoList`) zerlegen.
  * **Proaktive Klärung:** Bei mehrdeutigen Anfragen ("Fasse *den* Bericht zusammen") muss der Agent aktiv nachfragen, *bevor* er einen Plan ausführt.
  * **Quellennachweis:** Jede Information (Text oder Bild) in der Antwort muss auf ihre Quelle (Dokument und Seite) zurückverfolgt werden können.
  * **Filterung & Metadaten:** Benutzer müssen die Suche anhand von Metadaten (Datum, Dokumenttyp, Abteilung) einschränken können.

### 2.2 Design-Prinzipien (Nicht-Funktional)

  * **UX-Priorität:** Das ultimative Ziel ist die überlegene User Experience. Jede Design-Entscheidung wird dahingehend bewertet, ob sie den Benutzer davor bewahrt, ein PDF manuell zu öffnen.
  * **Trennung von Agent & Skill:** Die Kernlogik des Agenten (ReAct, State Management, Planning) bleibt generisch. Die RAG-Fähigkeiten werden als "Skill-Set" (Tools + Prompt) implementiert. Dies ermöglicht die Wiederverwendbarkeit des Agenten-Frameworks für andere Aufgaben.
  * **Verbalisierung von Wissen:** Wir nutzen die Fähigkeit von Azure AI Search, Bilder zu "verbalisieren" (automatische Bildunterschriften). Diese textuellen Beschreibungen machen Bilder semantisch durchsuchbar.
  * **Determinismus:** Der Planungsprozess des Agenten ist ergebnisorientiert. Der Agent plant *was* erreicht werden muss (Akzeptanzkriterien), nicht *wie* (Tool-Aufruf).

-----

## 3\. Systemarchitektur

Die Architektur besteht aus vier Hauptschichten, die zusammenarbeiten, um die autonome, multimodale Suche zu ermöglichen.

1.  **UI-Schicht (Frontend):**

      * Die Schnittstelle zum Benutzer (z.B. Web-Chat, Microsoft Teams App).
      * Muss in der Lage sein, Markdown-formattierte Antworten, insbesondere eingebettete Bilder (`![alt-text](url)`), zu rendern.
      * In Zukunft muss es interaktive Komponenten (z.B. Diagramm-Visualisierungen) rendern können.

2.  **Agenten-Schicht (Das Gehirn):**

      * **ReAct Orchestrator:** Die zentrale Steuereinheit, die den `Thought -> Action -> Observation`-Zyklus verwaltet.
      * **TodoList Manager:** Der generische Planungs-Service. Er wandelt Benutzer-Missionen in deterministische, ergebnisorientierte Pläne um.
      * **State Manager:** Verwaltet den Konversationszustand, Benutzerantworten auf Klärungsfragen und den Status der `TodoList` über Anfragen hinweg.
      * **RAG System Prompt:** Dies ist die "Persönlichkeit" oder "Intelligenz-Injektion". Es ist ein spezieller System-Prompt, der dem generischen Agenten beibringt, *wie* er sich als RAG-Experte verhalten soll, welche Planungsmuster er verwenden und welche Klärungsfragen er stellen muss.

3.  **Tool-Schicht (Die Hände):**

      * Eine Sammlung von spezialisierten Funktionen, die der Agent aufrufen kann ("Actions").
      * Enthält die definierten RAG-Tools (z.B. `SemanticSearchTool`, `ListDocumentsTool`).
      * Diese Tools kapseln die gesamte Logik für die Kommunikation mit dem Daten-Backend.

4.  **Daten-Schicht (Das Gedächtnis):**

      * **Azure AI Search:** Das Herzstück des RAG-Backends.
      * **Azure Blob Storage:** Speichert die Original-Dokumente und die extrahierten Bilddateien.

-----

## 4\. Daten- & Indexierungsstrategie

Um Text und Bilder nahtlos durchsuchbar zu machen, verfolgen wir eine **Zwei-Index-Strategie** in Azure AI Search.

### 4.1 Index 1: `documents-metadata`

Dieser Index enthält einen Eintrag pro *Dokument* und dient der Auflistung, Filterung und dem Abruf von Dokumenten-Metadaten.

  * **Zweck:** Dokumente auflisten, nach Metadaten filtern, vorab berechnete Zusammenfassungen abrufen.
  * **Wichtige Felder:**
      * `doc_id` (Eindeutige ID)
      * `filename` (Dateiname)
      * `title` (Extrahierter Titel)
      * `document_type` (z.B. "Handbuch", "Finanzbericht")
      * `upload_date`, `author`, `department` (Filterbare Metadaten)
      * `page_count`, `file_size`
      * `access_control_list` (Für Multi-Tenancy)
      * `summary_brief` (Vorab berechnete Kurzzusammenfassung)
      * `summary_standard` (Vorab berechnete Standardzusammenfassung)

### 4.2 Index 2: `content-blocks`

Dies ist der primäre Suchindex. Er ist **multimodal** und enthält einen Eintrag pro "Inhaltsblock", unabhängig davon, ob es sich um Text oder ein Bild handelt.

  * **Zweck:** Semantische Suche über *alle* Inhalte.
  * **Wichtige Felder:**
      * `block_id` (Eindeutige ID des Blocks)
      * `doc_id` (Referenz zum Elterndokument)
      * `page_number` (Quellenangabe)
      * **`block_type`** (Wichtig: "text" oder "image")
      * `content` (Nur bei `block_type = 'text'`: Der Originaltext-Chunk)
      * `content_vector` (Nur bei Text: Vektor-Embedding des `content`)
      * **`image_url`** (Nur bei `block_type = 'image'`: Link zur Bilddatei im Blob Storage)
      * **`image_caption`** (Nur bei Bild: Die von Azure AI generierte textuelle "Verbalisierung" des Bildes)
      * **`image_caption_vector`** (Nur bei Bild: Vektor-Embedding der `image_caption`)

**Vorteil dieser Struktur:** Wenn ein Benutzer nach "Funktionsweise der XYZ-Pumpe" sucht, findet die semantische Suche im `content-blocks`-Index *sowohl* Text-Chunks (über `content_vector`), die dies beschreiben, *als auch* relevante Diagramme (über `image_caption_vector`), deren verbalisierte Beschriftung (z.B. "Diagramm der XYZ-Pumpe") zur Anfrage passt.

-----

## 5\. Agenten-Logik & Autonomie

### 5.1 Query-Klassifizierung & Planung

Die Intelligenz des Agenten steckt im **RAG System Prompt**. Dieser Prompt weist den Agenten an, jede Benutzeranfrage zunächst zu klassifizieren:

1.  **LISTING:** ("Welche Dokumente gibt es?")
2.  **CONTENT\_SEARCH:** ("Was steht über Thema X?")
3.  **DOCUMENT\_SUMMARY:** ("Fasse Dokument Y zusammen.")
4.  **METADATA\_SEARCH:** ("Zeige alle PDFs von letzter Woche.")
5.  **COMPARISON:** ("Vergleiche Bericht A und B.")

Basierend auf dieser Klassifizierung und den Regeln im Prompt leitet der `TodoListManager` entweder eine **Klärungsfrage** ein (wenn Informationen fehlen) oder erstellt einen **Ausführungsplan**.

### 5.2 Beispiel-Plan (TodoList)

**User-Mission:** "Erkläre die Funktionsweise der XYZ-Pumpe."

Der Agent (angewiesen durch den Prompt) erstellt folgenden Plan:

1.  **Schritt 1 (Suchen):**
      * **Beschreibung:** "Finde alle relevanten Inhaltsblöcke (Text und Bilder) zur 'Funktionsweise der XYZ-Pumpe'."
      * **Akzeptanzkriterien:** "Eine Liste von mindestens 3 hochrelevanten Blöcken (Text oder Bild) wurde abgerufen."
2.  **Schritt 2 (Synthese):**
      * **Beschreibung:** "Synthetisiere die gefundenen Blöcke zu einer umfassenden, multimodalen Antwort."
      * **Akzeptanzkriterien:** "Eine kohärente Textantwort wurde generiert, die relevante Bilder im Markdown-Format einbettet und alle Quellen zitiert."

## 6\. RAG-Tool-Definitionen

Der Agent kann die folgenden "Actions" (Tools) ausführen. Diese Tools werden ihm im System Prompt bekannt gemacht.

  * **`SemanticSearchTool`**

      * **Zweck:** Führt eine hybride + semantische Vektorsuche im `content-blocks`-Index durch.
      * **Eingabe:** `query` (Text), `top_k` (Anzahl), `filters` (Metadaten-Filter).
      * **Ausgabe:** Eine Liste von Inhaltsblöcken (gemischt Text und Bild), sortiert nach Relevanz.

  * **`ListDocumentsTool`**

      * **Zweck:** Listet Dokumente aus dem `documents-metadata`-Index auf.
      * **Eingabe:** `filters`, `sort_by`, `limit`.
      * **Ausgabe:** Eine Liste von Dokumenten mit Metadaten und Kurzzusammenfassungen.

  * **`GetDocumentTool`**

      * **Zweck:** Ruft die Details für ein *einzelnes* Dokument ab, primär um die vorab berechnete Zusammenfassung zu erhalten.
      * **Eingabe:** `doc_id`.
      * **Ausgabe:** Dokumenten-Metadaten inkl. `summary_standard`.

  * **`SearchMetadataTool`**

      * **Zweck:** Führt eine strukturierte Suche/Filterung im `documents-metadata`-Index durch.
      * **Eingabe:** `criteria` (z.B. { "document\_type": "Handbuch", "date\_range": ... }).
      * **Ausgabe:** Eine Liste von Dokumenten, die den Kriterien entsprechen.

-----

## 7\. User Experience & Multimodaler Antwort-Flow

Dies ist der Kern der Vision. So wird eine Anfrage verarbeitet, um die nahtlose UX zu schaffen.

1.  **Anfrage:** Der Benutzer fragt: "Wie war die Umsatzentwicklung im letzten Quartal?"

2.  **Planung:** Der Agent erstellt den 2-Schritte-Plan (Suchen + Synthese).

3.  **Aktion 1 (Suchen):** Der Agent führt `SemanticSearchTool` aus. Das Tool liefert 4 Blöcke zurück:

      * `Block 1 (Text)`: "Der Umsatz stieg um 15%..." (Seite 5)
      * `Block 2 (Bild)`: { URL: "...", Caption: "Diagramm: Umsatzwachstum Q3 vs Q2" } (Seite 6)
      * `Block 3 (Text)`: "Herausforderungen im asiatischen Markt..." (Seite 5)
      * `Block 4 (Text)`: "Prognose für Q4..." (Seite 7)

4.  **Aktion 2 (Synthese):** Der Agent löst seine interne Synthese aus (z.B. durch einen `PythonTool`-Aufruf, der einen LLM mit spezifischem Prompt nutzt).

5.  **Synthese-Prompt (WICHTIG):** Der Prompt für diesen letzten Schritt ist entscheidend:

    > "Du bist ein hilfreicher Assistent. Synthetisiere die folgenden Inhaltsblöcke, um die Frage 'Wie war die Umsatzentwicklung?' zu beantworten. Integriere relevante Bilder *direkt* in deine Antwort, indem du das Markdown-Format `![Bildunterschrift](Bild-URL)` verwendest. Zitiere deine Quellen."

6.  **Finale Antwort (an UI):** Der LLM generiert die finale Markdown-Antwort, die der Agent an die UI weiterleitet:

    > Die Umsatzentwicklung im letzten Quartal war positiv. Der Umsatz stieg um 15% (Quelle: report.pdf, S. 5). Die Entwicklung ist auch in folgendem Diagramm ersichtlich:

    > 
    > (Quelle: report.pdf, S. 6)

    > Als Herausforderungen wurden Entwicklungen im asiatischen Markt genannt (Quelle: report.pdf, S. 5). Die Prognose für Q4 bleibt stabil (Quelle: report.pdf, S. 7).

-----

## 8\. Sicherheit & Mandantenfähigkeit

Sicherheit wird nicht dem Agenten überlassen, sondern auf Tool-Ebene erzwungen.

  * Der Agenten-Orchestrator erhält den Kontext des Benutzers (z.B. `user_id`, `department`, `org_id`).
  * Dieser Kontext wird an *jeden* Tool-Aufruf weitergegeben.
  * Die Tools (`SemanticSearchTool`, `ListDocumentsTool` etc.) sind dafür verantwortlich, diesen Benutzerkontext in einen **automatischen OData-Sicherheitsfilter** umzuwandeln.
  * Jede Abfrage an Azure AI Search enthält somit einen nicht übersteuerbaren Filter (z.B. `AND (access_control_list CONTAINS 'user_id' OR access_control_list CONTAINS 'department')`).

## 9\. Zukünftige Vision: Interaktive Antworten

Das aktuelle Design ist auf zukünftige Interaktivität ausgelegt. Um interaktive Diagramme zu unterstützen, sind folgende Schritte nötig:

1.  **Neues Tool:** Einführung eines `InteractiveChartTool`.
2.  **Logik:** Dieses Tool würde Rohdaten (z.B. aus einer extrahierten Tabelle) empfangen und eine JSON-Definition für ein interaktives Diagramm (z.B. Vega-Lite oder Plotly) zurückgeben.
3.  **Agenten-Prompt:** Der System-Prompt des Agenten würde erweitert, um zu erkennen, wann die Erstellung eines interaktiven Charts sinnvoll ist ("Zeige mir die Verkaufszahlen als Balkendiagramm").
4.  **UI-Anpassung:** Die Frontend-Anwendung muss in der Lage sein, diese JSON-Definition zu empfangen und das interaktive Diagramm zu rendern.

## 10\. Erfolgsmetriken

Der Erfolg des Systems wird nicht nur an der Relevanz der Antworten gemessen, sondern primär an der Erreichung des UX-Ziels.

  * **Primärmetrik (UX):** Reduktion der "Click-Through-Rate" auf Quelldokumente. Wenn Benutzer die Quellen nicht mehr öffnen, ist die Antwort des Agenten ausreichend.
  * **Sekundärmetrik (Qualität):** Von Benutzern bewertete Antwortqualität (waren Text und Bilder relevant und korrekt?).
  * **Agenten-Effizienz:** Rate der erfolgreich abgeschlossenen Pläne (ohne menschliches Eingreifen).
  * **Klärungsrate:** Wie oft muss der Agent nachfragen? (Eine niedrige Rate deutet auf gutes Query-Verständnis hin).



  Das ist ein sehr wichtiger Punkt. Die Definition der Anwendungsfälle und des "Scope of Interaction" ist entscheidend, um die Erwartungen der Benutzer zu steuern und den Wert des Agenten zu demonstrieren.

Ich schlage vor, wir fügen dem Designdokument den folgenden Abschnitt hinzu, idealerweise direkt nach "2. Anforderungen & Design-Prinzipien" als neuen "Abschnitt 3".

---

## 3. Anwendungsfälle & Benutzer-Szenarien

Dieses System ist nicht nur eine Suchmaschine, sondern ein **autonomer Assistent**, der komplexe, mehrstufige und multimodale Aufgaben bearbeiten kann. Die Intelligenz des Agenten, die durch das RAG-System-Prompt gesteuert wird, ermöglicht es ihm, die Absicht des Benutzers zu klassifizieren und darauf zu reagieren.

Im Folgenden sind die primären Aufgabenkategorien aufgeführt, die Benutzer an den Agenten stellen können.

### 3.1 Kategorie 1: Multimodaler Informationsabruf & Synthese
*(Klassifizierung: CONTENT_SEARCH)*

Dies ist der Kern-Anwendungsfall. Der Benutzer sucht nach Wissen, das *in* den Dokumenten enthalten ist. Der Agent findet die relevanten Text- und Bildblöcke und synthetisiert sie zu einer einzigen, kohärenten Antwort.

**Beispiel-Anfragen:**

* **Direkte Wissensfrage:** "Was sind die Hauptursachen für einen Überdruck in Pumpe Typ B-42?"
    * *Erwartete Antwort:* Text, der die Ursachen beschreibt, potenziell ergänzt um ein Diagramm oder Schema der Pumpe, das die relevanten Ventile zeigt.
* **Visuelle Suche:** "Zeig mir, wie die Notabschaltung für Anlage C aussieht."
    * *Erwartete Antwort:* Primär ein Bild des Not-Aus-Schalters (gefunden über die Bildunterschrift), begleitet von Text über dessen Standort und Funktion.
* **Verfahrensfrage:** "Wie lautet der Prozess zur Beantragung von Sonderurlaub?"
    * *Erwartete Antwort:* Eine schrittweise Textanleitung, die aus den HR-Handbüchern synthetisiert wird.
* **Multi-Dokument-Synthese:** "Erstelle eine Zusammenfassung aller bekannten Risiken für Projekt 'Titan', die in den Berichten von Q3 erwähnt werden."
    * *Erwartete Antwort:* Eine synthetisierte Liste von Risiken, die aus mehreren verschiedenen Berichten zusammengetragen wurden, jeweils mit Quellenangabe.

### 3.2 Kategorie 2: Dokumenten-Zusammenfassung & Analyse
*(Klassifizierung: DOCUMENT_SUMMARY)*

Der Benutzer möchte ein *spezifisches* Dokument verstehen, ohne es vollständig lesen zu müssen.

**Beispiel-Anfragen:**

* **Eindeutige Anfrage:** "Fasse mir den 'Quartalsbericht Q3 2024.pdf' zusammen."
    * *Erwartete Antwort:* Eine kohärente Zusammenfassung (basierend auf der vorab berechneten `summary_standard` oder einer Ad-hoc-Synthese), die die wichtigsten Ergebnisse, Diagramme und Schlussfolgerungen enthält.
* **Mehrdeutige Anfrage (führt zu Klärung):** "Gib mir die Kernaussagen des letzten Sicherheitsberichts."
    * *Erwartete Agenten-Nachfrage:* "Ich habe drei Sicherheitsberichte aus dem letzten Monat gefunden: [A, B, C]. Welchen davon meinen Sie?"
* **Gezielte Extraktion:** "Was sind die wichtigsten finanziellen Kennzahlen aus dem Jahresabschluss 2023?"
    * *Erwartete Antwort:* Eine Liste oder Tabelle mit den spezifischen Kennzahlen (Umsatz, EBITDA usw.), die direkt aus dem Zieldokument extrahiert wurden.

### 3.3 Kategorie 3: Navigation & Auffindbarkeit
*(Klassifizierung: LISTING / METADATA_SEARCH)*

Der Benutzer nutzt den Agenten, um den Dokumentenbestand zu durchsuchen und zu filtern, ähnlich einer "intelligenten Bibliothek".

**Beispiel-Anfragen:**

* **Allgemeine Auflistung:** "Welche Dokumente sind im System verfügbar?"
    * *Erwartete Antwort:* Eine Liste der verfügbaren Dokumente, typischerweise mit Titel, Datum und Kurzzusammenfassung.
* **Gefilterte Suche (Metadaten):** "Zeige mir alle Handbücher für die 'Produktion', die nach Juni 2024 aktualisiert wurden."
    * *Erwartete Antwort:* Eine gefilterte Liste, die nur Dokumente anzeigt, die *alle* Kriterien erfüllen.
* **Attribut-Suche:** "Welche Dokumente hat 'Max Mustermann' letzte Woche hochgeladen?"

### 3.4 Kategorie 4: Vergleichende Analyse
*(Klassifizierung: COMPARISON)*

Dies ist eine fortgeschrittene, mehrstufige Aufgabe, bei der der Agent Informationen aus *mehreren* Quellen abrufen und gegenüberstellen muss.

**Beispiel-Anfragen:**

* **Dokumenten-Vergleich:** "Was sind die Hauptunterschiede in den Finanzergebnissen zwischen dem Q2- und dem Q3-Bericht?"
* **Produkt-Vergleich:** "Vergleiche die Leistungsspezifikationen von Pumpe A-41 mit Pumpe B-42."
* **Verfahrens-Vergleich:** "Unterscheiden sich die Sicherheitsprotokolle für Standort München und Standort Berlin?"
    * *Erwartete Antwort:* Eine strukturierte Antwort, die die Unterschiede und Gemeinsamkeiten klar herausstellt (z.B. in einer Tabelle oder als Gegenüberstellung).

### 3.5 Was der Agent (noch) nicht kann (Nicht-Ziele)

Um die Erwartungen klar zu definieren, ist es ebenso wichtig zu verstehen, was *nicht* im Scope liegt:

* **Kein Zugriff auf das öffentliche Internet:** Das Wissen des Agenten ist strikt auf die indizierten Unternehmensdokumente beschränkt. Er kann keine aktuellen Nachrichten oder externe Webseiten durchsuchen.
* **Keine transaktionalen Aktionen:** Der Agent ist ein Informationssystem. Er kann (in dieser Ausbaustufe) keine Aktionen in Drittsystemen ausführen (z.B. "Buche einen Meetingraum", "Sende eine E-Mail" oder "Erstelle ein neues Dokument").
* **Keine Meinungen oder Erfindungen:** Der Agent ist darauf trainiert, auf Basis der Fakten in den Quelldokumenten zu antworten und diese zu zitieren. Er wird keine Meinungen äußern oder Informationen erfinden, die nicht in den Quellen vorhanden sind.