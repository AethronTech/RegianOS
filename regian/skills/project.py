# regian/skills/project.py
"""
Project-skills: aanmaken, activeren en opvragen van Regian-projecten.

Elk project leeft in REGIAN_ROOT_DIR/<naam>/ en heeft een .regian_project.json
manifest met metadata. Het actieve project wordt bijgehouden in .env als
ACTIVE_PROJECT en geeft de agent zijn werkcontext.

Ondersteunde projecttypen:
  - software   Python/JS/... applicaties, volledige GitHub-integratie
  - docs       Documentatieproject (Markdown, Sphinx, …)
  - data       Data-analyse of ETL-project
  - generic    Vrij project zonder type-specifieke toolset
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

_MANIFEST = ".regian_project.json"
_VALID_TYPES = {"software", "docs", "data", "generic"}


# ── Helpers ───────────────────────────────────────────────────

def _root() -> Path:
    from regian.settings import get_root_dir
    return Path(get_root_dir())


def _project_dir(name: str) -> Path:
    return _root() / name


def _manifest_path(name: str) -> Path:
    return _project_dir(name) / _MANIFEST


def _read_manifest(name: str) -> dict:
    """Leest het manifest van een project. Gooit FileNotFoundError als het niet bestaat."""
    mp = _manifest_path(name)
    if not mp.exists():
        raise FileNotFoundError(f"Project '{name}' niet gevonden (geen manifest in {mp.parent}).")
    return json.loads(mp.read_text(encoding="utf-8"))


def _write_manifest(data: dict) -> None:
    path = Path(data["path"]) / _MANIFEST
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Publieke skill-functies ───────────────────────────────────

def create_project(
    name: str,
    project_type: str = "software",
    description: str = "",
    git_repo: str = "",
    allowed_tools: str = "",
) -> str:
    """
    Maakt een nieuw project aan in de werkmap met mapstructuur en een .regian_project.json manifest.
    name: unieke projectnaam (wordt ook de mapnaam).
    project_type: 'software' | 'docs' | 'data' | 'generic' (standaard: software).
    description: korte omschrijving (optioneel).
    git_repo: gekoppelde GitHub-repo als 'gebruiker/repo-naam' (optioneel).
    allowed_tools: kommagescheiden lijst van skill-modules voor dit project (optioneel, leeg = gebruik projecttype-standaard).
    """
    project_type = project_type.lower()
    if project_type not in _VALID_TYPES:
        return (
            f"❌ Ongeldig projecttype '{project_type}'. "
            f"Kies uit: {', '.join(sorted(_VALID_TYPES))}."
        )

    safe_name = name.strip().replace(" ", "_")
    if not safe_name:
        return "❌ Geef een niet-lege projectnaam op."

    project_path = _project_dir(safe_name)
    if (project_path / _MANIFEST).exists():
        return f"⚠️  Project '{safe_name}' bestaat al in {project_path}."

    # Mapstructuur aanmaken
    project_path.mkdir(parents=True, exist_ok=True)
    _type_subdirs = {
        "software": ["src", "tests", "docs"],
        "docs":     ["content", "assets"],
        "data":     ["data/raw", "data/processed", "notebooks"],
        "generic":  [],
    }
    for sub in _type_subdirs.get(project_type, []):
        (project_path / sub).mkdir(parents=True, exist_ok=True)

    # Manifest schrijven
    manifest = {
        "name": safe_name,
        "type": project_type,
        "path": str(project_path),
        "git_repo": git_repo.strip(),
        "description": description.strip(),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "active": False,
        "allowed_tools": [m.strip() for m in allowed_tools.split(",") if m.strip()],
    }
    _write_manifest(manifest)

    subdirs = _type_subdirs.get(project_type, [])
    subdir_info = f" (mappen: {', '.join(subdirs)})" if subdirs else ""
    return (
        f"✅ Project '{safe_name}' aangemaakt in {project_path}{subdir_info}.\n"
        f"   Type: {project_type}"
        + (f" · Repo: {git_repo}" if git_repo else "")
        + f"\n   Gebruik `/activate_project {safe_name}` om het te activeren."
    )


def activate_project(name: str) -> str:
    """
    Markeert een project als actief. De agent gebruikt voortaan de context van dit project
    (werkmap, type, gekoppelde repo) bij het uitvoeren van taken.
    name: naam van het te activeren project.
    """
    safe_name = name.strip()
    try:
        manifest = _read_manifest(safe_name)
    except FileNotFoundError as e:
        return f"❌ {e}"

    from regian.settings import set_active_project, get_active_project

    previous = get_active_project()

    # Vlag in manifest bijwerken
    manifest["active"] = True
    _write_manifest(manifest)

    # Vorig actief project deactiveren in zijn manifest
    if previous and previous != safe_name:
        try:
            prev_manifest = _read_manifest(previous)
            prev_manifest["active"] = False
            _write_manifest(prev_manifest)
        except FileNotFoundError:
            pass  # vorig project manifest bestaat niet meer; geen probleem

    set_active_project(safe_name)

    return (
        f"✅ Project '{safe_name}' is nu actief.\n"
        f"   Type: {manifest['type']} · Pad: {manifest['path']}"
        + (f"\n   Repo: {manifest['git_repo']}" if manifest.get("git_repo") else "")
    )


def deactivate_project() -> str:
    """
    Deactiveert het huidige actieve project. De agent werkt daarna terug vanuit de algemene werkmap.
    """
    from regian.settings import get_active_project, clear_active_project

    current = get_active_project()
    if not current:
        return "ℹ️ Er is momenteel geen actief project."

    try:
        manifest = _read_manifest(current)
        manifest["active"] = False
        _write_manifest(manifest)
    except FileNotFoundError:
        pass

    clear_active_project()
    return f"✅ Project '{current}' gedeactiveerd. Werkcontext terug naar de algemene werkmap."


def get_project_info(name: str = "") -> str:
    """
    Toont de metadata van een project (manifest). Geef geen naam op voor het actieve project.
    name: projectnaam (leeg = actief project).
    """
    from regian.settings import get_active_project

    target = name.strip() or get_active_project()
    if not target:
        return "ℹ️ Geen actief project en geen naam opgegeven. Gebruik `/list_projects` voor een overzicht."

    try:
        m = _read_manifest(target)
    except FileNotFoundError as e:
        return f"❌ {e}"

    lines = [
        f"**📁 Project: {m['name']}**",
        f"- Type: `{m['type']}`",
        f"- Pad: `{m['path']}`",
        f"- Aangemaakt: {m.get('created_at', '?')}",
        f"- Actief: {'✅ ja' if m.get('active') else '❌ nee'}",
    ]
    if m.get("description"):
        lines.append(f"- Beschrijving: {m['description']}")
    if m.get("git_repo"):
        lines.append(f"- Git-repo: `{m['git_repo']}`")
    return "\n".join(lines)


def list_projects() -> str:
    """
    Geeft een overzicht van alle Regian-projecten in de werkmap.
    """
    from regian.settings import get_active_project

    active = get_active_project()
    root = _root()
    if not root.exists():
        return "ℹ️ Werkmap bestaat nog niet."

    projects = []
    for entry in sorted(root.iterdir()):
        if entry.is_dir() and (entry / _MANIFEST).exists():
            try:
                m = json.loads((entry / _MANIFEST).read_text(encoding="utf-8"))
                projects.append(m)
            except (json.JSONDecodeError, OSError):
                projects.append({"name": entry.name, "type": "?", "description": ""})

    if not projects:
        return "ℹ️ Geen projecten gevonden. Maak er een aan met `/create_project`."

    _TYPE_ICONS = {"software": "💻", "docs": "📄", "data": "📊", "generic": "📁"}
    lines = [f"**{len(projects)} project(en) in {root}:**\n"]
    for m in projects:
        icon = _TYPE_ICONS.get(m.get("type", ""), "📁")
        flag = " 🔵 *actief*" if m.get("name") == active else ""
        desc = f" — {m['description']}" if m.get("description") else ""
        repo = f" (`{m['git_repo']}`)" if m.get("git_repo") else ""
        lines.append(f"{icon} **{m['name']}** [{m.get('type','?')}]{flag}{desc}{repo}")

    return "\n".join(lines)
