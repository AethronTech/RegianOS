# tests/test_core_action_log.py
"""Tests voor regian/core/action_log.py"""
import json
import pytest
from pathlib import Path


@pytest.fixture
def log_file(tmp_path, monkeypatch):
    """Patch _get_log_file naar een tijdelijk bestand zodat tests geïsoleerd zijn."""
    import regian.core.action_log as al
    log = tmp_path / "test_action_log.jsonl"
    monkeypatch.setattr(al, "_get_log_file", lambda: log)
    return log


# ── log_action ────────────────────────────────────────────────────────────────

class TestLogAction:
    def test_creates_file_on_first_write(self, log_file):
        from regian.core.action_log import log_action
        assert not log_file.exists()
        log_action("write_file", {"path": "a.txt"}, "Succes")
        assert log_file.exists()

    def test_entry_contains_expected_fields(self, log_file):
        from regian.core.action_log import log_action
        log_action("run_shell", {"command": "echo hi"}, "hi", source="cli")
        raw = json.loads(log_file.read_text().strip())
        assert raw["tool"] == "run_shell"
        assert raw["source"] == "cli"
        assert raw["args"] == {"command": "echo hi"}
        assert raw["result"] == "hi"
        assert "ts" in raw

    def test_group_id_stored_when_given(self, log_file):
        from regian.core.action_log import log_action
        log_action("run_shell", {}, "ok", group_id="abc123")
        raw = json.loads(log_file.read_text().strip())
        assert raw["group_id"] == "abc123"

    def test_no_group_id_field_when_omitted(self, log_file):
        from regian.core.action_log import log_action
        log_action("run_shell", {}, "ok")
        raw = json.loads(log_file.read_text().strip())
        assert "group_id" not in raw

    def test_result_truncated_to_300_chars(self, log_file):
        from regian.core.action_log import log_action
        long_result = "x" * 500
        log_action("tool", {}, long_result)
        raw = json.loads(log_file.read_text().strip())
        assert len(raw["result"]) == 300

    def test_multiple_entries_appended(self, log_file):
        from regian.core.action_log import log_action
        log_action("tool_a", {}, "res_a")
        log_action("tool_b", {}, "res_b")
        lines = [l for l in log_file.read_text().splitlines() if l.strip()]
        assert len(lines) == 2
        assert json.loads(lines[0])["tool"] == "tool_a"
        assert json.loads(lines[1])["tool"] == "tool_b"

    def test_default_source_is_chat(self, log_file):
        from regian.core.action_log import log_action
        log_action("t", {}, "r")
        raw = json.loads(log_file.read_text().strip())
        assert raw["source"] == "chat"


# ── get_log ───────────────────────────────────────────────────────────────────

class TestGetLog:
    def test_returns_empty_list_when_no_file(self, log_file):
        from regian.core.action_log import get_log
        assert get_log() == []

    def test_returns_entries_newest_first(self, log_file):
        from regian.core.action_log import log_action, get_log
        log_action("first", {}, "r1")
        log_action("second", {}, "r2")
        entries = get_log()
        # nieuwste eerst
        assert entries[0]["tool"] == "second"
        assert entries[1]["tool"] == "first"

    def test_limit_is_respected(self, log_file):
        from regian.core.action_log import log_action, get_log
        for i in range(10):
            log_action(f"tool_{i}", {}, "r")
        entries = get_log(limit=3)
        assert len(entries) == 3

    def test_skips_corrupt_lines(self, log_file):
        from regian.core.action_log import get_log
        log_file.write_text('{"tool":"ok","ts":"x","source":"c","args":{},"result":"r"}\nnot json\n')
        entries = get_log()
        assert len(entries) == 1
        assert entries[0]["tool"] == "ok"


# ── log_count ──────────────────────────────────────────────────────────────────

class TestLogCount:
    def test_zero_when_no_file(self, log_file):
        from regian.core.action_log import log_count
        assert log_count() == 0

    def test_counts_written_entries(self, log_file):
        from regian.core.action_log import log_action, log_count
        log_action("a", {}, "r")
        log_action("b", {}, "r")
        assert log_count() == 2


# ── clear_log ─────────────────────────────────────────────────────────────────

class TestClearLog:
    def test_clears_existing_file(self, log_file):
        from regian.core.action_log import log_action, clear_log, log_count
        log_action("a", {}, "r")
        assert log_count() == 1
        result = clear_log()
        assert "✅" in result
        assert log_count() == 0

    def test_clear_on_nonexistent_file_is_safe(self, log_file):
        from regian.core.action_log import clear_log
        # bestand bestaat nog niet
        result = clear_log()
        assert "✅" in result

    def test_new_entries_after_clear(self, log_file):
        from regian.core.action_log import log_action, clear_log, get_log
        log_action("old", {}, "r")
        clear_log()
        log_action("new", {}, "r")
        entries = get_log()
        assert len(entries) == 1
        assert entries[0]["tool"] == "new"


