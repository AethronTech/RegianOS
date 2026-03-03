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
    r"\brm\b",
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
    r"\bchmod\b.+(777|o\+[wx]|a\+[wx]|ugo\+[wx])",  # wereld-schrijfbaar (chmod 777, o+w, ...)
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


# ── User Avatar Settings ───────────────────────────────────────

_DEFAULT_USER_AVATAR = "🧑"

def get_user_avatar() -> str:
    """Geeft het geconfigureerde gebruikers-emoji avatar terug."""
    return os.getenv("USER_AVATAR", _DEFAULT_USER_AVATAR)

def set_user_avatar(emoji: str):
    """Sla het gebruikers-emoji avatar op in .env."""
    set_key(str(ENV_FILE), "USER_AVATAR", emoji)
    os.environ["USER_AVATAR"] = emoji


# ── Agent Name Settings ────────────────────────────────────────

_DEFAULT_AGENT_NAME = "Reggy"

def get_agent_name() -> str:
    """Geeft de aangepaste naam van de chat-agent (standaard: Reggy)."""
    return os.getenv("AGENT_NAME", _DEFAULT_AGENT_NAME).strip() or _DEFAULT_AGENT_NAME

def set_agent_name(name: str):
    """Sla de naam van de chat-agent op in .env."""
    name = name.strip() or _DEFAULT_AGENT_NAME
    set_key(str(ENV_FILE), "AGENT_NAME", name)
    os.environ["AGENT_NAME"] = name


# ── Agent Max Iterations Settings ───────────────────────────────

_DEFAULT_AGENT_MAX_ITERATIONS = 5

def get_agent_max_iterations() -> int:
    """Geeft het maximale aantal ReAct-iteraties van de agent (standaard: 5)."""
    try:
        return int(os.getenv("AGENT_MAX_ITERATIONS", str(_DEFAULT_AGENT_MAX_ITERATIONS)))
    except (ValueError, TypeError):
        return _DEFAULT_AGENT_MAX_ITERATIONS

def set_agent_max_iterations(n: int):
    """Sla het maximale aantal agent-iteraties op in .env."""
    set_key(str(ENV_FILE), "AGENT_MAX_ITERATIONS", str(int(n)))
    os.environ["AGENT_MAX_ITERATIONS"] = str(int(n))


# ── LLM Model Lists ────────────────────────────────────────────

_DEFAULT_GEMINI_MODELS = "gemini-2.5-flash,gemini-2.5-pro,gemini-2.0-flash,gemini-flash-latest"
_DEFAULT_OLLAMA_MODELS = "mistral,llama3.1:8b,llama3.2,deepseek-r1:8b"

def get_gemini_models() -> list[str]:
    """Geeft de lijst van beschikbare Gemini-modellen (komma-separated in .env)."""
    raw = os.getenv("GEMINI_MODELS", _DEFAULT_GEMINI_MODELS)
    return [m.strip() for m in raw.split(",") if m.strip()]

def set_gemini_models(models: list[str]):
    """Sla de lijst van Gemini-modellen op in .env."""
    value = ",".join(m.strip() for m in models if m.strip())
    set_key(str(ENV_FILE), "GEMINI_MODELS", value)
    os.environ["GEMINI_MODELS"] = value

def get_ollama_models() -> list[str]:
    """Geeft de lijst van beschikbare Ollama-modellen (komma-separated in .env)."""
    raw = os.getenv("OLLAMA_MODELS", _DEFAULT_OLLAMA_MODELS)
    return [m.strip() for m in raw.split(",") if m.strip()]

def set_ollama_models(models: list[str]):
    """Sla de lijst van Ollama-modellen op in .env."""
    value = ",".join(m.strip() for m in models if m.strip())
    set_key(str(ENV_FILE), "OLLAMA_MODELS", value)
    os.environ["OLLAMA_MODELS"] = value


# ── Shell Timeout Settings ───────────────────────────────────────

_DEFAULT_SHELL_TIMEOUT = 30

def get_shell_timeout() -> int:
    """Geeft de shell-timeout in seconden (standaard: 30)."""
    try:
        return int(os.getenv("SHELL_TIMEOUT", str(_DEFAULT_SHELL_TIMEOUT)))
    except (ValueError, TypeError):
        return _DEFAULT_SHELL_TIMEOUT

def set_shell_timeout(seconds: int):
    """Sla de shell-timeout (in seconden) op in .env."""
    set_key(str(ENV_FILE), "SHELL_TIMEOUT", str(int(seconds)))
    os.environ["SHELL_TIMEOUT"] = str(int(seconds))


# ── Log Settings ───────────────────────────────────────────────

_DEFAULT_LOG_MAX_ENTRIES = 500
_DEFAULT_LOG_RESULT_MAX_CHARS = 300

