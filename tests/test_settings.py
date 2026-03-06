# tests/test_settings.py
"""Tests voor regian/settings.py — get/set functies met isolatie van .env."""
import os
import json
import pytest
from unittest.mock import patch
from pathlib import Path


# ── Helpers ────────────────────────────────────────────────────────────────────

def _patch_env_file(tmp_env_file, monkeypatch):
    """Patches ENV_FILE in settings zodat tests niet de echte .env aanraken."""
    import regian.settings as s
    monkeypatch.setattr(s, "ENV_FILE", tmp_env_file)
    return s


# ── LLM settings ───────────────────────────────────────────────────────────────

class TestLLMSettings:
    def test_get_llm_provider_default(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "gemini")
        from regian.settings import get_llm_provider
        assert get_llm_provider() == "gemini"

    def test_get_llm_provider_custom(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "ollama")
        from regian.settings import get_llm_provider
        assert get_llm_provider() == "ollama"

    def test_get_llm_model_default(self, monkeypatch):
        monkeypatch.setenv("LLM_MODEL", "gemini-2.5-flash")
        from regian.settings import get_llm_model
        assert get_llm_model() == "gemini-2.5-flash"

    def test_set_llm_provider_writes_env(self, monkeypatch, tmp_env_file):
        s = _patch_env_file(tmp_env_file, monkeypatch)
        s.set_llm_provider("ollama")
        assert os.environ.get("LLM_PROVIDER") == "ollama"
        assert "ollama" in tmp_env_file.read_text()

    def test_set_llm_model_writes_env(self, monkeypatch, tmp_env_file):
        s = _patch_env_file(tmp_env_file, monkeypatch)
        s.set_llm_model("mistral")
        assert os.environ.get("LLM_MODEL") == "mistral"
        assert "mistral" in tmp_env_file.read_text()


# ── CONFIRM_REQUIRED ────────────────────────────────────────────────────────────

class TestConfirmRequired:
    def test_get_returns_set(self, monkeypatch):
        monkeypatch.setenv("CONFIRM_REQUIRED", "delete_file,repo_delete")
        from regian.settings import get_confirm_required
        result = get_confirm_required()
        assert isinstance(result, set)
        assert "delete_file" in result
        assert "repo_delete" in result

    def test_get_ignores_empty_entries(self, monkeypatch):
        monkeypatch.setenv("CONFIRM_REQUIRED", "delete_file,,repo_delete,")
        from regian.settings import get_confirm_required
        result = get_confirm_required()
        assert "" not in result
        assert len(result) == 2

    def test_get_default_fallback(self, monkeypatch):
        monkeypatch.delenv("CONFIRM_REQUIRED", raising=False)
        from regian.settings import get_confirm_required
        result = get_confirm_required()
        assert isinstance(result, set)
        assert len(result) > 0

    def test_set_writes_sorted(self, monkeypatch, tmp_env_file):
        s = _patch_env_file(tmp_env_file, monkeypatch)
        s.set_confirm_required({"zebra_skill", "alpha_skill"})
        content = tmp_env_file.read_text()
        assert "alpha_skill" in content
        assert "zebra_skill" in content
        # gesorteerd: alpha komt eerst
        assert content.index("alpha_skill") < content.index("zebra_skill")


# ── DANGEROUS_PATTERNS ─────────────────────────────────────────────────────────

