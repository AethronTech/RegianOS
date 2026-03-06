# tests/test_core_token_log.py
"""
Tests voor regian/core/token_log.py (REG-2: token-verbruik & kostprijs).
"""
import json
import types
import pytest
from pathlib import Path
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Hulpfixture: patch _get_token_log_file naar tijdelijke map
# ---------------------------------------------------------------------------

@pytest.fixture
def token_log_file(tmp_path, monkeypatch):
    """Stuurt token_log.py naar een tijdelijk bestand."""
    log_file = tmp_path / "regian_token_log.jsonl"
    import regian.core.token_log as tlm
    monkeypatch.setattr(tlm, "_get_token_log_file", lambda: log_file)
    return log_file


# ---------------------------------------------------------------------------
# _calc_cost
# ---------------------------------------------------------------------------

def test_calc_cost_exact_match(monkeypatch):
    """Exacte match in pricing-tabel levert juiste kostprijs op."""
    import regian.core.token_log as tlm
    monkeypatch.setattr(tlm, "get_pricing", lambda: {
        "test-model": {"input": 1.0, "output": 2.0}
    })
    cost = tlm._calc_cost("test-model", 1_000_000, 1_000_000)
    assert cost == pytest.approx(3.0)


def test_calc_cost_prefix_match(monkeypatch):
    """Prefix-match (bijv. 'gemini-2.5-flash-001') valt terug op basismodel."""
    import regian.core.token_log as tlm
    monkeypatch.setattr(tlm, "get_pricing", lambda: {
        "gemini-2.5-flash": {"input": 0.075, "output": 0.30}
    })
    cost = tlm._calc_cost("gemini-2.5-flash-001", 1_000_000, 0)
    assert cost == pytest.approx(0.075)


def test_calc_cost_unknown_model(monkeypatch):
    """Onbekend model → kostprijs 0.0."""
    import regian.core.token_log as tlm
    monkeypatch.setattr(tlm, "get_pricing", lambda: {})
    cost = tlm._calc_cost("onbekend-model", 5000, 1000)
    assert cost == 0.0


def test_calc_cost_ollama_free(monkeypatch):
    """Ollama-model → kostprijs 0.0."""
    import regian.core.token_log as tlm
    monkeypatch.setattr(tlm, "get_pricing", lambda: {
        "mistral": {"input": 0.0, "output": 0.0}
    })
    cost = tlm._calc_cost("mistral", 100_000, 50_000)
    assert cost == 0.0


# ---------------------------------------------------------------------------
# _extract_tokens
# ---------------------------------------------------------------------------

def _make_response(um=None, rm=None):
    """Bouwen mock LangChain response."""
    r = types.SimpleNamespace()
    r.content = "antwoord"
    if um is not None:
        r.usage_metadata = um
    if rm is not None:
        r.response_metadata = rm
    return r


def test_extract_tokens_usage_metadata_dict():
    from regian.core.token_log import _extract_tokens
    r = _make_response(um={"input_tokens": 100, "output_tokens": 200})
    assert _extract_tokens(r) == (100, 200)


def test_extract_tokens_usage_metadata_object():
    from regian.core.token_log import _extract_tokens
    um = types.SimpleNamespace(input_tokens=50, output_tokens=80)
    r = _make_response(um=um)
    assert _extract_tokens(r) == (50, 80)


def test_extract_tokens_response_metadata_fallback():
    from regian.core.token_log import _extract_tokens
    rm = {"usage_metadata": {"prompt_token_count": 30, "candidates_token_count": 70}}
    r = _make_response(rm=rm)
    assert _extract_tokens(r) == (30, 70)


def test_extract_tokens_no_metadata():
    from regian.core.token_log import _extract_tokens
    r = types.SimpleNamespace(content="test")
    assert _extract_tokens(r) == (0, 0)


# ---------------------------------------------------------------------------
# log_tokens
# ---------------------------------------------------------------------------

