import os
import json
import re
import inspect
import importlib
import pkgutil
from dotenv import load_dotenv
from regian.core.action_log import log_action
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
import regian.skills as skills_package
from regian.settings import get_confirm_required, get_active_project

load_dotenv()

# ── PROJECT CONTEXT ────────────────────────────────────────────────────────────

# Welke skill-modules beschikbaar zijn per projecttype.
# 'all' = geen filtering (alle modules beschikbaar)
_TOOLS_BY_TYPE: dict[str, set[str] | str] = {
    "software": "all",
    "generic":  "all",
    "docs":     {"files", "terminal", "cron", "help", "project", "skills"},
    "data":     {"files", "terminal", "cron", "help", "project", "skills"},
}


def _get_project_context() -> dict | None:
    """
    Laadt het manifest van het actieve project.
    Geeft None terug als er geen actief project is.
    """
    name = get_active_project()
    if not name:
        return None
    try:
        from regian.skills.project import _read_manifest
        return _read_manifest(name)
    except FileNotFoundError:
        return None


def _project_context_block(ctx: dict | None) -> str:
    """Bouw een leesbaar tekstblok met de actieve projectcontext."""
    if not ctx:
        return ""  # geen actief project: geen context
    lines = [
        "── Actief project ──────────────────────────────",
        f"  Naam:  {ctx['name']}",
        f"  Type:  {ctx['type']}",
        f"  Pad:   {ctx['path']}",
    ]
    if ctx.get("git_repo"):
        lines.append(f"  Repo:  {ctx['git_repo']}")
    if ctx.get("description"):
        lines.append(f"  Info:  {ctx['description']}")
    lines.append("────────────────────────────────────────────────")
    return "\n".join(lines)

# ── SKILL REGISTRY ─────────────────────────────────────────────────────────────

