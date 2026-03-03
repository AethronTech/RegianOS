# regian/skills/files.py
import os
import shutil
from pathlib import Path
from typing import List, Union
from regian.settings import get_root_dir

def _resolve(path: str) -> Path:
    """Maak een pad absoluut t.o.v. de ingestelde rootdirectory."""
    p = Path(path)
    if p.is_absolute():
        return p
    return Path(get_root_dir()) / p

def write_file(path: str, content: str) -> str:
    """
    Schrijft content naar een bestand. Maakt de bovenliggende mappen aan als deze niet bestaan.
    """
    try:
        file_path = _resolve(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding='utf-8')
        return f"Succes: Bestand geschreven naar {file_path}"
    except Exception as e:
        return f"Fout bij schrijven naar {path}: {str(e)}"

def read_file(path: str) -> str:
    """
    Leest de inhoud van een specifiek bestand.
    """
    try:
        file_path = _resolve(path)
        if not file_path.exists():
            return f"Fout: Bestand {file_path} bestaat niet."
        return file_path.read_text(encoding='utf-8')
    except Exception as e:
        return f"Fout bij lezen van {path}: {str(e)}"

def list_directory(path: str = ".") -> Union[List[str], str]:
    """
    Geeft een lijst van alle bestanden en mappen in het opgegeven pad.
    """
    try:
        dir_path = _resolve(path)
        if not dir_path.is_dir():
            return f"Fout: {dir_path} is geen geldige map."
        items = [item.name for item in dir_path.iterdir()]
        return items
    except Exception as e:
        return f"Fout bij uitlezen van map {path}: {str(e)}"

def create_directory(path: str) -> str:
    """
    Maakt een nieuwe map aan (inclusief tussenliggende mappen).
    """
    try:
        dir_path = _resolve(path)
        dir_path.mkdir(parents=True, exist_ok=True)
        return f"Succes: Map {dir_path} is aangemaakt of bestond al."
    except Exception as e:
        return f"Fout bij aanmaken van map {path}: {str(e)}"

def delete_file(path: str) -> str:
    """
    Verwijdert een bestand.
    """
    try:
        file_path = _resolve(path)
        if not file_path.exists():
            return f"Fout: Bestand {file_path} bestaat niet."
        file_path.unlink()
        return f"Succes: Bestand {file_path} verwijderd."
    except Exception as e:
        return f"Fout bij verwijderen van {path}: {str(e)}"

def delete_directory(path: str) -> str:
    """
    Verwijdert een map en al zijn inhoud.
    """
    try:
        dir_path = _resolve(path)
        if not dir_path.exists():
            return f"Fout: Map {dir_path} bestaat niet."
        shutil.rmtree(dir_path)
        return f"Succes: Map {dir_path} en inhoud verwijderd."
    except Exception as e:
        return f"Fout bij verwijderen van map {path}: {str(e)}"

def rename_file(path: str, new_name: str) -> str:
    """
    Hernoemt een bestand of map. new_name is enkel de nieuwe naam (geen volledig pad).
    """
    try:
        src = _resolve(path)
        if not src.exists():
            return f"Fout: {src} bestaat niet."
        dst = src.parent / new_name
        src.rename(dst)
        return f"Succes: Hernoemd naar {dst}."
    except Exception as e:
        return f"Fout bij hernoemen van {path}: {str(e)}"

def move_file(path: str, destination: str) -> str:
    """
    Verplaatst een bestand of map naar een doelpad.
    """
    try:
        src = _resolve(path)
        dst = _resolve(destination)
        if not src.exists():
            return f"Fout: {src} bestaat niet."
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return f"Succes: {src} verplaatst naar {dst}."
    except Exception as e:
        return f"Fout bij verplaatsen van {path}: {str(e)}"

def copy_file(path: str, destination: str) -> str:
    """
    Kopieert een bestand naar een doelpad.
    """
    try:
        src = _resolve(path)
        dst = _resolve(destination)
        if not src.exists():
            return f"Fout: {src} bestaat niet."
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(str(src), str(dst))
        else:
            shutil.copy2(str(src), str(dst))
        return f"Succes: {src} gekopieerd naar {dst}."
    except Exception as e:
        return f"Fout bij kopiëren van {path}: {str(e)}"

def search_files(query: str, path: str = ".") -> Union[List[str], str]:
    """
    Zoekt naar bestanden of mappen waarvan de naam de zoekterm bevat.
    """
    try:
        base = _resolve(path)
        if not base.is_dir():
            return f"Fout: {base} is geen geldige map."
        matches = [str(p.relative_to(base)) for p in base.rglob(f"*{query}*")]
        if not matches:
            return f"Geen resultaten gevonden voor '{query}' in {base}."
        return matches
    except Exception as e:
        return f"Fout bij zoeken naar {query}: {str(e)}"