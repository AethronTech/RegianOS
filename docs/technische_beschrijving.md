# Regian OS — Technische Beschrijving

**Versie:** 1.3.0 · **Datum:** 7 maart 2026  
**Status:** Milestone 1.3.0 — Intern document

---

## 1. Overzicht

Regian OS is een Python-applicatie gebouwd op drie lagen:

```
┌─────────────────────────────────────────────────────┐
│  Interface-laag:  Streamlit GUI  │  CLI              │
├─────────────────────────────────────────────────────┤
│  Core-laag:   OrchestratorAgent │ Scheduler │ Log   │
├─────────────────────────────────────────────────────┤
│  Skill-laag:  terminal │ files │ github │ cron │ …  │
└─────────────────────────────────────────────────────┘
```

---

## 2. Technologiestack

| Component | Technologie | Versie |
|---|---|---|
| Runtime | Python | 3.13.3 |
| Web UI | Streamlit | 1.54.0 |
| LLM-integratie | LangChain | – |
| LLM-provider | Google Gemini (standaard) | gemini-2.5-flash |
| Lokale LLM | Ollama (optioneel) | – |
| Taakplanning | APScheduler | – |
| GitHub API | PyGithub | – |
| Env-beheer | python-dotenv | – |
| Tests | pytest + pytest-cov | – |

---

## 3. Directorystructuur

```
RegianOS/
├── main.py                        # CLI-entrypoint
├── build.sh                       # Build/installatiescript
├── requirements.txt               # Python-afhankelijkheden
├── pytest.ini                     # Testconfiguratie
├── .env                           # Configuratie (niet in VCS)
├── regian_action_log.jsonl        # Persistente actie-log
├── docs/
│   ├── handleiding.md             # Gebruikershandleiding
│   ├── functionele_beschrijving.md
│   └── technische_beschrijving.md
├── regian/
│   ├── __init__.py
│   ├── settings.py                # Configuratiebeheer
│   ├── core/
│   │   ├── __init__.py
│   │   ├── agent.py               # SkillRegistry + Orchestrator + RegianAgent
│   │   ├── scheduler.py           # APScheduler-wrapper
│   │   ├── token_log.py           # JSONL token-verbruik logger (REG-2)
│   │   └── action_log.py          # JSONL-logger
│   ├── interface/
│   │   ├── dashboard.py           # Streamlit GUI (~900 regels)
│   │   └── cli.py                 # Commandoregelinterface
│   └── skills/
│       ├── __init__.py
│       ├── terminal.py            # Shell + Python runner
│       ├── files.py               # Bestandsbeheer
│       ├── github.py              # GitHub API
│       ├── cron.py                # Taakplanning skills
│       ├── help.py                # Help skill
        ├── project.py             # Projectbeheer skills
        ├── knowledge.py           # Kennisbank-beheer skills
        ├── backup.py              # Backup & restore skills
        ├── tickets.py             # Kanban ticketsysteem (Milestone 1.1.18)
        └── skills.py              # Skillet meta-skill
└── tests/
    ├── conftest.py                # Fixtures: tmp_root, isolate_env
    ├── test_core_token_log.py     # Token-log tests (23 tests, REG-2)
    ├── test_core_action_log.py    # 26 tests
    ├── test_core_agent.py         # OrchestratorAgent tests
    ├── test_core_scheduler.py     # Scheduler CRUD tests
    ├── test_settings.py
    ├── test_skills_cron.py
    ├── test_skills_files.py
    ├── test_skills_help.py
    ├── test_skills_knowledge.py   # Kennisbank tests (9 tests)
    ├── test_skills_project.py     # Projectbeheer tests
    └── test_skills_terminal.py
```

---

## 4. Core-laag

### 4.1 `regian/core/agent.py`

**SkillRegistry**

Auto-discovery van alle skills via `pkgutil.iter_modules` over `regian/skills/`. Elke publieke functie (niet `_`-prefixed) met de correcte `__module__` wordt omgezet naar een `langchain_core.tools.StructuredTool`. De registry exposeert:
- `tools` — lijst van `StructuredTool`-objecten
- `tool_map` — dict `{naam: tool}`
- `call(name, args)` — directe aanroep via naam + dict
- `call_by_string(name, raw_args)` — aanroep met string-argument (JSON-fallback)
- `list_commands()` — markdown-overzicht
- `reload()` — herlaad skills (wist `sys.modules`-cache)

