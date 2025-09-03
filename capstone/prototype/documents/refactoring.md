Love it. Here’s a clean, end-to-end **refactor plan** that (1) makes the agent truly generic (mission prompt + tools only) and (2) keeps and elevates the **Checklist → TodoList** concept as a first-class, domain-agnostic progress tracker and decision aid.

---

# Phase 0 — What we have today (quick map)

* **Agent core** mixes generic ReAct with IDP/Git assumptions; imports `BUILTIN_TOOLS` by default and stitches tool rules into the system prompt; hard-codes “checklist” creation/updates and even special blockers (git dir conflict, missing GitHub token).
* **Checklist** is already implemented as a persisted Markdown doc with create/update helpers (`checklists_simple.py`); the agent reads/writes it and uses its existence to gate tool execution.
* **Prompts** include IDP/Git flavored system prompts baked into the package.
* **Tools** are well-abstracted via `ToolSpec`, `export_openai_tools`, `find_tool`, `execute_tool_by_name` (good, keep), with current IDP-specific tools in `tools_builtin.py`.

---

# Phase 1 — Rename & abstract “Checklist” → “TodoList”

## 1.1 File & symbol renames

* **Files**

  * `checklists_simple.py` → `todolist_md.py` (export the same creation/update helpers under the new name). Keep a thin compatibility import (optional) for one release.
* **Conceptual/API changes inside the helpers**

  * No behavioral change. Only words: “Checklist” → “TodoList”. Keep Markdown format: a title, meta, **checkbox list** `- [ ]`, and notes.
  * Keep `_slugify`, `get_*_path`, `create_*_md`, `update_*_md` signatures identical, just renamed (and update strings in prompts to say “Todo List”).

## 1.2 Agent code changes (names only; behavior preserved)

* In `idp.py`:

  * Replace **all** `checklist_*` context keys with `todolist_*`. Examples:

    * `checklist_created` → `todolist_created`
    * `checklist_file` → `todolist_file`
  * Rename action type: `UPDATE_CHECKLIST` → `UPDATE_TODOLIST` in `ActionType` (and any case labels).
  * Rename handler `_handle_checklist_action` → `_handle_todolist_action`; keep public behavior intact.
  * Rename helper `_get_checklist_status` → `_get_todolist_status`; update callers.
  * Update any user-facing strings (“Checklist” → “Todo List”) in yields and logs.

Why: You keep the persistent progress tracker but shed the “project checklist” connotation. It’s now a **generic Todo List** that any mission can use.

---

# Phase 2 — Make the agent truly generic (no domain assumptions)

## 2.1 Remove IDP/Git defaults from the agent

* **Constructor**: require the caller to pass `tools` explicitly; do **not** default to `BUILTIN_TOOLS`. (If `None`, use empty list.)
* **Prompts**: remove any import/usage of `IDP_COPILOT_SYSTEM_PROMPT*` from the agent module; the caller must provide `system_prompt` (mission prompt).
* **Main**: move the current IDP/Git command-line harness into an example script (see Phase 5).

Result: The core agent ships *no* opinions about IDP/Git.

## 2.2 Vendor-agnostic tool-calling boundary

* Today `_determine_action` reaches directly for OpenAI’s `.client.chat.completions.create` and mixes meta-actions with tool list.
* **Add** to `LLMProvider` an abstract `call_tools(system_prompt, messages, tools) -> Optional[{name, arguments}]`.

  * Implement in `OpenAIProvider` using the existing tool-calling flow (same as today, but moved behind the provider).
  * For providers without tool calling, return `None`, and we’ll fall back to schema JSON (already implemented).
* Update `_determine_action()` to **only** use the provider interface; remove direct SDK calls and try/except around OpenAI specifics.

## 2.3 Neutralize domain-specific “blockers”

* Replace hard-coded git/credential blockers (`dir_conflict`, `missing_github_token`) with a **generic** `self.context["blocker"] = {message, suggestion}` when tool results contain errors.
* Keep ASK\_USER escalation logic, but make its text generic (“A blocking error occurred…”).

## 2.4 Keep the TodoList bootstrapping — generically

* Preserve the nice property: **if no Todo List exists yet, create it** before the first tool call, because it orients the LLM and the user—but describe it as “Todo List”, not “Checklist”.
* Keep best-effort updates after tool runs (mark IN\_PROGRESS/COMPLETED/FAILED) by **instructional edits** through `update_todolist_md()`; do not require a structured in-memory list (keeps it storage-agnostic).

---

# Phase 3 — System prompt composition & context summary

## 3.1 Clean system prompt composition

* `_compose_system_prompt()` currently injects dynamic tool docs and also hardcodes IDP rules like “On blocking errors (directory conflict, missing GITHUB\_TOKEN)…” and “Limit retries for create\_repository to 1”.
* **Change**: inject only **neutral** usage rules:

  * Use only listed tools.
  * After each tool run, update the **Todo List** with status/result.
  * If a blocking error occurs, consider ASK\_USER with suggested next steps.
  * Don’t assume any specific tool (no `create_repository` special case).
* The per-tool required params summary is great — keep it.

## 3.2 Context summary updates

* `_build_context_summary()` should reference “Todo List File” instead of “Checklist File” and otherwise stay neutral.
* Keep short **Recent Actions** ring buffer (generic and helpful).

---

# Phase 4 — Public API surface and policies

## 4.1 Agent constructor signature

```python
class ProductionReActAgent:
    def __init__(
        self,
        system_prompt: str,
        llm_provider: LLMProvider,
        *,
        tools: list[ToolSpec] | None = None,
        policy: dict | None = None,
    ):
        ...
```

* `tools` default to `[]`.
* `policy` options (generic):

  * `max_steps` (default 50)
  * `max_retries` (default 3) with exponential backoff (existing)
  * `persist_state` (default True; current StateManager is kept)

