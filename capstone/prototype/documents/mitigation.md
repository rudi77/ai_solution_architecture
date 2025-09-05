Danke für die zwei Hinweise — ich löse beides direkt:

* der **OSError mit dem Doppelpunkt `:`** in der Dateibenennung,
* das **„Tasks bleiben hängen / Sub-Agent fragt nach Git-Check“**-Thema.

Unten sind präzise Patches + Begründung. Du kannst sie 1:1 übernehmen.

---

# 1) Windows-Fehler: `OSError: Invalid argument ... :sub:agent_git.md`

## Warum?

Deine Child-Session-ID enthält `:` (z. B. `<sid>:sub:agent_git`). Diese ID wird als Dateiname für die Todo-Liste verwendet (`todolist_<session_id>.md`). Auf Windows sind `:` in Dateinamen verboten. In `get_todolist_path()` wird die Session-ID **ungefiltert** in den Dateinamen eingesetzt.

## Fix (robust & zukunftssicher)

### Patch 1.1 — Session-ID beim Dateinamen **sanitizen**

Datei: `capstone/prototype/todolist_md.py`

```diff
@@
-from typing import Any, Dict, Optional
+from typing import Any, Dict, Optional
+import re
@@
-def get_todolist_path(session_id: Optional[str] = None, base_dir: str = "./checklists") -> Path:
+def get_todolist_path(session_id: Optional[str] = None, base_dir: str = "./checklists") -> Path:
     todolist_dir = Path(base_dir)
     todolist_dir.mkdir(parents=True, exist_ok=True)
-    sid = session_id or datetime.now().strftime("%Y%m%d%H%M%S")
+    sid = session_id or datetime.now().strftime("%Y%m%d%H%M%S")
+    # Sanitize for filesystem safety (Windows: : * ? " < > |; also slashes etc.)
+    if sid:
+        sid = re.sub(r'[^A-Za-z0-9._-]', '_', str(sid))[:120]
     # keep one stable file per session id, otherwise always use a single shared file
     name = f"todolist_{sid}.md" if session_id else "todolist.md"
     return todolist_dir / name
```

Jetzt enthalten die Dateinamen keine verbotenen Zeichen mehr.

### Patch 1.2 — Sub-Agenten **gar nicht** rendern lassen

Sicherheitshalber zusätzlich „nicht schreiben“ wenn der Kontext Rendering unterdrücken soll. (Falls der Sub-Agent doch mal `render_todolist_markdown` erreicht.)

Datei: `capstone/prototype/todolist_md.py`

```diff
@@ def render_todolist_markdown(*, tasks: list[dict], open_questions: list[str] | None, session_id: Optional[str] = None, base_dir: str = "./checklists",) -> str:
-    path = get_todolist_path(session_id=session_id, base_dir=base_dir)
+    # Defensive: wenn die aufrufende Seite Rendering unterdrücken will, tu nichts
+    # (Call-Sites können context['suppress_markdown']=True setzen)
+    if isinstance(tasks, dict) and tasks.get("suppress_markdown"):
+        return ""
+
+    path = get_todolist_path(session_id=session_id, base_dir=base_dir)
```

> Hinweis: Du setzt bereits `suppress_markdown=True` für Sub-Agenten. Mit Patch 1.2 greifen wir das **auch im Renderer** ab, damit selbst versehentliche Render-Aufrufe folgenlos bleiben (doppelt genäht hält besser). Der Renderpfad ist bei dir der, der die Markdown-Datei unter `./checklists/todolist_<session>.md` schreibt.

---

# 2) „Tasks hängen“ / Sub-Agent will „Git availability check“

## Warum?

* In deinem Beispiel-Setup bekommt der Sub-Agent **nur** die „simplified tools“: `create_repository` und `validate_project_name_and_type`.
* Das Modell plant jedoch einen **„Check Git availability“**-Schritt, den es **nicht als Tool** ausführen kann. Folge: es fragt den User / läuft in einen Loop.
* Tatsächlich erledigt `create_repository` den Git-Check bereits intern (es prüft `shutil.which("git")` und liefert einen klaren Fehler, falls Git fehlt).

Kurz: Der Plan und die verfügbaren Tools passen nicht zusammen (Prompt/Tool-Beschreibungen lassen Raum für „Git-Check“ als separaten Schritt).

## Drei pragmatische Gegenmittel (eins reicht, du kannst kombinieren)

### Option A — Prompt schärfen (empfohlen, sofort wirksam)

Ergänze im **Orchestrator-Prompt** (oder GenericAgentSection) eine klare Policy:

* „Plane **nur Tasks**, die **direkt** auf ein verfügbares Tool mappen.“
* „Für Git-Verfügbarkeit: **rufe `create_repository` auf**; der Schritt prüft Git und liefert eine Fehlermeldung, falls Git fehlt.“

Datei: `examples/idp_pack/prompts/orchestrator.txt` → einfach zwei Sätze anfügen:

