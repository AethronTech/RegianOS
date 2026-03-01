# tests/test_skills_terminal.py
"""Tests voor regian/skills/terminal.py — patronen, run_shell en run_python."""
import pytest


# ── is_destructive_shell_command ───────────────────────────────────────────────

class TestIsDestructive:
    """Elke variant die gevaarlijk moet zijn → True; onschadelijke → False."""

    @pytest.mark.parametrize("cmd", [
        "rm -rf /tmp/test",
        "rm -fr /home/user",
        "rm -r ./dir",
        "rm -f bestand.txt",
        "sudo apt update",
        "sudo rm bestand",
        "mkfs.ext4 /dev/sdb",
        "mkfs -t vfat /dev/sdc1",
        "dd if=/dev/zero of=/dev/sda",
        "dd if=/dev/urandom of=/dev/sdb bs=4M",
        "format C:",
        "fdisk /dev/sda",
        "parted /dev/sda",
        "shred -u bestand.txt",
        "wipefs -a /dev/sdb",
        "echo data > /dev/sda",
        "poweroff",
        "shutdown -h now",
        "reboot",
        "truncate -s 0 bestand.txt",
        "drop database mydb",
        "chmod 777 script.sh",
        "chmod o+w /etc/passwd",
        "chmod a+w /etc/passwd",
    ])
    def test_destructive_commands(self, cmd):
        from regian.skills.terminal import is_destructive_shell_command
        assert is_destructive_shell_command(cmd) is True, f"Verwacht True voor: {cmd}"

    @pytest.mark.parametrize("cmd", [
        "ls -la",
        "cat bestand.txt",
        "echo 'hello world'",
        "git status",
        "git pull",
        "git push origin main",
        "python3 script.py",
        "mkdir nieuwe_map",
        "cp bron.txt doel.txt",
        "mv oud.txt nieuw.txt",
        "grep 'patroon' bestand.txt",
        "find . -name '*.py'",
        "chmod 644 bestand.txt",
        "chmod 755 script.sh",
        "pip install requests",
        "df -h",
        "ps aux",
        "curl https://example.com",
    ])
    def test_safe_commands(self, cmd):
        from regian.skills.terminal import is_destructive_shell_command
        assert is_destructive_shell_command(cmd) is False, f"Verwacht False voor: {cmd}"

    def test_case_insensitive(self):
        from regian.skills.terminal import is_destructive_shell_command
        assert is_destructive_shell_command("SUDO apt update") is True
        assert is_destructive_shell_command("RM -RF /tmp") is True

    def test_empty_command(self):
        from regian.skills.terminal import is_destructive_shell_command
        assert is_destructive_shell_command("") is False

    def test_custom_patterns_from_settings(self, monkeypatch):
        """Aangepaste patronen uit settings worden correct toegepast."""
        import json
        monkeypatch.setenv("DANGEROUS_PATTERNS", json.dumps([r"\bcustom_danger\b"]))
        from regian.skills import terminal as t_mod
        import importlib
        import regian.settings as s
        # force herlaad van settings (override env)
        from regian.skills.terminal import is_destructive_shell_command
        # custom patroon triggert HITL
        assert is_destructive_shell_command("custom_danger command") is True
        # standaard rm niet meer gevaarlijk (custom lijst)
        assert is_destructive_shell_command("rm -rf /tmp") is False


# ── run_shell ──────────────────────────────────────────────────────────────────

