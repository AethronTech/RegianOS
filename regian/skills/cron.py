# regian/skills/cron.py
"""
Cron-skills: geplande taken aanmaken, beheren en uitvoeren.
"""
import re
from datetime import datetime


def schedule_command(job_id: str, command: str, schedule: str, description: str = "") -> str:
    """
    Plant een slash-command op een schema (bijv. 'elke 15 minuten', 'dagelijks om 09:00').
    Gebruik /command-syntax, bijv. '/repo_list' of '/run_shell git pull'.
    """
    from regian.core.scheduler import add_scheduled_job
    if not command.startswith("/"):
        command = "/" + command
    result = add_scheduled_job(
        job_id=job_id,
        task=command,
        job_type="command",
        schedule=schedule,
        description=description or f"Command: {command}",
    )
    if result == job_id:
        return f"✅ Taak '{job_id}' gepland: `{command}` — {schedule}"
    return result


def schedule_shell(job_id: str, command: str, schedule: str, description: str = "") -> str:
    """
    Plant een shell-commando op een schema (bijv. 'elke 30 minuten', 'dagelijks om 02:00').
    Voorbeelden van commando: 'git pull', 'python3 script.py'.
    """
    from regian.core.scheduler import add_scheduled_job
    result = add_scheduled_job(
        job_id=job_id,
        task=command,
        job_type="shell",
        schedule=schedule,
        description=description or f"Shell: {command}",
    )
    if result == job_id:
        return f"✅ Taak '{job_id}' gepland: `{command}` — {schedule}"
    return result


def schedule_prompt(job_id: str, prompt: str, schedule: str, description: str = "") -> str:
    """
    Plant een AI-prompt op een schema. De OrchestratorAgent voert de prompt uit op het opgegeven tijdstip.
    Voorbeeld: 'Controleer open issues en stuur een samenvatting'.
    """
    from regian.core.scheduler import add_scheduled_job
    result = add_scheduled_job(
        job_id=job_id,
        task=prompt,
        job_type="prompt",
        schedule=schedule,
        description=description or f"Prompt: {prompt[:60]}",
    )
    if result == job_id:
        return f"✅ Taak '{job_id}' gepland: AI-prompt — {schedule}"
    return result


def remove_job(job_id: str) -> str:
    """
    Verwijdert een geplande taak op basis van de job_id.
    """
    from regian.core.scheduler import remove_scheduled_job
    if remove_scheduled_job(job_id):
        return f"✅ Taak '{job_id}' verwijderd."
    return f"❌ Taak '{job_id}' niet gevonden."


def enable_job(job_id: str) -> str:
    """
    Activeert een gepauzeerde geplande taak.
    """
    from regian.core.scheduler import toggle_scheduled_job
    if toggle_scheduled_job(job_id, True):
        return f"✅ Taak '{job_id}' geactiveerd."
    return f"❌ Taak '{job_id}' niet gevonden."


def disable_job(job_id: str) -> str:
    """
    Pauzeert een geplande taak zonder hem te verwijderen.
    """
    from regian.core.scheduler import toggle_scheduled_job
    if toggle_scheduled_job(job_id, False):
        return f"⏸️ Taak '{job_id}' gepauzeerd."
    return f"❌ Taak '{job_id}' niet gevonden."


def run_job_now(job_id: str) -> str:
    """
    Voert een geplande taak onmiddellijk uit, buiten het schema om.
    """
    from regian.core.scheduler import run_job_now_by_id, get_all_jobs
    jobs = get_all_jobs()
    if job_id not in jobs:
        return f"❌ Taak '{job_id}' niet gevonden."
    run_job_now_by_id(job_id)
    return f"⚡ Taak '{job_id}' onmiddellijk uitgevoerd."


def list_jobs() -> str:
    """
    Toont alle geplande taken met status, schema en laatste uitvoering.
    """
    from regian.core.scheduler import get_all_jobs, get_next_run

    jobs = get_all_jobs()
    if not jobs:
        return "📭 Geen geplande taken."

    lines = [f"📅 **Geplande taken** ({len(jobs)} totaal):\n"]
    for job_id, job in sorted(jobs.items()):
        enabled = job.get("enabled", True)
        status_icon = "🟢" if enabled else "⏸️"
        job_type = job.get("type", "command")
        type_icon = {"command": "⚡", "shell": "🖥️", "prompt": "🧠"}.get(job_type, "📌")
        task = job.get("task", "")
        schedule = job.get("schedule", "")
        description = job.get("description", "")
        last_run = job.get("last_run") or "—"
        last_status = job.get("last_status") or ""
        next_run = get_next_run(job_id) if enabled else "—"

        lines.append(
            f"{status_icon} **{job_id}** {type_icon} `{task}`\n"
            f"   📌 {description}\n"
            f"   ⏰ Schema: `{schedule}`\n"
            f"   ▶️  Volgende run: {next_run}  |  Laatste run: {last_run} {last_status}\n"
        )
    return "\n".join(lines)


def job_output(job_id: str) -> str:
    """
    Toont de output van de laatste uitvoering van een taak.
    """
    from regian.core.scheduler import get_all_jobs
    jobs = get_all_jobs()
    job = jobs.get(job_id)
    if not job:
        return f"❌ Taak '{job_id}' niet gevonden."
    last_run = job.get("last_run") or "nog niet uitgevoerd"
    last_status = job.get("last_status") or ""
    last_output = job.get("last_output") or "(geen output)"
    return f"**{job_id}** — laatste run: {last_run} {last_status}\n\n```\n{last_output}\n```"


def list_schedule_examples() -> str:
    """
    Toont voorbeelden van geldige schedule-formaten voor het plannen van taken.
    """
    return """**Geldige schedule-formaten:**

**Interval:**
  `elke 5 minuten`         `every 5 minutes`
  `elke 30 minuten`        `elk uur` / `every hour`
  `elke 2 uur`             `elke 1 seconde`

**Dagelijks:**
  `dagelijks om 09:00`     `daily at 14:30`

**Dag van de week:**
  `elke maandag om 08:00`  `every friday at 17:00`
  `werkdagen om 07:30`     `weekdays at 09:00`

**Cron expressie (5 velden):**
  `0 9 * * 1-5`   (werkdagen om 09:00)
  `*/15 * * * *`  (elke 15 minuten)
  `0 0 * * 0`     (elke zondag om middernacht)
"""
