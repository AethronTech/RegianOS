# tests/test_core_scheduler.py
"""Tests voor regian/core/scheduler.py — schedule parser zonder echte scheduler."""
import pytest
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger


# ── parse_schedule — interval triggers ────────────────────────────────────────

class TestParseScheduleInterval:
    @pytest.mark.parametrize("schedule,expected_seconds", [
        ("elke 30 seconden", 30),
        ("elke 1 seconde", 1),
        ("every 10 seconds", 10),
        ("every 1 second", 1),
    ])
    def test_seconds(self, schedule, expected_seconds):
        from regian.core.scheduler import parse_schedule
        trigger = parse_schedule(schedule)
        assert isinstance(trigger, IntervalTrigger)
        assert trigger.interval.total_seconds() == expected_seconds

    @pytest.mark.parametrize("schedule,expected_minutes", [
        ("elke 5 minuten", 5),
        ("elke 15 minuten", 15),
        ("elke 1 minuut", 1),
        ("every 5 minutes", 5),
        ("every 30 minutes", 30),
        ("every minute", 1),
        ("elke minuut", 1),
    ])
    def test_minutes(self, schedule, expected_minutes):
        from regian.core.scheduler import parse_schedule
        trigger = parse_schedule(schedule)
        assert isinstance(trigger, IntervalTrigger)
        assert trigger.interval.total_seconds() == expected_minutes * 60

    @pytest.mark.parametrize("schedule,expected_hours", [
        ("elke 2 uur", 2),
        ("elke 1 uur", 1),
        ("every 4 hours", 4),
        ("every hour", 1),
        ("elk uur", 1),
    ])
    def test_hours(self, schedule, expected_hours):
        from regian.core.scheduler import parse_schedule
        trigger = parse_schedule(schedule)
        assert isinstance(trigger, IntervalTrigger)
        assert trigger.interval.total_seconds() == expected_hours * 3600


# ── parse_schedule — cron triggers ────────────────────────────────────────────

class TestParseScheduleCron:
    def test_daily_at_time(self):
        from regian.core.scheduler import parse_schedule
        trigger = parse_schedule("dagelijks om 09:00")
        assert isinstance(trigger, CronTrigger)

    def test_daily_en(self):
        from regian.core.scheduler import parse_schedule
        trigger = parse_schedule("daily at 08:30")
        assert isinstance(trigger, CronTrigger)

    def test_werkdagen(self):
        from regian.core.scheduler import parse_schedule
        trigger = parse_schedule("werkdagen om 07:30")
        assert isinstance(trigger, CronTrigger)

    def test_weekdays_en(self):
        from regian.core.scheduler import parse_schedule
        trigger = parse_schedule("weekdays at 09:00")
        assert isinstance(trigger, CronTrigger)

    @pytest.mark.parametrize("schedule,day_cron", [
        ("elke maandag om 08:00", "mon"),
        ("elke dinsdag om 09:00", "tue"),
        ("elke woensdag om 10:00", "wed"),
        ("elke donderdag om 11:00", "thu"),
        ("elke vrijdag om 17:00", "fri"),
        ("elke zaterdag om 12:00", "sat"),
        ("elke zondag om 14:00", "sun"),
        ("every monday at 08:00", "mon"),
        ("every friday at 17:00", "fri"),
    ])
    def test_weekday_patterns(self, schedule, day_cron):
        from regian.core.scheduler import parse_schedule
        trigger = parse_schedule(schedule)
        assert isinstance(trigger, CronTrigger)

    def test_cron_expression_5fields(self):
        from regian.core.scheduler import parse_schedule
        trigger = parse_schedule("0 9 * * 1-5")
        assert isinstance(trigger, CronTrigger)

    def test_cron_every_midnight(self):
        from regian.core.scheduler import parse_schedule
        trigger = parse_schedule("0 0 * * *")
        assert isinstance(trigger, CronTrigger)

    def test_cron_hourly(self):
        from regian.core.scheduler import parse_schedule
        trigger = parse_schedule("0 * * * *")
        assert isinstance(trigger, CronTrigger)


# ── parse_schedule — fouten ────────────────────────────────────────────────────

class TestParseScheduleErrors:
    def test_unknown_format_raises(self):
        from regian.core.scheduler import parse_schedule
        with pytest.raises(ValueError):
            parse_schedule("volledig onbekend formaat xyz123qwerty")

    def test_empty_string_raises(self):
        from regian.core.scheduler import parse_schedule
        with pytest.raises(ValueError):
            parse_schedule("")

    def test_partial_cron_raises(self):
        from regian.core.scheduler import parse_schedule
        with pytest.raises(ValueError):
            parse_schedule("0 9 * *")  # maar 4 velden


# ── _load_jobs / _save_jobs ────────────────────────────────────────────────────

class TestJobPersistence:
    def test_load_returns_empty_dict_when_no_file(self, tmp_path, monkeypatch):
        import regian.core.scheduler as sched
        monkeypatch.setattr(sched, "_get_jobs_file", lambda: tmp_path / "nonexistent.json")
        result = sched._load_jobs()
        assert result == {}

    def test_save_and_load_roundtrip(self, tmp_path, monkeypatch):
        import regian.core.scheduler as sched
        jobs_file = tmp_path / "jobs.json"
        monkeypatch.setattr(sched, "_get_jobs_file", lambda: jobs_file)
        jobs = {"job1": {"type": "shell", "task": "echo hi", "enabled": True}}
        sched._save_jobs(jobs)
        loaded = sched._load_jobs()
        assert loaded == jobs

    def test_load_handles_corrupt_json(self, tmp_path, monkeypatch):
        import regian.core.scheduler as sched
        jobs_file = tmp_path / "corrupt.json"
        jobs_file.write_text("{ niet geldig json !!!", encoding="utf-8")
        monkeypatch.setattr(sched, "_get_jobs_file", lambda: jobs_file)
        result = sched._load_jobs()
        assert result == {}


