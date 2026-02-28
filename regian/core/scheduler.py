# regian/core/scheduler.py
"""
Regian Scheduler — APScheduler-gebaseerde taakplanner.

Taken worden opgeslagen in jobs.json in de project root.
De scheduler draait als achtergrondthread naast Streamlit of CLI.
"""
import json
import logging
import re
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_JOBS_FILE = Path(__file__).parent.parent.parent / "regian_jobs.json"
_scheduler: Optional[BackgroundScheduler] = None
_lock = threading.Lock()


# ── Opslag ─────────────────────────────────────────────────────────────────────

def _load_jobs() -> dict:
    if _JOBS_FILE.exists():
        try:
            return json.loads(_JOBS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_jobs(jobs: dict):
    _JOBS_FILE.write_text(json.dumps(jobs, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Schedule parser ────────────────────────────────────────────────────────────

_INTERVAL_PATTERNS = [
    # NL
    (r"elke?\s+(\d+)\s+(?:seconde[n]?|sec)",    lambda m: IntervalTrigger(seconds=int(m.group(1)))),
    (r"elke?\s+(\d+)\s+(?:minuut|minuten|min)",  lambda m: IntervalTrigger(minutes=int(m.group(1)))),
    (r"elke?\s+(\d+)\s+(?:uur|uren|u)\b",        lambda m: IntervalTrigger(hours=int(m.group(1)))),
    (r"elk\s+uur",                                lambda m: IntervalTrigger(hours=1)),
    (r"elke?\s+minuut",                           lambda m: IntervalTrigger(minutes=1)),
    # EN
    (r"every\s+(\d+)\s+seconds?",                 lambda m: IntervalTrigger(seconds=int(m.group(1)))),
    (r"every\s+(\d+)\s+minutes?",                 lambda m: IntervalTrigger(minutes=int(m.group(1)))),
    (r"every\s+(\d+)\s+hours?",                   lambda m: IntervalTrigger(hours=int(m.group(1)))),
    (r"every\s+hour",                             lambda m: IntervalTrigger(hours=1)),
    (r"every\s+minute",                           lambda m: IntervalTrigger(minutes=1)),
]

_DAY_MAP = {
    "maandag": "mon", "dinsdag": "tue", "woensdag": "wed",
    "donderdag": "thu", "vrijdag": "fri", "zaterdag": "sat", "zondag": "sun",
    "monday": "mon", "tuesday": "tue", "wednesday": "wed",
    "thursday": "thu", "friday": "fri", "saturday": "sat", "sunday": "sun",
    "werkdagen": "mon-fri", "weekdays": "mon-fri",
}

_DAILY_PATTERN = re.compile(
    r"(?:dagelijks|daily|elke dag|every day)\s+(?:om|at)\s+(\d{1,2}):(\d{2})", re.I
)
_WEEKDAY_PATTERN = re.compile(
    r"(?:werkdagen|weekdays|weekdagen)\s+(?:om|at)\s+(\d{1,2}):(\d{2})", re.I
)
_DAY_PATTERN = re.compile(
    r"(?:elke?|every)\s+(\w+)\s+(?:om|at)\s+(\d{1,2}):(\d{2})", re.I
)
_CRON_PATTERN = re.compile(
    r"^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)$"  # standaard 5-veld cron
)


def parse_schedule(schedule_str: str):
    """
    Zet een leesbare schedule-string om naar een APScheduler trigger.

    Voorbeelden:
      "elke 5 minuten"          → IntervalTrigger(minutes=5)
      "dagelijks om 09:00"      → CronTrigger(hour=9, minute=0)
      "elke maandag om 08:30"   → CronTrigger(day_of_week='mon', hour=8, minute=30)
      "werkdagen om 07:00"      → CronTrigger(day_of_week='mon-fri', hour=7, minute=0)
      "0 9 * * 1-5"             → CronTrigger(minute=0, hour=9, day='*', month='*', day_of_week='1-5')
    """
    s = schedule_str.strip().lower()

    # Interval patronen
    for pattern, builder in _INTERVAL_PATTERNS:
        m = re.search(pattern, s, re.I)
        if m:
            return builder(m)

    # Dagelijks om HH:MM
    m = _DAILY_PATTERN.search(s)
    if m:
        return CronTrigger(hour=int(m.group(1)), minute=int(m.group(2)))

    # Werkdagen om HH:MM
    m = _WEEKDAY_PATTERN.search(s)
    if m:
        return CronTrigger(day_of_week="mon-fri", hour=int(m.group(1)), minute=int(m.group(2)))

    # Dag van de week om HH:MM
    m = _DAY_PATTERN.search(s)
    if m:
        day_nl = m.group(1).lower()
        day_cron = _DAY_MAP.get(day_nl)
        if day_cron:
            return CronTrigger(
                day_of_week=day_cron,
                hour=int(m.group(2)),
                minute=int(m.group(3)),
            )

    # Standaard cron expressie (5 velden)
    m = _CRON_PATTERN.match(s)
    if m:
        return CronTrigger(
            minute=m.group(1),
            hour=m.group(2),
            day=m.group(3),
            month=m.group(4),
            day_of_week=m.group(5),
        )

    raise ValueError(
        f"Onbekend schedule formaat: '{schedule_str}'\n"
        "Geldige voorbeelden:\n"
        "  'elke 15 minuten'  |  'dagelijks om 09:00'\n"
        "  'elke maandag om 08:00'  |  'werkdagen om 07:30'\n"
        "  '0 9 * * 1-5'  (cron expressie)"
    )


# ── Job uitvoering ─────────────────────────────────────────────────────────────

def _execute_job(job_id: str):
    """Callback die APScheduler aanroept bij elke trigger."""
    jobs = _load_jobs()
    job = jobs.get(job_id)
    if not job or not job.get("enabled", True):
        return

    job_type = job.get("type", "command")
    task = job.get("task", "")
    output = ""

    try:
        if job_type == "shell":
            result = subprocess.run(
                task, shell=True, capture_output=True, text=True, timeout=60,
                cwd=str(Path(__file__).parent.parent.parent),
            )
            output = result.stdout.strip() or result.stderr.strip() or "OK"

        elif job_type == "command":
            from regian.core.agent import registry
            parts = task.lstrip("/").split(" ", 1)
            name = parts[0].strip()
            raw_args = parts[1].strip() if len(parts) > 1 else ""
            output = registry.call_by_string(name, raw_args)

        elif job_type == "prompt":
            from regian.core.agent import OrchestratorAgent
            orch = OrchestratorAgent()
            output = orch.run(task)

        status = "✅"
    except Exception as e:
        output = str(e)
        status = "❌"

    # Sla laatste run op
    jobs = _load_jobs()
    if job_id in jobs:
        jobs[job_id]["last_run"] = datetime.now().isoformat(timespec="seconds")
        jobs[job_id]["last_status"] = status
        jobs[job_id]["last_output"] = output[:500]
        _save_jobs(jobs)

    logger.info(f"[Cron] {status} {job_id}: {output[:100]}")


# ── Scheduler beheer ───────────────────────────────────────────────────────────

def get_scheduler() -> BackgroundScheduler:
    """Geeft de globale scheduler terug, start hem indien nodig."""
    global _scheduler
    with _lock:
        if _scheduler is None or not _scheduler.running:
            _scheduler = BackgroundScheduler(timezone="Europe/Brussels")
            _load_all_jobs(_scheduler)
            _scheduler.start()
            logger.info(f"[Cron] Scheduler gestart met {len(_scheduler.get_jobs())} taken.")
    return _scheduler


def _load_all_jobs(scheduler: BackgroundScheduler):
    """Laad alle opgeslagen taken in de scheduler."""
    jobs = _load_jobs()
    for job_id, job in jobs.items():
        if not job.get("enabled", True):
            continue
        try:
            trigger = parse_schedule(job["schedule"])
            scheduler.add_job(
                _execute_job,
                trigger=trigger,
                id=job_id,
                args=[job_id],
                replace_existing=True,
            )
        except Exception as e:
            logger.warning(f"[Cron] Kon job '{job_id}' niet laden: {e}")


def add_scheduled_job(
    job_id: str,
    task: str,
    job_type: str,
    schedule: str,
    description: str = "",
) -> str:
    """Voeg een taak toe aan de scheduler en sla op in jobs.json."""
    try:
        trigger = parse_schedule(schedule)
    except ValueError as e:
        return f"❌ {e}"

    jobs = _load_jobs()
    jobs[job_id] = {
        "id": job_id,
        "task": task,
        "type": job_type,
        "schedule": schedule,
        "description": description,
        "enabled": True,
        "created": datetime.now().isoformat(timespec="seconds"),
        "last_run": None,
        "last_status": None,
        "last_output": None,
    }
    _save_jobs(jobs)

    scheduler = get_scheduler()
    scheduler.add_job(
        _execute_job,
        trigger=trigger,
        id=job_id,
        args=[job_id],
        replace_existing=True,
    )
    return job_id


def remove_scheduled_job(job_id: str) -> bool:
    jobs = _load_jobs()
    if job_id not in jobs:
        return False
    del jobs[job_id]
    _save_jobs(jobs)
    scheduler = get_scheduler()
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass
    return True


def toggle_scheduled_job(job_id: str, enabled: bool) -> bool:
    jobs = _load_jobs()
    if job_id not in jobs:
        return False
    jobs[job_id]["enabled"] = enabled
    _save_jobs(jobs)
    scheduler = get_scheduler()
    if enabled:
        try:
            trigger = parse_schedule(jobs[job_id]["schedule"])
            scheduler.add_job(
                _execute_job,
                trigger=trigger,
                id=job_id,
                args=[job_id],
                replace_existing=True,
            )
        except Exception:
            pass
    else:
        try:
            scheduler.remove_job(job_id)
        except Exception:
            pass
    return True


def run_job_now_by_id(job_id: str):
    """Voer een taak onmiddellijk uit (buiten het schema)."""
    _execute_job(job_id)


def get_all_jobs() -> dict:
    return _load_jobs()


def get_next_run(job_id: str) -> Optional[str]:
    scheduler = get_scheduler()
    job = scheduler.get_job(job_id)
    if job and job.next_run_time:
        return job.next_run_time.strftime("%d/%m/%Y %H:%M:%S")
    return None
