# Regian OS — Functionele Beschrijving

**Versie:** 1.3.0 · **Datum:** 7 maart 2026  
**Status:** Milestone 1.3.0 — Intern document

---

## 1. Doelstelling

Regian OS is een persoonlijk AI-operationeel systeem dat een technische gebruiker in staat stelt om taken op zijn werkstation en GitHub-omgeving te automatiseren en besturen via een conversationele interface. De kern van het systeem is een **LLM-gestuurde orchestrator** die taalopdrachten vertaalt naar gestructureerde tool-aanroepen, gecombineerd met een **grafische cockpit** (Streamlit) en een **commandoregelinterface** (CLI).

Het systeem is ontworpen als een **extensibel platform**: nieuwe functionaliteiten worden toegevoegd als skill-modules zonder aanpassing van de kern.

---

## 2. Functioneel Domein

### 2.1 Doelgebruiker

Een technische eindgebruiker (ontwikkelaar, devops, maker) die:
- regelmatig repetitieve taken uitvoert op bestandsniveau en GitHub
- een lage drempel wil voor automatisering (geen scripts schrijven)
- volledige transparantie en controle wil behouden over wat er uitgevoerd wordt

### 2.2 Context

- Lokale macOS/Linux-omgeving
- Persoonlijk GitHub-account
- Lokale werkmap (`RegianWorkspace`) als werkomgeving voor bestanden
- Optioneel lokale LLM via Ollama (offline gebruik)

---

## 3. Functies

### 3.1 Conversationele taakaansturing (Chat)

De gebruiker formuleert opdrachten in natuurlijke taal. Het systeem analyseert de opdracht, bouwt een **stappenplan** en voert dit uit. Voorbeeldopdrachten:

- *"Maak een GitHub-repo aan met de naam 'test-project' en voeg een README toe"*
- *"Lees alle .txt bestanden in de map notities en maak een samenvatting"*
- *"Voer git pull uit in elk project in de werkmap"*

Kenmerken:
- Meerstappe uitvoering (één prompt → meerdere acties)
- Tussentijdse bevestiging bij risicovolle acties (HITL)
- Persistente chatgeschiedenis binnen de sessie
- **Bestandsupload**: via het paperclip-icoon kunnen tekstbestanden, code en PDF's bijgevoegd worden; de inhoud wordt als context aan de LLM-prompt toegevoegd

### 3.2 Directe command-aansturing (Slash Commands)

Voor snelle, precieze acties zonder LLM-tussenkomst. Syntax: `/skill_naam argument`. Autocomplete-dropdown in de chatinput laat alle beschikbare commando's zien.

Kenmerken:
- Geen vertaalstap via LLM → deterministisch en snel
- JSON-argumenten of enkelvoudige string
- Ondersteuning voor alle geregistreerde skills

### 3.3 Bestandsbeheer

Lezen, schrijven, verplaatsen, kopiëren en verwijderen van bestanden en mappen binnen de werkmap. Alle paden worden opgelost relatief aan de geconfigureerde `REGIAN_ROOT_DIR`. Path-traversal buiten de werkmap wordt geblokkeerd.

Beschikbare operaties: `write_file`, `read_file`, `list_directory`, `create_directory`, `delete_file`, `delete_directory`, `move_file`, `copy_file`.

### 3.4 Shell- en Python-uitvoering

Willekeurige shell-commando's en Python-code-snippets worden uitgevoerd in de geconfigureerde werkmap, met een timeout van 30 seconden. Destructieve commando's (bijv. `rm`, `sudo`, `shutdown`) triggeren het HITL-mechanisme.

### 3.5 GitHub-integratie

Volledige beheercyclus van GitHub-repositories vanuit de cockpit:
- Repositories aanmaken, openen, verwijderen
- Bestanden committen en pushen
- Issues aanmaken en bekijken
- Branches aanmaken
- Pull requests openen

Authenticatie via persoonlijk `GITHUB_TOKEN` in `.env`.

### 3.6 Taakplanning (Cron)

Periodieke automatisering van drie typen taken:
- **Command**: directe skill-aanroep (`/repo_list`)
- **Shell**: shell-commando (`git pull`)
- **AI-prompt**: LLM-gestuurde taakreeks

Schemaformaten: vrije taal (`dagelijks om 09:00`, `elke 15 minuten`, `werkdagen om 07:30`) en standaard cron-expressies. Taken worden beheerd via een grafisch formulier of slash-commands.