**OrchestratorAgent**

Koppelt het LLM aan de SkillRegistry via LangChain's tool-calling API:

```
prompt → LLM.bind_tools(registry.tools) → plan (lijst van tool-calls)
                                         → execute_plan() → resultaten
```

- `plan(prompt)` — vraagt het LLM om een gestructureerd plan terug te geven als lijst van `{"tool": ..., "args": {...}}`
- `execute_plan(plan, source, group_id)` — voert het plan stap voor stap uit, logt elke stap via `log_action()`
- Provider-selectie: `gemini` of `ollama` op basis van `.env`

**RegianAgent** (legacy)

Enkel-stap ReAct-agent via LangChain AgentExecutor met `create_tool_calling_agent`. Gebruikt in `OrchestratorAgent.run()` als fallback voor enkelvoudige vragen.

**CONFIRM_REQUIRED**

`functools.lru_cache`-callable die de HITL-skill-set laadt uit `.env`. Cache wordt gewist bij modelwijziging.

**Projectcontext-helpers (Milestone 1.0.5)**

| Functie/Constante | Beschrijving |
|---|---|
| `_TOOLS_BY_TYPE` | Dict: `software/generic → "all"`, `docs/data → beperkte toolset` |
| `_get_project_context()` | Leest het `.regian_project.json`-manifest van het actieve project |
| `_project_context_block(ctx)` | Formatteert manifestdata als compacte tekst voor de systeemprompt |
| `_build_agent_prompt()` | Bouwt de dynamische systeemprompt met projectcontext |
| `SkillRegistry.tools_for_project(type, allowed_tools)` | Gefilterde toollijst: als `allowed_tools` niet leeg, worden enkel die modules gebruikt; anders type-gebaseerde filtering via `_TOOLS_BY_TYPE` |

De `OrchestratorAgent.plan()` injecteert zowel `_project_context_block()` als de gefilterde toolcatalogus in `PLANNER_PROMPT`. `RegianAgent.ask()` gebruikt `_build_agent_prompt()` bij elke aanroep. `allowed_tools` wordt gelezen uit `ctx.get("allowed_tools")` en doorgegeven aan `tools_for_project()` en `_tool_catalog()`.

### 4.2 `regian/core/scheduler.py`

APScheduler-wrapper met persistente opslag van jobdefinities. De bestandsnaam wordt dynamisch bepaald via `_get_jobs_file()` → `settings.get_jobs_file_name()` (standaard `regian_jobs.json`).

**Functies:**

| Functie | Beschrijving |
|---|---|
| `get_scheduler()` | Retourneert de singleton `BackgroundScheduler` (gestart bij eerste aanroep) |
| `add_scheduled_job(job_id, task, job_type, schedule, description)` | Voegt toe en persisteert |
| `remove_scheduled_job(job_id)` | Verwijdert uit APScheduler en persisteert |
| `toggle_scheduled_job(job_id, enabled)` | Pauzeert of hervat |
| `get_all_jobs()` | Laadt `regian_jobs.json` |
| `get_next_run(job_id)` | Geeft de volgende geplande run als string |
| `run_job_now_by_id(job_id)` | Voert taak onmiddellijk uit |
| `parse_schedule(schedule_str)` | Parseert vrije-taal schema naar APScheduler-kwargs |

**Job-uitvoering** roept `log_action()` aan na elke run met `source="cron"`, en schrijft `last_run`, `last_status`, `last_output` terug naar `regian_jobs.json`.

**Schema-parsing** ondersteunt:
- `elke N minuten/uur/uren` → `trigger="interval"`
- `dagelijks om HH:MM` → `trigger="cron"`
- `elke [dag] om HH:MM` → `trigger="cron"`
- `werkdagen om HH:MM` → `trigger="cron", day_of_week="mon-fri"`
- Standaard cron-expressies (`* * * * *`) → `trigger="cron"`

### 4.3 `regian/core/action_log.py`

