import os
import json
import inspect
import importlib
import pkgutil
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
import regian.skills as skills_package

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


# Globale registry — gedeeld door orchestrator en agent
registry = SkillRegistry()


# ── ORCHESTRATOR ───────────────────────────────────────────────────────────────
# Lichtgewicht agent die ALTIJD een snel/goedkoop model gebruikt
# voor betrouwbare tool-routing. Onafhankelijk van de gebruikerskeuze.

ORCHESTRATOR_PROMPT = (
    "Je bent een tool-uitvoerder. "
    "Roep DIRECT de juiste tool aan op basis van de vraag. "
    "Geen uitleg, geen tekst voor de tool-call. Gewoon uitvoeren. "
    "Na uitvoering: enkel een bondige bevestiging in het Nederlands."
)

class OrchestratorAgent:
    """
    Altijd-actieve, lichtgewichte agent voor betrouwbare tool-uitvoering.
    Gebruikt gemini-flash als GEMINI_API_KEY beschikbaar is, anders mistral.
    """
    def __init__(self):
        self.tools = registry.tools
        self.tool_map = registry.tool_map
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            base_llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                temperature=1,  # vereist bij thinking_budget=0
                google_api_key=gemini_key,
                model_kwargs={"thinking": {"thinking_budget": 0}},
            )
        else:
            base_llm = ChatOllama(model="mistral", temperature=0)
        self.llm = base_llm.bind_tools(self.tools, tool_choice="any")

    def run(self, prompt: str) -> str:
        try:
            messages = [
                SystemMessage(content=ORCHESTRATOR_PROMPT),
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
                    # Geef resultaten direct terug — geen tweede LLM-call
                    # (Gemini 2.5 geeft lege content terug bij samenvatting)
                    return "\n\n".join(results)
                content = response.content
                if content and content.strip():
                    return content.strip()
                # model gaf lege respons (bv. Gemini thinking) — herhaal
            return "⚠️ Het model gaf geen antwoord. Probeer opnieuw of gebruik een /command."
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
                if content and content.strip():
                    return content.strip()
            return "⚠️ Het model gaf geen antwoord. Probeer opnieuw."
        except Exception as e:
            return f"Agent Fout: {str(e)}"