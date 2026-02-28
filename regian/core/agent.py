import os
import json
import re
import inspect
import importlib
import pkgutil
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
import regian.skills as skills_package
from regian.settings import get_confirm_required

load_dotenv()

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


# Globale registry — gedeeld door orchestrator en agent
registry = SkillRegistry()

# Tools die expliciete gebruikersbevestiging vereisen (HITL) — geladen uit .env
def CONFIRM_REQUIRED() -> set[str]:
    """Lees altijd de actuele waarde uit .env (live, geen herstart nodig)."""
    return get_confirm_required()


# ── ORCHESTRATOR ───────────────────────────────────────────────────────────────

PLANNER_PROMPT = """Je bent een taakplanner. Analyseer de opdracht en maak een takenlijst.

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
- Zet stappen in de juiste volgorde
- Als de opdracht geen tools vereist, geef terug: []
"""

class OrchestratorAgent:
    """
    Plan → Execute orchestrator.
    Fase 1 (Planner): LLM analyseert de opdracht en geeft een JSON takenlijst terug.
    Fase 2 (Executor): taken worden één voor één deterministisch uitgevoerd.
    """
    def __init__(self):
        self.tools = registry.tools
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            self.base_llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                temperature=1,
                google_api_key=gemini_key,
                model_kwargs={"thinking": {"thinking_budget": 0}},
            )
        else:
            self.base_llm = ChatOllama(model="mistral", temperature=0)

    def _tool_catalog(self) -> str:
        lines = []
        for t in sorted(self.tools, key=lambda x: x.name):
            sig = str(inspect.signature(registry._functions[t.name]))
            lines.append(f"- {t.name}{sig}: {t.description.splitlines()[0]}")
        return "\n".join(lines)

    def plan(self, prompt: str) -> list:
        """Fase 1: analyseer de opdracht en geef een geordende takenlijst terug."""
        catalog = self._tool_catalog()
        system = PLANNER_PROMPT.format(tool_catalog=catalog)
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

    def execute_plan(self, plan: list) -> str:
        """Fase 2: voer een takenlijst deterministisch uit en geef resultaten terug."""
        results = []
        for step in plan:
            tool_name = step.get("tool", "")
            args = step.get("args", {})
            result = registry.call(tool_name, args)
            results.append(f"✅ **{tool_name}**: {result}")
        return "\n\n".join(results) if results else "Geen taken uitgevoerd."

    def run(self, prompt: str) -> str:
        """Plan + execute in één stap (enkel voor taken zonder HITL-tools)."""
        try:
            plan = self.plan(prompt)
            if not plan:
                response = self.base_llm.invoke([
                    SystemMessage(content="Je bent Regian, een AI-assistent van AethronTech. Antwoord bondig in het Nederlands."),
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

AGENT_PROMPT = (
    "Je bent Regian, een intelligente AI-assistent van AethronTech. "
    "Je hebt toegang tot tools voor bestanden, mappen en GitHub. "
    "KRITISCH: roep ONMIDDELLIJK de juiste tool aan zonder uitleg vooraf. "
    "Beschrijf NOOIT wat je gaat doen — doe het gewoon. "
    "Geef na uitvoering enkel een bondige bevestiging in het Nederlands."
)

class RegianAgent:
    def __init__(self, provider="ollama", model="mistral"):
        self.tools = registry.tools
        self.tool_map = registry.tool_map
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
            messages = [
                SystemMessage(content=AGENT_PROMPT),
                HumanMessage(content=prompt),
            ]
            for _ in range(5):
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