Persistente JSONL-logger met thread-veilige schrijfoperaties. De bestandsnaam wordt dynamisch bepaald via `_get_log_file()` → `settings.get_log_file_name()` (standaard `regian_action_log.jsonl`). De maximale grootte en tekens per resultaat worden gelezen via `_get_max_entries()` en `_get_result_max_chars()` uit `settings`.

**Testpatching**: tests patchen `_get_log_file` via `monkeypatch.setattr(al, "_get_log_file", lambda: tmp_path / "test.jsonl")`.

**Dataformaat** per entry:

```json
{
  "ts": "2026-03-01T14:23:11",
  "source": "chat",
  "tool": "run_shell",
  "args": {"command": "git pull"},
  "result": "Already up to date.",
  "group_id": "a3f7b2c1"
}
```

**Functies:**

| Functie | Beschrijving |
|---|---|
| `log_action(tool, args, result, source, group_id)` | Voegt entry toe, triggert `_trim()` |
| `get_log(limit)` | Retourneert entries nieuwste-eerst |
| `get_log_grouped(limit_groups)` | Groepeert op `group_id`, retourneert structuur met prompt + stappen |
| `clear_log()` | Wist logbestand |
| `log_count()` | Telt entries |
| `_trim()` | Behoudt maximaal `LOG_MAX_ENTRIES` regels (nieuwste), leest via `settings` |

**Group-ID flow**: bij elke chatopdracht genereert `dashboard.py` een `uuid4[:8]`. De `__prompt__`-entry registreert de originele tekst; alle tool-calls krijgen dezelfde `group_id`. `get_log_grouped()` reconstrueert de koppeling.

---

## 5. Skill-laag

### 5.1 Auto-discovery

Bij import van `regian.core.agent` scant `SkillRegistry._discover()` alle modules in `regian/skills/` via `pkgutil.iter_modules`. Elke publieke functie met docstring wordt:
1. Opgeslagen in `_functions: dict[str, callable]`
2. Omgezet naar `StructuredTool.from_function()` en opgeslagen in `_tools: list`

Dit maakt het toevoegen van een nieuwe skill zo eenvoudig als het aanmaken van een nieuw `.py`-bestand — geen registratie of configuratie vereist.

### 5.2 `terminal.py` — Beveiliging

**Path-resolution** (`_resolve_cwd`):
- Lege `cwd` → `REGIAN_ROOT_DIR`
- Relatief pad → `REGIAN_ROOT_DIR / cwd` (`.resolve()`)
- Detecteert path-traversal: als `target.relative_to(root)` faalt → `ValueError`

**HITL-detectie** (`is_destructive_shell_command`):
- Laadt patronen via `get_dangerous_patterns()` bij elke aanroep (cache via `.env`)
- `re.search(pat, command.lower())` over alle patronen

### 5.3 `github.py`

Alle functies maken gebruik van `PyGithub`. Authenticatie via `GITHUB_TOKEN`. `commit_and_push` leest het bestand lokaal uit `REGIAN_ROOT_DIR` en pusht via de GitHub Contents API (create of update op basis van bestaande SHA).

---

## 6. Interface-laag

### 6.1 `dashboard.py` (Streamlit GUI)

**Architectuur:**

```
start_gui()
  ├── _inject_global_styles()   # MutationObserver: ChatGPT → Gemini
  ├── _start_scheduler()         # APScheduler éénmalig starten
  ├── Tabs [Chat | Help | Cron | Log | Instellingen]
  │   ├── tab_chat
  │   │   ├── _inject_autocomplete()   # JS: slash-command dropdown
  │   │   ├── HITL-flow (pending_plan)
  │   │   └── Normale chat-flow (st.chat_input accept_file="multiple")
  │   ├── tab_help  [Commands | Documentatie | Handleiding]
  │   ├── tab_cron
  │   ├── tab_log   [Chronologisch | Per opdracht]
  │   └── tab_settings
  └── get_agent() / get_orchestrator()   # @st.cache_resource
```

**Bestandsupload** via `st.chat_input(accept_file="multiple", file_type=[...])`:
- Retourneert `ChatInputValue` met `.text` (getypte tekst) en `.files` (lijst van `UploadedFile`)
- `_read_uploaded_file(f)` extraheert de inhoud: UTF-8 decode voor tekstbestanden, `pypdf.PdfReader` voor PDF's
- Bestandsinhoud wordt als `--- Bijlage: naam ---\n<inhoud>\n---`-blokken vóór de getypte tekst in de effectieve prompt geplakt
- De chatgeschiedenis toont alleen de getypte tekst + 📎 bestandsnaam(en) — niet de volledige inhoud
- Bij slash-commands (prompt begint met `/`) worden bijlagen genegeerd met een waarschuwing

