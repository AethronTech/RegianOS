# tests/test_skills_tickets.py
"""Tests voor regian/skills/tickets.py — Kanban ticket-systeem."""
import pytest
from pathlib import Path
import json


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def ticket_project(tmp_path, monkeypatch):
    """Zet een tijdelijk project-pad op voor tickettests."""
    proj = tmp_path / "mijn_project"
    proj.mkdir()
    monkeypatch.setattr(
        "regian.skills.tickets._tickets_file",
        lambda: proj / ".regian_tickets.json",
    )
    return proj


# ── create_ticket ──────────────────────────────────────────────────────────────

class TestCreateTicket:
    def test_aanmaken_nieuw_ticket(self, ticket_project):
        from regian.skills.tickets import create_ticket, _load
        result = create_ticket("Bug in login", "Kan niet inloggen met Google")
        assert "✅" in result
        tickets = _load(ticket_project / ".regian_tickets.json")
        assert len(tickets) == 1
        assert tickets[0]["title"] == "Bug in login"
        assert tickets[0]["status"] == "todo"

    def test_ticket_krijgt_uniek_id(self, ticket_project):
        from regian.skills.tickets import create_ticket, _load
        create_ticket("Ticket A", "")
        create_ticket("Ticket B", "")
        tickets = _load(ticket_project / ".regian_tickets.json")
        ids = [t["id"] for t in tickets]
        assert len(set(ids)) == 2

    def test_geen_project_geeft_fout(self, monkeypatch):
        monkeypatch.setattr("regian.skills.tickets._tickets_file", lambda: None)
        from regian.skills.tickets import create_ticket
        result = create_ticket("test", "")
        assert "❌" in result

    def test_titel_wordt_gestript(self, ticket_project):
        from regian.skills.tickets import create_ticket, _load
        create_ticket("  Spaties rondom  ", "")
        tickets = _load(ticket_project / ".regian_tickets.json")
        assert tickets[0]["title"] == "Spaties rondom"


# ── list_tickets ───────────────────────────────────────────────────────────────

class TestListTickets:
    def test_lege_lijst(self, ticket_project):
        from regian.skills.tickets import list_tickets
        result = list_tickets()
        assert "Geen tickets" in result

    def test_toont_alle_tickets(self, ticket_project):
        from regian.skills.tickets import create_ticket, list_tickets
        create_ticket("Ticket 1", "")
        create_ticket("Ticket 2", "")
        result = list_tickets()
        assert "Ticket 1" in result
        assert "Ticket 2" in result

    def test_filter_op_status(self, ticket_project):
        from regian.skills.tickets import create_ticket, list_tickets
        create_ticket("A", "")
        create_ticket("B", "")
        result = list_tickets(status="todo")
        assert "A" in result
        result_none = list_tickets(status="done")
        assert "Geen tickets" in result_none

    def test_geen_project_geeft_fout(self, monkeypatch):
        monkeypatch.setattr("regian.skills.tickets._tickets_file", lambda: None)
        from regian.skills.tickets import list_tickets
        assert "❌" in list_tickets()


# ── move_ticket ────────────────────────────────────────────────────────────────

class TestMoveTicket:
    def test_verplaats_naar_review(self, ticket_project):
        from regian.skills.tickets import create_ticket, move_ticket, _load
        create_ticket("Test", "")
        tickets = _load(ticket_project / ".regian_tickets.json")
        tid = tickets[0]["id"]
        result = move_ticket(tid, "review")
        assert "✅" in result
        tickets = _load(ticket_project / ".regian_tickets.json")
        assert tickets[0]["status"] == "review"

    def test_toevoegen_opmerking(self, ticket_project):
        from regian.skills.tickets import create_ticket, move_ticket, _load
        create_ticket("Test", "")
        tickets = _load(ticket_project / ".regian_tickets.json")
        tid = tickets[0]["id"]
        move_ticket(tid, "done", comment="Prima gedaan!")
        tickets = _load(ticket_project / ".regian_tickets.json")
        comments = tickets[0].get("comments", [])
        assert any("Prima gedaan!" in c["text"] for c in comments)

    def test_ongeldige_status(self, ticket_project):
        from regian.skills.tickets import create_ticket, move_ticket, _load
        create_ticket("Test", "")
        tickets = _load(ticket_project / ".regian_tickets.json")
        tid = tickets[0]["id"]
        result = move_ticket(tid, "ongeldig_status")
        assert "❌" in result

    def test_onbekend_ticket_id(self, ticket_project):
        from regian.skills.tickets import move_ticket
        result = move_ticket("doesnotexist", "done")
        assert "❌" in result

    def test_geen_project(self, monkeypatch):
        monkeypatch.setattr("regian.skills.tickets._tickets_file", lambda: None)
        from regian.skills.tickets import move_ticket
        assert "❌" in move_ticket("abc", "done")


