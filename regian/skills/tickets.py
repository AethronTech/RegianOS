# regian/skills/tickets.py
"""
Ticket-beheersysteem (Kanban) voor Regian OS.

Tickets worden bijgehouden per project in <project>/.regian_tickets.json.
Kolommen: todo → in_progress → review → done.

Publieke functies zijn automatisch beschikbaar als slash-command én als LLM-tool.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path


# ── Intern helpers ─────────────────────────────────────────────────────────────

STATUSES = ("todo", "in_progress", "review", "done")


def _tickets_file() -> Path | None:
    """Geeft het pad naar het tickets-bestand van het actieve project."""
    from regian.skills.workflow import _project_path
    pp = _project_path()
    if not pp:
        return None
    return Path(pp) / ".regian_tickets.json"


def _load(path: Path) -> list[dict]:
    """Laad tickets van schijf; geeft [] terug als bestand ontbreekt of corrupt is."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def _save(path: Path, tickets: list[dict]) -> None:
    """Sla tickets op naar schijf."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tickets, ensure_ascii=False, indent=2), encoding="utf-8")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


# ── Publieke skills ────────────────────────────────────────────────────────────

def create_ticket(title: str, description: str = "") -> str:
    """
    Maak een nieuw ticket aan in de To Do-kolom van het actieve project.
    Vereist een actief project.

    Args:
        title: Korte omschrijving van het probleem of de taak.
        description: Uitgebreide beschrijving, stappen om te reproduceren, verwacht gedrag, enz.
    """
    f = _tickets_file()
    if f is None:
        return "❌ Geen actief project. Activeer eerst een project."
    tickets = _load(f)
    ticket = {
        "id": str(uuid.uuid4())[:8],
        "title": title.strip(),
        "description": description.strip(),
        "status": "todo",
        "created_at": _now(),
        "updated_at": _now(),
        "ai_output": "",
        "comments": [],
    }
    tickets.append(ticket)
    _save(f, tickets)
    return f"✅ Ticket `{ticket['id']}` aangemaakt: **{ticket['title']}**"


def list_tickets(status: str = "") -> str:
    """
    Toon alle tickets van het actieve project, optioneel gefilterd op status.

    Args:
        status: Filter op status: 'todo', 'in_progress', 'review' of 'done'. Leeg = alles.
    """
    f = _tickets_file()
    if f is None:
        return "❌ Geen actief project."
    tickets = _load(f)
    if status:
        tickets = [t for t in tickets if t["status"] == status]
    if not tickets:
        return f"Geen tickets{' met status ' + status if status else ''}."
    lines = []
    for t in tickets:
        icon = {"todo": "📋", "in_progress": "🔄", "review": "👀", "done": "✅"}.get(t["status"], "❓")
        lines.append(f"{icon} `{t['id']}` **{t['title']}** ({t['status']})")
        if t.get("description"):
            lines.append(f"   _{t['description'][:120]}_")
    return "\n".join(lines)


def move_ticket(ticket_id: str, new_status: str, comment: str = "") -> str:
    """
    Verplaats een ticket naar een andere kolom.

    Args:
        ticket_id: Het ID van het ticket (8 tekens).
        new_status: Doelkolom: 'todo', 'in_progress', 'review' of 'done'.
        comment: Optionele opmerking bij de statuswijziging.
    """
    if new_status not in STATUSES:
        return f"❌ Ongeldige status '{new_status}'. Gebruik: {', '.join(STATUSES)}"
    f = _tickets_file()
    if f is None:
        return "❌ Geen actief project."
    tickets = _load(f)
    for t in tickets:
        if t["id"] == ticket_id:
            old = t["status"]
            t["status"] = new_status
            t["updated_at"] = _now()
            if comment:
                t.setdefault("comments", []).append({
                    "text": comment.strip(),
                    "at": _now(),
                    "from": "user",
                })
            _save(f, tickets)
            return f"✅ Ticket `{ticket_id}` verplaatst: **{old}** → **{new_status}**"
    return f"❌ Ticket `{ticket_id}` niet gevonden."


def delete_ticket(ticket_id: str) -> str:
    """
    Verwijder een ticket permanent.

    Args:
        ticket_id: Het ID van het ticket (8 tekens).
    """
    f = _tickets_file()
    if f is None:
        return "❌ Geen actief project."
    tickets = _load(f)
    before = len(tickets)
    tickets = [t for t in tickets if t["id"] != ticket_id]
    if len(tickets) == before:
        return f"❌ Ticket `{ticket_id}` niet gevonden."
    _save(f, tickets)
    return f"✅ Ticket `{ticket_id}` verwijderd."


def fix_ticket(ticket_id: str) -> str:
    """
    Laat de AI-agent een specifiek ticket oplossen.
    Het ticket gaat naar 'in_progress', de agent voert de fix uit,
    daarna wordt het ticket naar 'review' verplaatst met de AI-uitvoer.

    Args:
        ticket_id: Het ID van het ticket dat gefixed moet worden.
    """
    f = _tickets_file()
    if f is None:
        return "❌ Geen actief project."
    tickets = _load(f)
    ticket = next((t for t in tickets if t["id"] == ticket_id), None)
    if not ticket:
        return f"❌ Ticket `{ticket_id}` niet gevonden."
    if ticket["status"] not in ("todo", "review"):
        return f"⚠️ Ticket staat op '{ticket['status']}'. Kan alleen 'todo' of 'review' tickets fixen."

    # In progress
    ticket["status"] = "in_progress"
    ticket["updated_at"] = _now()
    _save(f, tickets)

    # ── Bouw taakomschrijving + projectcontext voor de agent ──────────────────
    task = f"Fix het volgende probleem in het actieve project:\n\n**{ticket['title']}**"
    if ticket.get("description"):
        task += f"\n\n{ticket['description']}"
    if ticket.get("comments"):
        for c in ticket["comments"]:
            if c.get("from") == "user":
                task += f"\n\nOpmerking van gebruiker: {c['text']}"

    # Voeg de bronbestanden van het project toe als context
    try:
        from regian.skills.workflow import _project_path as _tkpp
        _pp = _tkpp()
        if _pp:
            from pathlib import Path as _TkPath
            _proj = _TkPath(_pp)
            # Verzamel relevante bronbestanden (geen node_modules, .git, build-artifacts)
            _IGNORE = {
                "node_modules", ".git", "__pycache__", ".venv", "venv",
                "dist", "build", "htmlcov", ".mypy_cache", ".pytest_cache",
            }
            _EXT = {".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json", ".md", ".sh"}
            _src_files = []
            for _p in sorted(_proj.rglob("*")):
                if any(ig in _p.parts for ig in _IGNORE):
                    continue
                if _p.is_file() and _p.suffix in _EXT and _p.stat().st_size < 40_000:
                    _src_files.append(_p)
                if len(_src_files) >= 30:
                    break

            if _src_files:
                task += f"\n\n── Projectpad: {_pp} ──"
                task += f"\n\nBronbestanden van het project (lees deze zorgvuldig voor je een fix schrijft):\n"
                for _sf in _src_files:
                    try:
                        _rel = _sf.relative_to(_proj)
                        _body = _sf.read_text(encoding="utf-8", errors="replace")
                        task += f"\n### {_rel}\n```\n{_body[:3000]}\n```\n"
                    except Exception:
                        pass

            task += (
                f"\n\n── Instructies ──\n"
                f"1. Analyseer de bronbestanden hierboven.\n"
                f"2. Identificeer welk bestand(en) de bug of ontbrekende functionaliteit bevatten.\n"
                f"3. Schrijf de volledige, gecorrigeerde versie van ENKEL de gewijzigde bestanden.\n"
                f"4. Gebruik write_file met het VOLLEDIGE absolute pad (startend met {_pp}/).\n"
                f"5. Schrijf geen nieuwe bestanden tenzij echt nodig — patch bestaande bestanden.\n"
                f"6. Test de fix na schrijven met run_terminal_command indien van toepassing.\n"
            )
    except Exception:
        pass

    # Agent uitvoeren
    from regian.core.agent import OrchestratorAgent
    try:
        orch = OrchestratorAgent()
        plan = orch.plan(task)
        if plan:
            output = orch.execute_plan(plan, source=f"ticket:{ticket_id}", group_id=ticket_id)
        else:
            output = orch.run(task)
    except Exception as e:
        # Terug naar todo bij fout
        ticket["status"] = "todo"
        ticket["updated_at"] = _now()
        _save(f, tickets)
        return f"❌ Fout tijdens uitvoeren: {e}"

    # Naar review
    ticket["status"] = "review"
    ticket["updated_at"] = _now()
    ticket["ai_output"] = output[:2000]
    ticket.setdefault("comments", []).append({
        "text": f"AI fix uitgevoerd.",
        "at": _now(),
        "from": "ai",
    })
    _save(f, tickets)
    return f"✅ Ticket `{ticket_id}` gefixed en klaar voor review.\n\n{output[:800]}"


def fix_all_tickets() -> str:
    """
    Laat de AI-agent alle tickets in de To Do-kolom oplossen.
    Elk ticket wordt sequentieel verwerkt: todo → in_progress → review.
    """
    f = _tickets_file()
    if f is None:
        return "❌ Geen actief project."
    tickets = _load(f)
    todo = [t for t in tickets if t["status"] == "todo"]
    if not todo:
        return "ℹ️ Geen tickets in To Do."
    results = []
    for t in todo:
        result = fix_ticket(t["id"])
        results.append(f"**{t['title']}**: {result.splitlines()[0]}")
    return "\n".join(results)