class TestDangerousPatterns:
    def test_get_returns_defaults_when_unset(self, monkeypatch):
        monkeypatch.delenv("DANGEROUS_PATTERNS", raising=False)
        from regian.settings import get_dangerous_patterns, _DEFAULT_DANGEROUS_PATTERNS
        result = get_dangerous_patterns()
        assert result == list(_DEFAULT_DANGEROUS_PATTERNS)

    def test_get_returns_custom_patterns(self, monkeypatch):
        custom = [r"\bcustom\b", r"\bdanger\b"]
        monkeypatch.setenv("DANGEROUS_PATTERNS", json.dumps(custom))
        from regian.settings import get_dangerous_patterns
        result = get_dangerous_patterns()
        assert result == custom

    def test_get_falls_back_on_invalid_json(self, monkeypatch):
        monkeypatch.setenv("DANGEROUS_PATTERNS", "not-valid-json!!")
        from regian.settings import get_dangerous_patterns, _DEFAULT_DANGEROUS_PATTERNS
        result = get_dangerous_patterns()
        assert result == list(_DEFAULT_DANGEROUS_PATTERNS)

    def test_set_writes_json(self, monkeypatch, tmp_env_file):
        s = _patch_env_file(tmp_env_file, monkeypatch)
        s.set_dangerous_patterns([r"\brm\b", r"\bsudo\b"])
        content = tmp_env_file.read_text()
        # Het bestand moet de patronen bevatten (mogelijk escaped voor .env)
        assert "brm" in content
        assert "bsudo" in content

    def test_roundtrip(self, monkeypatch, tmp_env_file):
        s = _patch_env_file(tmp_env_file, monkeypatch)
        original = [r"\btest_pattern\b", r"\bsecond\b"]
        s.set_dangerous_patterns(original)
        # Laad direct uit os.environ (al gezet door set_dangerous_patterns)
        # Omzeil load_dotenv zodat we niet het bestand opnieuw lezen.
        import unittest.mock as _mock
        with _mock.patch("regian.settings.load_dotenv"):
            result = s.get_dangerous_patterns()
        assert result == original


# ── Root dir ───────────────────────────────────────────────────────────────────

class TestRootDir:
    def test_get_root_dir_creates_dir(self, tmp_path, monkeypatch):
        target = tmp_path / "test_workspace"
        monkeypatch.setenv("REGIAN_ROOT_DIR", str(target))
        from regian.settings import get_root_dir
        result = get_root_dir()
        assert Path(result).exists()
        assert Path(result).is_dir()

    def test_set_root_dir_resolves_path(self, tmp_path, monkeypatch, tmp_env_file):
        import regian.settings as s
        monkeypatch.setattr(s, "ENV_FILE", tmp_env_file)
        new_dir = tmp_path / "new_root"
        result = s.set_root_dir(str(new_dir))
        assert Path(result).exists()
        assert str(new_dir) in result


# ── ActiveProject ───────────────────────────────────────────────────────────────

class TestActiveProject:
    def test_get_geeft_lege_string_als_standaard(self, monkeypatch):
        monkeypatch.delenv("ACTIVE_PROJECT", raising=False)
        from regian.settings import get_active_project
        assert get_active_project() == ""

    def test_get_geeft_ingestelde_waarde(self, monkeypatch):
        monkeypatch.setenv("ACTIVE_PROJECT", "mijn-project")
        from regian.settings import get_active_project
        assert get_active_project() == "mijn-project"

    def test_set_schrijft_naar_env_variabele(self, monkeypatch, tmp_env_file):
        import regian.settings as s
        monkeypatch.setattr(s, "ENV_FILE", tmp_env_file)
        s.set_active_project("nieuw-project")
        assert os.environ.get("ACTIVE_PROJECT") == "nieuw-project"

    def test_set_schrijft_naar_env_bestand(self, monkeypatch, tmp_env_file):
        import regian.settings as s
        monkeypatch.setattr(s, "ENV_FILE", tmp_env_file)
        s.set_active_project("repo-proj")
        assert "repo-proj" in tmp_env_file.read_text()

    def test_clear_wist_env_variabele(self, monkeypatch, tmp_env_file):
        import regian.settings as s
        monkeypatch.setattr(s, "ENV_FILE", tmp_env_file)
        monkeypatch.setenv("ACTIVE_PROJECT", "actief")
        s.clear_active_project()
        assert os.environ.get("ACTIVE_PROJECT") == ""

    def test_clear_wist_uit_env_bestand(self, monkeypatch, tmp_env_file):
        import regian.settings as s
        monkeypatch.setattr(s, "ENV_FILE", tmp_env_file)
        s.set_active_project("te-wissen")
        s.clear_active_project()
        content = tmp_env_file.read_text()
        # De sleutel mag nog aanwezig zijn maar de waarde moet leeg zijn
        assert "te-wissen" not in content

    def test_roundtrip_set_en_get(self, monkeypatch, tmp_env_file):
        import regian.settings as s
        monkeypatch.setattr(s, "ENV_FILE", tmp_env_file)
        s.set_active_project("testproject")
        assert s.get_active_project() == "testproject"
        s.clear_active_project()
        assert s.get_active_project() == ""