class SkillRegistry:
    """
    Ontdekt en beheert automatisch alle skills uit regian/skills/.
    Geen manuele registratie nodig — voeg een functie toe aan een skill-module en klaar.
    """
    def __init__(self):
        self._functions: dict = {}
        self._tools: list = []
        self._discover()

    def _discover(self):
        self._functions = {}
        self._tools = []
        prefix = skills_package.__name__ + "."
        for _, module_name, _ in pkgutil.iter_modules(skills_package.__path__, prefix):
            module = importlib.import_module(module_name)
            for name, func in inspect.getmembers(module, inspect.isfunction):
                if name.startswith("_") or func.__module__ != module.__name__:
                    continue
                self._functions[name] = func
                self._tools.append(
                    StructuredTool.from_function(
                        func=func,
                        name=name,
                        description=inspect.getdoc(func) or f"Voer {name} uit.",
                    )
                )

    @property
    def tools(self):
        return self._tools

    @property
    def tool_map(self):
        return {t.name: t for t in self._tools}

    def call(self, name: str, args: dict) -> str:
        """Roep een skill aan op naam met een dict van argumenten."""
        tool = self.tool_map.get(name)
        if not tool:
            return f"❌ Onbekende skill: '{name}'. Gebruik /get_help voor een overzicht."
        try:
            return str(tool.invoke(args))
        except Exception as e:
            return f"❌ Fout bij '{name}': {str(e)}"

    def call_by_string(self, name: str, raw_args: str) -> str:
        """
        Roep een skill aan op naam met een ruwe string als argument.
        Probeert eerst JSON-parsing, daarna eerste parameter als string.
        """
        tool = self.tool_map.get(name)
        if not tool:
            available = ", ".join(sorted(self._functions.keys()))
            return f"❌ Onbekende skill: '{name}'.\nBeschikbaar: {available}"
        try:
            try:
                args = json.loads(raw_args) if raw_args.strip() else {}
                if isinstance(args, dict):
                    return str(tool.invoke(args))
            except (json.JSONDecodeError, ValueError):
                pass
            func = self._functions[name]
            params = list(inspect.signature(func).parameters.keys())
            if params:
                return str(tool.invoke({params[0]: raw_args.strip()}))
            return str(tool.invoke({}))
        except Exception as e:
            return f"❌ Fout bij '{name}': {str(e)}"

    def list_commands(self) -> str:
        """Geeft een overzicht van alle beschikbare slash commands."""
        lines = ["**Beschikbare /commands:**\n"]
        current_module = None
        for t in sorted(self._tools, key=lambda x: x.name):
            func = self._functions[t.name]
            module = func.__module__.split(".")[-1]
            if module != current_module:
                current_module = module
                lines.append(f"\n**{module}**")
            sig = str(inspect.signature(func))
            lines.append(f"  `/{t.name}{sig}`")
        return "\n".join(lines)

    def reload(self):
        """Herlaad alle skill-modules (opgelet: importlib cache wordt geleegd)."""
        import sys
        # Verwijder gecachede skill-modules zodat importlib ze opnieuw inlaadt
        to_remove = [k for k in sys.modules if k.startswith("regian.skills.")]
        for k in to_remove:
            del sys.modules[k]
        self._discover()
        return f"Registry herladen: {len(self._tools)} skills geladen."

    def skill_modules(self) -> list[str]:
        """Geeft een lijst van alle geladen skill-modulenamen."""
        modules = set()
        for t in self._tools:
            func = self._functions.get(t.name)
            if func:
                modules.add(func.__module__.split(".")[-1])
        return sorted(modules)

    def tools_for_project(self, project_type: str | None = None, allowed_tools: list | None = None) -> list:
        """
        Geeft de gefilterde tool-lijst terug op basis van het projecttype.
        Bij 'software' / 'generic' / None komen alle tools terug.
        Bij 'docs' en 'data' worden GitHub-commando's uitgesloten.
        Als allowed_tools is opgegeven (manifest-override), wordt alleen die set gebruikt.
        """
        if allowed_tools:
            allowed_set = set(allowed_tools)
            return [
                t for t in self._tools
                if self._functions.get(t.name) is not None
                and self._functions[t.name].__module__.split(".")[-1] in allowed_set
            ]
        if project_type is None:
            project_type = "all"
        allowed = _TOOLS_BY_TYPE.get(project_type, "all")
        if allowed == "all":
            return list(self._tools)
        return [
            t for t in self._tools
            if self._functions.get(t.name, None) is not None
            and self._functions[t.name].__module__.split(".")[-1] in allowed
        ]


# Globale registry — gedeeld door orchestrator en agent
registry = SkillRegistry()

# Tools die expliciete gebruikersbevestiging vereisen (HITL) — geladen uit .env
def CONFIRM_REQUIRED() -> set[str]:
    """Lees altijd de actuele waarde uit .env (live, geen herstart nodig)."""
    return get_confirm_required()


# ── ORCHESTRATOR ───────────────────────────────────────────────────────────────

PLANNER_PROMPT = """Je bent een taakplanner van Regian OS (AethronTech). Analyseer de opdracht en maak een takenlijst.

{project_context}
Gebruik UITSLUITEND tools uit deze lijst:
{tool_catalog}

Geef je antwoord als een JSON-array (zonder markdown, geen uitleg):
[
  {{"tool": "tool_naam", "args": {{"param1": "waarde1"}}}},
  {{"tool": "tool_naam2", "args": {{}}}}
]

Regels:
- Gebruik alleen tools die in de lijst staan
- Vul args in op basis van de opdracht
- Relatieve paden zijn altijd t.o.v. het actieve projectpad (indien aanwezig)
- Zet stappen in de juiste volgorde
- Als de opdracht geen tools vereist, geef terug: []

BELANGRIJK — wanneer geef je [] terug (geen tools):
- Vragen die beantwoord kunnen worden vanuit de context (uploads, kennisbank) die al in de prompt aanwezig zijn: beantwoord die direct zonder tools
- Uitleg-, analyse- of samenvattingsvragen over gegevens die al in de context staan: altijd []
- Gebruik NOOIT write_file, activate_project of andere tools enkel om een vraag te beantwoorden; schrijf antwoorden in de chat, niet naar bestanden

WANNEER je run_python gebruikt voor CSV-analyse:
- Lees de kolomnamen ALTIJD eerst uit de eerste rij van het bestand — doe GEEN aannames
- ING-bankbestanden gebruiken puntkomma (;) als scheidingsteken, niet komma
- Het `Bedrag`-veld gebruikt komma als decimaalteken (bv. -12,76) → vervang komma door punt voor float()
- Jaar extraheren uit `Boekingsdatum` (formaat DD/MM/YYYY): gebruik datum.split('/')[2]
- "Omzet" of "inkomsten" = rijen met positief Bedrag; "uitgaven" = rijen met negatief Bedrag
- Print altijd de kolomnamen als eerste debugregel zodat fouten zichtbaar zijn
"""