def get_log_max_entries() -> int:
    """Geeft het maximale aantal log-entries dat bewaard wordt (standaard: 500)."""
    try:
        return int(os.getenv("LOG_MAX_ENTRIES", str(_DEFAULT_LOG_MAX_ENTRIES)))
    except (ValueError, TypeError):
        return _DEFAULT_LOG_MAX_ENTRIES

def set_log_max_entries(n: int):
    """Sla het maximale aantal log-entries op in .env."""
    set_key(str(ENV_FILE), "LOG_MAX_ENTRIES", str(int(n)))
    os.environ["LOG_MAX_ENTRIES"] = str(int(n))

def get_log_result_max_chars() -> int:
    """Geeft het maximale aantal tekens per log-resultaat (standaard: 300)."""
    try:
        return int(os.getenv("LOG_RESULT_MAX_CHARS", str(_DEFAULT_LOG_RESULT_MAX_CHARS)))
    except (ValueError, TypeError):
        return _DEFAULT_LOG_RESULT_MAX_CHARS

def set_log_result_max_chars(n: int):
    """Sla het maximale aantal tekens per log-resultaat op in .env."""
    set_key(str(ENV_FILE), "LOG_RESULT_MAX_CHARS", str(int(n)))
    os.environ["LOG_RESULT_MAX_CHARS"] = str(int(n))


# ── Log/Jobs File Name Settings ────────────────────────────────

_DEFAULT_LOG_FILE_NAME = "regian_action_log.jsonl"
_DEFAULT_JOBS_FILE_NAME = "regian_jobs.json"

def get_log_file_name() -> str:
    """Geeft de bestandsnaam van het actie-logbestand (standaard: regian_action_log.jsonl)."""
    return os.getenv("LOG_FILE_NAME", _DEFAULT_LOG_FILE_NAME).strip() or _DEFAULT_LOG_FILE_NAME

def set_log_file_name(name: str):
    """Sla de bestandsnaam van het actie-logbestand op in .env."""
    name = name.strip() or _DEFAULT_LOG_FILE_NAME
    set_key(str(ENV_FILE), "LOG_FILE_NAME", name)
    os.environ["LOG_FILE_NAME"] = name

def get_jobs_file_name() -> str:
    """Geeft de bestandsnaam van het jobs-bestand (standaard: regian_jobs.json)."""
    return os.getenv("JOBS_FILE_NAME", _DEFAULT_JOBS_FILE_NAME).strip() or _DEFAULT_JOBS_FILE_NAME

def set_jobs_file_name(name: str):
    """Sla de bestandsnaam van het jobs-bestand op in .env."""
    name = name.strip() or _DEFAULT_JOBS_FILE_NAME
    set_key(str(ENV_FILE), "JOBS_FILE_NAME", name)
    os.environ["JOBS_FILE_NAME"] = name


# ── Active Project Settings ────────────────────────────────────

def get_active_project() -> str:
    """Geeft de naam van het actieve project, of een lege string indien geen actief project."""
    return os.getenv("ACTIVE_PROJECT", "")

def set_active_project(name: str):
    """Sla het actieve project op in .env en de huidige omgeving."""
    set_key(str(ENV_FILE), "ACTIVE_PROJECT", name)
    os.environ["ACTIVE_PROJECT"] = name

def clear_active_project():
    """Verwijder het actieve project (geen actief project meer)."""
    set_key(str(ENV_FILE), "ACTIVE_PROJECT", "")
    os.environ["ACTIVE_PROJECT"] = ""


# ── Backup Settings ────────────────────────────────────────────

_DEFAULT_BACKUP_MAX_COUNT = 5

def get_backup_max_count() -> int:
    """Geeft het maximum aantal te bewaren backups (standaard: 5)."""
    try:
        return int(os.getenv("BACKUP_MAX_COUNT", str(_DEFAULT_BACKUP_MAX_COUNT)))
    except (ValueError, TypeError):
        return _DEFAULT_BACKUP_MAX_COUNT

def set_backup_max_count(n: int):
    """Sla het maximum aantal te bewaren backups op in .env."""
    set_key(str(ENV_FILE), "BACKUP_MAX_COUNT", str(int(n)))
    os.environ["BACKUP_MAX_COUNT"] = str(int(n))

def get_backup_dir() -> str:
    """Geeft de map waar backups worden opgeslagen (standaard: RegianBackups naast de werkmap)."""
    default = str(Path(get_root_dir()).parent / "RegianBackups")
    return os.getenv("BACKUP_DIR", default)

def set_backup_dir(path: str) -> str:
    """Sla de backup-map op in .env."""
    resolved = str(Path(path).expanduser().resolve())
    set_key(str(ENV_FILE), "BACKUP_DIR", resolved)
    os.environ["BACKUP_DIR"] = resolved
    return resolved