**State management** via `st.session_state`:
- `messages`: chatgeschiedenis (lijst van `{role, content, badge}`)
- `pending_plan`: HITL-plan wachtend op bevestiging
- `pending_group_id`: `group_id` voor het gepauzeerde plan
- `provider`, `model`: actieve LLM-instellingen
- `active_project`: naam van het actieve project (initieel via `get_active_project()`)

**Caching** via `@st.cache_resource`:
- `get_agent(provider, model, active_project)` → singleton `RegianAgent` per combinatie
- `get_orchestrator(active_project)` → singleton `OrchestratorAgent` per project
- Beide caches worden gewist bij modelwijziging én projectwisseling

**Projectselector (Milestone 1.0.5)**

Bovenaan de zijbalk staat een selectbox met alle beschikbare projecten (geladen via `_load_project_list()`) plus de optie `(geen project)`. Bij selectie:
1. `set_active_project(name)` schrijft naar `.env` + `os.environ`
2. `activate_project(name)` uit `project.py` werkt het manifest bij
3. `get_agent.clear()` + `get_orchestrator.clear()` wissen de caches
4. `st.rerun()` herlaadt de sessie met de nieuwe context

`_TYPE_ICONS_SIDEBAR = {"software": "💻", "docs": "📄", "data": "📊", "generic": "📁"}` bepaalt het icoon in de projectbadge.

**JavaScript-injecties:**

| Functie | Doel |
|---|---|
| `_inject_global_styles()` | MutationObserver: vervangt "Ask ChatGPT" door "Ask Gemini" in foutdialogen |
| `_inject_autocomplete()` | Slash-command autocomplete dropdown + signature hint in chatinput |

### 6.2 `cli.py` (CLI)

Twee modi aangestuurd via `argparse`:

```bash
python main.py run /skill_naam argument    # directe uitvoering
python main.py chat                        # interactieve chat-loop
```

Beide modi loggen via `log_action()` met respectievelijk `source="direct"` en `source="cli"`. Chat-modus genereert een `group_id` per invoer en geeft deze door aan `execute_plan()`.

---

## 7. Configuratie (`regian/settings.py`)

Alle configuratie wordt opgeslagen in `.env` via `python-dotenv`. De module biedt getters en setters per instelling:

| Sleutel | Getter/Setter | Standaard |
|---|---|---|
| `REGIAN_ROOT_DIR` | `get/set_root_dir` | `~/RegianWorkspace` |
| `LLM_PROVIDER` | `get/set_llm_provider` | `gemini` |
| `LLM_MODEL` | `get/set_llm_model` | `gemini-2.5-flash` |
| `GEMINI_MODELS` | `get/set_gemini_models` | 4 modellen (kommalijst) |
| `OLLAMA_MODELS` | `get/set_ollama_models` | 4 modellen (kommalijst) |
| `CONFIRM_REQUIRED` | `get/set_confirm_required` | `repo_delete,delete_file,delete_directory` |
| `DANGEROUS_PATTERNS` | `get/set_dangerous_patterns` | 16 defaults (JSON) |
| `USER_AVATAR` | `get/set_user_avatar` | `🧑` |
| `SHELL_TIMEOUT` | `get/set_shell_timeout` | `30` (seconden) |
| `AGENT_MAX_ITERATIONS` | `get/set_agent_max_iterations` | `5` |
| `LOG_MAX_ENTRIES` | `get/set_log_max_entries` | `500` |
| `LOG_RESULT_MAX_CHARS` | `get/set_log_result_max_chars` | `300` |
| `LOG_FILE_NAME` | `get/set_log_file_name` | `regian_action_log.jsonl` |
| `JOBS_FILE_NAME` | `get/set_jobs_file_name` | `regian_jobs.json` |
| `BACKUP_MAX_COUNT` | `get/set_backup_max_count` | `5` |
| `BACKUP_DIR` | `get/set_backup_dir` | `RegianBackups/` naast werkmap |
| `GITHUB_TOKEN` | direct via `os.getenv` | – |
| `GOOGLE_API_KEY` | direct via `os.getenv` | – |
| `ACTIVE_PROJECT` | `get/set_active_project`, `clear_active_project` | `""` |
| `AGENT_NAME` | `get/set_agent_name` | `Reggy` |