class OrchestratorAgent:
    """
    Plan → Execute orchestrator.
    Fase 1 (Planner): LLM analyseert de opdracht en geeft een JSON takenlijst terug.
    Fase 2 (Executor): taken worden één voor één deterministisch uitgevoerd.
    """
    def __init__(self):
        self.tools = registry.tools
        from regian.settings import get_llm_provider, get_llm_model
        provider = get_llm_provider()
        model = get_llm_model()
        if provider == "gemini":
            model_kwargs = {"thinking": {"thinking_budget": 0}} if model.startswith("gemini-2.5") else {}
            self.base_llm = ChatGoogleGenerativeAI(
                model=model,
                temperature=1,
                google_api_key=os.getenv("GEMINI_API_KEY"),
                model_kwargs=model_kwargs,
            )
        else:
            self.base_llm = ChatOllama(model=model, temperature=0)

    def _tool_catalog(self, project_type: str | None = None, allowed_tools: list | None = None) -> str:
        filtered = registry.tools_for_project(project_type, allowed_tools)
        lines = []
        for t in sorted(filtered, key=lambda x: x.name):
            sig = str(inspect.signature(registry._functions[t.name]))
            lines.append(f"- {t.name}{sig}: {t.description.splitlines()[0]}")
        return "\n".join(lines)

    def plan(self, prompt: str) -> list:
        """Fase 1: analyseer de opdracht en geef een geordende takenlijst terug."""
        ctx = _get_project_context()
        project_type = ctx["type"] if ctx else None
        allowed_tools = ctx.get("allowed_tools") or None if ctx else None
        catalog = self._tool_catalog(project_type, allowed_tools)
        ctx_block = _project_context_block(ctx)
        project_section = f"{ctx_block}\n\n" if ctx_block else ""
        system = PLANNER_PROMPT.format(
            tool_catalog=catalog,
            project_context=project_section,
        )
        response = self.base_llm.invoke([
            SystemMessage(content=system),
            HumanMessage(content=prompt),
        ])
        content = response.content
        if isinstance(content, list):
            content = " ".join(str(c) for c in content if c)
        content = content.strip()
        content = re.sub(r"^```[a-z]*\n?", "", content)
        content = re.sub(r"\n?```$", "", content)
        try:
            plan = json.loads(content)
            if isinstance(plan, list):
                return plan
        except (json.JSONDecodeError, ValueError):
            pass
        return []

    def execute_plan(self, plan: list, source: str = "chat", group_id: str | None = None) -> str:
        """Fase 2: voer een takenlijst deterministisch uit en geef resultaten terug."""
        results = []
        for step in plan:
            tool_name = step.get("tool", "")
            args = step.get("args", {})
            result = registry.call(tool_name, args)
            log_action(tool_name, args, result, source=source, group_id=group_id)
            results.append(f"✅ **{tool_name}**: {result}")
        return "\n\n".join(results) if results else "Geen taken uitgevoerd."

    def run(self, prompt: str) -> str:
        """Plan + execute in één stap (enkel voor taken zonder HITL-tools)."""
        try:
            plan = self.plan(prompt)
            if not plan:
                ctx = _get_project_context()
                ctx_block = _project_context_block(ctx)
                base_system = (
                    "Je bent Regian, een AI-assistent van AethronTech. Antwoord bondig in het Nederlands.\n"
                    "Als er CSV-data aanwezig is in de context, analyseer die direct en geef concrete antwoorden.\n"
                    "ING-bankbestanden: puntkomma-gescheiden, Bedrag-kolom met komma als decimaalteken, Boekingsdatum in DD/MM/YYYY-formaat.\n"
                    "Omzet/inkomsten = positieve Bedrag-waarden; uitgaven = negatieve waarden."
                )
                system = f"{base_system}\n\n{ctx_block}" if ctx_block else base_system
                response = self.base_llm.invoke([
                    SystemMessage(content=system),
                    HumanMessage(content=prompt),
                ])
                content = response.content
                if isinstance(content, list):
                    content = " ".join(str(c) for c in content if c)
                return str(content).strip()
            return self.execute_plan(plan)
        except Exception as e:
            return f"Orchestrator Fout: {str(e)}"


