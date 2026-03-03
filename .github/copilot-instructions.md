# GitHub Copilot — Werkinstructies voor RegianOS

## Bij elke nieuwe feature of wijziging

### 1. Update de drie documentatiebestanden

Na elke toevoeging of wijziging aan de codebase moeten de volgende bestanden actueel worden gehouden:

- **`docs/handleiding.md`** — Gebruikershandleiding: beschrijf de nieuwe functionaliteit vanuit gebruikersperspectief (wat doet het, hoe gebruik je het, voorbeeldcommando's).
- **`docs/functionele_beschrijving.md`** — Functionele beschrijving: registreer wat het systeem nu doet, update lijsten van functies, skills of modules.
- **`docs/technische_beschrijving.md`** — Technische beschrijving: update architectuur, module-beschrijvingen, datastructuren of beveiligingsmodel waar van toepassing.

### 2. Vul de testset aan — code coverage mag niet dalen

De huidige minimumdrempel is **80% coverage** (ingesteld in `build.sh` als `--cov-fail-under=60`, maar feitelijk target is 80%).

Regels:
- Elke nieuwe publieke functie in `regian/` krijgt minstens één test in de overeenkomstige `tests/test_*.py`.
- Nieuwe skill-modules (`regian/skills/*.py`) krijgen een eigen `tests/test_skills_<naam>.py`.
- Nieuwe core-modules (`regian/core/*.py`) krijgen een eigen `tests/test_core_<naam>.py`.
- Gebruik de bestaande fixtures uit `tests/conftest.py`: `tmp_root`, `isolate_env`, `tmp_env_file`.
- Valideer na elke wijziging met: `pytest --cov=regian --cov-report=term-missing`

## Projectstructuur (referentie)

```
regian/
  core/        → agent.py, scheduler.py, action_log.py
  interface/   → dashboard.py, cli.py
  skills/      → terminal.py, files.py, github.py, cron.py, project.py, ...
  settings.py
docs/
  handleiding.md
  functionele_beschrijving.md
  technische_beschrijving.md
tests/
  conftest.py
  test_core_*.py
  test_skills_*.py
  test_settings.py
```

## Codestijl

- Nederlands voor docstrings, gebruikersmeldingen en commentaar.
- Publieke functies in `regian/skills/` zijn automatisch beschikbaar als slash-command én als LLM-tool — schrijf altijd een duidelijke docstring (die de agent als instructie gebruikt).
- Skills starten **nooit** met `_` (worden dan genegeerd door de registry).
- Geen manuele registratie nodig: een nieuwe `.py` in `regian/skills/` wordt automatisch ontdekt.
