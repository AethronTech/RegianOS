# regian/core/token_log.py
"""
Token-verbruik logging voor Regian OS (REG-2).

Elke LLM-aanroep in OrchestratorAgent en RegianAgent wordt hier geregistreerd
met provider, model, token-aantallen, kostprijs en project-context.

Opslag: regian_token_log.jsonl (naast de actie-log in de projectroot).

Structuur per entry:
    {
        "ts":           "2026-03-06T14:23:11",
        "provider":     "gemini",
        "model":        "gemini-2.5-flash",
        "project":      "mijn-app",           # "" = geen actief project
        "call_type":    "plan" | "run" | "agent",
        "input_tokens":  1234,
        "output_tokens":  567,
        "total_tokens":  1801,
        "cost_eur":      0.00045              # berekend via pricing-tabel
    }
"""
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

_lock = threading.Lock()

# ── Bestandslocatie ────────────────────────────────────────────────────────────

def _get_token_log_file() -> Path:
    return Path(__file__).parent.parent.parent / "regian_token_log.jsonl"


# ── Pricing-tabel (EUR per 1 000 000 tokens) ──────────────────────────────────
# Bron: Google Gemini pricing (maart 2026, approximatief).
# Instelbaar via settings.py (TOKEN_PRICING in .env als JSON).

_DEFAULT_PRICING: dict[str, dict[str, float]] = {
    # Gemini
    "gemini-2.5-flash":    {"input": 0.075,  "output": 0.30},
    "gemini-2.5-pro":      {"input": 1.25,   "output": 5.00},
    "gemini-2.0-flash":    {"input": 0.075,  "output": 0.30},
    "gemini-flash-latest": {"input": 0.075,  "output": 0.30},
    # Ollama (lokaal → gratis)
    "mistral":             {"input": 0.0,    "output": 0.0},
    "llama3.1:8b":         {"input": 0.0,    "output": 0.0},
    "llama3.2":            {"input": 0.0,    "output": 0.0},
    "deepseek-r1:8b":      {"input": 0.0,    "output": 0.0},
}

def get_pricing() -> dict[str, dict[str, float]]:
    """
    Geeft de pricing-tabel terug.
    Probeert eerst TOKEN_PRICING uit .env te laden (JSON);
    valt terug op de ingebouwde standaardtabel.
    """
    try:
        import os
        raw = os.getenv("TOKEN_PRICING", "")
        if raw:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
    except Exception:
        pass
    return _DEFAULT_PRICING


def set_pricing(pricing: dict[str, dict[str, float]]) -> None:
    """Sla de pricing-tabel op in .env als JSON."""
    from regian.settings import ENV_FILE
    from dotenv import set_key
    import os
    value = json.dumps(pricing)
    set_key(str(ENV_FILE), "TOKEN_PRICING", value)
    os.environ["TOKEN_PRICING"] = value


