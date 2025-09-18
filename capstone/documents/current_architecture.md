Awesome — here’s a **Mermaid-first** architecture doc of your current agent framework with C4 diagrams. I kept the prose light and placed everything important into diagrams. Citations point to the specific spots in your code.

# System Overview

A ReAct-style agent plans (clarifies first), then executes a strict TodoList using sandboxed tools; state and plans are persisted locally. &#x20;

```mermaid
%% C4: Level 1 — System Context
C4Context
title Hybrid Agent Framework — Context

Person(user, "Human User", "Provides mission; answers clarifying questions")
System(agent, "Hybrid Agent Framework", "Plans & executes deterministic steps")

System_Ext(llm, "LLM (via litellm)", "Planning, thoughts, actions")
System_Ext(web, "Web (DuckDuckGo API + HTTP)", "Search & fetch")
System_Ext(github, "GitHub API", "Repo operations")
SystemDb(fs, "Local Filesystem", "State (pickle) + TodoLists (JSON)")

Rel(user, agent, "Mission & answers; receives results/events")
Rel(agent, llm, "LLM calls for question-mining, plan, ReAct JSON")
Rel(agent, web, "web_search / web_fetch")
Rel(agent, github, "GitHub repo ops")
Rel(agent, fs, "save/load state; persist TodoLists")
```

**Why:** The agent streams events (THOUGHT/ACTION/TOOL\_RESULT/ASK/COMPLETE) and uses local files for state & plans. &#x20;

---

# Containers (C4 Level 2)

```mermaid
%% C4: Level 2 — Container Diagram
C4Container
title Hybrid Agent Framework — Containers

System_Boundary(sys, "Hybrid Agent Framework") {
  Container(cli, "TaskForce CLI", "Python", "Interactive driver for HybridAgent")
  Container(conv, "ConversationManager", "Python", "Bridges CLI ↔ Agent; tracks plan_id & history")
  Container(agent, "Agent Runtime", "Python", "Clarify → Plan → ReAct execute; emits events")
  Container(plan, "Planning Subsystem", "Python", "TodoList models + manager")
  Container(tools, "Tooling Suite", "Python", "Web, File I/O, Git/GitHub, Shell, PowerShell, Python exec")
  Container(state, "State Store", "Pickle files", "Async save/load via StateManager")
  Container(plstore, "Plan Store", "JSON files", "TodoList persistence & markdown")
}

System_Ext(llm, "LLM (litellm)", "")
System_Ext(web, "Web / DuckDuckGo + HTTP", "")
System_Ext(gh, "GitHub REST API", "")

Rel(cli, conv, "start(), user_says()")
Rel(conv, agent, "execute(mission|user_message, session_id, plan_id)")
Rel(agent, plan, "create/parse/validate TodoList")
Rel(agent, tools, "Executes tool calls")
Rel(agent, state, "load_state/save_state")
Rel(plan, plstore, "read/write TodoList JSON/MD")
Rel(agent, llm, "planning + thought/action JSON")
Rel(tools, web, "web_search / web_fetch")
Rel(tools, gh, "repo create/list/delete")
```

* **ConversationManager** keeps session/plan linkage.&#x20;
* **StateManager** persists per-session pickle asynchronously.&#x20;
* **TodoList** is the single source of truth (items/open\_questions/notes).&#x20;

---

# Components (C4 Level 3)

```mermaid
%% C4: Level 3 — Component Diagram (Agent + Planning + Tools)
C4Component
title Key Components

Container_Boundary(agent, "Agent Runtime") {
  Component(Agent, "Agent", "agent.Agent", "Orchestrates clarify→plan→ReAct; streams events")
  Component(MsgHistory, "MessageHistory", "agent.MessageHistory", "System prompt + mission + tool desc")
  Component(ThoughtSel, "Thought/Action Generator", "LLM calls", "Strict JSON for actions")
  Component(Exec, "Action Executor", "agent._execute_action", "Invokes Tool.execute()")
  Component(Events, "Events", "AgentEvent/Type", "THOUGHT|ACTION|TOOL_RESULT|ASK|COMPLETE")
}

Container_Boundary(plan, "Planning") {
  Component(Models, "TodoList & TodoItem", "planning.todolist", "Schema + (de)serialization")
  Component(TLMgr, "TodoListManager", "planning.todolist.TodoListManager", "Clarification prompts + final plan; R/W files")
}

Container_Boundary(state, "State") {
  Component(StateMgr, "StateManager", "statemanager.StateManager", "Async pickle save/load; cleanup")
}

Container_Boundary(tools, "Tools") {
  Component(WebSearch, "WebSearchTool", "tools.web_tool", "DuckDuckGo")
  Component(WebFetch, "WebFetchTool", "tools.web_tool", "HTTP GET")
  Component(FileIO, "FileRead/WriteTool", "tools.file_tool", "Safe size & backups")
  Component(Git, "GitTool", "tools.git_tool", "Local git ops")
  Component(GH, "GitHubTool", "tools.git_tool", "GitHub REST ops")
  Component(Shell, "ShellTool", "tools.shell_tool", "Async shell with dangerous-pattern blocklist")
  Component(PS, "PowerShellTool", "tools.shell_tool", "pwsh/powershell with guards")
  Component(Py, "PythonTool", "tools.code_tool", "Controlled Python exec")
}

Rel(Agent, TLMgr, "Clarification Qs → Final TodoList")
Rel(Agent, StateMgr, "save/load state")
Rel(Exec, WebSearch, "tool_call")
Rel(Exec, WebFetch, "tool_call")
Rel(Exec, FileIO, "tool_call")
Rel(Exec, Git, "tool_call")
Rel(Exec, GH, "tool_call")
Rel(Exec, Shell, "tool_call")
Rel(Exec, PS, "tool_call")
Rel(Exec, Py, "tool_call")
```