# ── REGIAN AGENT ───────────────────────────────────────────────────────────────

_AGENT_PROMPT_BASE = (
    "Je bent Regian, een intelligente AI-assistent van AethronTech. "
    "Je hebt toegang tot tools voor bestanden, mappen en GitHub. "
    "KRITISCH: roep ONMIDDELLIJK de juiste tool aan zonder uitleg vooraf. "
    "Beschrijf NOOIT wat je gaat doen — doe het gewoon. "
    "Geef na uitvoering enkel een bondige bevestiging in het Nederlands."
)


def _build_agent_prompt() -> str:
    """Bouw de agent-systeemprompt dynamisch, inclusief de actieve projectcontext."""
    ctx = _get_project_context()
    ctx_block = _project_context_block(ctx)
    if not ctx_block:
        return _AGENT_PROMPT_BASE
    return f"{_AGENT_PROMPT_BASE}\n\n{ctx_block}"

class RegianAgent:
    def __init__(self, provider="ollama", model="mistral"):
        ctx = _get_project_context()
        project_type = ctx["type"] if ctx else None
        allowed_tools = ctx.get("allowed_tools") or None if ctx else None
        self.tools = registry.tools_for_project(project_type, allowed_tools)
        self.tool_map = {t.name: t for t in self.tools}
        if provider == "gemini":
            # thinking_budget=0: schakel thinking uit voor betrouwbare tool-calling
            model_kwargs = {"thinking": {"thinking_budget": 0}} if model.startswith("gemini-2.5") else {}
            base_llm = ChatGoogleGenerativeAI(
                model=model,
                temperature=1,  # vereist door API wanneer thinking_budget=0
                google_api_key=os.getenv("GEMINI_API_KEY"),
                model_kwargs=model_kwargs,
            )
        else:
            base_llm = ChatOllama(model=model, temperature=0)
        self.llm = base_llm.bind_tools(self.tools, tool_choice="any")

    def ask(self, prompt: str) -> str:
        try:
            from regian.settings import get_agent_max_iterations
            max_iter = get_agent_max_iterations()
            messages = [
                SystemMessage(content=_build_agent_prompt()),
                HumanMessage(content=prompt),
            ]
            for _ in range(max_iter):
                response = self.llm.invoke(messages)
                messages.append(response)
                if response.tool_calls:
                    seen = set()
                    results = []
                    for tc in response.tool_calls:
                        key = (tc["name"], str(tc["args"]))
                        if key in seen:
                            continue
                        seen.add(key)
                        result = registry.call(tc["name"], tc["args"])
                        results.append(result)
                        messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))
                    return "\n\n".join(results)
                content = response.content
                if isinstance(content, list):
                    content = " ".join(str(c) for c in content if c)
                if content and str(content).strip():
                    return str(content).strip()
            return "⚠️ Het model gaf geen antwoord. Probeer opnieuw."
        except Exception as e:
            return f"Agent Fout: {str(e)}"