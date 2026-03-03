"""Backup en restore van de RegianOS werkmap."""

import zipfile
from datetime import datetime
from pathlib import Path

from regian.settings import get_root_dir, get_backup_max_count, get_backup_dir


def _backup_dir_path() -> Path:
    """Geeft het pad naar de backup-map en maakt deze aan indien nodig."""
    d = Path(get_backup_dir())
    d.mkdir(parents=True, exist_ok=True)
    return d


def _prune_backups(bdir: Path, keep: int) -> None:
    """Verwijder oudste backups zodra het maximum wordt overschreden."""
    backups = sorted(bdir.glob("*.zip"))
    while len(backups) > keep:
        backups.pop(0).unlink()


def backup_workspace() -> str:
    """
    Maakt een zip-backup van de volledige werkmap (REGIAN_ROOT_DIR) en slaat die op in de backup-map.
    Oudste backups worden automatisch verwijderd als het geconfigureerde maximum wordt overschreden.
    Gebruik /list_backups om bestaande backups te bekijken, of /restore_workspace om te herstellen.
    """
    root = Path(get_root_dir())
    if not root.exists():
        return f"❌ Werkmap '{root}' bestaat niet."

    bdir = _backup_dir_path()
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    zip_name = f"{ts}_workspace_backup.zip"
    zip_path = bdir / zip_name

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in root.rglob("*"):
                if file.is_file():
                    try:
                        zf.write(file, file.relative_to(root.parent))
                    except (OSError, ValueError):
                        pass  # sla onleesbare/symlinked bestanden over

        size_mb = zip_path.stat().st_size / (1024 * 1024)
        max_count = get_backup_max_count()
        _prune_backups(bdir, max_count)

        return (
            f"✅ Backup aangemaakt: `{zip_name}` ({size_mb:.1f} MB)\n"
            f"   Opgeslagen in: {bdir}\n"
            f"   Maximaal {max_count} backups worden bewaard."
        )
    except Exception as e:
        if zip_path.exists():
            zip_path.unlink()
        return f"❌ Backup mislukt: {e}"


def list_backups() -> str:
    """
    Toont een overzicht van alle beschikbare backups met datum en bestandsgrootte.
    Gebruik /restore_workspace <naam> om een backup terug te zetten.
    """
    bdir = _backup_dir_path()
    backups = sorted(bdir.glob("*.zip"), reverse=True)
    if not backups:
        return f"ℹ️ Geen backups gevonden in `{bdir}`."

    max_count = get_backup_max_count()
    lines = [
        f"📦 **Backups** in `{bdir}`\n"
        f"   {len(backups)} bestand(en), maximum: {max_count}\n"
    ]
    for b in backups:
        size_mb = b.stat().st_size / (1024 * 1024)
        lines.append(f"- `{b.name}` · {size_mb:.1f} MB")
    return "\n".join(lines)


def restore_workspace(backup_name: str) -> str:
    """
    Herstelt de werkmap vanuit een opgegeven backup-zip. Bestaande bestanden worden overschreven.
    backup_name: bestandsnaam van de backup (bijv. 2026-03-03_12-00-00_workspace_backup.zip).
    Gebruik /list_backups om de beschikbare backupnamen te bekijken.
    ⚠️ Let op: dit overschrijft bestanden in de werkmap met de inhoud van de gekozen backup.
    """
    bdir = _backup_dir_path()
    zip_path = bdir / backup_name.strip()

    if not zip_path.exists():
        available = [b.name for b in sorted(bdir.glob("*.zip"), reverse=True)]
        avail_str = (
            "\n".join(f"  - {n}" for n in available)
            if available
            else "  (geen backups beschikbaar)"
        )
        return (
            f"❌ Backup '{backup_name}' niet gevonden in `{bdir}`.\n"
            f"Beschikbare backups:\n{avail_str}"
        )

    root = Path(get_root_dir())
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(root.parent)
        return f"✅ Werkmap hersteld vanuit `{backup_name}`.\n   Doelmap: {root}"
    except Exception as e:
        return f"❌ Restore mislukt: {e}"
