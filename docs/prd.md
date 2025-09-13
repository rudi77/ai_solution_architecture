Perfekt 👍 – hier ist ein **vollständig ausgearbeitetes Product Requirements Document (PRD)** für dein **IDP Copilot** Capstone Projekt.
Es ist so strukturiert, dass ein Entwicklerteam sofort damit arbeiten könnte, und gleichzeitig „Capstone-tauglich“ bleibt.

---

# 📑 Product Requirements Document (PRD)

**Product:** IDP Copilot
**Author:** Rudi Dittrich
**Date:** August 2025
**Version:** 1.0

---

## 1. Executive Summary

**IDP Copilot** ist ein AI-gestützter Assistent für Entwickler, der es ermöglicht, über eine **Chat-Oberfläche** neue Services und Projekte zu erzeugen.
Die Lösung automatisiert das Anlegen von Git-Repositories, das Einfügen von Templates, das Erzeugen von Unit Tests und das Aufsetzen von CI/CD-Pipelines.

Kernidee:

* **Chat-first**: Entwickler interagieren ausschließlich über Chat (React UI).
* **Intelligente Rückfragen** (Clarifications): Fehlende Informationen werden automatisch vom Agenten abgefragt.
* **Automation via Tools**: Integration mit Git, FileSystem, Templates, CI/CD via **MCP**.
* **Firmenspezifisches Wissen** (Coding-Guidelines, Doku, Templates) wird über ein **RAG-System (ChromaDB)** verfügbar gemacht.

---

## 2. Goals & Non-Goals

### Goals

* 🎯 Schnelles Erzeugen neuer Services per Chat.
* 🤖 Automatisierte Tool-Nutzung (Git, FS, CI/CD, Templates).
* 🧩 Flexible Architektur: Start als Monolith, später skalierbar in Microservices.
* 📚 Kontextbasierte Unterstützung über RAG (ChromaDB).
* 🔄 Event-getriebene Transparenz im Chat (Tasks, Status, Clarifications).

### Non-Goals

* ❌ Vollständige Produktionsreife (kein Fokus auf Security, Monitoring, Multi-Tenant Support).
* ❌ Enterprise-grade Skalierung.
* ❌ Erweiterte Tool-Landschaft (erst Git/FS/Templates/CI/CD).
* ❌ LLM Fine-Tuning (vorerst Standard-LLM via API).

---

## 3. Target Users

* **Software Engineers / DevOps Engineers**

  * Möchten neue Services schnell und guideline-konform erstellen.
  * Wollen weniger Boilerplate manuell anlegen.
* **Tech Leads / Architects**

  * Stellen sicher, dass neue Projekte mit Firmenstandards konsistent sind.
* **Demo Audience (Capstone)**

  * Fokus: „Wow-Effekt“ und klare Darstellung der Funktionalität.

---

## 4. Use Cases

### UC-1: Service Creation with Clarification

**Actor:** Entwickler

1. Entwickler gibt im Chat ein: „Erzeuge einen neuen REST-Service in Go.“
2. Agent prüft Eingabe → Repo-Name fehlt.
3. Agent fragt zurück: „Wie soll das Repository heißen?“
4. Entwickler antwortet: „go-payment-api“
5. Agent erzeugt Taskliste:

   * Git Repo anlegen
   * Templates einfügen
   * Unit Tests generieren
   * CI/CD Pipeline konfigurieren
6. Tasks werden Schritt für Schritt ausgeführt, Fortschritt im Chat sichtbar.

### UC-2: Nutzung interner Guidelines

1. Entwickler fragt: „Erzeuge ein Service nach unseren Standardrichtlinien.“
2. Agent ruft ChromaDB ab → erhält Firmenrichtlinien.
3. Tasks werden gemäß Guidelines ausgeführt.

### UC-3: User Interruption

1. Während der Ausführung zeigt die Chat UI den Task-Fortschritt.
2. Entwickler kann eingreifen → Task abbrechen oder ändern.
3. Agent reagiert auf den Eingriff und passt Workflow an.

---

## 5. Functional Requirements

### Core Features

* \[FR1] **Chat-UI**:

  * Eingabe von Befehlen.
  * Anzeige von Task-Events, Clarifications, Ergebnissen.

* \[FR2] **Conversation Management**:

  * Starten, Speichern, Fortführen von Konversationen.
  * Behandlung von Clarifications.

* \[FR3] **Agent Orchestrator (Google ADK)**:

  * Erstellung & Abarbeitung von Tasklisten.
  * Interaktion mit Tools via MCP.
  * Clarification-Handling.

