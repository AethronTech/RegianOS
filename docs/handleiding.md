# Regian OS — Gebruikershandleiding

**Versie:** 1.1.17 · **Datum:** 3 maart 2026

---

## Inhoud

1. [Wat is Regian OS?](#wat-is-regian-os)  
2. [Opstarten](#opstarten)  
3. [Chatinterface](#chatinterface)  
4. [Kennisbank](#kennisbank)  
5. [Slash Commands](#slash-commands)  
6. [Cron — Geplande Taken](#cron-geplande-taken)  
7. [Log — Actieoverzicht](#log-actieoverzicht)  
8. [Instellingen](#instellingen)  
9. [Beveiliging & HITL](#beveiliging-hitl)  
10. [Projectbeheer](#projectbeheer)  
11. [Workflows — Van Idee tot MVP](#workflows-van-idee-tot-mvp)  
12. [Tips & Veelgestelde Vragen](#tips-veelgestelde-vragen)

---

## Wat is Regian OS?

Regian OS is een persoonlijk AI-cockpit. Je geeft opdrachten in gewone taal of via slash-commando's en Regian vertaalt dit automatisch naar de juiste acties: bestanden aanmaken, GitHub-repos beheren, shell-commando's uitvoeren en taken plannen — allemaal vanuit één interface.

Het systeem werkt met een **grote taalmodel** (LLM, standaard Google Gemini) als planningsbrein. Alle uitgevoerde acties worden bijgehouden in een **actie-log** en risico-operaties worden afgeschermd door het **HITL-mechanisme** dat jouw expliciete bevestiging vereist vóór uitvoering.

---

## Opstarten

```bash
cd RegianOS
source .venv/bin/activate
streamlit run main.py
```

De applicatie opent op `http://localhost:8501`. Configureer vóór gebruik de `.env`-variabelen:

| Variabele | Beschrijving | Voorbeeld |
|---|---|---|
| `GOOGLE_API_KEY` | API-sleutel voor Gemini | `AIza...` |
| `GITHUB_TOKEN` | Persoonlijk GitHub token | `ghp_...` |
| `REGIAN_ROOT_DIR` | Werkmap voor bestanden | `/Users/jou/RegianWorkspace` |
| `LLM_PROVIDER` | Provider: `gemini` of `ollama` | `gemini` |
| `LLM_MODEL` | Modelnaam | `gemini-2.5-flash` |

> **Tip:** Al deze instellingen zijn ook instelbaar via de tab **⚙️ Instellingen** in de applicatie zelf.

---

## Chatinterface

De **💬 Chat**-tab is het primaire ingangspunt. Je typt een opdracht in gewone Nederlandse (of Engelse) taal en het systeem stelt automatisch een plan op en voert dit uit.

### Voorbeeldopdrachten

```
Maak een nieuw GitHub-repo aan met de naam 'mijn-project'
```
```
Schrijf een Python-script dat de huidige datum print en sla het op als datum.py
```
```
Voer git status uit in de map mijn-project
```
```
Geef me een overzicht van alle bestanden in de werkmap
```

### Hoe werkt het?

1. Je typt een opdracht → het LLM maakt een **stappenplan** (één of meerdere tool-calls)  
2. Bevat het plan gevaarlijke stappen? → **HITL-scherm** verschijnt ter bevestiging  
3. Je bevestigt (of annuleert) → Regian voert de stappen één voor één uit  
4. Tussen elke stap verschijnt een **voortgangsbalk** en een **⏹️ Stop**-knop  
5. Het resultaat verschijnt in de chat

**Stop-knop tijdens uitvoering**  
Zodra een meerstappenplan start, verschijnt bovenaan de chat een voortgangsbalk met een **⏹️ Stop uitvoering**-knop. Klik hierop om de uitvoering te onderbreken na de lopende stap. Al uitgevoerde stappen worden bewaard in het antwoord.

### Bestanden bijvoegen

Via het paperclip-icoon (📎) naast het invoerveld kun je rechtstreeks bestanden toevoegen aan je chatbericht. De inhoud van het bestand wordt automatisch als context doorgegeven aan het LLM.

**Ondersteunde bestandstypen:**

| Categorie | Extensies |
|---|---|
| Tekst / Docs | `.txt`, `.md`, `.pdf` |
| Code | `.py`, `.js`, `.ts`, `.jsx`, `.tsx`, `.rs`, `.go`, `.java`, `.c`, `.cpp`, `.h`, `.sh`, `.sql` |
| Data / Config | `.json`, `.csv`, `.yaml`, `.yml`, `.toml`, `.ini`, `.xml`, `.html`, `.css` |

**Voorbeeldgebruik:**

- Upload een `requirements.txt` en vraag: *"Zijn er verouderde packages in dit bestand?"*
- Upload een Python-bestand en vraag: *"Schrijf unit-tests voor deze code"*
- Upload een PDF-rapport en vraag: *"Maak een samenvatting van dit document"*
- Je kunt meerdere bestanden tegelijk toevoegen

> **Automatisch opslaan:** Elk geüpload bestand wordt automatisch bewaard in de `uploads/`-map van jouw actief project (of in de werkmap-root als er geen actief project is). Zo kun je zelf later de bestanden terugvinden of verwijzen vanuit andere opdrachten.

> **Let op:** Bij slash-commands (`/`) worden bijlagen genegeerd.

### Markering in de chat

| Pictogram | Betekenis |
|---|---|
| Jouw avatar (instelbaar) | Jouw berichten |
| 🤖 (Streamlit-standaard) | Reactie van Regian |
| 🟢 Stap | Veilige stap in HITL-overzicht |
| 🔴 Stap | Gevaarlijke stap die bevestiging vereist |

### Berichten kopiëren en bewerken

Elk bericht toont knoppen zodra het zichtbaar is:

**Op antwoorden van Regian (🤖):**
- **📋** — kopieert de volledige tekst van het antwoord naar het klembord

**Op jouw vragen:**
- **📋** — kopieert de vraagtekst naar het klembord
- **✏️** — opent een bewerkingsveld met de originele vraag; pas aan en klik **▶️ Uitvoeren** om de vraag opnieuw te sturen (de chat wordt teruggespoeld naar dat punt). Klik **✖️ Annuleren** om te sluiten zonder wijziging.

### Voortgangsindicatoren

Tijdens het verwerken van een vraag toont de agent genummerde stappen:

- **Stap 1/N — bestand lezen**: elk geüpload bestand wordt apart geteld en getoond als `📂 Stap X/N: bestand.csv lezen...`
- **Stap N/N — plan genereren**: de LLM-aanroep met voortgangstekst
- **Stap X/Ntotaal — uitvoeren**: elke tool-aanroep in het plan wordt stap voor stap getoond met ✅-preview van het resultaat

### Resultaten automatisch opgeslagen

Elke LLM-respons (analyse, samenvatting, plan-uitvoer) wordt automatisch bewaard als Markdown-bestand in `<project>/results/` (of `<root>/results/` bij geen actief project).

- Bestandsnaam: `YYYY-MM-DD_HH-MM-SS_resultaat.md`
- Onderaan het antwoord verschijnt een kleine notitie: `💾 Opgeslagen als results/...`
- Slash-commands (`/`) worden **niet** opgeslagen — enkel LLM-gegenereerde antwoorden
- Eerder opgeslagen resultaten zijn toegankelijk via `/list_directory results`

Je chatgeschiedenis wordt **automatisch bewaard** tussen sessies. Bij het opnieuw openen van de Cockpit zie je jouw vorige berichten terug.

- De geschiedenis is **per project** gescheiden: wisselen van actief project laadt automatisch de chatlog van dat project
- Bij het wisselen van project via de zijbalk worden de berichten direct vervangen door de chat van het nieuwe project
- Klik op **🗑️ Reset Chat** in de zijbalk om de chatgeschiedenis te wissen (zowel uit sessie als van schijf)
- Chatbestanden worden opgeslagen als `.regian_chat.json` in de projectmap of werkmap-root

---

## Kennisbank

De **kennisbank** maakt het mogelijk om bestanden permanent als achtergrondcontext bij te houden voor het LLM. Elk bestand dat je toevoegt, wordt automatisch bij elke chat-prompt meegegeven, zonder dat je er steeds opnieuw naar hoeft te verwijzen.

**Wanneer gebruiken?**  
- Projectspecificaties of architectuurdocumenten die de agent altijd moet kennen
- Eerder gegenereerde samenvattingen of resultaten
- Codestijlgidsen, API-documentatie of woordenlijsten

| Command | Beschrijving |
|---|---|
| `/add_to_knowledge <pad>` | Voegt een bestand toe (relatief pad t.o.v. werkmap) |
| `/list_knowledge` | Toont alle kennisbestanden met grootte |
| `/remove_from_knowledge <naam>` | Verwijdert één kennisbestand |
| `/clear_knowledge` | Wist de volledige kennisbank |

**Kennisbank widget in zijbalk:**  
De linkerzijbalk toont automatisch hoeveel kennisbestanden er zijn en welke. De context wordt bij elke LLM-opdracht meegegeven (maximaal 8 000 tekens).

> **Tip:** Bestanden van de chat-upload worden automatisch opgeslagen in `uploads/`. Je kunt ze daarna rechtstreeks toevoegen aan de kennisbank: `/add_to_knowledge uploads/mijn-document.pdf`

---

## Slash Commands

Slash-commando's sturen een specifieke skill rechtstreeks aan, zonder tussenkomst van het LLM. Dit is sneller en voorspelbaarder.

**Syntax:**

```
/skill_naam argument
/skill_naam {"param1": "waarde", "param2": 42}
```

**Voorbeelden:**

```
/repo_list
/run_shell git pull
/write_file {"path": "notities.txt", "content": "Hallo wereld"}
/list_directory .
/repo_info mijn-project
```

Typ `/` in het chatvenster om de autocomplete-dropdown te activeren met een volledig overzicht van alle beschikbare commando's.

### Overzicht van skills per categorie

#### 📁 Files

| Command | Beschrijving |
|---|---|
| `/write_file(path, content)` | Schrijft content naar een bestand |
| `/read_file(path)` | Leest de inhoud van een bestand |
| `/list_directory(path)` | Toont de inhoud van een map |
| `/create_directory(path)` | Maakt een map aan |
| `/delete_file(path)` | Verwijdert een bestand (**HITL**) |
| `/delete_directory(path)` | Verwijdert een map en inhoud (**HITL**) |
| `/move_file(src, dst)` | Verplaatst of hernoemt een bestand |
| `/copy_file(src, dst)` | Kopieert een bestand |

> Alle paden zijn relatief aan de geconfigureerde **werkmap** (`REGIAN_ROOT_DIR`).

#### 🖥️ Terminal

| Command | Beschrijving |
|---|---|
| `/run_shell(command, cwd)` | Voert een shell-commando uit (30s timeout) |
| `/run_python(code)` | Voert een Python-snippet uit |

> `cwd` is optioneel en relatief aan de werkmap. Commando's die matches met de **destructieve patronen** (zie Instellingen) triggeren HITL.

#### 🐙 GitHub

| Command | Beschrijving |
|---|---|
| `/repo_create(name, private)` | Maakt een nieuwe repo aan |
| `/repo_list()` | Toont al jouw repos |
| `/repo_info(repo_name)` | Details van een specifieke repo |
| `/repo_delete(repo_name)` | Verwijdert een repo permanent (**HITL**) |
| `/commit_and_push(repo_name, file_path, commit_message)` | Commit & push een bestand |
| `/create_issue(repo_name, title, body)` | Maakt een issue aan |
| `/list_issues(repo_name)` | Toont open issues |
| `/create_branch(repo_name, branch_name)` | Maakt een branch aan |
| `/create_pull_request(repo_name, title, head, base, body)` | Opent een pull request |

#### 📅 Cron

| Command | Beschrijving |
|---|---|
| `/schedule_command(job_id, command, schedule)` | Plant een slash-command |
| `/schedule_shell(job_id, command, schedule)` | Plant een shell-commando |
| `/schedule_prompt(job_id, prompt, schedule)` | Plant een AI-prompt |
| `/cancel_scheduled_job(job_id)` | Verwijdert een geplande taak |
| `/list_scheduled_jobs()` | Toont alle geplande taken |

#### ❓ Help

| Command | Beschrijving |
|---|---|
| `/get_help(topic)` | Geeft uitleg over een topic |

#### 📂 Project

| Command | Beschrijving |
|---|---|
| `/create_project(name, project_type, description, git_repo)` | Maakt een nieuw project aan inclusief mapstructuur |
| `/activate_project(name)` | Activeert een project als actieve context |
| `/deactivate_project()` | Deactiveert het huidige actieve project |
| `/get_project_info(name)` | Toont details van een project (leeg = actief project) |
| `/list_projects()` | Toont alle beschikbare projecten |
| `/rename_project(old_name, new_name)` | Hernoemt een bestaand project (mapnaam, manifest en actief project worden bijgewerkt) |

> Projecten worden aangemaakt als submappen in de werkmap en bevatten een `.regian_project.json`-manifest. Het actieve project bepaalt de context van het LLM én de beschikbare tools.

#### 📚 Kennisbank

| Command | Beschrijving |
|---|---|
| `/add_to_knowledge(path)` | Voegt een bestand toe aan de kennisbank (pad relatief t.o.v. werkmap) |
| `/list_knowledge()` | Toont alle kennisbestanden met bestandsgrootte |
| `/remove_from_knowledge(name)` | Verwijdert één kennisbestand op naam |
| `/clear_knowledge()` | Wist de volledige kennisbank |

> Kennisbestanden worden bewaard in `<project>/.regian_knowledge/` en worden automatisch bij elke LLM-opdracht als achtergrondcontext meegegeven.

#### 💾 Backup

| Command | Beschrijving |
|---|---|
| `/backup_workspace()` | Maakt een zip-backup van de volledige werkmap |
| `/list_backups()` | Toont alle beschikbare backups met datum en grootte |
| `/restore_workspace(backup_name)` | Herstelt de werkmap vanuit een backup |

> Backups worden opgeslagen in `RegianBackups/` naast de werkmap (configureerbaar). Het maximum aantal te bewaren backups is instelbaar in de **⚙️ Instellingen**-tab (standaard: 5).  
> Stel een automatische dagelijkse backup in via de **📅 Cron**-tab: schema `dagelijks om 02:00`, commando `/backup_workspace`.

---

## Cron — Geplande Taken

De **📅 Cron**-tab beheert periodieke taken die automatisch worden uitgevoerd.

### Taak aanmaken

Klik op **➕ Nieuwe taak toevoegen** en vul in:

| Veld | Beschrijving |
|---|---|
| **Naam** | Unieke identifier, bijv. `dagelijkse_backup` |
| **Type** | `/command`, `shell` of `AI-prompt` |
| **Schema** | Wanneer de taak uitgevoerd wordt (zie tabel hieronder) |
| **Taak** | Het commando of de prompt |
| **Beschrijving** | Optionele omschrijving |

### Geldige schema-formaten

| Formaat | Voorbeeld |
|---|---|
| Interval | `elke 5 minuten` · `elk uur` · `elke 2 uur` |
| Dagelijks | `dagelijks om 09:00` |
| Dag van week | `elke maandag om 08:00` |
| Werkdagen | `werkdagen om 07:30` |
| Cron expressie | `0 9 * * 1-5` |

### Taakoverzicht

Voor elke taak worden weergegeven:
- Status (🟢 actief / ⏸️ gepauzeerd)
- Volgende geplande run
- Tijdstip en status van de laatste run
- Output van de laatste run (klapbaar)

### Actieknoppen

| Knop | Actie |
|---|---|
| ▶️ | Voer nu onmiddellijk uit |
| ⏸️ / ▶️ | Pauzeer of activeer |
| 🗑️ | Verwijder de taak |

---

## Log — Actieoverzicht

De **📋 Log**-tab toont een chronologisch overzicht van alles wat Regian heeft uitgevoerd.

### Weergavemodi

**🕐 Chronologisch** — Alle tool-aanroepen op volgorde van uitvoering. Filter op bron en skill-naam.

**💬 Per opdracht** — Groepeert alle tool-calls die voortkwamen uit dezelfde chatopdracht. Toont:
- De originele prompt
- Alle uitgevoerde stappen (tool + argumenten + resultaat)

### Bronpictogrammen

| Pictogram | Bron |
|---|---|
| 💬 | Chat (interactieve opdracht) |
| ⚡ | Direct (slash-command) |
| 📅 | Cron (geplande taak) |
| 🖥️ | CLI (commandoregel) |

### Log wissen

Klik **🗑️ Log wissen** rechts bovenaan om de volledige log te verwijderen. De log houdt maximaal **500 entries** bij; oudere worden automatisch verwijderd.

---

## Instellingen

De **⚙️ Instellingen**-tab biedt directe toegang tot alle configuratie.

### 📁 Werkmap

De root-directory waar Regian bestanden opslaat. Standaard `~/RegianWorkspace`. Alle relatieve paden in skills worden t.o.v. deze map opgelost.

### 🤖 Chat Model

Kies de LLM-provider en het model:

| Provider | Beschikbare modellen |
|---|---|
| **Gemini** | gemini-2.5-flash, gemini-2.5-pro, gemini-2.0-flash, gemini-flash-latest |
| **Ollama** | mistral, llama3.1:8b, llama3.2, deepseek-r1:8b |

Bij het overschakelen wordt de agent-cache gewist zodat het nieuwe model meteen actief is.

### 🔐 Bevestiging vereist (HITL)

Kies welke skills altijd expliciete bevestiging vereisen vóór uitvoering. Standaard staan `repo_delete`, `delete_file` en `delete_directory` op de lijst.

### 🙂 Gebruikers-avatar

Kies een emoji die als jouw avatar in de chatweergave verschijnt. De keuze wordt bewaard in `.env`.
### 🤖 Chat-agentnaam

Standaard heet de chat-agent **Reggy**. Je kunt deze naam aanpassen via het tekstveld. De naam verschijnt als label boven de antwoorden van de agent en in de voortgangsindicatoren (bijv. „Reggy antwoordt...“).

> De tool zelf heet altijd **Regian OS** — enkel de chat-persona verandert.
### ⚠️ Destructieve shell-patronen

Regex-patronen die HITL triggeren bij `run_shell`. Eén patroon per regel. Standaardpatronen omvatten `rm`, `sudo`, `mkfs`, `shutdown` en gelijkaardigen. Klik **↩️ Herstel standaard** om terug te zetten.

### ⏱️ Shell timeout

Maximale looptijd (in seconden) voor elk shell-commando. Standaard **30 seconden**. Verhoog dit voor langlopende scripts, verlaag het voor snellere time-outs.

### 🔁 Agent max. iteraties

Maximale aantal LLM-rondes dat de agent mag doen per opdracht. Standaard **5**. Een hogere waarde laat de agent complexere meertraps-taken oplossen; een lagere waarde beperkt het token- en kostenverbruik.

### 📋 Log instellingen

- **Max. log-entries** — Maximale aantal regels dat het actie-logbestand bewaart. Oudere entries worden automatisch verwijderd. Standaard **500**.
- **Max. tekens per resultaat** — Hoeveel tekens van elk tool-resultaat worden opgeslagen. Standaard **300**.

### 🗂️ Bestandsnamen

- **Actie-logbestand** — Naam van het JSONL-bestand met de actie-log. Standaard `regian_action_log.jsonl`.
- **Jobs-bestand** — Naam van het JSON-bestand met geplande taken. Standaard `regian_jobs.json`.

Beide bestanden worden opgeslagen in de RegianOS-projectroot (naast `main.py`). Herstart Regian na een naamswijziging om het nieuwe bestand te gebruiken.

### 💾 Backup

- **Max. te bewaren backups** — Maximum aantal zip-backups dat wordt bijgehouden. Oudste worden automatisch verwijderd. Standaard **5**.
- **Backup-map** — Map waar backups worden opgeslagen. Standaard `RegianBackups/` naast de werkmap.
- **Nu backup maken** — Knop om direct een backup te starten.
- **Backups bekijken** — Toont lijst van beschikbare backups.

> **Tip:** Maak een dagelijkse automatische backup via de **📅 Cron**-tab met schema `dagelijks om 02:00` en commando `/backup_workspace`.

---

## Beveiliging & HITL

**HITL** (Human-in-the-Loop) is het veiligheidsmechanisme van Regian OS.

### Wanneer wordt HITL geactiveerd?

1. Het LLM-plan bevat een skill die in de HITL-lijst staat (`delete_file`, `repo_delete`, …)
2. Een `run_shell`-commando matcht een destructief patroon uit de instellingen (bijv. `rm`, `sudo`)

### Wat verschijnt er?

Een overzichtsscherm met alle geplande stappen:
- 🟢 = veilige stap
- 🔴 = stap die bevestiging vereist

Je kiest:
- **✅ Bevestigen & uitvoeren** — plan wordt volledig uitgevoerd
- **❌ Annuleren** — plan wordt afgebroken, geen wijzigingen

### Path-traversal beveiliging

Alle bestandsoperaties worden gecontroleerd op **path-traversal**. Paden buiten de werkmap worden geblokkeerd met een foutmelding.

---

## Projectbeheer

Regian OS ondersteunt project-gebaseerd werken. Een **project** is een map in je werkmap met een bijbehorend `.regian_project.json`-manifest dat naam, type, beschrijving en git-repo bijhoudt.

### Projectselector in de zijbalk

Bovenaan de linkerzijbalk vind je een **projectselector**. Kies een project uit de lijst om het te activeren. Het actieve project wordt weergegeven als een badge met typeicoon (bijv. `💻 mijn-app`). Kies `(geen project)` om de projectcontext te wissen.

Wanneer een project actief is:
- Injecteert het LLM automatisch de projectinformatie in elk plan
- Worden de beschikbare tools gefilterd op het projecttype (bij `docs`- en `data`-projecten zijn GitHub-skills niet beschikbaar)

### Projecttypen

| Type | Icoon | Automatisch aangemaakte submappen |
|---|---|---|
| `software` | 💻 | `src/`, `tests/`, `docs/` |
| `docs` | 📄 | `content/`, `assets/` |
| `data` | 📊 | `data/raw/`, `data/processed/`, `notebooks/` |
| `generic` | 📁 | *(geen)* |

### Project aanmaken

```
Maak een nieuw softwareproject aan met de naam 'mijn-app'
```

Of via slash-command:

```
/create_project {"name": "mijn-app", "project_type": "software", "description": "Mijn eerste project"}
```

### Project activeren

```
/activate_project mijn-app
```

Of kies het project in de zijbalk. Na activering verschijnt de projectbadge en start het LLM met projectcontext.

### Projectinfo opvragen

```
/get_project_info
```

Geeft naam, type, descripie, aanmaakdatum en git-repo van het actieve project.

### Tool-filtering per projecttype

Bij `docs`- en `data`-projecten zijn GitHub-skills (repo's aanmaken, pushen, pull requests…) verborgen om de beschikbare tools overzichtelijk te houden. Bij `software`- en `generic`-projecten zijn alle tools beschikbaar.

### Aangepaste toolset via manifest

Bij het aanmaken van een project kun je een kommagescheiden lijst van skill-modules opgeven via de parameter `allowed_tools`. Dit overschrijft de standaard type-filtering:

```
/create_project {"name": "mijn-project", "project_type": "docs", "allowed_tools": "files,terminal,help"}
```

Als `allowed_tools` leeg is (standaard), geldt de type-gebaseerde filtering.

---

## Tips & Veelgestelde Vragen

**Hoe voeg ik een nieuwe skill toe?**  
Maak een Python-bestand aan in `regian/skills/` met publieke functies voorzien van docstrings. De skill wordt automatisch ontdekt bij de volgende opstart (geen registratie nodig).

**Welk model is het snelst?**  
`gemini-2.5-flash` biedt de beste balans tussen snelheid en kwaliteit voor dagelijks gebruik.

**Kan ik Ollama gebruiken zonder internet?**  
Ja. Zet `LLM_PROVIDER=ollama` in `.env` en zorg dat Ollama lokaal draait (`ollama serve`).

**De chat geeft geen reactie — wat nu?**  
Controleer of de API-sleutel correct is in `.env`. Bekijk de terminaloutput van `streamlit run` voor foutmeldingen.

**Hoe reset ik de chat?**  
Klik op **🗑️ Reset Chat** in de linkerzijbalk.

**Kan ik meerdere bestanden tegelijk verwerken?**  
Ja, via een AI-prompt: `Lees alle .txt bestanden in de map notities en maak een samenvatting`. Het LLM bouwt dan een meerstappe-plan.

**Hoe stop ik een cron-taak tijdelijk?**  
Klik op ⏸️ naast de taak in de Cron-tab. De taak blijft bewaard maar wordt niet meer uitgevoerd totdat je ze heractiveer met ▶️.

---

---

## Workflows — Van Idee tot MVP

Met de workflow-module kun je complexe meerstappe-processen definiëren die automatisch door het systeem worden uitgevoerd, met mogelijkheden voor menselijke tussenkomst op cruciale momenten.

### 11.1 Wat is een workflow?

Een workflow is een JSON-bestand met een geordende lijst van **fasen** (phases). Elke fase heeft een type dat bepaalt hoe het systeem hem uitvoert:

| Type | Beschrijving |
|---|---|
| `llm_prompt` | Stuur een prompt naar het LLM, sla het antwoord op als artifact |
| `task_loop` | Voer een LLM-gegenereerde takenlijst uit via de agent |
| `human_checkpoint` | Pauzeer en wacht op jouw goedkeuring |
| `tool_chain` | Voer een vaste reeks tools deterministisch uit |

### 11.2 De Workflows-tab in het dashboard

Open de **🔄 Workflows**-tab in de cockpit:

- **▶️ Starten**: kies een template, voer je idee in, klik *Start*.
- **📋 Actieve runs**: bekijk de voortgang en resultaten. Per run zie je:
  - Fase-badges (✅ klaar / ▶️ actief / ⬜ gepland)
  - **📦 Artifacts** — altijd uitgeklapt bovenaan, direct leesbaar
  - **Uitgevoerde taken** — elke taak is een inklapbare regel (`**Taak X/Y: …**`); klik om de details te tonen
  - Bij pauzering: een infobanner met de precieze fase die wacht op goedkeuring, plus feedback-invoer en de knoppen *Goedkeuren*, *Bijsturen* en *Annuleren*
- **📚 Templates**: bekijk beschikbare templates, exporteer als BPMN, importeer een `.bpmn`-bestand of laat het LLM een nieuw template genereren.

### 11.3 Workflow starten via slash-command

```
/start_workflow van_idee_tot_mvp Bouw een productiviteits-app voor developers
```

Volg daarna de voortgang:

```
/workflow_status <run_id>
```

Keur een wachtende fase goed:

```
/approve_workflow <run_id> Ziet er goed uit, ga door!
```

Annuleer:

```
/cancel_workflow <run_id>
```

### 11.4 Ingebouwde template: van_idee_tot_mvp

De meegeleverde template `van_idee_tot_mvp` bevat vier fasen:

1. **Product Architect** (llm_prompt + goedkeuring) — schrijft een PRD
2. **Lead Developer** (llm_prompt + goedkeuring) — breakdown in taken
3. **AI Implementatie** (task_loop + goedkeuring) — voert alle taken uit via de agent
4. **Review** (human_checkpoint) — eindcontrole door de gebruiker

### 11.5 Eigen template maken

Via het dashboard (LLM-generator) of via slash-command:

```
/create_workflow_template code_review Automatiseer code-reviews op pull requests
```

Of maak een `.json`-bestand aan in `<werkmap>/.regian_workflow/mijn_workflow.json`.

### 11.6 BPMN import/export

Workflows zijn compatibel met [bpmn.io](https://bpmn.io):

- **Export**: `/export_bpmn van_idee_tot_mvp` → `.bpmn` XML-bestand
- **Import**: `/import_bpmn /pad/naar/bestand.bpmn` → converteert naar workflow-template

---

*Regian OS — Milestone 1.1.17 · 3 maart 2026*
