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