* \[FR4] **MCP Tool Integration**:

  * Git (Repo anlegen, commit/push).
  * Filesystem (Templates einfügen).
  * CI/CD (Pipeline config).

* \[FR5] **RAG (ChromaDB)**:

  * Speicherung von Coding Guidelines, Templates, Best Practices.
  * Embedding-gestützte Suche für kontextuelle Antworten.

* \[FR6] **Persistence (SQLite/Postgres)**:

  * Speicherung von Conversations, Tasks, Events.

---

## 6. Non-Functional Requirements

* \[NFR1] **Schnelligkeit**: Erste Antwortzeit < 2 Sekunden.
* \[NFR2] **Erweiterbarkeit**: Klare Modulstruktur (später Microservices möglich).
* \[NFR3] **Verständlichkeit**: Einfach für Entwickler und Demo-Publikum nachvollziehbar.
* \[NFR4] **Portabilität**: Deployment via Docker-compose.
* \[NFR5] **Robustheit**: Fehlerhafte Tools-Aufrufe werden protokolliert und sauber behandelt.

---

## 7. Tech Stack

* **Frontend:** React, TypeScript
* **Backend:** FastAPI (Python), Google Agent Development Kit (ADK)
* **MCP Client:** Python SDK, Tool Endpoints (Git, FS, CI/CD, Templates)
* **RAG:** ChromaDB (lokal, persistente Vektor-DB)
* **Persistence:** SQLite (Demo) / PostgreSQL (optional)
* **Infra:** Docker, docker-compose

---

## 8. Architecture (Phase 1: Monolith)

```
User ↔ Chat UI (React/TypeScript)
      ↕
Backend (FastAPI + ADK)
 ├─ Conversation Module
 ├─ Agent Orchestrator (ADK)
 ├─ MCP Client (Git, FS, CI/CD, Templates)
 ├─ RAG (ChromaDB)
 └─ Persistence (SQLite/Postgres)
```

---

## 9. Milestones & Deliverables

* **M1 – Projekt Setup (Woche 1)**

  * Repo, Projektstruktur, Docker-Setup

* **M2 – Conversation & Clarification (Woche 2)**

  * API für Chat
  * Clarification-Handling

* **M3 – Agent Orchestrator (Woche 3)**

  * Tasklisten erstellen, MCP-Anbindung

* **M4 – RAG Integration (Woche 4)**

  * ChromaDB Setup, Embedding/Query

* **M5 – End-to-End Demo (Woche 5)**

  * Service Creation Flow (mit Clarification, Tasks, RAG)

* **Final Deliverables**

  * 📊 Presentation
  * 🎥 5-Minuten Demo Video
  * 💻 GitHub Repo

---

## 10. Risks & Mitigations

| Risiko                                 | Mitigation                                       |
| -------------------------------------- | ------------------------------------------------ |
| LLM liefert falsche/ungenaue Antworten | RAG + Templates + Clarifications als Absicherung |
| MCP Tools schlagen fehl                | Fallback Logging, klare Fehlermeldungen          |
| Zeitliche Limitierung im Capstone      | Fokus auf Demo-taugliche Kernfunktionalität      |
| Fehlende Auth/Access Control           | Bewusst verschoben auf spätere Phase             |

---

## 11. Success Metrics

* 👨‍💻 Entwickler kann per Chat einen Service vollständig erzeugen.
* 🔄 Clarifications laufen korrekt (Agent fragt nach fehlenden Infos).
* 📚 Guidelines aus ChromaDB werden angewendet.
* 🖥️ Demo zeigt transparente Schritte (Taskliste, Events, Eingriffe möglich).

---

## 12. Future Extensions

* Multi-User Support & Authentication (OIDC)
* Erweiterte Tool-Integration (Kubernetes, Monitoring, Secrets)
* Multi-Agent Patterns (Separation of roles: Planner, Executor, Reviewer)
* Enterprise-grade Deployment (K8s, Observability, Event Bus)
* LLM Fine-Tuning auf Firmendaten

---

✅ **Fazit:**
Das **IDP Copilot PRD** liefert eine klare Vision, detaillierte Features, Use Cases, Architektur und Roadmap. Für das Capstone-Projekt ist der **Funktionsumfang genau richtig gewählt** – anspruchsvoll, aber realistisch in 6–8 Wochen umsetzbar.

---

👉 Soll ich dir jetzt noch eine **detaillierte Entwickler-Taskliste mit Epics & Stories (im Jira-Stil)** erstellen, sodass du die Implementierung Schritt für Schritt planen kannst?
