# regian/skills/terminal.py
"""
Terminal-skills: shell runner en Python executor.
"""
import re
import subprocess
from pathlib import Path


_PROJECT_ROOT = Path(__file__).parent.parent.parent


def _resolve_cwd(cwd: str) -> Path:
    """
    Zet een cwd-string om naar een absoluut Path.
    - Leeg of "."        → REGIAN_ROOT_DIR
    - Relatief pad       → REGIAN_ROOT_DIR / cwd
    - Absoluut pad       → letterlijk
    Maakt de map aan als die nog niet bestaat.
    Gooit ValueError als het pad buiten REGIAN_ROOT_DIR valt (path-traversal).
    """
    from regian.settings import get_root_dir
    root = Path(get_root_dir()).resolve()

    if not cwd or cwd.strip() in (".", ""):
        target = root
    else:
        p = Path(cwd)
        target = (root / p).resolve() if not p.is_absolute() else p.resolve()

    # Blokkeer path-traversal buiten de root
    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError(
            f"❌ Verboden pad: '{cwd}' valt buiten REGIAN_ROOT_DIR ({root}). "
            "Gebruik enkel paden binnen de werkmap."
        )

    target.mkdir(parents=True, exist_ok=True)
    return target


def is_destructive_shell_command(command: str) -> bool:
    """Geeft True als het commando een destructief patroon bevat (geladen uit .env)."""
    from regian.settings import get_dangerous_patterns
    lower = command.lower()
    return any(re.search(pat, lower) for pat in get_dangerous_patterns())


def run_shell(command: str, cwd: str = "") -> str:
    """
    Voert een shell-commando uit en geeft de output terug (stdout + stderr).
    cwd: werkmap voor het commando. Leeg = REGIAN_ROOT_DIR.
         Relatief pad wordt t.o.v. REGIAN_ROOT_DIR opgelost, bijv. 'project_a/src'.
         Gebruik cwd als bestanden in een specifiek project staan.
         Voorbeeld: run_shell('pytest', cwd='project_a')
    """
    try:
        work_dir = _resolve_cwd(cwd)
    except ValueError as e:
        return str(e)
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(work_dir),
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


def run_python(code: str, cwd: str = "") -> str:
    """
    Voert een stuk Python-code uit en geeft stdout terug.
    Gebruik dit om Python-bestanden of -snippets uit te voeren.
    Geeft de voorkeur aan run_python boven run_shell voor Python-code
    (bijv. NIET 'run_shell python3 script.py', maar run_python(open('script.py').read(), cwd=...)).
    cwd: werkmap die als sys.path[0] en os.getcwd() wordt ingesteld.
         Leeg = REGIAN_ROOT_DIR. Relatief pad t.o.v. REGIAN_ROOT_DIR.
         Voorbeeld voor een bestand in TestDev/: run_python(open('test_script.py').read(), cwd='TestDev')
    """
    try:
        work_dir = _resolve_cwd(cwd)
    except ValueError as e:
        return str(e)
    try:
        import io
        import os
        import sys
        from contextlib import redirect_stdout, redirect_stderr
        buf_out = io.StringIO()
        buf_err = io.StringIO()
        prev_cwd = os.getcwd()
        prev_path = sys.path[:]
        os.chdir(str(work_dir))
        sys.path.insert(0, str(work_dir))
        exec_globals = {"__name__": "__main__"}
        try:
            with redirect_stdout(buf_out), redirect_stderr(buf_err):
                exec(compile(code, "<regian>", "exec"), exec_globals)
        finally:
            os.chdir(prev_cwd)
            sys.path = prev_path
        output = buf_out.getvalue().strip()
        errors = buf_err.getvalue().strip()
        if errors:
            return f"⚠️ Stderr:\n{errors}\n\nStdout:\n{output}"
        return output or "✅ Code uitgevoerd (geen output)"
    except Exception as e:
        return f"❌ Fout: {str(e)}"
