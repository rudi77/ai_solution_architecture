# Refactoring Plan: Agent V2 Architecture

## Phase 1: Core Concepts umstellen (2-3 Tage)

### 1.1 TodoItem neu definieren
**Datei:** `planning/todolist.py`

```python
@dataclass
class TodoItem:
    position: int
    description: str
    acceptance_criteria: str  # NEU: "File exists at path X" statt "use file_write"
    dependencies: List[int] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    
    # Runtime-Felder (werden während Execution gefüllt)
    chosen_tool: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    execution_result: Optional[Dict[str, Any]] = None
    attempts: int = 0
    max_attempts: int = 3
```

**Begründung:** Plan beschreibt *Ziele*, nicht *Implementierung*.

**Migration:**
- Bestehende TodoItems: `tool` → `None`, `parameters` → `None`
- Neue Logik: Tool-Wahl passiert in `_generate_thought()`

---

### 1.2 Thought-Action vereinfachen
**Datei:** `agent.py`

```python
@dataclass
class Action:
    type: ActionType  # tool_call, ask_user, complete, replan
    
    # Für tool_call:
    tool: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    
    # Für ask_user:
    question: Optional[str] = None
    answer_key: Optional[str] = None  # Stable identifier
    
    # Für complete:
    summary: Optional[str] = None

@dataclass
class Thought:
    step_ref: int
    rationale: str  # Max 2 Sätze
    action: Action  # Direkt die ausführbare Action
    expected_outcome: str
    confidence: float = 1.0  # 0-1, für spätere Uncertainty-Handling
```

**Änderung:** Entferne `ThoughtAction` Zwischenschicht, `Thought.action` ist direkt `Action`.

---

### 1.3 Pre-Clarification entfernen
**Datei:** `agent.py`, Methode `execute()`

**ALT:**
```python
# Zeile 236-280: Ganzer Pre-Clarification Block
if not self.state.get("todolist_id"):
    if "clar_questions" not in self.state:
        clar_qs = await self.todo_list_manager.extract_clarification_questions(...)
    # ...
```

**NEU:**
```python
async def execute(self, user_message: str, session_id: str):
    # 1. State laden
    self.state = await self.state_manager.load_state(session_id)
    
    # 2. Mission setzen (nur beim ersten Call)
    if self.mission is None:
        self.mission = user_message
    
    # 3. Pending Question beantworten (falls vorhanden)
    if self.state.get("pending_question"):
        answer_key = self.state["pending_question"]["answer_key"]
        self.state.setdefault("answers", {})[answer_key] = user_message
        self.state.pop("pending_question")
        await self.state_manager.save_state(session_id, self.state)
        yield AgentEvent(type=AgentEventType.STATE_UPDATED, 
                        data={"answer_received": answer_key})
    
    # 4. Plan erstellen (falls noch nicht vorhanden)
    todolist = await self._get_or_create_plan(session_id)
    
    # 5. ReAct Loop
    async for event in self._react_loop(session_id, todolist):
        yield event
```

**Begründung:** Fragen stellen passiert dynamisch im ReAct-Loop, nicht vorab.

---

## Phase 2: ReAct Loop neu implementieren (3-4 Tage)

### 2.1 Neue ReAct-Methode
**Datei:** `agent.py`