* **Models**: `TaskStatus`, `TodoItem`, `TodoList` with robust alias parsing & JSON/MD helpers. &#x20;
* **Tools** include safety checks (e.g., shell/pwsh pattern blocklists, timeouts). &#x20;
* **WebSearch** via DuckDuckGo’s API; tolerant to non-standard content-type. &#x20;

---

# Execution Flow (Mermaid Sequence)

```mermaid
sequenceDiagram
autonumber
participant U as User
participant A as Agent
participant SM as StateManager
participant TL as TodoListManager
participant L as LLM
participant T as Tools

U->>A: Mission / user_message
A->>SM: load_state(session_id)
SM-->>A: state (pending_question?, todolist_id?)
alt First run (no plan)
  A->>TL: extract_clarification_questions(mission, tools_desc)
  TL->>L: Clarification-Mining prompt (JSON array)
  L-->>TL: [{"key","question"},...]
  TL-->>A: unanswered?
  alt Any unanswered
    A-->>U: ASK_USER (single precise question)
    U->>A: answer
    A->>SM: save_state(pending_question cleared; answers)
  end
  A->>TL: create_todolist(No-ASK mode)
  TL->>L: Final plan prompt (strict JSON)
  L-->>TL: TodoList (no open_questions)
  TL-->>A: TodoList; persisted
else Resume with existing plan
  A->>TL: load_todolist_by_id(state.todolist_id)
end
loop For each TodoItem
  A->>L: generate Thought + Action (JSON)
  L-->>A: Thought/Action JSON
  A->>T: execute(action.tool, params)
  T-->>A: observation {success|error}
  A->>SM: save_state(last_observation, step status)
  A->>TL: update_todolist()
end
A-->>U: COMPLETE (TodoList markdown)
```

* Clarify → Final plan (no `ASK_USER` in plan), then ReAct over steps; each step sets status and persists. &#x20;
* Completion returns TodoList as Markdown.&#x20;

---

# Safety & Policies (at-a-glance)

```mermaid
flowchart TD
A[Shell/PowerShell Tools] -->|blocklists & timeouts| B{Dangerous?}
B -- yes --> C[Fail with error]
B -- no --> D[Execute safely]
A --> E[Validate cwd; resolve pwsh/powershell]
```

* Shell dangerous pattern blocklists; timeout handling & process kill. &#x20;
* PowerShell validates cwd, resolves executable, same timeout/kill discipline. &#x20;

---

# Data Model Cheatsheet

```mermaid
classDiagram
  class TodoList {
    +string todolist_id
    +List~TodoItem~ items
    +List~string~ open_questions
    +string notes
    +to_json()
    +to_markdown()
  }

  class TodoItem {
    +int position
    +string description
    +string tool
    +Dict parameters
    +TaskStatus status
  }

  class TaskStatus {
    <<enum>>
    PENDING
    IN_PROGRESS
    COMPLETED
    FAILED
    SKIPPED
  }

  TodoList "1" o--> "*" TodoItem
```

Backed by robust (de)serialization and status normalization. &#x20;

---

# Operational Notes

```mermaid
stateDiagram-v2
  [*] --> Init
  Init: CLI boots HybridAgent
  Init --> Waiting: cm.start(mission)
  Waiting --> Executing: user_says(text)
  Executing --> Waiting: needs_user_input?
  Executing --> Done: COMPLETE
```

* **TaskForce CLI** wires up `HybridAgent` and loops on user input. &#x20;
* **State** at `./agent_states/*.pkl` (async save/load + cleanup). &#x20;

---

If you want, I can export these Mermaid blocks into a single Markdown/PDF handout or split them into per-team variants (PM vs. Eng).