### 3.7 Actie-logging

Elke uitgevoerde tool-aanroep wordt bijgehouden in een persistent JSONL-logbestand (`regian_action_log.jsonl`). De log is raadpleegbaar via de cockpit in twee weergavemodi:

- **Chronologisch**: tijdlijn van alle acties, filterbaar op bron (chat/cron/cli/direct) en skill-naam
- **Per opdracht**: gegroepeerde weergave waarbij alle stappen van één chatopdracht samen worden getoond met de originele prompt als header

### 3.8 Configuratiebeheer

Alle instellingen zijn aanpasbaar via de ⚙️-tab en worden persistent opgeslagen in `.env`:
- Werkmap (`REGIAN_ROOT_DIR`)
- LLM-provider en -model (incl. bewerkbare modellijsten per provider)
- HITL-skills (welke acties bevestiging vereisen)
- Gebruikers-avatar (emoji)
- Destructieve shell-patronen (regex)
- Shell-timeout in seconden (`SHELL_TIMEOUT`, standaard 30)
- Agent max. iteraties (`AGENT_MAX_ITERATIONS`, standaard 5)
- Max. log-entries (`LOG_MAX_ENTRIES`, standaard 500)
- Max. tekens per log-resultaat (`LOG_RESULT_MAX_CHARS`, standaard 300)
- Naam van het actie-logbestand (`LOG_FILE_NAME`, standaard `regian_action_log.jsonl`)
- Naam van het jobs-bestand (`JOBS_FILE_NAME`, standaard `regian_jobs.json`)
- Backup-instellingen: max. te bewaren backups (`BACKUP_MAX_COUNT`, standaard 5) en backup-map (`BACKUP_DIR`, standaard `RegianBackups/` naast de werkmap)

### 3.9 HITL — Human-in-the-Loop

Veiligheidsmechanisme dat risicovolle acties onderschept vóór uitvoering:
- Geactiveerd op basis van twee criteria: de skill staat op de HITL-lijst, of het shell-commando matcht een destructief patroon
- Toont een overzicht van alle geplande stappen met kleurmarkering (🟢 veilig / 🔴 risico)
- Gebruiker bevestigt of annuleert het volledige plan

### 3.10 Projectbeheer

Project-gebaseerde werkcontext zodat het LLM en de tools afgestemd worden op het actieve project.

**Fase 1 — Project-skills (`regian/skills/project.py`)**  
Zes publieke skills beheren de levenscyclus van projecten:
- `create_project` — maakt een projectmap met type-specifieke submappen en een `.regian_project.json`-manifest
- `activate_project` — activeert een project (schrijft `ACTIVE_PROJECT` naar `.env`)
- `deactivate_project` — wist de actieve projectcontext
- `get_project_info` — leest het manifest van een project (leeg = actief project)
- `list_projects` — scant de werkmap voor alle projectmappen met manifest
- `rename_project` — hernoemt een project: mapnaam, manifest-velden (`name` + `path`) en eventueel `ACTIVE_PROJECT` worden bijgewerkt; `project_path`-velden in workflow run-states worden gecorrigeerd

**Fase 2 — Contextbewuste agent (`regian/core/agent.py`)**  
Bij een actief project wordt de systeemprompt van het LLM dynamisch opgebouwd met:
- Projectnaam, type en beschrijving
- **Bestandspad-instructie**: de agent wordt expliciet geïnstrueerd om bestanden altijd binnen het projectpad aan te maken; voor software-projecten (python, node, typescript, react, web, …) wordt de `src/`-submap aanbevolen
- Gefilterde toolset op basis van projecttype: bij `docs`- en `data`-projecten zijn GitHub-skills verborgen

**Fase 3 — Profielkiezer in dashboard (`regian/interface/dashboard.py`)**  
Een projectselector in de linkerzijbalk laat de gebruiker visueel wisselen tussen projecten. Het actieve project wordt getoond als badge met type-icoon. Bij wisseling worden de agent- en orchestratorcaches gewist en herstart Streamlit de sessie.

**Manifest-formaat** per project (`<project_dir>/.regian_project.json`):

```json
{
  "name": "mijn-app",
  "type": "software",
  "path": "/Users/.../RegianWorkspace/mijn-app",
  "git_repo": "",
  "description": "Mijn eerste project",
  "created_at": "2026-03-01T12:00:00",
  "active": true,
  "allowed_tools": []
}
```