```python
async def _react_loop(self, session_id: str, todolist: TodoList) -> AsyncIterator[AgentEvent]:
    """
    Echte ReAct-Schleife: Thought → Action → Observation → Repeat
    """
    max_iterations = 50  # Safety limit
    iteration = 0
    
    while not self._is_plan_complete(todolist) and iteration < max_iterations:
        iteration += 1
        
        # 1. Nächster Step (PENDING oder FAILED mit Retries übrig)
        current_step = self._get_next_actionable_step(todolist)
        
        if not current_step:
            self.logger.info("no_actionable_steps", session_id=session_id)
            break
        
        self.logger.info("step_start", step=current_step.position, 
                        desc=current_step.description[:50])
        
        # 2. THOUGHT: Analysiere + entscheide Tool
        context = self._build_thought_context(current_step, todolist)
        thought = await self._generate_thought(context)
        
        yield AgentEvent(type=AgentEventType.THOUGHT, 
                        data={"step": current_step.position, "thought": asdict(thought)})
        
        # 3. ACTION: Führe aus
        if thought.action.type == ActionType.ASK:
            # User-Input benötigt
            self.state["pending_question"] = {
                "answer_key": thought.action.answer_key,
                "question": thought.action.question,
                "for_step": current_step.position
            }
            await self.state_manager.save_state(session_id, self.state)
            
            yield AgentEvent(type=AgentEventType.ASK_USER, 
                            data={"question": thought.action.question})
            return  # Pause execution
        
        elif thought.action.type == ActionType.TOOL:
            # Tool ausführen
            observation = await self._execute_tool_safe(thought.action)
            
            # Runtime-Felder füllen
            current_step.chosen_tool = thought.action.tool
            current_step.tool_input = thought.action.tool_input
            current_step.execution_result = observation
            current_step.attempts += 1
            
            # Status updaten
            if observation.get("success"):
                # Acceptance Criteria prüfen
                if await self._check_acceptance(current_step, observation):
                    current_step.status = TaskStatus.COMPLETED
                else:
                    current_step.status = TaskStatus.FAILED
                    self.logger.warning("acceptance_failed", step=current_step.position)
            else:
                current_step.status = TaskStatus.FAILED
            
            yield AgentEvent(type=AgentEventType.TOOL_RESULT, data=observation)
        
        elif thought.action.type == ActionType.REPLAN:
            # Plan anpassen
            todolist = await self._replan(current_step, thought, todolist)
            yield AgentEvent(type=AgentEventType.STATE_UPDATED, 
                            data={"plan_updated": True})
        
        elif thought.action.type == ActionType.DONE:
            # Frühzeitiger Abschluss
            break
        
        # 4. State + Plan persistieren
        await self.state_manager.save_state(session_id, self.state)
        await self.todo_list_manager.update_todolist(todolist)
        
        # 5. Error Recovery (falls Step failed)
        if current_step.status == TaskStatus.FAILED:
            if current_step.attempts < current_step.max_attempts:
                # Retry mit angepasstem Context
                current_step.status = TaskStatus.PENDING
                self.logger.info("retry_step", step=current_step.position, 
                                attempt=current_step.attempts)
            else:
                # Abbrechen oder Replan triggern
                self.logger.error("step_exhausted", step=current_step.position)
                # Optional: ask_user für manuelle Intervention
    
    # Fertig
    yield AgentEvent(type=AgentEventType.COMPLETE, 
                    data={"todolist": todolist.to_markdown()})
```

---

### 2.2 Helper-Methoden
**Datei:** `agent.py`

```python
def _get_next_actionable_step(self, todolist: TodoList) -> Optional[TodoItem]:
    """Findet nächsten Step, der ausgeführt werden kann."""
    for step in sorted(todolist.items, key=lambda s: s.position):
        if step.status == TaskStatus.COMPLETED:
            continue
        
        if step.status == TaskStatus.PENDING:
            # Dependencies erfüllt?
            deps_met = all(
                any(s.position == dep and s.status == TaskStatus.COMPLETED 
                    for s in todolist.items)
                for dep in step.dependencies
            )
            if deps_met:
                return step
        
        if step.status == TaskStatus.FAILED and step.attempts < step.max_attempts:
            return step  # Retry
    
    return None

def _build_thought_context(self, step: TodoItem, todolist: TodoList) -> Dict[str, Any]:
    """Baut Context für Thought-Generation."""
    # Ergebnisse vorheriger Steps
    previous_results = [
        {
            "step": s.position,
            "tool": s.chosen_tool,
            "result": s.execution_result
        }
        for s in todolist.items 
        if s.status == TaskStatus.COMPLETED and s.execution_result
    ]
    
    return {
        "current_step": step,
        "previous_results": previous_results[-5:],  # Last 5
        "available_tools": self.tools_description,
        "user_answers": self.state.get("answers", {}),
        "mission": self.mission,
    }

async def _check_acceptance(self, step: TodoItem, observation: Dict) -> bool:
    """Prüft ob Acceptance Criteria erfüllt sind."""
    # Einfache Heuristik: Wenn Tool erfolgreich war, ist Step erfüllt
    # TODO: Später mit LLM-Call verfeinern
    return observation.get("success", False)

def _is_plan_complete(self, todolist: TodoList) -> bool:
    """Check ob alle Steps completed/skipped sind."""
    return all(
        s.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED) 
        for s in todolist.items
    )
```