class TestRunShell:
    def test_echo_command(self):
        from regian.skills.terminal import run_shell
        result = run_shell("echo hallo")
        assert "hallo" in result

    def test_exit_code_error(self):
        from regian.skills.terminal import run_shell
        result = run_shell("exit 1")
        # exit 1 in een subshell — resultaat mag leeg zijn of foutmelding
        # het commando zelf geeft exit code 1
        assert isinstance(result, str)

    def test_nonexistent_command(self):
        from regian.skills.terminal import run_shell
        result = run_shell("dit_bestaat_echt_niet_123456")
        assert "⚠️" in result or "Fout" in result or "not found" in result.lower()

    def test_returns_stdout(self):
        from regian.skills.terminal import run_shell
        result = run_shell("echo testoutput")
        assert "testoutput" in result

    def test_multiline_output(self):
        from regian.skills.terminal import run_shell
        result = run_shell("printf 'regel1\\nregel2\\nregel3'")
        assert "regel1" in result
        assert "regel2" in result

    def test_empty_output_message(self):
        from regian.skills.terminal import run_shell
        result = run_shell("true")
        assert isinstance(result, str)
        assert len(result) > 0  # altijd een melding

    def test_cwd_default_is_root(self, tmp_root):
        from regian.skills.terminal import run_shell
        # Schrijf bestand in root, voer run_shell zonder cwd uit → vindt het bestand
        (tmp_root / "hello.txt").write_text("root", encoding="utf-8")
        result = run_shell("cat hello.txt")
        assert "root" in result

    def test_cwd_relative_subdir(self, tmp_root):
        from regian.skills.terminal import run_shell
        sub = tmp_root / "subproject"
        sub.mkdir()
        (sub / "info.txt").write_text("subproject", encoding="utf-8")
        result = run_shell("cat info.txt", cwd="subproject")
        assert "subproject" in result

    def test_cwd_creates_missing_dir(self, tmp_root):
        from regian.skills.terminal import run_shell
        result = run_shell("echo nieuw", cwd="nieuwe_map/submap")
        assert "nieuw" in result
        assert (tmp_root / "nieuwe_map" / "submap").is_dir()

    def test_cwd_absolute_path(self, tmp_path, tmp_root):
        from regian.skills.terminal import run_shell
        # Absoluut pad binnen root → mag
        sub = tmp_root / "absoluut"
        sub.mkdir()
        result = run_shell("echo ok", cwd=str(sub))
        assert "ok" in result

    def test_cwd_path_traversal_blocked(self, tmp_root):
        from regian.skills.terminal import run_shell
        # ../../../ buiten root → geblokkeerd
        result = run_shell("echo hack", cwd="../../etc")
        assert "❌" in result or "Verboden" in result


# ── run_python ─────────────────────────────────────────────────────────────────

class TestRunPython:
    def test_print_output(self):
        from regian.skills.terminal import run_python
        result = run_python("print('hallo python')")
        assert "hallo python" in result

    def test_arithmetic(self):
        from regian.skills.terminal import run_python
        result = run_python("print(2 + 2)")
        assert "4" in result

    def test_multiline_code(self):
        from regian.skills.terminal import run_python
        code = "x = 10\ny = 20\nprint(x + y)"
        result = run_python(code)
        assert "30" in result

    def test_syntax_error(self):
        from regian.skills.terminal import run_python
        result = run_python("def broken(:")
        assert "Fout" in result or "❌" in result

    def test_runtime_exception(self):
        from regian.skills.terminal import run_python
        result = run_python("raise ValueError('test fout')")
        assert "Fout" in result or "❌" in result

    def test_stderr_captured(self):
        from regian.skills.terminal import run_python
        result = run_python("import sys; sys.stderr.write('stderr bericht')")
        assert "stderr bericht" in result or "⚠️" in result

    def test_no_output_message(self):
        from regian.skills.terminal import run_python
        result = run_python("x = 1 + 1")  # geen print
        assert isinstance(result, str)
        assert len(result) > 0

    def test_import_stdlib(self):
        from regian.skills.terminal import run_python
        result = run_python("import os; print(type(os).__name__)")
        assert "module" in result

    def test_cwd_sets_working_directory(self, tmp_root):
        from regian.skills.terminal import run_python
        sub = tmp_root / "myproject"
        sub.mkdir()
        (sub / "data.txt").write_text("project data", encoding="utf-8")
        # os.getcwd() in de code moet de submap zijn
        result = run_python(
            "import os; f=open('data.txt'); print(f.read().strip())",
            cwd="myproject",
        )
        assert "project data" in result

    def test_cwd_adds_to_syspath(self, tmp_root):
        from regian.skills.terminal import run_python
        sub = tmp_root / "pkg"
        sub.mkdir()
        (sub / "mymod.py").write_text("VALUE = 42", encoding="utf-8")
        result = run_python("import mymod; print(mymod.VALUE)", cwd="pkg")
        assert "42" in result

    def test_cwd_restores_after_error(self, tmp_root):
        import os
        from regian.skills.terminal import run_python
        original_cwd = os.getcwd()
        run_python("raise RuntimeError('boom')", cwd="submap")
        assert os.getcwd() == original_cwd  # hersteld ondanks fout

    def test_cwd_path_traversal_blocked(self, tmp_root):
        from regian.skills.terminal import run_python
        result = run_python("print('hack')", cwd="../../etc")
        assert "❌" in result or "Verboden" in result
