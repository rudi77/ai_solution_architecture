100% d’accord: Lass uns **Single Responsibility** durchziehen – keine „Sammel-Tools“ wie `apply_template_and_commit`, und auch `create_repository` wird aufgespalten. Unten bekommst du eine präzise, umsetzbare Roadmap (inkl. konkreter Tool-Signaturen, Prompt-Updates und UI-Änderungen), die deine Demo stabil macht und den Code radikal vereinfacht.

---

# 1) Zielbild (SRP, deterministisch, demo-tauglich)

## Minimale Pipeline (nur die nötigen Schritte)

1. `git_init_repo(name)` → legt Ordner unter `repos/` an, `git init`, `branch main`, Git-Identität setzen (falls fehlt).
2. `discover_templates` → Kandidaten ermitteln.
3. `select_template(user_input)` → ggf. Rückfrage.
4. `apply_project_template(template_file, target_dir, project_name)` → nur Dateien schreiben (kein Git).
5. `git_add_files(repo_path, files=["."])` → Bühne füllen (SRP).
6. `git_commit(repo_path, message="Apply template: …")` → Commit (SRP).
7. Optional Remote:
   a) `github_create_repo(name, visibility)` → nur Remote über API anlegen (SRP).
   b) `git_set_remote(repo_path, remote_url)` → `origin` setzen (SRP).
   c) `git_push(repo_path)` → pushen (SRP).

> Wichtig: **Keine** impliziten Pushes und **keine** impliziten Commits mehr. Alles ist explizit, klein und testbar.
> Heute blockiert `create_repository` genau hier, weil es Initial-Commit schreibt **und** versucht, Remote zu bauen/pushen, was in deiner Demo ohne Token schiefgeht und den Agent auf `git push` „anfixt“ .

---

# 2) Konkrete Code-Änderungen

## 2.1 Neue schlanke Git-Tools (SRP)

Im Modul `prototype/tool_packages/git_tools/git_ops.py`:

* `async def git_init_repo(name: str) -> {success, repo_path, default_branch}`

  * Erstellt `repos/<name>`, `git init`, `branch -M main`, setzt `user.name`/`user.email` falls leer.
  * **Kein** README, **kein** Commit, **kein** Remote.
* `async def github_create_repo(name: str, visibility: str="private") -> {success, html_url, clone_url, owner}`

  * Nur GitHub-API-Call; **kein** lokaler Git-Aufruf.
* `async def git_set_remote(repo_path: str, remote_url: str, name: str="origin")`

  * `git remote add/set-url …` (SRP).
* (Optional) `async def git_add_all(repo_path: str)`

  * Alias für `git_add_files(repo_path, files=["."])` (du kannst auch einfach die bestehende `git_add_files` mit `["."]` verwenden).

> Parallel: **`create_repository` als „Legacy/Convenience“ markieren und aus Default-Allow-Liste entfernen.** Die jetzige Fassung bündelt von `git init` bis GitHub-Push (inkl. README) zu viel in einem Tool und ist die **Root-Cause** für die Push-Fehlversuche ohne Token .

## 2.2 Bestehende Tools weiterverwenden

* `apply_project_template` bleibt reines Files-Schreiben (SRP). Heute macht es genau das (und **kein** Git) – das passt perfekt in die Pipeline .
* `git_add_files`, `git_commit`, `git_push` bleiben wie sind; du rufst sie nun **immer explizit** (statt gebündelt) .

## 2.3 Path-Manager entschärfen (Demo)

* Für die Demo: `validate_working_directory`/`WorkingDirectoryManager` **nicht** auf Repo-Pfad „korrigieren“. Verwende strikt den von `git_init_repo`/SRP-Tools gelieferten `repo_path`. Dein aktueller Guard erzeugt Drift/Noise – für die Demo raus oder als No-Op konfigurieren .

---

# 3) Prompt-& Missions-Updates (SRP-konform)

## 3.1 Mission „Template-Based Project Creation“

Passe `examples/idp_pack/prompts/mission_template_git.txt` an (Kernaussage):

* Entferne die Anweisung zu einem kombinierten Commit-Tool; **verlange explizite SRP-Calls** nach dem Template-Schritt:
  „Nach `apply_project_template`: `git_add_files(["."])` → `git_commit(… )`. Push nur, wenn Remote existiert.“
* Definiere die Remote-Sequenz **separat**: `github_create_repo` → `git_set_remote` → `git_push`.
  So verhinderst du, dass der Plan Tools erfindet oder zu früh `git_push` wählt (das war ein Orchestrierungsfehler im Zusammenspiel mit deiner bisherigen Mission) .

