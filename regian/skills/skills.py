# regian/skills/skills.py
"""
Skill-beheer: skill generator, preview, herladen en overzicht.
"""
import os
import re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_SKILLS_DIR = Path(__file__).parent


# ── Skill generator ────────────────────────────────────────────────────────────

def create_skill(name: str, description: str) -> str:
    """
    Genereert een nieuwe skill-module op basis van een naam en beschrijving.
    Gebruikt de LLM om de functies te schrijven, valideert de code, schrijft het
    bestand naar regian/skills/<name>.py en herlaadt de registry automatisch.
    """
    name = name.strip().lower().replace(" ", "_").replace("-", "_")
    if not name.isidentifier():
        return f"❌ Ongeldige naam '{name}'. Gebruik alleen letters, cijfers en underscores."

    target = _SKILLS_DIR / f"{name}.py"
    if target.exists():
        return f"❌ Skill '{name}' bestaat al in {target}. Kies een andere naam."

    files_example = (_SKILLS_DIR / "files.py").read_text(encoding="utf-8")[:1500]

    prompt = f"""Je bent een expert Python developer. Schrijf een skill-module voor Regian OS.

REGELS:
- Enkel pure Python functies op module-niveau (geen klassen)
- Elke functie heeft een duidelijke Nederlandstalige docstring (één zin)
- Functies geven altijd een string terug (succes of foutmelding)
- Fouten opvangen met try/except en terugsturen als string: "Fout: ..."
- Geen functies die beginnen met _ (die worden genegeerd door de registry)
- Bovenaan het bestand: comment met # regian/skills/{name}.py

BESTAANDE SKILL ALS VOORBEELD (files.py):
{files_example}

BESCHRIJVING VAN DE NIEUWE SKILL:
Naam: {name}
Beschrijving: {description}

GEVRAAGDE EXTERNE BIBLIOTHEKEN (vermeld ze in een comment bovenaan als: # pip install ...):
Vermeld ze als ze nodig zijn.

Schrijf nu de volledige Python module. Enkel code, geen uitleg, geen markdown code blocks."""

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage

        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=1,
            google_api_key=os.getenv("GEMINI_API_KEY"),
            model_kwargs={"thinking": {"thinking_budget": 0}},
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        code = response.content
        if isinstance(code, list):
            code = " ".join(str(c) for c in code if c)
        code = re.sub(r"^```[a-z]*\n?", "", code.strip())
        code = re.sub(r"\n?```$", "", code)
    except Exception as e:
        return f"❌ LLM fout bij genereren: {str(e)}"

    try:
        compile(code, f"regian/skills/{name}.py", "exec")
    except SyntaxError as e:
        return f"❌ Gegenereerde code bevat syntaxfouten: {e}\n\nCode:\n{code[:500]}"

    try:
        target.write_text(code, encoding="utf-8")
    except Exception as e:
        return f"❌ Kon bestand niet schrijven: {str(e)}"

    reload_msg = reload_skills()

    return (
        f"✅ Skill '{name}' aangemaakt in {target}\n"
        f"{reload_msg}\n\n"
        f"Gebruik `/` + Tab om de nieuwe functies te zien."
    )


def preview_skill(name: str, description: str) -> str:
    """
    Toont een voorbeeld van hoe de gegenereerde skill er zou uitzien, zonder het bestand te schrijven.
    Handig om de LLM output te controleren voor je de skill aanmaakt.
    """
    name = name.strip().lower().replace(" ", "_").replace("-", "_")
    files_example = (_SKILLS_DIR / "files.py").read_text(encoding="utf-8")[:1500]

    prompt = f"""Je bent een expert Python developer. Schrijf een skill-module voor Regian OS.

REGELS:
- Enkel pure Python functies op module-niveau (geen klassen)
- Elke functie heeft een duidelijke Nederlandstalige docstring (één zin)
- Functies geven altijd een string terug
- Fouten opvangen met try/except
- Geen functies die beginnen met _

BESTAANDE SKILL ALS VOORBEELD:
{files_example}

Schrijf een module voor: {description}
Enkel code, geen uitleg, geen markdown code blocks."""

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=1,
            google_api_key=os.getenv("GEMINI_API_KEY"),
            model_kwargs={"thinking": {"thinking_budget": 0}},
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        code = response.content
        if isinstance(code, list):
            code = " ".join(str(c) for c in code if c)
        code = re.sub(r"^```[a-z]*\n?", "", code.strip())
        code = re.sub(r"\n?```$", "", code)
        return f"📝 **Preview voor '{name}':**\n\n```python\n{code}\n```"
    except Exception as e:
        return f"❌ Fout: {str(e)}"


def reload_skills() -> str:
    """
    Herlaadt alle skills uit regian/skills/ zonder de server te herstarten.
    Nieuwe of gewijzigde skill-bestanden worden automatisch opgepikt.
    """
    try:
        from regian.core.agent import registry
        result = registry.reload()
        return f"✅ {result}"
    except Exception as e:
        return f"❌ Fout bij herladen: {str(e)}"


def list_skill_modules() -> str:
    """
    Toont alle geladen skill-modules met het aantal functies per module.
    """
    try:
        from regian.core.agent import registry
        modules: dict[str, list] = {}
        for t in registry.tools:
            func = registry._functions.get(t.name)
            if func:
                mod = func.__module__.split(".")[-1]
                modules.setdefault(mod, []).append(t.name)
        lines = [f"📦 **Geladen skill-modules** ({len(registry.tools)} functies totaal):\n"]
        for mod, funcs in sorted(modules.items()):
            lines.append(f"  **{mod}** ({len(funcs)} functies): {', '.join(sorted(funcs))}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Fout: {str(e)}"