Setters gebruiken `dotenv.set_key()` voor persistentie én `os.environ[...]` voor onmiddellijk effect in de lopende sessie.

---

## 8. Testarchitectuur

### 8.1 Fixtures (`tests/conftest.py`)

| Fixture | Scope | Beschrijving |
|---|---|---|
| `tmp_root` | function | Tijdelijke werkmap per test |
| `isolate_env` | function, autouse | Omgevingsvariabelen geïsoleerd via `monkeypatch` |
| `tmp_env_file` | function | Tijdelijk `.env`-bestand per test |

### 8.2 Dekking op Milestone 1.0.10

| Module | Dekking |
|---|---|
| `core/action_log.py` | ~90% |
| `core/agent.py` | ~79% |
| `core/scheduler.py` | ~62% |
| `settings.py` | ~90% |
| `skills/project.py` | ~95% |
| `skills/knowledge.py` | ~85% |
| `skills/backup.py` | ~87% |
| `skills/files.py` | ~87% |
| `skills/tickets.py` | ~67% |
| `skills/*.py` (overige) | ~80–93% |
| **Totaal** | **≥80%** |

457 tests, allemaal passend. Drempel: `--cov-fail-under=80`. Uitvoeren:

```bash
pytest --cov=regian --cov-report=html
```

HTML-rapport beschikbaar in `htmlcov/index.html`.

---

## 9. Persistentiemechanismen (Milestone 1.0.10)

### 9.1 Chatgeschiedenis

Geïmplementeerd via module-level helpers in `regian/interface/dashboard.py`:

| Functie | Beschrijving |
|---|---|
| `_chat_file() → Path` | Geeft het pad terug (`<project>/.regian_chat.json` of `<root>/.regian_chat.json`) |
| `_load_chat_history() → list` | Leest de JSON-array van schijf; geeft `[]` bij ontbrekend/corrupt bestand |
| `_save_chat_history(messages)` | Schrijft de volledige lijst als ingedente JSON (UTF-8) |
| `_append_msg(role, content, badge)` | Voegt toe aan `st.session_state.messages` én slaat direct op |

Chat-init bij sessiestart: `st.session_state.messages = _load_chat_history()`.

### 9.2 Upload-opslag

Elk ge-upload bestand (via `st.chat_input(accept_file=...)`) wordt gesynchroniseerd opgeslagen via `_save_uploaded_file(uf) → Path`:

- Bestemmingsmap: `<project>/uploads/` of `<root>/uploads/`
- Bestandsinhoud: `uf.getvalue()` (bytes) → `dest.write_bytes()`
- Inline context: tegelijk als platte tekst in de effectieve LLM-prompt

### 9.3 Kennisbank

Kennisbestanden worden bewaard in `<project>/.regian_knowledge/` (of `<root>/.regian_knowledge/`).

**Context-injectie in `dashboard.py`:**

```python
_kb_ctx = _load_knowledge_context()  # max 8 000 tekens
if _kb_ctx:
    effective_prompt = _kb_ctx + effective_prompt
```

`_load_knowledge_context()` leest alle bestanden gesorteerd op naam, beperkt het totaal tot 8 000 tekens en formatteert elk bestand als:

```
--- Kennisbank: bestand.md ---
<inhoud>
---
```

**Skills-module `regian/skills/knowledge.py`** implementeert vier publieke functies die de kennismap beheren via dezelfde locatielogica.

### 9.4 Resultaten automatisch opslaan

Na elke LLM-respons (plan-uitvoer of directe `run()` respons) roept het dashboard `_save_result(content)` aan:

```python
def _save_result(content: str) -> Path:
    rdir = _results_dir()   # <project>/results/ of <root>/results/
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dest = rdir / f"{ts}_resultaat.md"
    dest.write_text(content, encoding="utf-8")
    return dest
```

