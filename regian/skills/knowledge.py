"""Kennisbank-skills voor het actieve project.

Bestanden in de kennisbank worden automatisch als achtergrondcontext
meegegeven bij elke LLM-opdracht. Dit maakt het mogelijk om projectdocumenten,
specificaties of eerdere resultaten persistent beschikbaar te stellen.

Slash-commands:
  /add_to_knowledge <pad>
  /list_knowledge
  /remove_from_knowledge <naam>
  /clear_knowledge
"""

import shutil
from pathlib import Path


def _get_knowledge_dir() -> Path:
    """Geeft de kennisbank-map voor het actieve project (of de werkmap-root)."""
    from regian.settings import get_active_project, get_root_dir

    root = Path(get_root_dir())
    name = get_active_project()
    if name:
        try:
            from regian.skills.project import _read_manifest

            m = _read_manifest(name)
            return Path(m["path"]) / ".regian_knowledge"
        except Exception:
            pass
    return root / ".regian_knowledge"


def add_to_knowledge(path: str) -> str:
    """Voegt een bestand uit de werkmap toe aan de kennisbank van het actieve project.

    De inhoud van het bestand wordt voortaan automatisch als context meegegeven
    bij elke LLM-opdracht, zodat de agent op de hoogte blijft van de inhoud.

    path: relatief pad t.o.v. de werkmap-root (bijv. 'docs/architectuur.md').
    """
    from regian.settings import get_root_dir

    src = Path(get_root_dir()) / path
    if not src.exists():
        return f"❌ Bestand '{path}' niet gevonden in de werkmap."
    if not src.is_file():
        return f"❌ '{path}' is geen bestand."

    kdir = _get_knowledge_dir()
    kdir.mkdir(parents=True, exist_ok=True)
    dst = kdir / src.name
    shutil.copy2(src, dst)
    return f"✅ '{src.name}' toegevoegd aan de kennisbank. Wordt automatisch als context gebruikt."


def list_knowledge() -> str:
    """Geeft een overzicht van alle bestanden in de kennisbank van het actieve project."""
    kdir = _get_knowledge_dir()
    if not kdir.exists():
        return "📭 Kennisbank is leeg."

    files = sorted(kdir.iterdir())
    if not files:
        return "📭 Kennisbank is leeg."

    lines = [f"📚 **Kennisbank** ({len(files)} bestand{'en' if len(files) != 1 else ''}):", ""]
    for f in files:
        size = f.stat().st_size
        size_str = f"{size / 1024:.1f} KB" if size >= 1024 else f"{size} B"
        lines.append(f"  📄 `{f.name}` — {size_str}")
    lines.append("")
    lines.append("*Gebruik `/remove_from_knowledge <naam>` om een bestand te verwijderen.*")
    return "\n".join(lines)


def remove_from_knowledge(name: str) -> str:
    """Verwijdert een bestand uit de kennisbank van het actieve project.

    name: de bestandsnaam (zonder pad), zoals getoond in /list_knowledge.
    """
    kdir = _get_knowledge_dir()
    target = kdir / name
    if not target.exists():
        return f"❌ '{name}' niet gevonden in de kennisbank."
    target.unlink()
    return f"✅ '{name}' verwijderd uit de kennisbank."


def clear_knowledge() -> str:
    """Wist de volledige kennisbank van het actieve project.

    Alle opgeslagen kennisbestanden worden permanent verwijderd.
    De agent zal daarna geen automatische kenniscontext meer ontvangen.
    """
    kdir = _get_knowledge_dir()
    if not kdir.exists() or not any(kdir.iterdir()):
        return "📭 Kennisbank was al leeg."
    count = sum(1 for _ in kdir.iterdir())
    shutil.rmtree(kdir)
    return f"✅ Kennisbank gewist ({count} bestand{'en' if count != 1 else ''} verwijderd)."