def test_log_tokens_schrijft_naar_bestand(token_log_file, monkeypatch):
    """log_tokens() schrijft een geldige JSON-regel naar het logbestand."""
    import regian.core.token_log as tlm
    monkeypatch.setenv("REGIAN_ACTIVE_PROJECT", "test-project")
    tlm.log_tokens("gemini", "gemini-2.5-flash", 100, 50, call_type="plan", project="test-project")
    lines = token_log_file.read_text().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["provider"] == "gemini"
    assert entry["model"] == "gemini-2.5-flash"
    assert entry["input_tokens"] == 100
    assert entry["output_tokens"] == 50
    assert entry["total_tokens"] == 150
    assert entry["call_type"] == "plan"
    assert entry["project"] == "test-project"
    assert "cost_eur" in entry
    assert "ts" in entry


def test_log_tokens_meerdere_aanroepen(token_log_file):
    """Meerdere aanroepen schrijven meerdere regels."""
    from regian.core.token_log import log_tokens
    for i in range(3):
        log_tokens("ollama", "mistral", 10 * i, 5 * i, call_type="agent", project="")
    lines = token_log_file.read_text().splitlines()
    assert len(lines) == 3


# ---------------------------------------------------------------------------
# get_all_entries
# ---------------------------------------------------------------------------

def test_get_all_entries_leeg(token_log_file):
    from regian.core.token_log import get_all_entries
    assert get_all_entries() == []


def test_get_all_entries_nieuwste_eerst(token_log_file):
    """get_all_entries() geeft entries nieuwste-eerst terug."""
    import regian.core.token_log as tlm
    tlm.log_tokens("gemini", "gemini-2.5-flash", 10, 5, project="")
    tlm.log_tokens("gemini", "gemini-2.5-flash", 20, 10, project="")
    entries = tlm.get_all_entries()
    assert len(entries) == 2
    # Nieuwste (tweede entry) staat vooraan
    assert entries[0]["input_tokens"] == 20


# ---------------------------------------------------------------------------
# get_summary_by_model
# ---------------------------------------------------------------------------

def test_get_summary_by_model(token_log_file):
    """Aggregatie per model klopt."""
    import regian.core.token_log as tlm
    tlm.log_tokens("gemini", "gemini-2.5-flash", 100, 50, project="")
    tlm.log_tokens("gemini", "gemini-2.5-flash", 200, 100, project="")
    tlm.log_tokens("ollama", "mistral", 50, 25, project="")
    rows = tlm.get_summary_by_model()
    # Twee modellen
    models = {r["model"] for r in rows}
    assert "gemini-2.5-flash" in models
    assert "mistral" in models
    gemini_row = next(r for r in rows if r["model"] == "gemini-2.5-flash")
    assert gemini_row["input_tokens"] == 300
    assert gemini_row["output_tokens"] == 150
    assert gemini_row["calls"] == 2


# ---------------------------------------------------------------------------
# get_summary_by_project
# ---------------------------------------------------------------------------

def test_get_summary_by_project(token_log_file):
    """Aggregatie per project klopt."""
    import regian.core.token_log as tlm
    tlm.log_tokens("gemini", "gemini-2.5-flash", 100, 50, project="proj-a")
    tlm.log_tokens("gemini", "gemini-2.5-flash", 200, 100, project="proj-a")
    tlm.log_tokens("gemini", "gemini-2.5-flash", 50, 25, project="proj-b")
    rows = tlm.get_summary_by_project()
    projects = {r["project"] for r in rows}
    assert "proj-a" in projects
    assert "proj-b" in projects
    pa = next(r for r in rows if r["project"] == "proj-a")
    assert pa["calls"] == 2
    assert pa["input_tokens"] == 300


# ---------------------------------------------------------------------------
# get_monthly_evolution
# ---------------------------------------------------------------------------

