# regian/skills/terminal.py
"""
Terminal-skills: shell runner en Python executor.
"""
import re
import subprocess
from pathlib import Path


_PROJECT_ROOT = Path(__file__).parent.parent.parent

# Patronen die als destructief worden beschouwd — HITL vereist
_DANGEROUS_PATTERNS: list[str] = [
    r"\brm\b.*-[a-z]*[rf]",       # rm -rf / rm -fr / rm -r / rm -f
    r"\bsudo\b",                  # alles met sudo
    r"\bmkfs\b",                  # filesystem formatteren
    r"\bdd\b.+of=/dev/",          # schrijven naar block device
    r"\bformat\b",                # Windows-style format
    r"\bfdisk\b",                 # partition editor
    r"\bparted\b",                # partition editor
    r"\bshred\b",                 # secure wipe
    r"\bwipefs\b",                # filesystem signature wissen
    r">\s*/dev/sd",               # redirect naar block device
    r"\bpoweroff\b",              # systeem uitschakelen
    r"\bshutdown\b",              # systeem uitschakelen
    r"\breboot\b",                # systeem herstarten
    r"\btruncate\b",              # bestanden afkappen/leegmaken
    r"\bdrop\s+database\b",       # SQL database wissen
    r"\bchmod\s+[0-7]*7[0-7]*\b",# brede permissies (777, 707, …)
]


def is_destructive_shell_command(command: str) -> bool:
    """Geeft True als het commando een destructief patroon bevat."""
    lower = command.lower()
    return any(re.search(pat, lower) for pat in _DANGEROUS_PATTERNS)


def run_shell(command: str) -> str:
    """
    Voert een shell-commando uit en geeft de output terug (stdout + stderr).
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(_PROJECT_ROOT),
        )
        output = result.stdout.strip()
        errors = result.stderr.strip()
        if result.returncode != 0:
            return f"⚠️ Exit code {result.returncode}\n{errors or output}"
        return output or "✅ Commando uitgevoerd (geen output)"
    except subprocess.TimeoutExpired:
        return "❌ Timeout: commando duurde langer dan 30 seconden."
    except Exception as e:
        return f"❌ Fout: {str(e)}"


def run_python(code: str) -> str:
    """
    Voert een stuk Python-code uit en geeft stdout terug. Handig voor snelle tests.
    """
    try:
        import io
        from contextlib import redirect_stdout, redirect_stderr
        buf_out = io.StringIO()
        buf_err = io.StringIO()
        exec_globals = {"__name__": "__main__"}
        with redirect_stdout(buf_out), redirect_stderr(buf_err):
            exec(compile(code, "<regian>", "exec"), exec_globals)
        output = buf_out.getvalue().strip()
        errors = buf_err.getvalue().strip()
        if errors:
            return f"⚠️ Stderr:\n{errors}\n\nStdout:\n{output}"
        return output or "✅ Code uitgevoerd (geen output)"
    except Exception as e:
        return f"❌ Fout: {str(e)}"
