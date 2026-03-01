# regian/skills/terminal.py
"""
Terminal-skills: shell runner en Python executor.
"""
import subprocess
from pathlib import Path


_PROJECT_ROOT = Path(__file__).parent.parent.parent


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
