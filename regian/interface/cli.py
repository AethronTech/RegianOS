# regian/interface/cli.py
"""
Hybride CLI voor Regian OS.

Standaard input  → chat modus (stuurt naar OrchestratorAgent)
Input met /      → command modus (stuurt direct naar Skill, geen LLM)
"""
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from regian.core.agent import registry, OrchestratorAgent, CONFIRM_REQUIRED


# ── Stijl ──────────────────────────────────────────────────────────────────────

STYLE = Style.from_dict({
    "prompt":    "ansigreen bold",
    "separator": "ansibrightblack",
})

_C = {
    "result":    "\033[0m",
    "info":      "\033[33m",
    "error":     "\033[31;1m",
    "cmd":       "\033[36;1m",
    "sep":       "\033[90m",
    "success":   "\033[32m",
}
_R = "\033[0m"


def _print(text: str, kind: str = "result"):
    print(f"{_C.get(kind, '')}{text}{_R}")


def _separator():
    _print("─" * 60, "sep")


# ── Auto-completion ────────────────────────────────────────────────────────────

class RegianCompleter(Completer):
    """
    Auto-completion voor slash-commands.
    Typ '/' + Tab om alle skills te zien, of '/git' + Tab om te filteren.
    """
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if not text.startswith("/"):
            return
        word = text[1:].split(" ")[0]
        if " " in text[1:]:
            return  # geen arg-completion
        import inspect
        for t in sorted(registry.tools, key=lambda x: x.name):
            if t.name.startswith(word):
                func = registry._functions.get(t.name)
                sig = str(inspect.signature(func)) if func else ""
                doc = (func.__doc__ or "").strip().splitlines()[0][:55] if func else ""
                yield Completion(
                    t.name,
                    start_position=-len(word),
                    display=f"/{t.name}{sig}",
                    display_meta=doc,
                )


# ── Handlers ───────────────────────────────────────────────────────────────────

def _handle_command(raw: str):
    """Directe skill-aanroep, geen LLM."""
    parts = raw[1:].split(" ", 1)
    name = parts[0].strip()
    raw_args = parts[1].strip() if len(parts) > 1 else ""

    if not name:
        _print(registry.list_commands(), "info")
        return

    _print(f"⚡ Direct: /{name}({raw_args})", "cmd")
    _separator()
    _print(registry.call_by_string(name, raw_args))


def _handle_chat(prompt: str, orchestrator: OrchestratorAgent):
    """Plan → Execute via OrchestratorAgent met HITL voor gevaarlijke stappen."""
    _print("🧠 Planner werkt...", "info")
    plan = orchestrator.plan(prompt)

    if not plan:
        _print("⚠️  Geen plan gegenereerd. Probeer anders te formuleren.", "error")
        return

    _separator()
    _print("📋 Plan:", "info")
    confirm_set = CONFIRM_REQUIRED()
    has_dangerous = False
    for i, step in enumerate(plan, 1):
        tool = step.get("tool", "")
        args = step.get("args", {})
        icon = "🔴" if tool in confirm_set else "🟢"
        _print(f"  {icon} Stap {i}: {tool} — {args}", "info")
        if tool in confirm_set:
            has_dangerous = True
    _separator()

    if has_dangerous:
        _print("⚠️  Dit plan bevat destructieve operaties!", "error")
        try:
            antwoord = input("   Bevestigen? (ja/nee): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            _print("\n❌ Geannuleerd.", "error")
            return
        if antwoord not in ("ja", "j", "yes", "y"):
            _print("❌ Opdracht geannuleerd.", "error")
            return

    _print("⚙️  Uitvoeren...", "info")
    _separator()
    _print(orchestrator.execute_plan(plan))


# ── Hoofd-loop ─────────────────────────────────────────────────────────────────

def start_cli():
    session: PromptSession = PromptSession(
        history=FileHistory(str(Path.home() / ".regian_history")),
        auto_suggest=AutoSuggestFromHistory(),
        completer=RegianCompleter(),
        complete_while_typing=True,
        style=STYLE,
    )
    orchestrator = OrchestratorAgent()

    _print("🚀 Regian OS CLI", "success")
    _print("   Typ een opdracht voor de agent, of gebruik /command (Tab = auto-complete).", "info")
    _print("   /help voor alle commands  |  exit om te stoppen.", "info")
    _separator()

    while True:
        try:
            raw = session.prompt(
                HTML("<prompt>regian</prompt> <separator> › </separator>"),
                style=STYLE,
            ).strip()
        except KeyboardInterrupt:
            continue
        except EOFError:
            _print("\n👋 Tot ziens!", "success")
            break

        if not raw:
            continue
        if raw.lower() in ("exit", "quit", "stop"):
            _print("👋 Tot ziens!", "success")
            break

        if raw.startswith("/"):
            _handle_command(raw)
        else:
            _handle_chat(raw, orchestrator)
        print()


if __name__ == "__main__":
    start_cli()