---

## Phase 3: Tool-Robustheit (2 Tage)

### 3.1 Safe Execution Wrapper
**Datei:** `tool.py`

```python
class Tool(ABC):
    async def execute_safe(self, **kwargs) -> Dict[str, Any]:
        """
        Robust wrapper um execute() mit:
        - Validation
        - Retry-Logik
        - Error Handling
        - Timeout
        """
        max_retries = 3
        timeout_seconds = 60
        
        for attempt in range(max_retries):
            try:
                # 1. Parameter validieren
                valid, error = self.validate_params(**kwargs)
                if not valid:
                    return {
                        "success": False,
                        "error": f"Invalid parameters: {error}",
                        "tool": self.name
                    }
                
                # 2. Execute mit Timeout
                result = await asyncio.wait_for(
                    self.execute(**kwargs),
                    timeout=timeout_seconds
                )
                
                # 3. Result validieren
                if not isinstance(result, dict):
                    return {
                        "success": False,
                        "error": f"Tool returned invalid type: {type(result)}",
                        "tool": self.name
                    }
                
                if "success" not in result:
                    result["success"] = False  # Default to False
                
                result["tool"] = self.name
                result["attempt"] = attempt + 1
                
                return result
                
            except asyncio.TimeoutError:
                if attempt == max_retries - 1:
                    return {
                        "success": False,
                        "error": f"Tool timed out after {timeout_seconds}s",
                        "tool": self.name,
                        "retries": attempt + 1
                    }
                await asyncio.sleep(2 ** attempt)
                
            except Exception as e:
                import traceback
                if attempt == max_retries - 1:
                    return {
                        "success": False,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "traceback": traceback.format_exc(),
                        "tool": self.name,
                        "retries": attempt + 1
                    }
                await asyncio.sleep(2 ** attempt)
        
        return {"success": False, "error": "Should not reach here"}
```

**Agent ändert:**
```python
async def _execute_tool_safe(self, action: Action) -> Dict[str, Any]:
    tool = self._get_tool(action.tool)
    if not tool:
        return {"success": False, "error": f"Tool '{action.tool}' not found"}
    
    return await tool.execute_safe(**action.tool_input)
```

---

### 3.2 Python Tool Fixes
**Datei:** `tools/code_tool.py`

```python
async def execute(self, code: str, context: Dict[str, Any] = None, cwd: str = None, **kwargs):
    # 1. CWD mit Context Manager
    @contextlib.contextmanager
    def safe_chdir(path):
        original = os.getcwd()
        try:
            if path:
                os.chdir(path)
            yield
        finally:
            try:
                os.chdir(original)
            except (OSError, FileNotFoundError):
                pass
    
    # 2. Separate Import-Behandlung
    import_code = """
import os, sys, json, re, pathlib, shutil
# ... rest
"""
    
    safe_namespace = {"__builtins__": {...}, "context": context or {}}
    
    try:
        # Imports zuerst (mit spezifischem Error)
        exec(import_code, safe_namespace)
    except ImportError as e:
        return {
            "success": False,
            "error": f"Missing library: {e.name}",
            "hint": f"Install with: pip install {e.name}",
            "type": "ImportError"
        }
    
    try:
        with safe_chdir(cwd):
            exec(code, safe_namespace)
        
        # 3. Result-Check
        if 'result' not in safe_namespace:
            return {
                "success": False,
                "error": "Code must assign output to 'result' variable",
                "hint": "Add: result = your_output",
                "variables": list(safe_namespace.keys())
            }
        
        return {
            "success": True,
            "result": _sanitize(safe_namespace['result']),
            "variables": {k: _sanitize(v) for k, v in safe_namespace.items() 
                         if not k.startswith('_')}
        }
    
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc()
        }
```

---

## Phase 4: State Management verbessern (1-2 Tage)

### 4.1 Versionierung + Locks
**Datei:** `statemanager.py`

