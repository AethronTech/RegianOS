import os
from dotenv import load_dotenv, set_key
from pathlib import Path

ENV_FILE = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_FILE)

def get_root_dir() -> str:
    root = os.getenv("REGIAN_ROOT_DIR", str(Path.home() / "RegianWorkspace"))
    Path(root).mkdir(parents=True, exist_ok=True)
    return root

def set_root_dir(path: str) -> str:
    resolved = str(Path(path).expanduser().resolve())
    Path(resolved).mkdir(parents=True, exist_ok=True)
    set_key(str(ENV_FILE), "REGIAN_ROOT_DIR", resolved)
    os.environ["REGIAN_ROOT_DIR"] = resolved
    return resolved


# ── LLM Settings ──────────────────────────────────────────────

def get_llm_provider() -> str:
    return os.getenv("LLM_PROVIDER", "gemini")

def set_llm_provider(provider: str):
    set_key(str(ENV_FILE), "LLM_PROVIDER", provider)
    os.environ["LLM_PROVIDER"] = provider

def get_llm_model() -> str:
    return os.getenv("LLM_MODEL", "gemini-2.5-flash")

def set_llm_model(model: str):
    set_key(str(ENV_FILE), "LLM_MODEL", model)
    os.environ["LLM_MODEL"] = model


# ── CONFIRM_REQUIRED Settings ─────────────────────────────────

_DEFAULT_CONFIRM = "repo_delete,delete_file,delete_directory"

def get_confirm_required() -> set[str]:
    raw = os.getenv("CONFIRM_REQUIRED", _DEFAULT_CONFIRM)
    return {x.strip() for x in raw.split(",") if x.strip()}

def set_confirm_required(tools: set[str]):
    value = ",".join(sorted(tools))
    set_key(str(ENV_FILE), "CONFIRM_REQUIRED", value)
    os.environ["CONFIRM_REQUIRED"] = value


# ── DANGEROUS_PATTERNS Settings ───────────────────────────────

import json as _json

_DEFAULT_DANGEROUS_PATTERNS: list[str] = [
    r"\brm\b.*-[a-z]*[rf]",
    r"\bsudo\b",
    r"\bmkfs\b",
    r"\bdd\b.+of=/dev/",
    r"\bformat\b",
    r"\bfdisk\b",
    r"\bparted\b",
    r"\bshred\b",
    r"\bwipefs\b",
    r">\s*/dev/sd",
    r"\bpoweroff\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\btruncate\b",
    r"\bdrop\s+database\b",
    r"\bchmod\s+[0-7]*7[0-7]*\b",
]

def get_dangerous_patterns() -> list[str]:
    """Laad destructieve shell-patronen uit .env (JSON). Valt terug op defaults."""
    load_dotenv(ENV_FILE, override=True)
    raw = os.getenv("DANGEROUS_PATTERNS", "")
    if not raw:
        return list(_DEFAULT_DANGEROUS_PATTERNS)
    try:
        result = _json.loads(raw)
        if isinstance(result, list):
            return result
    except (_json.JSONDecodeError, ValueError):
        pass
    return list(_DEFAULT_DANGEROUS_PATTERNS)

def set_dangerous_patterns(patterns: list[str]):
    """Sla destructieve shell-patronen op als JSON in .env."""
    value = _json.dumps(patterns)
    set_key(str(ENV_FILE), "DANGEROUS_PATTERNS", value)
    os.environ["DANGEROUS_PATTERNS"] = value