def _calc_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Bereken de kostprijs in EUR op basis van de pricing-tabel."""
    pricing = get_pricing()
    # exacte match
    if model in pricing:
        p = pricing[model]
    else:
        # prefix-match (bijv. "gemini-2.5-flash-001" → "gemini-2.5-flash")
        p = next(
            (v for k, v in pricing.items() if model.lower().startswith(k.lower())),
            {"input": 0.0, "output": 0.0},
        )
    cost = (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000
    return round(cost, 8)


# ── Logging ────────────────────────────────────────────────────────────────────

def log_tokens(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    call_type: str = "plan",
    project: Optional[str] = None,
) -> None:
    """
    Schrijf één token-verbruik entry naar regian_token_log.jsonl.

    :param provider:       'gemini' of 'ollama'
    :param model:          naam van het model (bv. 'gemini-2.5-flash')
    :param input_tokens:   aantal invoer-tokens
    :param output_tokens:  aantal uitvoer-tokens
    :param call_type:      'plan', 'run' of 'agent'
    :param project:        naam van het actieve project (of None)
    """
    if project is None:
        try:
            from regian.settings import get_active_project
            project = get_active_project() or ""
        except Exception:
            project = ""

    total = input_tokens + output_tokens
    cost = _calc_cost(model, input_tokens, output_tokens)

    entry = {
        "ts":            datetime.now().isoformat(timespec="seconds"),
        "provider":      provider,
        "model":         model,
        "project":       project,
        "call_type":     call_type,
        "input_tokens":  input_tokens,
        "output_tokens": output_tokens,
        "total_tokens":  total,
        "cost_eur":      cost,
    }
    line = json.dumps(entry, ensure_ascii=False)
    with _lock:
        with open(_get_token_log_file(), "a", encoding="utf-8") as f:
            f.write(line + "\n")


def _extract_tokens(response) -> tuple[int, int]:
    """
    Haal input- en output-tokencount op uit een LangChain response.
    Ondersteunt usage_metadata (dict of object) en response_metadata.
    Geeft (0, 0) als er geen metadata beschikbaar is.
    """
    # usage_metadata (LangChain generiek)
    um = getattr(response, "usage_metadata", None)
    if um:
        if isinstance(um, dict):
            inp = int(um.get("input_tokens", 0) or um.get("prompt_token_count", 0))
            out = int(um.get("output_tokens", 0) or um.get("candidates_token_count", 0))
            return inp, out
        # object
        inp = int(getattr(um, "input_tokens", 0) or getattr(um, "prompt_token_count", 0))
        out = int(getattr(um, "output_tokens", 0) or getattr(um, "candidates_token_count", 0))
        return inp, out

    # response_metadata (Gemini-specifiek fallback)
    rm = getattr(response, "response_metadata", None)
    if rm and isinstance(rm, dict):
        usage = rm.get("usage_metadata", {}) or {}
        inp = int(usage.get("prompt_token_count", 0))
        out = int(usage.get("candidates_token_count", 0))
        return inp, out

    return 0, 0


# ── Rapport-queries ────────────────────────────────────────────────────────────

def get_all_entries() -> list[dict]:
    """Geeft alle token-log entries terug (nieuwste eerst)."""
    with _lock:
        f = _get_token_log_file()
        if not f.exists():
            return []
        lines = f.read_text(encoding="utf-8").splitlines()

    entries = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return entries


def get_summary_by_model() -> list[dict]:
    """
    Geeft een samenvatting per (provider, model):
    totaal input/output/total tokens en totale kostprijs.
    Gesorteerd op kostprijs aflopend.
    """
    agg: dict[tuple, dict] = {}
    for e in get_all_entries():
        key = (e.get("provider", "?"), e.get("model", "?"))
        if key not in agg:
            agg[key] = {
                "provider": key[0],
                "model": key[1],
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cost_eur": 0.0,
                "calls": 0,
            }
        agg[key]["input_tokens"]  += e.get("input_tokens", 0)
        agg[key]["output_tokens"] += e.get("output_tokens", 0)
        agg[key]["total_tokens"]  += e.get("total_tokens", 0)
        agg[key]["cost_eur"]      += e.get("cost_eur", 0.0)
        agg[key]["calls"]         += 1
    return sorted(agg.values(), key=lambda x: x["cost_eur"], reverse=True)


def get_summary_by_project() -> list[dict]:
    """
    Geeft een samenvatting per project (inclusief "" = geen project):
    totaal tokens en kostprijs.
    Gesorteerd op kostprijs aflopend.
    """
    agg: dict[str, dict] = {}
    for e in get_all_entries():
        proj = e.get("project", "") or ""
        if proj not in agg:
            agg[proj] = {
                "project": proj or "(geen project)",
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cost_eur": 0.0,
                "calls": 0,
            }
        agg[proj]["input_tokens"]  += e.get("input_tokens", 0)
        agg[proj]["output_tokens"] += e.get("output_tokens", 0)
        agg[proj]["total_tokens"]  += e.get("total_tokens", 0)
        agg[proj]["cost_eur"]      += e.get("cost_eur", 0.0)
        agg[proj]["calls"]         += 1
    return sorted(agg.values(), key=lambda x: x["cost_eur"], reverse=True)


def get_monthly_evolution() -> list[dict]:
    """
    Geeft token-verbruik en kostprijs per maand terug (YYYY-MM),
    gesorteerd chronologisch.
    """
    agg: dict[str, dict] = {}
    for e in get_all_entries():
        ts = e.get("ts", "")
        month = ts[:7]  # YYYY-MM
        if not month:
            continue
        if month not in agg:
            agg[month] = {
                "month": month,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cost_eur": 0.0,
                "calls": 0,
            }
        agg[month]["input_tokens"]  += e.get("input_tokens", 0)
        agg[month]["output_tokens"] += e.get("output_tokens", 0)
        agg[month]["total_tokens"]  += e.get("total_tokens", 0)
        agg[month]["cost_eur"]      += e.get("cost_eur", 0.0)
        agg[month]["calls"]         += 1
    return sorted(agg.values(), key=lambda x: x["month"])


def get_totals() -> dict:
    """Geeft de globale totalen over alle entries."""
    entries = get_all_entries()
    return {
        "input_tokens":  sum(e.get("input_tokens", 0) for e in entries),
        "output_tokens": sum(e.get("output_tokens", 0) for e in entries),
        "total_tokens":  sum(e.get("total_tokens", 0) for e in entries),
        "cost_eur":      round(sum(e.get("cost_eur", 0.0) for e in entries), 6),
        "calls":         len(entries),
    }


def clear_token_log() -> str:
    """Wis het token-logbestand volledig."""
    f = _get_token_log_file()
    if f.exists():
        f.write_text("", encoding="utf-8")
    return "✅ Token-log gewist."