```python
class StateManager:
    def __init__(self, state_dir: str = "./agent_states"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(exist_ok=True)
        self.locks: Dict[str, asyncio.Lock] = {}
        self.logger = structlog.get_logger()
    
    def _get_lock(self, session_id: str) -> asyncio.Lock:
        if session_id not in self.locks:
            self.locks[session_id] = asyncio.Lock()
        return self.locks[session_id]
    
    async def save_state(self, session_id: str, state_data: Dict) -> bool:
        async with self._get_lock(session_id):
            try:
                state_file = self.state_dir / f"{session_id}.pkl"
                
                # Version erhöhen
                current_version = state_data.get("_version", 0)
                state_data["_version"] = current_version + 1
                state_data["_updated_at"] = datetime.now().isoformat()
                
                state_to_save = {
                    'session_id': session_id,
                    'timestamp': datetime.now().isoformat(),
                    'state_data': state_data
                }
                
                import aiofiles
                async with aiofiles.open(state_file, 'wb') as f:
                    await f.write(pickle.dumps(state_to_save))
                
                self.logger.info("state_saved", session_id=session_id, 
                                version=state_data["_version"])
                return True
                
            except Exception as e:
                self.logger.error("state_save_failed", session_id=session_id, error=str(e))
                return False
```

---

### 4.2 Message History Sliding Window
**Datei:** `agent.py` (oder neue Datei `message_history.py`)

```python
class MessageHistory:
    MAX_MESSAGES = 50
    SUMMARY_THRESHOLD = 40
    
    async def add_message(self, message: str, role: str):
        self.messages.append({"role": role, "content": message})
        
        if len(self.messages) > self.MAX_MESSAGES:
            await self._compress_history()
    
    async def _compress_history(self):
        """Summarize alte Messages mit LLM."""
        old_messages = self.messages[1:self.SUMMARY_THRESHOLD]  # Skip system
        
        summary_prompt = f"""Summarize this conversation history concisely:

{json.dumps(old_messages, indent=2)}

Provide a 2-3 paragraph summary of key decisions, results, and context."""
        
        response = await litellm.acompletion(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": summary_prompt}],
            temperature=0
        )
        
        summary = response.choices[0].message.content
        
        self.messages = [
            self.system_prompt,
            {"role": "system", "content": f"[Previous context summary]\n{summary}"},
            *self.messages[self.SUMMARY_THRESHOLD:]
        ]
```

---

## Phase 5: Plan-Erstellung anpassen (1 Tag)

### 5.1 Neuer Plan-Prompt
**Datei:** `planning/todolist.py`

```python
def create_final_todolist_prompts(self, mission: str, tools_desc: str, answers: Any):
    structure = """
{
  "items": [
    {
      "position": 1,
      "description": "What needs to be done (outcome-oriented)",
      "acceptance_criteria": "How to verify it's done (observable condition)",
      "dependencies": [],
      "status": "PENDING"
    }
  ],
  "open_questions": [],
  "notes": ""
}
"""
    
    system_prompt = f"""You are a planning agent. Create a minimal, goal-oriented plan.

Mission:
{mission}

User Answers:
{json.dumps(answers, indent=2)}

Available Tools (for reference, DO NOT specify in plan):
{tools_desc}

RULES:
1. Each item describes WHAT to achieve, NOT HOW (no tool names, no parameters)
2. acceptance_criteria: Observable condition (e.g., "File X exists with content Y")
3. dependencies: List of step positions that must complete first
4. Keep plan minimal (prefer 3-7 steps over 20)
5. open_questions MUST be empty (all clarifications resolved)

Return JSON matching:
{structure}
"""
    
    return ("Generate the plan", system_prompt)
```

---

## Migrations-Reihenfolge

### Woche 1:
1. **Tag 1-2:** Phase 1 (TodoItem, Action, Thought umstellen)
2. **Tag 3-4:** Phase 2.1 (ReAct Loop Grundgerüst)
3. **Tag 5:** Phase 2.2 (Helper-Methoden)

### Woche 2:
1. **Tag 1-2:** Phase 3 (Tools robuster machen)
2. **Tag 3:** Phase 4 (StateManager Locks)
3. **Tag 4:** Phase 5 (Plan-Prompts anpassen)
4. **Tag 5:** Integration Testing

### Testing-Strategie:
```python
# tests/test_react_loop.py
async def test_simple_file_creation():
    agent = Agent.create_agent(...)
    
    events = []
    async for event in agent.execute("Create hello.txt with 'Hello World'", "test-1"):
        events.append(event)
    
    assert any(e.type == AgentEventType.COMPLETE for e in events)
    assert Path("hello.txt").exists()
```

Das ist ein realistischer 2-Wochen-Plan. Fragen?