## 3.2 Orchestrator-Regeln

In `orchestrator.txt` (Decision & Delegation Policy) zwei harte Gates ergänzen:

* „**Kein** `git_push`, wenn kein Remote gesetzt (prüfe vorher, ob ein Remote existiert/aus SRP-Tool zurückkam).“
* „Nach jedem File-Write/Template-Schritt **immer** erst `git_add_files(["."])`, dann `git_commit` – niemals direkt pushen.“
  Der Orchestrator verlangt schon heute 1:1 Tool-Mapping ohne Tool-Erfindung – das spielen wir mit SRP perfekt aus .

---

# 4) Streamlit-Defaults & Backend

## 4.1 Streamlit Default-YAML verschlanken

Im Tab „Agent System“ in `frontend/streamlit_app.py` die Tool-Allow-Liste des Workers auf SRP setzen (und `create_repository`/kombinierte Tools entfernen):
`git_init_repo, discover_templates, select_template, apply_project_template, git_add_files, git_commit, (optional) github_create_repo, git_set_remote, git_push, file_*`
Die aktuelle Default-Liste enthält noch `create_repository` und lenkt den Agent in den alten Flow – raus damit .

## 4.2 Backend bleibt gleich

* Euer FastAPI-SSE/Chat-Strom ist dafür schon passend; keine Änderung nötig .
* Der Agent-Builder hängt die Tools aus der Allow-Liste korrekt an, inkl. Sub-Agenten – das passt weiter zu SRP (nur Liste anpassen) .

---

# 5) Migrationsplan (inkrementell, risikoarm)

## Phase A – Sofortmaßnahmen (Demo stabilisieren)

1. **Neue SRP-Tools implementieren** (`git_init_repo`, `github_create_repo`, `git_set_remote`).
2. **`create_repository` aus Worker-Allow-Liste entfernen** (nicht löschen – nur nicht default benutzen).
3. **Mission & Orchestrator** wie oben anpassen (explizites `add → commit`, Push nur mit Remote).
4. **Path-Manager dämpfen** (No-Op im Demo-Modus).

**Erwartetes Verhalten:**

* Ohne Token: lokales Repo (kein README-Auto-Commit mehr), Template-Files → `add` → `commit`. **Kein** Push-Versuch.
* Mit Token: `github_create_repo` + `git_set_remote` + `git_push` funktionieren deterministisch.

## Phase B – Aufräumen & Tests

1. **Unit-Tests** für jede SRP-Funktion (Mock von `subprocess.run` und GitHub-API).
2. **E2E-Smoke**: „Create Python FastAPI…“ → prüfe: `repos/<name>`, Commit-Hash, Dateien, (optional) Remote.
3. **Logs vereinfachen**: weniger Rauschen aus dem Guard; klare, kurze Statusmeldungen in SSE/Streamlit.

## Phase C – Optional

* `git_add_all` als Alias anbieten (Qualität des Plans steigt, aber nicht nötig).
* „Remote Demo“ als Checkbox in Streamlit (setzt Tools `github_create_repo` / `git_set_remote` auf die Allow-Liste).

---

# 6) Konkrete Spezifikationen (Kurz-Signaturen)

```text
git_init_repo
  in:  { name: string }
  out: { success: bool, repo_path: str, default_branch: "main", error?: str }

github_create_repo
  in:  { name: string, visibility?: "private"|"public" }
  out: { success: bool, html_url: str, clone_url: str, owner: str, error?: str }

git_set_remote
  in:  { repo_path: string, remote_url: string, name?: "origin" }
  out: { success: bool, message: string, error?: str }
```

Andere bleiben wie sind (`discover_templates`, `select_template`, `apply_project_template`, `git_add_files`, `git_commit`, `git_push`) .

---

# 7) Warum das eure Probleme löst

* **Kein vorzeitiger Push mehr**: Push ist ein eigener Schritt hinter einer klaren Remote-Gate-Bedingung (Remote existiert). Zuvor triggert `create_repository` Push-Logik/Fehler, was den Agent fehlleitet .
* **Explizite Commits**: Nach Template-Schreiben erfolgt immer `add` → `commit`, weil es **Pflicht-Schritte** im Plan sind (Mission/Orchestrator fordern das explizit) .
* **Weniger Moving Parts**: Pfad-Magie raus; der Repo-Pfad kommt aus `git_init_repo` und wird durchgereicht (SRP, deterministisch) .
* **Streamlit ist kohärent**: Default-Allow-Liste zeigt dem Agent exakt die SRP-Werkzeuge – keine Versuchung mehr, Kombi-Tools zu „halluzinieren“ oder zu frühe Pushes zu planen .