# ── ShellTimeout ────────────────────────────────────────────────────────────────

class TestShellTimeout:
    def test_get_standaard(self, monkeypatch):
        monkeypatch.delenv("SHELL_TIMEOUT", raising=False)
        from regian.settings import get_shell_timeout
        assert get_shell_timeout() == 30

    def test_get_ingestelde_waarde(self, monkeypatch):
        monkeypatch.setenv("SHELL_TIMEOUT", "60")
        from regian.settings import get_shell_timeout
        assert get_shell_timeout() == 60

    def test_get_valt_terug_op_standaard_bij_ongeldige_waarde(self, monkeypatch):
        monkeypatch.setenv("SHELL_TIMEOUT", "geen-getal")
        from regian.settings import get_shell_timeout
        assert get_shell_timeout() == 30

    def test_set_schrijft_naar_env(self, monkeypatch, tmp_env_file):
        import regian.settings as s
        monkeypatch.setattr(s, "ENV_FILE", tmp_env_file)
        s.set_shell_timeout(45)
        assert os.environ.get("SHELL_TIMEOUT") == "45"
        assert "45" in tmp_env_file.read_text()

    def test_roundtrip(self, monkeypatch, tmp_env_file):
        import regian.settings as s
        monkeypatch.setattr(s, "ENV_FILE", tmp_env_file)
        s.set_shell_timeout(120)
        assert s.get_shell_timeout() == 120


# ── LogMaxEntries ───────────────────────────────────────────────────────────────

class TestLogMaxEntries:
    def test_get_standaard(self, monkeypatch):
        monkeypatch.delenv("LOG_MAX_ENTRIES", raising=False)
        from regian.settings import get_log_max_entries
        assert get_log_max_entries() == 500

    def test_get_ingestelde_waarde(self, monkeypatch):
        monkeypatch.setenv("LOG_MAX_ENTRIES", "200")
        from regian.settings import get_log_max_entries
        assert get_log_max_entries() == 200

    def test_get_valt_terug_op_standaard_bij_ongeldige_waarde(self, monkeypatch):
        monkeypatch.setenv("LOG_MAX_ENTRIES", "niet-geldig")
        from regian.settings import get_log_max_entries
        assert get_log_max_entries() == 500

    def test_set_schrijft_naar_env(self, monkeypatch, tmp_env_file):
        import regian.settings as s
        monkeypatch.setattr(s, "ENV_FILE", tmp_env_file)
        s.set_log_max_entries(1000)
        assert os.environ.get("LOG_MAX_ENTRIES") == "1000"
        assert "1000" in tmp_env_file.read_text()

    def test_roundtrip(self, monkeypatch, tmp_env_file):
        import regian.settings as s
        monkeypatch.setattr(s, "ENV_FILE", tmp_env_file)
        s.set_log_max_entries(250)
        assert s.get_log_max_entries() == 250


# ── LogResultMaxChars ───────────────────────────────────────────────────────────