# ── delete_ticket ──────────────────────────────────────────────────────────────

class TestDeleteTicket:
    def test_verwijder_bestaand(self, ticket_project):
        from regian.skills.tickets import create_ticket, delete_ticket, _load
        create_ticket("Te verwijderen", "")
        tickets = _load(ticket_project / ".regian_tickets.json")
        tid = tickets[0]["id"]
        result = delete_ticket(tid)
        assert "✅" in result
        assert _load(ticket_project / ".regian_tickets.json") == []

    def test_verwijder_onbekend(self, ticket_project):
        from regian.skills.tickets import delete_ticket
        result = delete_ticket("onbekend_id")
        assert "❌" in result

    def test_geen_project(self, monkeypatch):
        monkeypatch.setattr("regian.skills.tickets._tickets_file", lambda: None)
        from regian.skills.tickets import delete_ticket
        assert "❌" in delete_ticket("x")


# ── fix_ticket ─────────────────────────────────────────────────────────────────

class TestFixTicket:
    def test_fix_verplaatst_naar_review(self, ticket_project, monkeypatch):
        from regian.skills.tickets import create_ticket, _load

        # Mock OrchestratorAgent — wordt lazy geïmporteerd in fix_ticket
        class _MockOrch:
            def plan(self, task): return []
            def run(self, task): return "Fix uitgevoerd."
            def execute_plan(self, plan, **kw): return "Plan uitgevoerd."

        monkeypatch.setattr("regian.core.agent.OrchestratorAgent", _MockOrch)

        create_ticket("Bug X", "De knop werkt niet")
        tickets = _load(ticket_project / ".regian_tickets.json")
        tid = tickets[0]["id"]

        from regian.skills.tickets import fix_ticket
        result = fix_ticket(tid)
        assert "✅" in result or "review" in result.lower()
        tickets = _load(ticket_project / ".regian_tickets.json")
        assert tickets[0]["status"] == "review"

    def test_fix_onbekend_ticket(self, ticket_project):
        from regian.skills.tickets import fix_ticket
        result = fix_ticket("onbekend")
        assert "❌" in result

    def test_fix_al_in_progress_geeft_warning(self, ticket_project, monkeypatch):
        from regian.skills.tickets import create_ticket, _load

        class _MockOrch:
            def plan(self, t): return []
            def run(self, t): return "ok"

        monkeypatch.setattr("regian.core.agent.OrchestratorAgent", _MockOrch)

        create_ticket("Ticket Y", "")
        tickets = _load(ticket_project / ".regian_tickets.json")
        tickets[0]["status"] = "in_progress"
        (ticket_project / ".regian_tickets.json").write_text(
            json.dumps(tickets), encoding="utf-8"
        )
        from regian.skills.tickets import fix_ticket
        result = fix_ticket(tickets[0]["id"])
        assert "⚠️" in result

    def test_geen_project(self, monkeypatch):
        monkeypatch.setattr("regian.skills.tickets._tickets_file", lambda: None)
        from regian.skills.tickets import fix_ticket
        assert "❌" in fix_ticket("x")


# ── fix_all_tickets ────────────────────────────────────────────────────────────

class TestFixAllTickets:
    def test_no_todo_returns_info(self, ticket_project):
        from regian.skills.tickets import fix_all_tickets
        result = fix_all_tickets()
        assert "ℹ️" in result or "Geen" in result

    def test_fix_all_verwerkt_todo(self, ticket_project, monkeypatch):
        from regian.skills.tickets import create_ticket

        class _MockOrch:
            def plan(self, t): return []
            def run(self, t): return "ok"

        monkeypatch.setattr("regian.core.agent.OrchestratorAgent", _MockOrch)

        create_ticket("Bug A", "")
        create_ticket("Bug B", "")
        from regian.skills.tickets import fix_all_tickets, _load
        from pathlib import Path as P
        result = fix_all_tickets()
        tickets = _load(ticket_project / ".regian_tickets.json")
        statuses = [t["status"] for t in tickets]
        assert all(s == "review" for s in statuses)

    def test_geen_project(self, monkeypatch):
        monkeypatch.setattr("regian.skills.tickets._tickets_file", lambda: None)
        from regian.skills.tickets import fix_all_tickets
        assert "❌" in fix_all_tickets()