Na opslaan toont het dashboard `st.caption(f"💾 Opgeslagen als results/{_saved_path.name}")`. Slash-commands en HITL-annuleringen worden **niet** opgeslagen.

### 9.5 Configureerbare agent-naam

De `AGENT_NAME` env-variabele (getter/setter in `settings.py`) bepaalt de weergavenaam van de agent in de chat. In `dashboard.py` wordt `_agent_name = get_agent_name()` eenmalig per rendering-cyclus opgeroepen en gebruikt als eerste argument van `st.chat_message(_agent_name, avatar="🤖")`. Streamlit toont deze naam als label boven de agent-berichten.

---

## 10. Beveiligingsmodel

| Bedreiging | Maatregel |
|---|---|
| Destructieve shell-commando's | HITL via regex-matching op `DANGEROUS_PATTERNS` |
| Onverwachte skill-aanroepen | HITL-lijst per skill configureerbaar |
| Path-traversal buiten werkmap | `target.relative_to(root)` in `_resolve_cwd` |
| Ongeautoriseerde GitHub-acties | `repo_delete` standaard in HITL-lijst |
| API-sleutels in code | Exclusief via `.env` (niet in VCS) |

---

## 11. Uitbreidbaarheid

### Nieuwe skill toevoegen

```python
# regian/skills/mijn_skill.py
def mijn_functie(param: str) -> str:
    """Beschrijving die het LLM als instructie gebruikt."""
    return f"Resultaat: {param}"
```

Na opstart automatisch beschikbaar als `/mijn_functie` en als LLM-tool.

### Nieuwe LLM-provider toevoegen

In `agent.py`, methode `_build_llm()`:

```python
elif provider == "nieuwe_provider":
    return MijnLLM(model=model, api_key=os.getenv("MIJN_API_KEY"))
```

---

## 13. Workflow-engine (Milestone 1.1.18)

### 13.1 Architectuur

```
regian/core/workflow.py        ← engine, state, fase-uitvoering
regian/skills/workflow.py      ← publieke slash-commands
regian/workflows/*.json        ← ingebouwde templates
<project>/.regian_workflow/    ← projectspecifieke templates
<project>/.regian_workflow_state/ ← run-state (JSON)
```

### 13.2 WorkflowRun dataklasse

```python
@dataclass
class WorkflowRun:
    run_id:               str       # 8-karakter UUID-prefix
    workflow_id:          str       # template-ID
    workflow_name:        str
    started_at:           str       # ISO 8601
    updated_at:           str
    status:               str       # running | waiting | done | cancelled | error
    current_phase_index:  int
    artifacts:            dict      # output_key → waarde
    phase_log:            list      # logboek per fase
    input:                str       # originele gebruikersinvoer
    project_path:         str
```

### 13.3 Fase-uitvoering

De `execute_phase(run, phase)` functie dispatcht op `phase["type"]`:

| Type | Handler | Output |
|---|---|---|
| `llm_prompt` | `_run_llm_prompt()` | LLM-response string |
| `task_loop` | `_run_task_loop()` | Geaggregeerde taakresultaten |
| `human_checkpoint` | direct | Prompt-tekst, `needs_approval=True` |
| `tool_chain` | `_run_tool_chain()` | Geconcateneerde tool-resultaten |

### 13.4 _advance-loop

De interne `_advance(run, template)` functie itereert over de fasen:

```
while current_phase_index < len(phases):
    output, needs_approval = execute_phase(run, phase)
    if needs_approval:
        run.status = STATUS_WAITING
        save_run(run)
        return run   ← pauze
    current_phase_index += 1
run.status = STATUS_DONE
```

### 13.5 Template-substitutie

`_render_template(template, artifacts)` vervangt `{{sleutel}}`-patronen met waarden uit het `artifacts`-dict. Onbekende placeholders blijven ongewijzigd.

### 13.6 BPMN-mapping

| BPMN-element | Fase-type |
|---|---|
| `serviceTask` | `llm_prompt` |
| `userTask` | `human_checkpoint` |
| `scriptTask` | `tool_chain` |
| `callActivity` | `task_loop` |

Import loopt via `xml.etree.ElementTree`; sequence flows bepalen de fase-volgorde. Export genereert valide BPMN 2.0 XML met DI-annotaties voor bpmn.io.