## 4.2 Action space

* Keep: `TOOL_CALL`, `ASK_USER`, `COMPLETE`, `ERROR_RECOVERY`.
* Rename: `UPDATE_CHECKLIST` → `UPDATE_TODOLIST`.
* Internally, we continue to expose “meta-actions” to the LLM (ask\_user, complete, update\_todolist, error\_recovery) through the provider’s `call_tools()` when it supports function calling.

---

# Phase 5 — Extract domain packs (examples, not core)

* Move all IDP/Git-specific assets into `examples/idp_pack/`:

  * `system_prompt_idp.txt` (old `IDP_COPILOT_SYSTEM_PROMPT`) and `system_prompt_git.txt` (old `IDP_COPILOT_SYSTEM_PROMPT_GIT`).
  * `idp_tools.py` exporting the current `BUILTIN_TOOLS` (unchanged content, only location moved).
  * `run_idp_cli.py` that composes: mission prompt + tool list + policies and launches the agent like your current `main()`.

This leaves `ProductionReActAgent` 100% generic.

---

# Phase 6 — Code edits (surgical)

Below are the minimal, targeted edits. (Names use the new TodoList terms; line numbers omitted for brevity.)

## 6.1 `todolist_md.py` (ex-`checklists_simple.py`)

* Rename public functions:

  * `create_checklist_md` → `create_todolist_md`
  * `update_checklist_md` → `update_todolist_md`
* Change prompt strings “Checklist” → “Todo List”, keep structure and rules identical.

## 6.2 `idp.py` (agent)

* **Enums**

  * `ActionType.UPDATE_CHECKLIST` → `ActionType.UPDATE_TODOLIST`.
* **State keys**

  * Replace `checklist_*` with `todolist_*` everywhere (created/file/status getters).
* **Handlers**

  * `_handle_checklist_action` → `_handle_todolist_action`; internal calls to `create_todolist_md`, `update_todolist_md` (import from `todolist_md`).
  * `_execute_tool_call`:

    * Keep the “ensure todolist exists” guard, just renamed.
    * Keep best-effort status updates via `update_todolist_md()` (IN\_PROGRESS/COMPLETED/FAILED, with recorded result).
    * Remove IDP-specific blocker typing; set a generic `blocker = {message, suggestion}` when any error string exists.
* **Provider abstraction**

  * Add `LLMProvider.call_tools()` and refactor `_determine_action()` to call it; remove direct OpenAI SDK usage here.
* **System prompt composition**

  * Update `_compose_system_prompt()` rules to be generic and mention “Todo List” not “Checklist”; drop tool-specific retry rules.
* **Constructor**

  * Stop defaulting `tools` to `BUILTIN_TOOLS`. Use `[]` if not provided.
* **Main**

  * Remove (or replace with a tiny sample) — the IDP CLI moves to `examples/idp_pack/run_idp_cli.py`.

## 6.3 `tools.py`

* No changes; keep as is (it’s already generic and solid).

## 6.4 `tools_builtin.py`

* No functional changes for core; move into example pack (export unchanged `BUILTIN_TOOLS`).

## 6.5 `prompt.py`

* Move the IDP prompts into example pack; the core module should not import them.

---

# Phase 7 — Migration notes

* If you want one release of backwards compatibility:

  * Keep import shims:

    * `from todolist_md import create_todolist_md as create_checklist_md` etc.
  * Map `ActionType.UPDATE_CHECKLIST` to `UPDATE_TODOLIST` in a deprecated alias for one version.
* Update any existing missions/prompts that say “Checklist” to say “Todo List.”

---

# Phase 8 — Tests & acceptance criteria

1. **Zero-tools mode**

   * Start agent with `tools=[]` and a trivial mission; agent can only `ASK_USER`/`COMPLETE`. No crashes.
2. **Hello-tools mode**

   * Register two demo tools (`echo`, `math.add`); mission instructs to use them; agent calls via provider tool-calling (OpenAI) or falls back to schema JSON; **Todo List** is created and updated after each call.
3. **IDP pack**

   * In `examples/idp_pack/`, compose the moved prompts + current `BUILTIN_TOOLS` and verify the same behavior you have today (repository creation flow), but with a **generic core** agent.
4. **Persistence**

   * Interrupt a session; resume with same `session_id`; agent restores state and **todolist** path and continues.
5. **Blockers & ASK\_USER**

   * Simulate a failing tool (e.g., `create_repository` without `GITHUB_TOKEN`); verify generic blocker → `ASK_USER` with non-IDP-specific wording.

---

# Phase 9 — Optional polish (quick wins)

* **Pydantic v2**: migrate deprecated `@validator` to `@field_validator` in `ActionDecision`.
* **Policy knob** to disable automatic TodoList bootstrapping (let missions opt-out).
* **Todo item schema hint**: when creating the Todo List, suggest an item field `tool: <exact_tool_name>` (the current doc text already nudges this) so the LLM can align actions to items cleanly.

---

## Deliverables (by PR)

* **PR-1**: Rename & extract `todolist_md.py`; agent string/enum/key renames; no behavior change.
* **PR-2**: Remove IDP/Git defaults (no `BUILTIN_TOOLS`, no built-in prompts); neutral system-prompt composition.
* **PR-3**: Provider `call_tools()` abstraction; `_determine_action()` refactor.
* **PR-4**: Generic blocker handling; context summary & messages use “Todo List.”
* **PR-5**: Example pack `examples/idp_pack/` with moved prompts/tools and a CLI runner.

This leaves you with a **generic, mission-configured ReAct agent** that leverages a **Todo List** as a universal, persistent progress & decision aid — exactly what you outlined.