Het veld `allowed_tools` is een optionele lijst van skill-modulenamen. Als de lijst niet leeg is, overschrijft die de standaard type-gebaseerde filtering; de agent heeft dan enkel toegang tot de gespecificeerde modules.

### 3.11 Persistente chatgeschiedenis

De chatgeschiedenis van de gebruiker wordt **automatisch bewaard op schijf** en herladen bij elke sessiestart.

- Opslaglocatie: `<project_dir>/.regian_chat.json` (per project) of `<root>/.regian_chat.json` (globaal)
- Formaat: JSON-array van `{"role": "user"|"assistant", "content": "..."}` entries
- Wisselen van actief project laadt de bijbehorende chatgeschiedenis
- "🗑️ Reset Chat" wist zowel de sessiestate als het JSON-bestand op schijf

### 3.12 Automatisch bewaren van uploadbestanden

Bestanden die worden bijgevoegd via de chat-upload worden **automatisch opgeslagen** in de `uploads/`-map van het actieve project (of in `<root>/uploads/` als er geen actief project is).

- Het opgeslagen bestand is daarna bereikbaar via normale file-skills
- De inhoud wordt tegelijk als inline context meegegeven aan de LLM-prompt
- De uploads-map kan geraadpleegd worden via `/list_directory uploads`

### 3.13 Kennisbank — persistent LLM-context

Een projectgebonden kennisbank (`<project_dir>/.regian_knowledge/`) bevat documenten die automatisch als achtergrondcontext worden meegegeven bij elke LLM-chatprompt.

**Vier skills** (`regian/skills/knowledge.py`):
- `add_to_knowledge(path)` — kopieert een bestand uit de werkmap naar de kennisbank
- `list_knowledge()` — toont alle kennisbestanden met bestandsgrootte
- `remove_from_knowledge(name)` — verwijdert één bestand
- `clear_knowledge()` — verwijdert de volledige kennisbank

**Context-injectie (dashboard):** Elke keer dat een gebruiker een prompt verstuurt, laadt `_load_knowledge_context()` alle kennisbestanden (max 8 000 tekens) en plaatst die vóór de gebruikersprompt. Zo heeft het LLM altijd projectdocumenten beschikbaar zonder dat de gebruiker er expliciet naar moet verwijzen.

**Sidebar-widget:** De linkerzijbalk toont automatisch een overzicht van de kennisbestanden (naam + grootte).

### 3.14 Configureerbare chat-agentnaam (`AGENT_NAME`)

De naam waarmee de chat-agent verschijnt in de chatinterface is instelbaar via `.env` (`AGENT_NAME`, standaard `Reggy`). De naam:
- verschijnt als label boven elke agent-respons in de chat
- wordt geüntegreerd in de voortgangsindicatoren (`🧠 Reggy antwoordt...`)
- is aanpasbaar via de Instellingen-tab zonder herstart

De naam heeft **geen invloed** op de werking van de agent of de skills — enkel op de chat-persona.

### 3.15 Voortgangsindicatoren met stap X/N

Tijdens het verwerken van een chatprompt worden alle voorbereiding- en uitvoeringsstappen als genummerde sub-stappen getoond in de `st.status()`-box:

- **Bestanden lezen**: stap 1 t/m N per geüpload bestand (bestandsnaam zichtbaar)
- **Plan genereren**: stap N+1/N+1 (LLM-aanroep)
- **Tool-uitvoering**: stap 1 t/m M per geplande actie, met ✅-preview van het resultaat

### 3.16 Automatisch opslaan van resultaten

Elke LLM-gegenereerde respons (plan-uitvoer + directe LLM-antwoorden) wordt automatisch bewaard als Markdown-bestand:

- Opslaglocatie: `<project>/results/` (of `<root>/results/`)
- Bestandsnaam: `YYYY-MM-DD_HH-MM-SS_resultaat.md`
- Zichtbaar in de chat als klein caption: `💾 Opgeslagen als results/...`
- Bereikbaar via `/list_directory results` of `/read_file results/<naam>`

---

## 4. Gebruikersinterfaces

### 4.1 Grafische Cockpit (Streamlit)

Zes tabs:

| Tab | Functie |
|---|---|
| 💬 Chat | Conversationele opdrachten en slash-commands met autocomplete |
| 📖 Help & Commands | Skill-overzicht, documentatie en gebruikershandleiding |
| 📅 Cron | Aanmaken en beheren van geplande taken |
| 📋 Log | Actie-log in chronologische en gegroepeerde weergave |
| ⚙️ Instellingen | Alle configuratieparameters |
| 🔄 Workflows | Workflow-beheer, tickets en project-uitvoering |
| 📊 Tokens | Token-verbruik, kostprijs en pricing-beheer |

**Zijbalk**: Naast de Reset Chat-knop toont de zijbalk een **projectselector** (dropdown), een **kennisbank-widget** (bestanden + grootte), en een **notificatie-indicator** voor cron-taakmeldingen. Het actieve project wordt getoond met type-icoon (bijv. `💻 mijn-app`). Bij projectwisseling wordt de agent herladen en de sessie herstart.

### 4.2 Commandoregelinterface (CLI)

Alternatieve toegang tot dezelfde functionality zonder grafische interface:
- Directe uitvoering: `python main.py run /skill_naam argument`
- Interactieve chat-modus: `python main.py chat`
- Alle acties worden gelogd met `source="cli"`

---

## 5. Skill-systeem

Skills zijn de functionele bouwblokken van Regian OS. Elk Python-bestand in `regian/skills/` met publieke functies voorzien van docstrings wordt automatisch ontdekt en geregistreerd als slash-command én als LLM-tool.

Bestaande skill-modules op Milestone 1.0.5:

| Module | Beschrijving | Aantal functies |
|---|---|---|
| `terminal` | Shell-uitvoering, Python-runner | 2 |
| `files` | Bestandsbeheer | 8 |
| `github` | GitHub-integratie | 9 |
| `cron` | Taakplanning | 5 |
| `help` | Hulp en documentatie | 1 |
| `project` | Projectbeheer en -context | 6 |
| `knowledge` | Kennisbank-beheer | 4 |
| `backup` | Werkmap backup & restore | 3 |

---

## 6. Uitbreidbaarheid

Nieuwe skills toevoegen vereist enkel:
1. Een nieuw `.py`-bestand in `regian/skills/`
2. Publieke functies met duidelijke docstrings (gebruikt als LLM-instructies)

Geen configuratie, geen registratie — het systeem ontdekt de skill automatisch bij de volgende opstart. Dit maakt Regian OS een groeiplatform waarbij functionaliteit incrementeel uitgebreid kan worden.

---

## 7. Kwaliteit en betrouwbaarheid

- **Testdekking**: ≥ 80% (486 tests, geautomatiseerd via pytest)
- **Logretentie**: maximaal 500 entries (oudste worden automatisch verwijderd)
- **Timeout**: shell-commando's worden na 30 seconden afgebroken
- **Path-traversal**: bestands-skills blokkeren paden buiten de werkmap

---

## 8. Workflow-systeem (nieuw in 1.1.18)

### 8.1 Concept

Het workflow-systeem stelt gebruikers in staat om **meerstappe-processen** te definiëren en automatisch uit te voeren. Een workflow bestaat uit een geordende reeks fasen van vier typen:

- `llm_prompt` — AI-aanroep met template-substitutie
- `task_loop` — iteratief uitvoeren van een takenlijst via de agent
- `human_checkpoint` — pauze voor menselijke goedkeuring (HITL)
- `tool_chain` — deterministisch uitvoeren van een reeks tools

### 8.2 Fase-artefacten

Elke fase kan zijn uitvoer opslaan als een **artifact** (sleutel-waarde-paar). Latere fasen kunnen via `{{sleutel}}`-substitutie de uitvoer van vorige fasen als invoer gebruiken. Zo ontstaat een **datapijplijn** binnen de workflow.

### 8.3 State-beheer

De status van een workflow-run wordt na elke fase opgeslagen op disk (`<project>/.regian_workflow_state/<run_id>.json`). Runs kunnen na een onderbreking worden voortgezet.

### 8.4 Template-systeem

Templates worden gezocht in prioriteitsvolgorde:
1. `<project>/.regian_workflow/<naam>.json`
2. `<root>/.regian_workflow/<naam>.json`
3. `regian/workflows/<naam>.json` (ingebouwde templates)