# ── _trim ──────────────────────────────────────────────────────────────────────

class TestTrim:
    def test_trim_keeps_max_entries(self, log_file, monkeypatch):
        monkeypatch.setenv("LOG_MAX_ENTRIES", "5")
        from regian.core.action_log import log_action, log_count
        for i in range(10):
            log_action(f"tool_{i}", {}, "r")
        assert log_count() <= 5

    def test_trim_keeps_newest(self, log_file, monkeypatch):
        monkeypatch.setenv("LOG_MAX_ENTRIES", "3")
        from regian.core.action_log import log_action, get_log
        for i in range(6):
            log_action(f"tool_{i}", {}, f"r{i}")
        entries = get_log()
        tools = [e["tool"] for e in entries]
        # de laatste 3 ingevoerde moeten aanwezig zijn
        assert "tool_5" in tools
        assert "tool_4" in tools
        assert "tool_3" in tools

    def test_trim_no_file_is_safe(self, log_file):
        import regian.core.action_log as al
        al._trim()  # mag geen exceptie gooien


# ── get_log_grouped ───────────────────────────────────────────────────────────

class TestGetLogGrouped:
    def test_returns_empty_when_no_file(self, log_file):
        from regian.core.action_log import get_log_grouped
        assert get_log_grouped() == []

    def test_groups_by_group_id(self, log_file):
        from regian.core.action_log import log_action, get_log_grouped
        log_action("__prompt__", {"prompt": "maak bestand"}, "", source="chat", group_id="g1")
        log_action("write_file", {"path": "a.txt"}, "Succes", source="chat", group_id="g1")
        log_action("run_shell", {"command": "ls"}, "a.txt", source="chat", group_id="g1")
        groups = get_log_grouped()
        assert len(groups) == 1
        assert groups[0]["prompt"] == "maak bestand"
        assert len(groups[0]["steps"]) == 2

    def test_multiple_groups(self, log_file):
        from regian.core.action_log import log_action, get_log_grouped
        log_action("__prompt__", {"prompt": "eerste"}, "", source="chat", group_id="g1")
        log_action("write_file", {}, "ok", source="chat", group_id="g1")
        log_action("__prompt__", {"prompt": "tweede"}, "", source="chat", group_id="g2")
        log_action("run_shell", {}, "ok", source="chat", group_id="g2")
        groups = get_log_grouped()
        assert len(groups) == 2
        prompts = {g["prompt"] for g in groups}
        assert "eerste" in prompts
        assert "tweede" in prompts

    def test_entries_without_group_id_not_returned_as_group(self, log_file):
        from regian.core.action_log import log_action, get_log_grouped
        log_action("run_shell", {}, "ok")  # geen group_id
        groups = get_log_grouped()
        assert len(groups) == 0

    def test_prompt_missing_but_steps_still_shown(self, log_file):
        from regian.core.action_log import log_action, get_log_grouped
        # groep zonder __prompt__ entry
        log_action("write_file", {}, "ok", group_id="g9")
        groups = get_log_grouped()
        assert len(groups) == 1
        assert groups[0]["prompt"] == ""
        assert len(groups[0]["steps"]) == 1

    def test_limit_groups_respected(self, log_file):
        from regian.core.action_log import log_action, get_log_grouped
        for i in range(10):
            log_action("__prompt__", {"prompt": f"vraag {i}"}, "", group_id=f"g{i}")
            log_action("run_shell", {}, "ok", group_id=f"g{i}")
        groups = get_log_grouped(limit_groups=3)
        assert len(groups) == 3

    def test_grouped_newest_first(self, log_file):
        """Schrijf twee groepen met bekende ts-waarden direct in het logbestand."""
        import json
        line_old = json.dumps({"ts": "2026-03-01T08:00:00", "source": "chat", "tool": "__prompt__",
                                "args": {"prompt": "oud"}, "result": "", "group_id": "g_old"})
        line_new = json.dumps({"ts": "2026-03-01T09:00:00", "source": "chat", "tool": "__prompt__",
                                "args": {"prompt": "nieuw"}, "result": "", "group_id": "g_new"})
        log_file.write_text(line_old + "\n" + line_new + "\n")
        from regian.core.action_log import get_log_grouped
        groups = get_log_grouped()
        assert groups[0]["prompt"] == "nieuw"