class TestLogResultMaxChars:
    def test_get_standaard(self, monkeypatch):
        monkeypatch.delenv("LOG_RESULT_MAX_CHARS", raising=False)
        from regian.settings import get_log_result_max_chars
        assert get_log_result_max_chars() == 300

    def test_get_ingestelde_waarde(self, monkeypatch):
        monkeypatch.setenv("LOG_RESULT_MAX_CHARS", "500")
        from regian.settings import get_log_result_max_chars
        assert get_log_result_max_chars() == 500

    def test_get_valt_terug_op_standaard_bij_ongeldige_waarde(self, monkeypatch):
        monkeypatch.setenv("LOG_RESULT_MAX_CHARS", "abc")
        from regian.settings import get_log_result_max_chars
        assert get_log_result_max_chars() == 300

    def test_set_schrijft_naar_env(self, monkeypatch, tmp_env_file):
        import regian.settings as s
        monkeypatch.setattr(s, "ENV_FILE", tmp_env_file)
        s.set_log_result_max_chars(600)
        assert os.environ.get("LOG_RESULT_MAX_CHARS") == "600"
        assert "600" in tmp_env_file.read_text()

    def test_roundtrip(self, monkeypatch, tmp_env_file):
        import regian.settings as s
        monkeypatch.setattr(s, "ENV_FILE", tmp_env_file)
        s.set_log_result_max_chars(150)
        assert s.get_log_result_max_chars() == 150


# ── AgentMaxIterations ──────────────────────────────────────────────────────────

class TestAgentMaxIterations:
    def test_get_standaard(self, monkeypatch):
        monkeypatch.delenv("AGENT_MAX_ITERATIONS", raising=False)
        from regian.settings import get_agent_max_iterations
        assert get_agent_max_iterations() == 5

    def test_get_ingestelde_waarde(self, monkeypatch):
        monkeypatch.setenv("AGENT_MAX_ITERATIONS", "10")
        from regian.settings import get_agent_max_iterations
        assert get_agent_max_iterations() == 10

    def test_get_valt_terug_op_standaard_bij_ongeldige_waarde(self, monkeypatch):
        monkeypatch.setenv("AGENT_MAX_ITERATIONS", "veel")
        from regian.settings import get_agent_max_iterations
        assert get_agent_max_iterations() == 5

    def test_set_schrijft_naar_env(self, monkeypatch, tmp_env_file):
        import regian.settings as s
        monkeypatch.setattr(s, "ENV_FILE", tmp_env_file)
        s.set_agent_max_iterations(8)
        assert os.environ.get("AGENT_MAX_ITERATIONS") == "8"
        assert "8" in tmp_env_file.read_text()

    def test_roundtrip(self, monkeypatch, tmp_env_file):
        import regian.settings as s
        monkeypatch.setattr(s, "ENV_FILE", tmp_env_file)
        s.set_agent_max_iterations(3)
        assert s.get_agent_max_iterations() == 3


# ── GeminiModels ────────────────────────────────────────────────────────────────

class TestGeminiModels:
    def test_get_standaard(self, monkeypatch):
        monkeypatch.delenv("GEMINI_MODELS", raising=False)
        from regian.settings import get_gemini_models
        result = get_gemini_models()
        assert isinstance(result, list)
        assert "gemini-2.5-flash" in result

    def test_get_ingestelde_waarde(self, monkeypatch):
        monkeypatch.setenv("GEMINI_MODELS", "model-a,model-b")
        from regian.settings import get_gemini_models
        assert get_gemini_models() == ["model-a", "model-b"]

    def test_get_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("GEMINI_MODELS", " model-a , model-b ")
        from regian.settings import get_gemini_models
        assert get_gemini_models() == ["model-a", "model-b"]

    def test_get_negeert_lege_onderdelen(self, monkeypatch):
        monkeypatch.setenv("GEMINI_MODELS", "model-a,,model-b,")
        from regian.settings import get_gemini_models
        assert "" not in get_gemini_models()
        assert len(get_gemini_models()) == 2

    def test_set_schrijft_naar_env(self, monkeypatch, tmp_env_file):
        import regian.settings as s
        monkeypatch.setattr(s, "ENV_FILE", tmp_env_file)
        s.set_gemini_models(["model-x", "model-y"])
        assert "model-x" in os.environ.get("GEMINI_MODELS", "")
        assert "model-x" in tmp_env_file.read_text()

    def test_roundtrip(self, monkeypatch, tmp_env_file):
        import regian.settings as s
        monkeypatch.setattr(s, "ENV_FILE", tmp_env_file)
        s.set_gemini_models(["gemini-test-1", "gemini-test-2"])
        assert s.get_gemini_models() == ["gemini-test-1", "gemini-test-2"]