---

## 14. Ticket-systeem (Milestone 1.1.18)

### 14.1 Module `regian/skills/tickets.py`

Kanban-gebaseerde bugtracker per project. Tickets worden opgeslagen als JSON-array in `<project>/.regian_tickets.json`.

**Datastructuur per ticket:**
```json
{
  "id": "a1b2c3d4",
  "title": "...",
  "description": "...",
  "status": "todo|in_progress|review|done",
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "ai_output": "...",
  "comments": [{"text": "...", "at": "...", "from": "user|ai"}]
}
```

**Publieke functies (slash-commands + LLM-tools):**

| Functie | Beschrijving |
|---|---|
| `create_ticket(title, description)` | Nieuw ticket aanmaken in To Do |
| `list_tickets(status)` | Tickets tonen, optioneel gefilterd |
| `move_ticket(id, status, comment)` | Ticket verplaatsen, optioneel met opmerking |
| `delete_ticket(id)` | Ticket permanent verwijderen |
| `fix_ticket(id)` | AI-agent lost ticket op: `todo → in_progress → review` |
| `fix_all_tickets()` | Alle To Do-tickets sequentieel laten fixen |

**Integratie:** `fix_ticket()` importeert `OrchestratorAgent` lazy (uit `regian.core.agent`) om circulaire imports te vermijden. De agent bouwt een taakomschrijving op basis van `title`, `description` en de laatste `comment`. Aanvullend leest `fix_ticket()` **tot 30 bronbestanden** uit het actieve projectpad (extensies: `.py`, `.js`, `.ts`, `.jsx`, `.tsx`, `.html`, `.css`, `.json`, `.md`, `.sh`; max. 40 KB per bestand) en voegt die als volledige broncode toe aan de agent-context — zodat de agent bestaande bestanden kan analyseren en patches op de correcte locaties kan schrijven. Mappen als `node_modules`, `.git`, `__pycache__`, `dist` en `build` worden genegeerd. De eerste 2000 tekens van de uitvoer worden opgeslagen als `ai_output`.

### 14.2 Dashboard: `🐛 Tickets`-tab

Visueel Kanban-board met 4 kolommen in het workflow-scherm. Knop **🤖 Fix alle** triggert `fix_all_tickets()` met `st.spinner`.

In de **👀 Review**-kolom toont elk ticket:
- **🤖 AI samenvatting** — `_tkt["ai_output"]`, ingeklapt via `st.expander`
- **📋 Agent log (N stappen)** — haalt via `get_log_grouped()` de stappen op die horen bij de `group_id = ticket["id"]`; toont per stap: tool-naam, argumenten (preview 120 tekens per waarde) en resultaat (max. 400 tekens); ✅/❌ icoon op basis van resultaat

### 14.3 Dashboard: `▶️ Project uitvoeren`-tab

Detecteert build/run-scripts in het actieve projectpad en biedt:
- Synchrone uitvoering (build, test, make) met `subprocess.run(timeout=120)`
- **Live-server modus** (npm dev, npm start, python main.py): server beheer volledig vanuit Regian:
  - `subprocess.Popen(..., shell=True, stdout=logf, stderr=logf)` start de server als achtergrondproces
  - PID opgeslagen in `st.session_state[f"srv_pid_{project}_{cmd}"]`
  - Liveness-controle via `os.kill(pid, 0)` bij elke rendering-cyclus
  - Stop via `os.kill(pid, signal.SIGTERM)`
  - Serveruitvoer weggeschreven naar `<project>/.regian_server.log`
  - Logviewer: laatste 200 regels via `splitlines()[-200:]`, auto-uitklapt terwijl server actief is
  - Poortdetectie: regex `r"-p\s+(\d+)|--port[= ](\d+)|:(\d{4,5})"` op de script-body in `package.json`; fallback 5173/3000/8080
  - Server-link naar `http://127.0.0.1:<poort>` (IPv6-safe)
- Fallback: AI genereert een `build.sh` via `OrchestratorAgent`

---

## 15. Token-verbruik module (REG-2, Milestone 1.3.0+)

### 15.1 Opslag

