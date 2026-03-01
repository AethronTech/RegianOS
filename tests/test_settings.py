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