# ── OllamaModels ────────────────────────────────────────────────────────────────

class TestOllamaModels:
    def test_get_standaard(self, monkeypatch):
        monkeypatch.delenv("OLLAMA_MODELS", raising=False)
        from regian.settings import get_ollama_models
        result = get_ollama_models()
        assert isinstance(result, list)
        assert "mistral" in result

    def test_get_ingestelde_waarde(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_MODELS", "llama3,phi3")
        from regian.settings import get_ollama_models
        assert get_ollama_models() == ["llama3", "phi3"]

    def test_get_negeert_lege_onderdelen(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_MODELS", "llama3,,phi3,")
        from regian.settings import get_ollama_models
        assert "" not in get_ollama_models()
        assert len(get_ollama_models()) == 2

    def test_set_schrijft_naar_env(self, monkeypatch, tmp_env_file):
        import regian.settings as s
        monkeypatch.setattr(s, "ENV_FILE", tmp_env_file)
        s.set_ollama_models(["custom-model"])
        assert "custom-model" in os.environ.get("OLLAMA_MODELS", "")
        assert "custom-model" in tmp_env_file.read_text()

    def test_roundtrip(self, monkeypatch, tmp_env_file):
        import regian.settings as s
        monkeypatch.setattr(s, "ENV_FILE", tmp_env_file)
        s.set_ollama_models(["test-llm", "another-llm"])
        assert s.get_ollama_models() == ["test-llm", "another-llm"]


# ── Log File Name Settings ──────────────────────────────────────────────────────

class TestLogFileName:
    def test_get_default(self, monkeypatch):
        monkeypatch.delenv("LOG_FILE_NAME", raising=False)
        from regian.settings import get_log_file_name
        assert get_log_file_name() == "regian_action_log.jsonl"

    def test_get_custom_value(self, monkeypatch):
        monkeypatch.setenv("LOG_FILE_NAME", "my_log.jsonl")
        from regian.settings import get_log_file_name
        assert get_log_file_name() == "my_log.jsonl"

    def test_set_schrijft_naar_env(self, monkeypatch, tmp_env_file):
        s = _patch_env_file(tmp_env_file, monkeypatch)
        s.set_log_file_name("custom_log.jsonl")
        assert os.environ.get("LOG_FILE_NAME") == "custom_log.jsonl"
        assert "custom_log.jsonl" in tmp_env_file.read_text()

    def test_set_lege_waarde_valt_terug_op_standaard(self, monkeypatch, tmp_env_file):
        s = _patch_env_file(tmp_env_file, monkeypatch)
        s.set_log_file_name("")
        assert os.environ.get("LOG_FILE_NAME") == "regian_action_log.jsonl"

    def test_get_negeert_lege_env_waarde(self, monkeypatch):
        monkeypatch.setenv("LOG_FILE_NAME", "")
        from regian.settings import get_log_file_name
        assert get_log_file_name() == "regian_action_log.jsonl"


# ── Jobs File Name Settings ─────────────────────────────────────────────────────

class TestJobsFileName:
    def test_get_default(self, monkeypatch):
        monkeypatch.delenv("JOBS_FILE_NAME", raising=False)
        from regian.settings import get_jobs_file_name
        assert get_jobs_file_name() == "regian_jobs.json"

    def test_get_custom_value(self, monkeypatch):
        monkeypatch.setenv("JOBS_FILE_NAME", "my_jobs.json")
        from regian.settings import get_jobs_file_name
        assert get_jobs_file_name() == "my_jobs.json"

    def test_set_schrijft_naar_env(self, monkeypatch, tmp_env_file):
        s = _patch_env_file(tmp_env_file, monkeypatch)
        s.set_jobs_file_name("custom_jobs.json")
        assert os.environ.get("JOBS_FILE_NAME") == "custom_jobs.json"
        assert "custom_jobs.json" in tmp_env_file.read_text()

    def test_set_lege_waarde_valt_terug_op_standaard(self, monkeypatch, tmp_env_file):
        s = _patch_env_file(tmp_env_file, monkeypatch)
        s.set_jobs_file_name("")
        assert os.environ.get("JOBS_FILE_NAME") == "regian_jobs.json"

    def test_get_negeert_lege_env_waarde(self, monkeypatch):
        monkeypatch.setenv("JOBS_FILE_NAME", "")
        from regian.settings import get_jobs_file_name
        assert get_jobs_file_name() == "regian_jobs.json"


# ── Agent Name settings ────────────────────────────────────────────────────────

class TestAgentNameSettings:
    def test_get_default(self, monkeypatch):
        monkeypatch.delenv("AGENT_NAME", raising=False)
        from regian.settings import get_agent_name
        assert get_agent_name() == "Reggy"

    def test_get_custom_value(self, monkeypatch):
        monkeypatch.setenv("AGENT_NAME", "Max")
        from regian.settings import get_agent_name
        assert get_agent_name() == "Max"

    def test_set_schrijft_naar_env(self, monkeypatch, tmp_env_file):
        s = _patch_env_file(tmp_env_file, monkeypatch)
        s.set_agent_name("Aria")
        assert os.environ.get("AGENT_NAME") == "Aria"
        assert "Aria" in tmp_env_file.read_text()

    def test_set_lege_waarde_valt_terug_op_standaard(self, monkeypatch, tmp_env_file):
        s = _patch_env_file(tmp_env_file, monkeypatch)
        s.set_agent_name("")
        assert os.environ.get("AGENT_NAME") == "Reggy"

    def test_get_negeert_lege_env_waarde(self, monkeypatch):
        monkeypatch.setenv("AGENT_NAME", "")
        from regian.settings import get_agent_name
        assert get_agent_name() == "Reggy"


# ── Token-log settings ─────────────────────────────────────────────────────────

class TestTokenSettings:
    def test_get_token_log_file_default(self, monkeypatch):
        monkeypatch.delenv("TOKEN_LOG_FILE", raising=False)
        from regian.settings import get_token_log_file_name
        assert get_token_log_file_name() == "regian_token_log.jsonl"

    def test_get_token_log_file_custom(self, monkeypatch):
        monkeypatch.setenv("TOKEN_LOG_FILE", "mijn_tokens.jsonl")
        from regian.settings import get_token_log_file_name
        assert get_token_log_file_name() == "mijn_tokens.jsonl"

    def test_set_token_log_file_schrijft_naar_env(self, monkeypatch, tmp_env_file):
        s = _patch_env_file(tmp_env_file, monkeypatch)
        s.set_token_log_file_name("custom.jsonl")
        assert os.environ.get("TOKEN_LOG_FILE") == "custom.jsonl"
        assert "custom.jsonl" in tmp_env_file.read_text()

    def test_get_token_pricing_default_leeg(self, monkeypatch):
        monkeypatch.delenv("TOKEN_PRICING", raising=False)
        from regian.settings import get_token_pricing
        assert get_token_pricing() == ""

    def test_get_token_pricing_custom(self, monkeypatch):
        custom = json.dumps({"gemini-2.5-flash": {"input": 0.075, "output": 0.30}})
        monkeypatch.setenv("TOKEN_PRICING", custom)
        from regian.settings import get_token_pricing
        assert get_token_pricing() == custom

    def test_set_token_pricing_schrijft_naar_env(self, monkeypatch, tmp_env_file):
        custom = json.dumps({"my-model": {"input": 1.0, "output": 2.0}})
        s = _patch_env_file(tmp_env_file, monkeypatch)
        s.set_token_pricing(custom)
        assert os.environ.get("TOKEN_PRICING") == custom
        assert "my-model" in tmp_env_file.read_text()