Elke LLM-aanroep wordt opgeslagen in `regian_token_log.jsonl` (projectroot, naast `regian_action_log.jsonl`). De drie call-sites zijn:

| Call-site | `call_type` | Klasse |
|---|---|---|
| `OrchestratorAgent.plan()` | `"plan"` | Plan-generatie (JSON stappenlijst) |
| `OrchestratorAgent.run()` | `"run"` | Directe LLM-antwoorden (geen tools) |
| `RegianAgent.ask()` | `"agent"` | Tool-selectie + antwoorden in agent-loop |

JSON-structuur per entry (bijgewerkt formaat):

```json
{
  "ts":            "2026-03-07T10:00:00",
  "provider":      "gemini",
  "model":         "gemini-2.5-flash",
  "project":       "mijn-app",
  "prompt":        "Maak een README aan",
  "call_type":     "plan",
  "input_tokens":  1234,
  "output_tokens":  567,
  "total_tokens":  1801,
  "cost_eur":      0.00045
}
```

Het `prompt`-veld bevat de eerste 500 tekens van de gebruikersopdracht. Lege string als de opdracht leeg was of als het een geautomatiseerde achtergrondaanroep betreft.

### 15.2 Token-extractie

`_extract_tokens(response)` ondersteunt drie response-formaten:
1. `response.usage_metadata` als `dict` (LangChain generiek)
2. `response.usage_metadata` als object met attributen
3. `response.response_metadata["usage_metadata"]` (Gemini-specifiek fallback)

Bij geen metadata: `(0, 0)`.

### 15.3 Pricing-tabel (datumreeksen)

Prijzen (EUR per 1 000 000 tokens) zijn geconfigureerd in `_DEFAULT_PRICING` met ondersteuning voor datumreeksen. Meerdere periodes per model zijn mogelijk:

```python
_DEFAULT_PRICING = {
    "gemini-2.5-flash": [
        {"from": "2025-01-01", "to": None, "input": 0.075, "output": 0.30}
    ],
}
```

`_calc_cost(model, input_tokens, output_tokens, date=None)`:
- `date` standaard = vandaag (JJJJ-MM-DD string)
- Vindt entry waar `from <= date <= to` (of `to is None`)
- Bij meerdere overeenkomsten: de entry met de meest recente `from`-datum
- **Backward compat**: oud formaat `{model: {"input": x, "output": y}}` werkt nog steeds
- Prefix-match: `gemini-2.5-flash-001` matched op `gemini-2.5-flash`
- Ollama-modellen zijn altijd 0,00 €

### 15.4 Aggregatie-functies

| Functie | Beschrijving |
|---|---|
| `get_summary_by_model()` | Per provider/model, gesorteerd op kostprijs aflopend |
| `get_summary_by_project()` | Per project, gesorteerd op kostprijs |
| `get_monthly_evolution()` | Per maand (JJJJ-MM), chronologisch |
| `get_daily_evolution()` | Per dag (JJJJ-MM-DD), chronologisch |
| `get_summary_by_prompt()` | Per unieke opdracht (eerste 200 tekens als key), kost aflopend |
| `get_totals()` | Globale totalen |

`get_summary_by_prompt()` groepeert lege prompts onder `"(geen opdracht)"`.

### 15.5 Configuratie (.env)

| Variabele | Standaard | Beschrijving |
|---|---|---|
| `TOKEN_LOG_FILE` | `regian_token_log.jsonl` | Bestandsnaam van het logbestand |
| `TOKEN_PRICING` | _(ingebouwde tabel)_ | JSON-string met datumreeks-prijzen per model |

### 15.6 Thread-safety

Schrijven naar het logbestand verloopt via `threading.Lock()` (`_lock`), identiek aan `action_log.py`.

---

## 12. Bekende beperkingen (Milestone 1)

| Beperking | Beschrijving |
|---|---|
| Geen authenticatie | De Streamlit-app heeft geen loginscherm; bedoeld voor lokaal gebruik |
| Enkelvoudige gebruiker | Geen multi-user ondersteuning |
| Log-retentie | Configureerbaar via UI (`LOG_MAX_ENTRIES`); geen archivering |
| Geen HTTPS | Standaard Streamlit-poort op localhost, geen TLS |

---

*Regian OS — Milestone 1.3.1 · Intern document · 2026*