Ingebouwde template: `van_idee_tot_mvp` (5 fasen: PRD → taakopsplitsing → implementatie → test & validatie → review).

### 8.5 BPMN-compatibiliteit

Workflows kunnen worden geïmporteerd vanuit en geëxporteerd naar BPMN 2.0 XML-bestanden (compatibel met [bpmn.io](https://bpmn.io)).

### 8.6 Dashboard-weergave workflow-runs

De run-weergave toont per run:
- **Fase-indicators** — visuele badges (✅/▶️/⬜) per fase
- **Artifacts** — altijd uitgeklapt bovenaan de run; inhoud direct zichtbaar
- **Uitgevoerde taken** — elke taak (`**Taak X/Y:**`) is een inklapbare expander; standaard ingeklapt
- **Goedkeuringscontext** — bij `STATUS_WAITING` verschijnt een infobanner met fase-naam, -index en -type boven de goedkeuringsacties
- **Projectnaam** — elke actieve run toont de naam van het bijbehorende project

### 8.7 Beschikbare slash-commands

| Command | Functie |
|---|---|
| `/list_workflows` | Alle beschikbare templates |
| `/list_workflow_runs` | Alle actieve en afgeronde runs |
| `/start_workflow <naam> <invoer>` | Start een workflow |
| `/workflow_status <run_id>` | Status en artifacts van een run |
| `/approve_workflow <run_id>` | Keur een fase goed en ga door |
| `/cancel_workflow <run_id>` | Annuleer een actieve run |
| `/create_workflow_template <naam> <beschrijving>` | LLM genereert een template |
| `/import_bpmn <pad>` | Importeer BPMN XML naar workflow-JSON |
| `/export_bpmn <naam>` | Exporteer workflow naar BPMN XML |

---

## 9. Ticket-systeem — Kanban (nieuw in 1.1.18)

Het ticket-systeem biedt een Kanban-gebaseerde bugtracker die volledig geïntegreerd is in het workflow-scherm. Tickets worden opgeslagen per project in `<project>/.regian_tickets.json`.

### 9.1 Kolommen

| Kolom | Status | Beschrijving |
|---|---|---|
| 📋 To Do | `todo` | Nieuw aangemaakt door gebruiker |
| 🔄 In Progress | `in_progress` | AI is bezig met de fix |
| 👀 Review | `review` | AI-fix klaar, gebruiker test |
| ✅ Done | `done` | Goedgekeurd door gebruiker |

### 9.2 Workflow

1. Gebruiker maakt ticket aan (titel + beschrijving met stappen/verwacht gedrag)
2. Klik **🤖 Fix** op een ticket of **🤖 Fix alle** voor de volledige To Do-kolom
3. Agent voert de fix uit: `todo → in_progress → review`
4. Gebruiker test het resultaat en klikt **✅ Done** of **🔙 To Do** met opmerking
5. Bij terugplaatsing kan de AI de opmerking gebruiken als context voor een tweede poging

### 9.3 Beschikbare slash-commands

| Command | Functie |
|---|---|
| `/create_ticket <titel> <beschrijving>` | Nieuw ticket aanmaken |
| `/list_tickets [status]` | Tickets weergeven, optioneel gefilterd |
| `/move_ticket <id> <status> [opmerking]` | Ticket verplaatsen |
| `/fix_ticket <id>` | AI-agent lost dit ticket op |
| `/fix_all_tickets` | Alle To Do-tickets laten oplossen |
| `/delete_ticket <id>` | Ticket verwijderen |

---

## 10. Project uitvoeren (nieuw in 1.1.18)

Vanuit het **🔄 Workflows → ▶️ Project uitvoeren**-scherm kunnen build- en runscripts van het actieve project worden uitgevoerd zonder de Regian-interface te verlaten.

### 10.1 Detectie

Regian detecteert automatisch:
- `build.sh`, `dev.sh`, `start.sh`
- `Makefile` (`make`)
- `package.json` → npm scripts (`build`, `dev`, `start`, `test`)
- `requirements.txt` + optioneel `main.py` → `pytest` / `python main.py`

### 10.2 Uitvoermodi

| Mode | Gedrag |
|---|---|
| **Build/test** | Wordt synchroon uitgevoerd (timeout 120s), output getoond in expander |
| **Live server** (npm dev, npm start, python main.py) | Start/stop rechtstreeks vanuit Regian via `▶️ Start` / `🔴 Stop server`; PID bijgehouden in sessie |

### 10.3 Server log

Serveruitvoer (stdout + stderr) wordt weggeschreven naar `<project>/.regian_server.log`. Regian toont de laatste 200 regels in een logviewer in het dashboard zolang de server actief is. De knop **🗑️ Wis log** maakt het logbestand leeg.

### 10.4 Poortdetectie

De poort wordt automatisch herkend via de `-p`-vlag of `--port`-optie in de `package.json`-scriptbody. Fallback-poorten: 5173 (Vite), 3000 (React/Next), 8080 (overig). De browser-link verwijst steeds naar `http://127.0.0.1:<poort>` (IPv6-safe).

### 10.5 Automatisch aanmaken

Als er geen script gevonden wordt: de knop **🔨 Maak build.sh aan** laat de AI een passend script genereren op basis van de projectbestanden.

---

## 11. Verbeteringen in Milestone 1.2.1

### 11.1 Agent-context bij ticket-fixes

`fix_ticket()` leest automatisch tot 30 bronbestanden uit het actieve project en geeft deze als volledige broncode mee aan de agent. Hierdoor kan de agent bestaande implementaties analyseren en gerichte patches schrijven in plaats van bestanden opnieuw aan te maken.

### 11.2 Agent log in ticket review

In de **👀 Review**-kolom van het Kanban-board toont elk ticket nu een inklapbaar overzicht `📋 Agent log (N stappen)` met alle tool-aanroepen die de agent deed tijdens de fix. Zo kan je precies zien wat de agent heeft gedaan zonder de actie-log te raadplegen.

### 11.3 Template van_idee_tot_mvp — 5 fasen

De ingebouwde template bevat nu een extra fase **Test & Validatie** (na de implementatiefase). Deze fase vraagt de agent om de testrunner te draaien en bevindingen te rapporteren, vóór de eindreview door de gebruiker.

---

---

## 12. Verbeteringen in Milestone 1.3.0 (REG-2)

### 12.1 Token-verbruik & kostprijs tracking

Elke LLM-aanroep in `OrchestratorAgent.plan()`, `OrchestratorAgent.run()` en `RegianAgent.ask()` wordt voortaan geregistreerd in `regian_token_log.jsonl`.

Per entry:
- Timestamp, provider, model, actief project, call-type
- Input tokens, output tokens, totaal tokens
- Kostprijs in EUR (berekend via configureerbare pricing-tabel)

### 12.2 Token-log module (`regian/core/token_log.py`)

Nieuwe core-module met de volgende functies:

| Functie | Beschrijving |
|---|---|
| `log_tokens()` | Schrijft één entry naar het JSONL-logbestand |
| `_extract_tokens(response)` | Haalt token-aantallen op uit een LangChain response |
| `_calc_cost(model, in, out)` | Berekent EUR-kostprijs via prefix-match pricing |
| `get_summary_by_model()` | Aggregatie per provider/model, gesorteerd op kostprijs |
| `get_summary_by_project()` | Aggregatie per project, gesorteerd op kostprijs |
| `get_monthly_evolution()` | Maandelijkse evolutie, chronologisch gesorteerd |
| `get_totals()` | Globale totalen (tokens, kostprijs, aanroepen) |
| `get_pricing()` / `set_pricing()` | Lees/schrijf de pricing-tabel (EUR/1M tokens) |
| `clear_token_log()` | Wis het logbestand |

### 12.3 Dashboard — 📊 Tokens-tab

Nieuwe zevende tab in de cockpit met:
- **KPI-rij**: 4 metrics (aanroepen, totaal/input tokens, kostprijs EUR)
- **Per provider/model**: tabel met uitsplitsing
- **Per project**: tabel met uitsplitsing per actief project
- **Evolutie per maand**: staafgrafiek + overzichtstabel
- **Prijsinstellingen**: editable JSON-editor voor de pricing-tabel
- **Wis token-log**: knop om het logbestand te leegmaken

### 12.4 Configuratie

Nieuwe .env-variabelen:
- `TOKEN_PRICING`: JSON-string met prijzen per model (EUR/1M tokens)
- `TOKEN_LOG_FILE`: bestandsnaam van het token-logbestand (standaard `regian_token_log.jsonl`)

---

*Regian OS — Milestone 1.3.0 · Intern document · 7 maart 2026*