def test_get_monthly_evolution(token_log_file):
    """Aggregatie per maand klopt en is chronologisch gesorteerd."""
    import regian.core.token_log as tlm
    # Voeg entries in met gesimuleerde timestamps
    entries = [
        {"ts": "2026-01-15T10:00:00", "provider": "gemini", "model": "gemini-2.5-flash",
         "project": "", "call_type": "plan", "input_tokens": 100, "output_tokens": 50,
         "total_tokens": 150, "cost_eur": 0.0},
        {"ts": "2026-01-20T10:00:00", "provider": "gemini", "model": "gemini-2.5-flash",
         "project": "", "call_type": "plan", "input_tokens": 200, "output_tokens": 100,
         "total_tokens": 300, "cost_eur": 0.0},
        {"ts": "2026-02-05T10:00:00", "provider": "gemini", "model": "gemini-2.5-flash",
         "project": "", "call_type": "plan", "input_tokens": 50, "output_tokens": 25,
         "total_tokens": 75, "cost_eur": 0.0},
    ]
    with open(token_log_file, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")
    rows = tlm.get_monthly_evolution()
    assert len(rows) == 2
    assert rows[0]["month"] == "2026-01"
    assert rows[1]["month"] == "2026-02"
    assert rows[0]["total_tokens"] == 450
    assert rows[1]["total_tokens"] == 75


# ---------------------------------------------------------------------------
# get_totals
# ---------------------------------------------------------------------------

def test_get_totals_leeg(token_log_file):
    from regian.core.token_log import get_totals
    t = get_totals()
    assert t["calls"] == 0
    assert t["total_tokens"] == 0
    assert t["cost_eur"] == 0.0


def test_get_totals_gevuld(token_log_file):
    import regian.core.token_log as tlm
    tlm.log_tokens("gemini", "gemini-2.5-flash", 100, 50, project="")
    tlm.log_tokens("ollama", "mistral", 200, 100, project="")
    t = tlm.get_totals()
    assert t["calls"] == 2
    assert t["input_tokens"] == 300
    assert t["output_tokens"] == 150
    assert t["total_tokens"] == 450


# ---------------------------------------------------------------------------
# clear_token_log
# ---------------------------------------------------------------------------

def test_clear_token_log(token_log_file):
    import regian.core.token_log as tlm
    tlm.log_tokens("gemini", "gemini-2.5-flash", 100, 50, project="")
    tlm.clear_token_log()
    assert token_log_file.read_text() == ""
    assert tlm.get_all_entries() == []


def test_clear_token_log_niet_bestaand(tmp_path, monkeypatch):
    """clear_token_log() mag niet crashen als het bestand niet bestaat."""
    import regian.core.token_log as tlm
    monkeypatch.setattr(tlm, "_get_token_log_file", lambda: tmp_path / "nonexistent.jsonl")
    result = tlm.clear_token_log()
    assert "gewist" in result


# ---------------------------------------------------------------------------
# get_pricing / set_pricing
# ---------------------------------------------------------------------------

def test_get_pricing_default(monkeypatch):
    """Zonder TOKEN_PRICING in env → standaard pricing-tabel."""
    monkeypatch.delenv("TOKEN_PRICING", raising=False)
    from regian.core.token_log import get_pricing, _DEFAULT_PRICING
    assert get_pricing() == _DEFAULT_PRICING


def test_get_pricing_from_env(monkeypatch):
    """Met TOKEN_PRICING in env → custom tabel."""
    custom = {"my-model": {"input": 5.0, "output": 10.0}}
    monkeypatch.setenv("TOKEN_PRICING", json.dumps(custom))
    from regian.core.token_log import get_pricing
    assert get_pricing() == custom


def test_get_pricing_invalid_json(monkeypatch):
    """Ongeldige JSON in TOKEN_PRICING → fallback naar standaard."""
    monkeypatch.setenv("TOKEN_PRICING", "geen geldige json{{{")
    from regian.core.token_log import get_pricing, _DEFAULT_PRICING
    assert get_pricing() == _DEFAULT_PRICING


def test_get_pricing_non_dict_json(monkeypatch):
    """Geldige JSON maar geen dict → fallback naar standaard."""
    monkeypatch.setenv("TOKEN_PRICING", json.dumps([1, 2, 3]))
    from regian.core.token_log import get_pricing, _DEFAULT_PRICING
    assert get_pricing() == _DEFAULT_PRICING
