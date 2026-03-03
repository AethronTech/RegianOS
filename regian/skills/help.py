# regian/skills/help.py
import inspect
import importlib
import pkgutil
import regian.skills as skills_package

def get_help(topic: str = "") -> str:
    """
    Toont alle beschikbare skills en hun functies met beschrijving.
    Gebruik 'topic' om te filteren op een specifieke skill of functienaam.
    """
    lines = ["# 📖 Regian OS — Beschikbare Skills\n"]
    skills_path = skills_package.__path__
    skills_prefix = skills_package.__name__ + "."

    for _, module_name, _ in pkgutil.iter_modules(skills_path, skills_prefix):
        module = importlib.import_module(module_name)
        short_name = module_name.split(".")[-1]

        # Filter op topic indien opgegeven
        if topic and topic.lower() not in short_name.lower():
            continue

        funcs = [
            (name, func)
            for name, func in inspect.getmembers(module, inspect.isfunction)
            if not name.startswith("_") and func.__module__ == module.__name__
        ]

        if not funcs:
            continue

        lines.append(f"## 🔧 {short_name}")
        for name, func in funcs:
            doc = inspect.getdoc(func) or "Geen beschrijving."
            sig = str(inspect.signature(func))
            lines.append(f"- **{name}**`{sig}`")
            lines.append(f"  {doc}")
        lines.append("")

    return "\n".join(lines)
