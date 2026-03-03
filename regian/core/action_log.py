# regian/core/action_log.py
"""
Persistent actie-logging voor Regian OS.

Elke tool-aanroep (naam, args, resultaat, tijdstip, bron) wordt bijgehouden
in een JSONL-bestand zodat de gebruiker kan zien wat er is uitgevoerd.
Verwante acties (één chatopdracht → meerdere tool-calls) worden gegroepeerd
via een group_id.
"""
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional


def _get_max_entries() -> int:
    try:
        from regian.settings import get_log_max_entries
        return get_log_max_entries()
    except Exception:
        return 500


def _get_result_max_chars() -> int:
    try:
        from regian.settings import get_log_result_max_chars
        return get_log_result_max_chars()
    except Exception:
        return 300


def _get_log_file() -> Path:
    try:
        from regian.settings import get_log_file_name
        return Path(__file__).parent.parent.parent / get_log_file_name()
    except Exception:
        return Path(__file__).parent.parent.parent / "regian_action_log.jsonl"


_lock = threading.Lock()


def log_action(
    tool: str,
    args: dict,
    result: str,
    source: str = "chat",
    group_id: Optional[str] = None,
) -> None:
    """
    Schrijf één actie-entry naar het logbestand.

    :param tool:     naam van de aangeroepen skill (of '__prompt__' voor de originele vraag)
    :param args:     argumenten als dict
    :param result:   resultaat (eerste 300 tekens)
    :param source:   'chat', 'cron', 'cli' of 'direct'
    :param group_id: optionele UUID-string die verwante entries koppelt
    """
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "tool": tool,
        "args": args,
        "result": str(result)[:_get_result_max_chars()],
    }
    if group_id:
        entry["group_id"] = group_id
    line = json.dumps(entry, ensure_ascii=False)
    with _lock:
        with open(_get_log_file(), "a", encoding="utf-8") as f:
            f.write(line + "\n")
        _trim()


def get_log_grouped(limit_groups: int = 100) -> list[dict]:
    """
    Geeft log-entries terug gegroepeerd per chatopdracht (group_id).

    Elke groep heeft de structuur::

        {
          "group_id": str,
          "ts": str,           # tijdstip van de originele prompt
          "prompt": str,       # tekst van de originele prompt
          "source": str,
          "steps": [...]       # alle tool-calls in deze groep
        }

    Groepen zonder ``__prompt__`` entry of entries zonder group_id worden
    onder ``group_id = None`` gebundeld als losse items.
    """
    with _lock:
        if not _get_log_file().exists():
            return []
        lines = _get_log_file().read_text(encoding="utf-8").splitlines()

    entries = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    # Groepeer op group_id, bewaar volgorde van eerste optreden
    groups: dict[str, dict] = {}  # group_id -> groep
    ungrouped: list[dict] = []

    for e in entries:
        gid = e.get("group_id")
        if not gid:
            ungrouped.append(e)
            continue
        if gid not in groups:
            groups[gid] = {
                "group_id": gid,
                "ts": e["ts"],
                "prompt": "",
                "source": e.get("source", ""),
                "steps": [],
            }
        if e.get("tool") == "__prompt__":
            groups[gid]["prompt"] = e.get("args", {}).get("prompt", "")
            groups[gid]["ts"] = e["ts"]
        else:
            groups[gid]["steps"].append(e)

    # Sorteer: nieuwste groepen eerst
    sorted_groups = sorted(groups.values(), key=lambda g: g["ts"], reverse=True)
    return sorted_groups[:limit_groups]


def get_log(limit: int = 200) -> list[dict]:
    """Geeft de meest recente `limit` entries terug (nieuwste eerst)."""
    with _lock:
        if not _get_log_file().exists():
            return []
        lines = _get_log_file().read_text(encoding="utf-8").splitlines()
    entries = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
        if len(entries) >= limit:
            break
    return entries


def clear_log() -> str:
    """Wist het volledige logbestand."""
    with _lock:
        if _get_log_file().exists():
            _get_log_file().write_text("", encoding="utf-8")
    return "✅ Actie-log gewist."


def log_count() -> int:
    """Geeft het totaal aantal gelogde entries terug."""
    with _lock:
        if not _get_log_file().exists():
            return 0
        return sum(1 for l in _get_log_file().read_text(encoding="utf-8").splitlines() if l.strip())


def _trim():
    """Houd het logbestand beperkt tot LOG_MAX_ENTRIES regels (oudste worden verwijderd)."""
    if not _get_log_file().exists():
        return
    lines = [l for l in _get_log_file().read_text(encoding="utf-8").splitlines() if l.strip()]
    max_entries = _get_max_entries()
    if len(lines) > max_entries:
        trimmed = lines[-max_entries:]
        _get_log_file().write_text("\n".join(trimmed) + "\n", encoding="utf-8")