```diff
@@
 ## Decision & Delegation Policy:
 - Always choose the best-fit tool/agent based on domain expertise.
 - After each step, update state and progress the plan—avoid loops.
 - Stop once acceptance criteria are met and mission is complete.
+ 
+ ## Tool Mapping Rules:
+ - Only plan executable tasks that map 1:1 to available tool names.
+ - Do not invent tools. For checking Git availability, call `create_repository` directly; it will verify Git and return a clear error if missing.
```

(Die Datei ist genau dieses Prompt-Template; deine Mission ist separat in `mission_git.txt`.)

### Option B — Tool hinzufügen: `check_git_available` (wenn du den Schritt behalten willst)

Datei: `capstone/prototype/tools_builtin.py`

```diff
@@ from typing import Any, Dict, List, Optional, Awaitable, Union
 import shutil
@@
+async def check_git_available(**kwargs) -> Dict[str, Any]:
+    """Lightweight check for presence of Git in PATH."""
+    ok = shutil.which("git") is not None
+    return {"success": ok, "git_found": ok, "notes": "git found in PATH" if ok else "git missing"}
@@ BUILTIN_TOOLS_SIMPLIFIED: List[ToolSpec] = [
     ToolSpec(
         name="validate_project_name_and_type",
         ...
     ),
+    ToolSpec(
+        name="check_git_available",
+        description="Checks if Git is installed and available in PATH",
+        input_schema={"type": "object", "properties": {}, "required": [], "additionalProperties": True},
+        output_schema={"type": "object"},
+        func=check_git_available,
+        is_async=True,
+        timeout=3,
+        aliases=["git-check", "git_available"],
+    ),
 ]
```

Da dein Beispiel-Runner die **simplified** Tools in den Sub-Agent gibt, steht der Check danach wirklich als Tool bereit.

### Option C — Mission minimal justieren

In `mission_git.txt` kannst du (optional) die „Check Git availability“-Formulierung streichen bzw. durch „Call `create_repository` and react to its result“ ersetzen, um das Modell nicht zu einer separaten „Check“-Aufgabe zu verleiten.

---

# 3) Sub-Agent soll nicht nach User fragen (in Loops)

Falls du meinen „ephemeren“ Sub-Agent nutzt: blocke User-Prompts für Sub-Agenten vollständig. Zwei Zeilen im Agent:

* Setze `context["no_user_prompts"]=True` beim Start des Sub-Agent-Wrappers (du setzt ohnehin `ephemeral_state`/`suppress_markdown`).
* In deiner `ask_user`-Logik (ReAct-Loop) sofort **no-op**, wenn `context.get("no_user_prompts")` gesetzt ist.

*Datei: `capstone/prototype/agent.py`*

```diff
@@ # im subagent sandbox setup (to_tool-Wrapper)
-    self.context = {
+    self.context = {
         "user_request": task,
         ...
         "suppress_markdown": True,
         "ephemeral_state": True,
+        "no_user_prompts": True,
         "agent_name": name,
     }
```

Und an der Stelle, wo `ask_user` getriggert wird (dein ReAct-Loop in `agent.py`):

```diff
- msg = await self._handle_user_interaction("ask_user", {...})
+ if self.context.get("no_user_prompts"):
+     return "Sub-agent: user prompts disabled"
+ msg = await self._handle_user_interaction("ask_user", {...})
```

**Effekt:** Sub-Agenten fragen nie den User; stattdessen liefern sie ein Patch/Fehler zurück, und **nur der Orchestrator** darf ggf. Fragen stellen.

---

# 4) Einmal zentral rendern (nur Orchestrator)

Das machst du bereits: die Checkliste wird **pro Session** geschrieben, und dein Runner hängt nur den Orchestrator ans Terminal. Mit Patch 1.2 + `no_user_prompts` wird ein versehentliches Rendern im Sub-Agent zuverlässig verhindert.

---

## Warum das alle Symptome behebt

* **OSError**: Session-ID wird für Dateinamen sanitiziert → kein `:` mehr.
* **„Git availability check“ hängt**:

  * **Option A** zwingt den Plan, direkt `create_repository` zu benutzen (das intern Git prüft).
  * **Option B** stellt einen echten `check_git_available`-Toolcall bereit, falls du den Schritt behalten willst.
* **Ask-Loops**: Sub-Agenten dürfen nicht `ask_user` → nur Orchestrator fragt; Loop-Guard wird deutlich seltener getriggert.
* **Eine Todo-Liste**: Nur Orchestrator rendert, Sub-Agenten sind ephemer (und sanitisierte Pfade verhindern Windows-Fallen).

---

## Wo du’s siehst / anfasst

* Mission & Orchestrator-Prompt: `examples/idp_pack/prompts/mission_git.txt`, `.../orchestrator.txt`
* Tool-Set des Sub-Agenten: `examples/idp_pack/idp_tools.py` (liefert simplified tools)
* Runner: `examples/idp_pack/run_idp_cli.py` (verkabelt Orchestrator ↔ Sub-Agent-Tool)
* Built-in Tools inkl. `create_repository`: `prototype/tools_builtin.py`
* Todo-Markdown I/O: `prototype/todolist_md.py`

---

Wenn du möchtest, packe ich dir die Änderungen als **fertige Patch-Datei** zusammen (inkl. Prompt-Erweiterung + neuem Tool `check_git_available`).