# ── add / remove / toggle / get_all_jobs ─────────────────────────────────────

@pytest.fixture
def isolated_scheduler(tmp_path, monkeypatch):
    """Patcht _get_jobs_file en get_scheduler, zodat geen echte scheduler start."""
    from unittest.mock import MagicMock
    import regian.core.scheduler as sched

    jobs_file = tmp_path / "jobs.json"
    monkeypatch.setattr(sched, "_get_jobs_file", lambda: jobs_file)

    mock_scheduler = MagicMock()
    monkeypatch.setattr(sched, "get_scheduler", lambda: mock_scheduler)
    return sched, mock_scheduler


class TestAddScheduledJob:
    def test_adds_job_to_persistence(self, isolated_scheduler):
        sched, _ = isolated_scheduler
        result = sched.add_scheduled_job("job1", "echo hi", "shell", "elke 1 minuut", "test")
        assert result == "job1"
        jobs = sched._load_jobs()
        assert "job1" in jobs
        assert jobs["job1"]["task"] == "echo hi"

    def test_job_enabled_by_default(self, isolated_scheduler):
        sched, _ = isolated_scheduler
        sched.add_scheduled_job("job2", "ls", "shell", "elke 5 minuten")
        jobs = sched._load_jobs()
        assert jobs["job2"]["enabled"] is True

    def test_invalid_schedule_returns_error(self, isolated_scheduler):
        sched, _ = isolated_scheduler
        result = sched.add_scheduled_job("job_bad", "echo", "shell", "dit is geen schema")
        assert "❌" in result
        jobs = sched._load_jobs()
        assert "job_bad" not in jobs

    def test_shell_job_added_to_scheduler(self, isolated_scheduler):
        sched, mock_sched = isolated_scheduler
        sched.add_scheduled_job("job3", "echo ok", "shell", "elke 1 minuut")
        mock_sched.add_job.assert_called_once()


class TestRemoveScheduledJob:
    def test_removes_existing_job(self, isolated_scheduler):
        sched, _ = isolated_scheduler
        sched.add_scheduled_job("job_rm", "echo", "shell", "elke 1 minuut")
        result = sched.remove_scheduled_job("job_rm")
        assert result is True
        assert "job_rm" not in sched._load_jobs()

    def test_returns_false_for_nonexistent(self, isolated_scheduler):
        sched, _ = isolated_scheduler
        result = sched.remove_scheduled_job("bestaat_niet")
        assert result is False


class TestToggleScheduledJob:
    def test_disable_job(self, isolated_scheduler):
        sched, _ = isolated_scheduler
        sched.add_scheduled_job("job_tog", "echo", "shell", "elke 1 minuut")
        result = sched.toggle_scheduled_job("job_tog", False)
        assert result is True
        jobs = sched._load_jobs()
        assert jobs["job_tog"]["enabled"] is False

    def test_enable_job(self, isolated_scheduler):
        sched, _ = isolated_scheduler
        sched.add_scheduled_job("job_en", "echo", "shell", "elke 1 minuut")
        sched.toggle_scheduled_job("job_en", False)
        result = sched.toggle_scheduled_job("job_en", True)
        assert result is True
        jobs = sched._load_jobs()
        assert jobs["job_en"]["enabled"] is True

    def test_returns_false_for_nonexistent(self, isolated_scheduler):
        sched, _ = isolated_scheduler
        result = sched.toggle_scheduled_job("bestaat_niet", True)
        assert result is False


class TestGetAllJobs:
    def test_returns_empty_when_no_file(self, isolated_scheduler):
        sched, _ = isolated_scheduler
        jobs = sched.get_all_jobs()
        assert jobs == {}

    def test_returns_all_saved_jobs(self, isolated_scheduler):
        sched, _ = isolated_scheduler
        sched.add_scheduled_job("j1", "echo a", "shell", "elke 1 minuut")
        sched.add_scheduled_job("j2", "echo b", "shell", "elke 2 minuten")
        all_jobs = sched.get_all_jobs()
        assert "j1" in all_jobs
        assert "j2" in all_jobs


class TestGetNextRun:
    def test_returns_none_when_job_not_in_scheduler(self, isolated_scheduler):
        sched, mock_sched = isolated_scheduler
        mock_sched.get_job.return_value = None
        result = sched.get_next_run("onbekend")
        assert result is None

    def test_returns_formatted_time_when_scheduled(self, isolated_scheduler):
        from unittest.mock import MagicMock
        from datetime import datetime, timezone
        sched, mock_sched = isolated_scheduler
        mock_job = MagicMock()
        mock_job.next_run_time = datetime(2026, 3, 1, 9, 0, 0, tzinfo=timezone.utc)
        mock_sched.get_job.return_value = mock_job
        result = sched.get_next_run("job_x")
        assert "01/03/2026" in result
        assert "09:00:00" in result
