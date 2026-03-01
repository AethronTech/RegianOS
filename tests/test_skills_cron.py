# tests/test_skills_cron.py
"""Tests voor regian/skills/cron.py — job scheduling via gemockte scheduler."""
import pytest
from unittest.mock import patch, MagicMock


# ── Helpers ────────────────────────────────────────────────────────────────────

def _mock_add_job(job_id, task, job_type, schedule, description=""):
    """Simpele mock: geeft job_id terug als alles klopt (= succes)."""
    return job_id


def _mock_add_job_fail(job_id, task, job_type, schedule, description=""):
    return "❌ scheduler niet beschikbaar"


# ── schedule_command ───────────────────────────────────────────────────────────

class TestScheduleCommand:
    def test_success(self):
        from regian.skills.cron import schedule_command
        with patch("regian.core.scheduler.add_scheduled_job", side_effect=_mock_add_job):
            result = schedule_command("mijn_job", "/repo_list", "elke 5 minuten")
        assert "mijn_job" in result
        assert "✅" in result

    def test_adds_slash_prefix(self):
        """Commando zonder / prefix krijgt er één."""
        from regian.skills.cron import schedule_command
        captured = {}
        def capture_add(job_id, task, job_type, schedule, description=""):
            captured["task"] = task
            return job_id
        with patch("regian.core.scheduler.add_scheduled_job", side_effect=capture_add):
            schedule_command("j", "repo_list", "elke 5 minuten")
        assert captured["task"].startswith("/")

    def test_slash_not_doubled(self):
        """Commando dat al / heeft mag niet dubbel //-prefix krijgen."""
        from regian.skills.cron import schedule_command
        captured = {}
        def capture_add(job_id, task, job_type, schedule, description=""):
            captured["task"] = task
            return job_id
        with patch("regian.core.scheduler.add_scheduled_job", side_effect=capture_add):
            schedule_command("j", "/repo_list", "elke 5 minuten")
        assert not captured["task"].startswith("//")

    def test_scheduler_error_propagated(self):
        from regian.skills.cron import schedule_command
        with patch("regian.core.scheduler.add_scheduled_job", side_effect=_mock_add_job_fail):
            result = schedule_command("j", "/repo_list", "elke 5 minuten")
        assert "❌" in result


# ── schedule_shell ─────────────────────────────────────────────────────────────

class TestScheduleShell:
    def test_success(self):
        from regian.skills.cron import schedule_shell
        with patch("regian.core.scheduler.add_scheduled_job", side_effect=_mock_add_job):
            result = schedule_shell("backup", "git pull", "dagelijks om 02:00")
        assert "backup" in result
        assert "✅" in result

    def test_job_type_is_shell(self):
        from regian.skills.cron import schedule_shell
        captured = {}
        def capture_add(job_id, task, job_type, schedule, description=""):
            captured["type"] = job_type
            return job_id
        with patch("regian.core.scheduler.add_scheduled_job", side_effect=capture_add):
            schedule_shell("j", "ls", "elke 10 minuten")
        assert captured["type"] == "shell"


# ── schedule_prompt ────────────────────────────────────────────────────────────

class TestSchedulePrompt:
    def test_success(self):
        from regian.skills.cron import schedule_prompt
        with patch("regian.core.scheduler.add_scheduled_job", side_effect=_mock_add_job):
            result = schedule_prompt("ai_check", "Controleer issues", "dagelijks om 09:00")
        assert "ai_check" in result
        assert "✅" in result

    def test_job_type_is_prompt(self):
        from regian.skills.cron import schedule_prompt
        captured = {}
        def capture_add(job_id, task, job_type, schedule, description=""):
            captured["type"] = job_type
            return job_id
        with patch("regian.core.scheduler.add_scheduled_job", side_effect=capture_add):
            schedule_prompt("j", "doe iets", "elke 5 minuten")
        assert captured["type"] == "prompt"


# ── remove_job ─────────────────────────────────────────────────────────────────

class TestRemoveJob:
    def test_remove_existing(self):
        from regian.skills.cron import remove_job
        with patch("regian.core.scheduler.remove_scheduled_job", return_value=True):
            result = remove_job("mijn_job")
        assert "✅" in result
        assert "mijn_job" in result

    def test_remove_nonexistent(self):
        from regian.skills.cron import remove_job
        with patch("regian.core.scheduler.remove_scheduled_job", return_value=False):
            result = remove_job("bestaat_niet")
        assert "❌" in result


# ── enable_job / disable_job ───────────────────────────────────────────────────

class TestToggleJob:
    def test_enable_success(self):
        from regian.skills.cron import enable_job
        with patch("regian.core.scheduler.toggle_scheduled_job", return_value=True):
            result = enable_job("j")
        assert "✅" in result

    def test_enable_fail(self):
        from regian.skills.cron import enable_job
        with patch("regian.core.scheduler.toggle_scheduled_job", return_value=False):
            result = enable_job("bestaat_niet")
        assert "❌" in result

    def test_disable_success(self):
        from regian.skills.cron import disable_job
        with patch("regian.core.scheduler.toggle_scheduled_job", return_value=True):
            result = disable_job("j")
        assert "⏸️" in result or "gepauzeerd" in result.lower()


# ── run_job_now ────────────────────────────────────────────────────────────────

class TestRunJobNow:
    def test_run_existing(self):
        from regian.skills.cron import run_job_now
        with patch("regian.core.scheduler.get_all_jobs", return_value={"j": {"type": "shell", "task": "echo hi"}}):
            with patch("regian.core.scheduler._execute_job", return_value=None) as mock_exec:
                result = run_job_now("j")
        assert "j" in result

    def test_run_nonexistent(self):
        from regian.skills.cron import run_job_now
        with patch("regian.core.scheduler.get_all_jobs", return_value={}):
            result = run_job_now("bestaat_niet")
        assert "❌" in result


# ── list_jobs ──────────────────────────────────────────────────────────────────

class TestListJobs:
    def test_empty(self):
        from regian.skills.cron import list_jobs
        with patch("regian.core.scheduler.get_all_jobs", return_value={}):
            result = list_jobs()
        assert isinstance(result, str)
        assert "geen" in result.lower() or result.strip() != ""

    def test_with_jobs(self):
        from regian.skills.cron import list_jobs
        jobs = {
            "job1": {"type": "shell", "task": "echo hi", "enabled": True,
                     "schedule": "elke 5 minuten", "description": "test"},
        }
        with patch("regian.core.scheduler.get_all_jobs", return_value=jobs):
            with patch("regian.core.scheduler.get_next_run", return_value="morgen"):
                result = list_jobs()
        assert "job1" in result
