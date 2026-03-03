# regian/core/workflow.py
"""
Workflow-engine voor Regian OS.

Een workflow is een JSON-bestand (.regian_workflow/<naam>.json) met een
geordende lijst van fasen. Elke fase heeft een 'type' dat bepaalt hoe
de engine hem uitvoert:

  llm_prompt       → LLM-aanroep met prompt-template en variabele-substitutie
  task_loop        → Takenlijst via planner + executor (agent)
  human_checkpoint → Pauzeer en wacht op gebruikersgoedkeuring
  tool_chain       → Voer een vaste lijst tools deterministisch uit

State van een run wordt bijgehouden in:
  <project>/.regian_workflow_state/<run_id>.json

Zo kan een run na een crash of herstart worden voortgezet.
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


# ── Statuswaarden ──────────────────────────────────────────────────────────────

STATUS_RUNNING   = "running"
STATUS_WAITING   = "waiting"   # wacht op menselijke goedkeuring
STATUS_DONE      = "done"
STATUS_CANCELLED = "cancelled"
STATUS_ERROR     = "error"


# ── WorkflowRun dataklasse ─────────────────────────────────────────────────────

@dataclass
class WorkflowRun:
    """Houdt de volledige staat van één workflow-uitvoering bij."""
    run_id:       str
    workflow_id:  str
    workflow_name: str
    started_at:   str
    updated_at:   str
    status:       str                          # zie STATUS_*
    current_phase_index: int                   # index in phases-lijst
    artifacts:    dict[str, Any]               # sleutel = output_key van fase
    phase_log:    list[dict]                   # logboek per fase
    input:        str                          # originele gebruikersinvoer
    project_path: str = ""                     # pad naar actief project (mag leeg)

    # ── Serialisatie ──────────────────────────────────────────
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "WorkflowRun":
        return cls(**d)


# ── Pad-helpers ───────────────────────────────────────────────────────────────

def _workflow_dir(project_path: str = "") -> Path:
    """Geeft de map met workflow-templates terug."""
    if project_path:
        return Path(project_path) / ".regian_workflow"
    from regian.settings import get_root_dir
    return Path(get_root_dir()) / ".regian_workflow"


def _state_dir(project_path: str = "") -> Path:
    """Geeft de map voor workflow-state (runs) terug."""
    if project_path:
        return Path(project_path) / ".regian_workflow_state"
    from regian.settings import get_root_dir
    return Path(get_root_dir()) / ".regian_workflow_state"


def _builtin_template_dir() -> Path:
    """Geeft de map met ingebouwde workflow-templates (in de package) terug."""
    return Path(__file__).parent.parent / "workflows"


# ── Template laden ────────────────────────────────────────────────────────────

def load_workflow(name: str, project_path: str = "") -> dict:
    """
    Laad een workflow-template op naam.
    Zoekorde:
      1. <project>/.regian_workflow/<naam>.json
      2. <root>/.regian_workflow/<naam>.json
      3. regian/workflows/<naam>.json  (ingebouwde templates)
    Gooit FileNotFoundError als de template niet gevonden wordt.
    """
    candidates = [
        _workflow_dir(project_path) / f"{name}.json",
        _workflow_dir() / f"{name}.json",
        _builtin_template_dir() / f"{name}.json",
    ]
    for path in candidates:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    searched = "\n  ".join(str(c) for c in candidates)
    raise FileNotFoundError(
        f"Workflow-template '{name}' niet gevonden. Gezocht in:\n  {searched}"
    )


def list_workflows(project_path: str = "") -> list[dict]:
    """
    Geeft alle beschikbare workflow-templates terug als lijst van dicts
    met 'id', 'name' en 'description'.
    """
    seen: dict[str, dict] = {}
    dirs = [
        _builtin_template_dir(),
        _workflow_dir(),
        _workflow_dir(project_path) if project_path else None,
    ]
    for d in dirs:
        if d is None or not d.exists():
            continue
        for f in sorted(d.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                wid = data.get("id", f.stem)
                seen[wid] = {
                    "id":          wid,
                    "name":        data.get("name", wid),
                    "description": data.get("description", ""),
                    "phases":      len(data.get("phases", [])),
                    "source":      str(f),
                }
            except Exception:
                continue
    return list(seen.values())


# ── State persistentie ────────────────────────────────────────────────────────

def save_run(run: WorkflowRun) -> None:
    """Sla de run-state op naar schijf."""
    sdir = _state_dir(run.project_path)
    sdir.mkdir(parents=True, exist_ok=True)
    path = sdir / f"{run.run_id}.json"
    path.write_text(json.dumps(run.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def load_run(run_id: str, project_path: str = "") -> WorkflowRun:
    """Laad een run-state van schijf."""
    path = _state_dir(project_path) / f"{run_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Run '{run_id}' niet gevonden in {_state_dir(project_path)}")
    return WorkflowRun.from_dict(json.loads(path.read_text(encoding="utf-8")))


def list_runs(project_path: str = "") -> list[WorkflowRun]:
    """Geeft alle runs terug (actief en afgerond), gesorteerd op starttijd (nieuwste eerst)."""
    sdir = _state_dir(project_path)
    if not sdir.exists():
        return []
    runs = []
    for f in sdir.glob("*.json"):
        try:
            runs.append(WorkflowRun.from_dict(json.loads(f.read_text(encoding="utf-8"))))
        except Exception:
            continue
    return sorted(runs, key=lambda r: r.started_at, reverse=True)


# ── Template-substitutie ──────────────────────────────────────────────────────

def _render_template(template: str, artifacts: dict) -> str:
    """
    Vervang {{sleutel}} placeholders in een template-string door waarden uit artifacts.
    Onbekende placeholders blijven staan.
    """
    def replace(match: re.Match) -> str:
        key = match.group(1).strip()
        return str(artifacts.get(key, match.group(0)))
    return re.sub(r"\{\{(\w+)\}\}", replace, template)


# ── LLM-helper (hergebruik OrchestratorAgent's llm) ──────────────────────────

def _get_llm():
    """Maak een LLM-instantie op basis van de ingestelde provider/model."""
    from regian.core.agent import OrchestratorAgent
    return OrchestratorAgent().base_llm


# ── Fase-uitvoer ──────────────────────────────────────────────────────────────

def execute_phase(run: WorkflowRun, phase: dict) -> tuple[str, bool]:
    """
    Voer één fase uit.
    Geeft (output_tekst, needs_approval) terug.
    Bij needs_approval=True moet de aanroeper de run pauzeren.
    Bij type='human_checkpoint' wordt altijd needs_approval=True teruggegeven.
    """
    phase_type = phase.get("type", "")
    artifacts = run.artifacts

    if phase_type == "llm_prompt":
        return _run_llm_prompt(phase, artifacts), phase.get("require_approval", False)

    elif phase_type == "task_loop":
        output = _run_task_loop(phase, artifacts, run)
        return output, phase.get("require_approval", False)

    elif phase_type == "human_checkpoint":
        prompt_text = _render_template(phase.get("prompt", "Controleer en bevestig."), artifacts)
        return prompt_text, True  # altijd wachten

    elif phase_type == "tool_chain":
        return _run_tool_chain(phase, artifacts, run), phase.get("require_approval", False)

    else:
        return f"⚠️ Onbekend fase-type: '{phase_type}'", False


def _run_llm_prompt(phase: dict, artifacts: dict) -> str:
    """Voer een llm_prompt-fase uit: render template → LLM-aanroep → resultaat."""
    from langchain_core.messages import HumanMessage, SystemMessage

    template = phase.get("prompt_template", "")
    prompt = _render_template(template, artifacts)
    system = phase.get("system_prompt", "Je bent een AI-assistent van Regian OS. Antwoord bondig in het Nederlands.")
    llm = _get_llm()
    response = llm.invoke([
        SystemMessage(content=system),
        HumanMessage(content=prompt),
    ])
    content = response.content
    if isinstance(content, list):
        content = " ".join(str(c) for c in content if c)
    return str(content).strip()


def _run_task_loop(phase: dict, artifacts: dict, run: WorkflowRun) -> str:
    """
    Voer een task_loop-fase uit.
    Leest de takenlijst uit artifacts[source_key], maakt een plan per taak
    en voert ze uit via de OrchestratorAgent.
    """
    from regian.core.agent import OrchestratorAgent

    source_key = phase.get("source_key", "task_list")
    raw = artifacts.get(source_key, "")
    if not raw:
        return f"⚠️ Geen takenlijst gevonden onder sleutel '{source_key}'."

    # Verwerk takenlijst: genummerde regels of bullet-points
    tasks = [
        re.sub(r"^\s*[\d]+[\.\)]\s*|^\s*[-*•]\s*", "", line).strip()
        for line in raw.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    tasks = [t for t in tasks if t]

    if not tasks:
        return "⚠️ Kon geen taken extraheren uit de takenlijst."

    orch = OrchestratorAgent()
    results = []
    for i, task in enumerate(tasks, 1):
        plan = orch.plan(task)
        if plan:
            result = orch.execute_plan(plan, source=f"workflow:{run.run_id}", group_id=run.run_id)
        else:
            result = orch.run(task)
        results.append(f"**Taak {i}/{len(tasks)}:** {task}\n{result}")

    return "\n\n---\n\n".join(results)


def _run_tool_chain(phase: dict, artifacts: dict, run: WorkflowRun) -> str:
    """Voer een tool_chain-fase uit: vaste lijst tools deterministisch."""
    from regian.core.agent import registry

    steps = phase.get("steps", [])
    if not steps:
        return "⚠️ Geen stappen gedefinieerd in tool_chain fase."

    results = []
    for step in steps:
        tool_name = _render_template(step.get("tool", ""), artifacts)
        raw_args = step.get("args", {})
        # Render template-variabelen in args-waarden
        args = {k: _render_template(str(v), artifacts) for k, v in raw_args.items()}
        result = registry.call(tool_name, args)
        results.append(f"✅ **{tool_name}**: {result}")

    return "\n\n".join(results)


# ── Workflow starten ──────────────────────────────────────────────────────────

def start_workflow(
    name: str,
    user_input: str,
    project_path: str = "",
) -> WorkflowRun:
    """
    Start een nieuwe workflow-run.
    Voert de eerste fase uit (tenzij die human_checkpoint is).
    Geeft de WorkflowRun terug (gesaved op schijf).
    """
    template = load_workflow(name, project_path)
    now = datetime.now().isoformat(timespec="seconds")
    run = WorkflowRun(
        run_id=str(uuid.uuid4())[:8],
        workflow_id=template.get("id", name),
        workflow_name=template.get("name", name),
        started_at=now,
        updated_at=now,
        status=STATUS_RUNNING,
        current_phase_index=0,
        artifacts={"input": user_input},
        phase_log=[],
        input=user_input,
        project_path=project_path,
    )
    save_run(run)
    return _advance(run, template)


def advance_run(run_id: str, user_feedback: str = "", project_path: str = "") -> WorkflowRun:
    """
    Zet een run voort na menselijke goedkeuring (human_checkpoint).
    user_feedback wordt als artifact 'feedback_<fase_id>' opgeslagen.
    """
    run = load_run(run_id, project_path)
    if run.status != STATUS_WAITING:
        raise ValueError(f"Run '{run_id}' staat niet op 'waiting' (huidig: {run.status}).")

    # Sla feedback op
    phases = _get_phases(run)
    if run.current_phase_index < len(phases):
        phase = phases[run.current_phase_index]
        if user_feedback:
            run.artifacts[f"feedback_{phase['id']}"] = user_feedback

    # Ga naar volgende fase
    run.current_phase_index += 1
    run.status = STATUS_RUNNING
    run.updated_at = datetime.now().isoformat(timespec="seconds")
    save_run(run)

    template = load_workflow(run.workflow_id, project_path)
    return _advance(run, template)


def cancel_run(run_id: str, project_path: str = "") -> WorkflowRun:
    """Annuleer een actieve run."""
    run = load_run(run_id, project_path)
    run.status = STATUS_CANCELLED
    run.updated_at = datetime.now().isoformat(timespec="seconds")
    save_run(run)
    return run


def create_run(name: str, user_input: str, project_path: str = "") -> WorkflowRun:
    """
    Maakt een nieuwe workflow-run aan zonder fasen uit te voeren.
    Gebruik advance_one_phase() om fase-voor-fase te starten.
    """
    template = load_workflow(name, project_path)
    now = datetime.now().isoformat(timespec="seconds")
    run = WorkflowRun(
        run_id=str(uuid.uuid4())[:8],
        workflow_id=template.get("id", name),
        workflow_name=template.get("name", name),
        started_at=now,
        updated_at=now,
        status=STATUS_RUNNING,
        current_phase_index=0,
        artifacts={"input": user_input},
        phase_log=[],
        input=user_input,
        project_path=project_path,
    )
    save_run(run)
    return run


def advance_one_phase(run_id: str, project_path: str = "") -> WorkflowRun:
    """
    Voert precies één fase uit en geeft de bijgewerkte run terug.
    Bij needs_approval zet de run naar WAITING.
    Bij afloop van alle fasen zet de run naar DONE.
    """
    run = load_run(run_id, project_path)
    if run.status != STATUS_RUNNING:
        return run
    template = load_workflow(run.workflow_id, project_path)
    phases = template.get("phases", [])

    if run.current_phase_index >= len(phases):
        run.status = STATUS_DONE
        run.updated_at = datetime.now().isoformat(timespec="seconds")
        save_run(run)
        return run

    phase = phases[run.current_phase_index]
    phase_id = phase.get("id", str(run.current_phase_index))

    try:
        output, needs_approval = execute_phase(run, phase)
    except Exception as exc:
        run.status = STATUS_ERROR
        run.phase_log.append({
            "phase_id": phase_id,
            "phase_name": phase.get("name", phase_id),
            "status": "error",
            "output": str(exc),
            "ts": datetime.now().isoformat(timespec="seconds"),
        })
        run.updated_at = datetime.now().isoformat(timespec="seconds")
        save_run(run)
        return run

    output_key = phase.get("output_key")
    if output_key:
        run.artifacts[output_key] = output

    run.phase_log.append({
        "phase_id": phase_id,
        "phase_name": phase.get("name", phase_id),
        "status": "waiting" if needs_approval else "done",
        "output": output,
        "ts": datetime.now().isoformat(timespec="seconds"),
    })
    run.updated_at = datetime.now().isoformat(timespec="seconds")

    if needs_approval:
        run.status = STATUS_WAITING
        save_run(run)
        return run

    run.current_phase_index += 1
    if run.current_phase_index >= len(phases):
        run.status = STATUS_DONE
    save_run(run)
    return run


def revise_run(run_id: str, feedback: str, project_path: str = "") -> WorkflowRun:
    """
    Hervoert de huidige wachtende fase met gebruikersfeedback.
    De vorige uitvoer + feedback worden als context aan het LLM meegegeven.
    De run blijft in WAITING-status zodat de gebruiker opnieuw kan goedkeuren.
    """
    run = load_run(run_id, project_path)
    if run.status != STATUS_WAITING:
        raise ValueError(f"Run '{run_id}' staat niet op 'waiting' (huidig: {run.status}).")

    phases = _get_phases(run)
    phase = phases[run.current_phase_index]
    phase_id = phase.get("id", str(run.current_phase_index))

    # Vorige uitvoer ophalen uit phase_log
    prev_output = ""
    for entry in reversed(run.phase_log):
        if entry.get("phase_id") == phase_id:
            prev_output = entry.get("output", "")
            break

    # Bouw aangepaste fase: inject feedback + vorige uitvoer in het prompt
    revised_phase = dict(phase)
    if phase.get("type") == "llm_prompt" and phase.get("prompt_template"):
        revised_phase["prompt_template"] = (
            phase["prompt_template"]
            + "\n\n---\n## Vorige uitvoer (ter referentie):\n"
            + prev_output
            + "\n\n## Bijsturing van de gebruiker:\n"
            + feedback
            + "\n\nVerwerk de bijsturing volledig in een herziene versie van het document."
        )
    elif phase.get("type") == "human_checkpoint":
        revised_phase = dict(phase)
        run.artifacts["feedback_revision"] = feedback

    try:
        output, _ = execute_phase(run, revised_phase)
    except Exception as exc:
        raise RuntimeError(f"Heruitvoering mislukt: {exc}") from exc

    output_key = phase.get("output_key")
    if output_key:
        run.artifacts[output_key] = output

    new_entry = {
        "phase_id": phase_id,
        "phase_name": phase.get("name", phase_id),
        "status": "waiting",
        "output": output,
        "ts": datetime.now().isoformat(timespec="seconds"),
        "revised": True,
        "feedback": feedback,
    }
    if run.phase_log and run.phase_log[-1].get("phase_id") == phase_id:
        run.phase_log[-1] = new_entry
    else:
        run.phase_log.append(new_entry)

    run.status = STATUS_WAITING
    run.updated_at = datetime.now().isoformat(timespec="seconds")
    save_run(run)
    return run


def _get_phases(run: WorkflowRun) -> list[dict]:
    """Laad de fasen van de workflow die bij deze run hoort."""
    try:
        template = load_workflow(run.workflow_id, run.project_path)
        return template.get("phases", [])
    except FileNotFoundError:
        return []


def _advance(run: WorkflowRun, template: dict) -> WorkflowRun:
    """
    Voert opeenvolgende fasen uit totdat:
    - de workflow klaar is (alle fasen doorlopen), of
    - een fase needs_approval=True retourneert (pauze).
    """
    phases = template.get("phases", [])

    while run.current_phase_index < len(phases):
        phase = phases[run.current_phase_index]
        phase_id = phase.get("id", str(run.current_phase_index))

        try:
            output, needs_approval = execute_phase(run, phase)
        except Exception as exc:
            run.status = STATUS_ERROR
            run.phase_log.append({
                "phase_id": phase_id,
                "status": "error",
                "output": str(exc),
                "ts": datetime.now().isoformat(timespec="seconds"),
            })
            run.updated_at = datetime.now().isoformat(timespec="seconds")
            save_run(run)
            return run

        # Sla output op in artifacts
        output_key = phase.get("output_key")
        if output_key:
            run.artifacts[output_key] = output

        run.phase_log.append({
            "phase_id": phase_id,
            "phase_name": phase.get("name", phase_id),
            "status": "waiting" if needs_approval else "done",
            "output": output,
            "ts": datetime.now().isoformat(timespec="seconds"),
        })
        run.updated_at = datetime.now().isoformat(timespec="seconds")

        if needs_approval:
            run.status = STATUS_WAITING
            save_run(run)
            return run

        run.current_phase_index += 1

    # Alle fasen doorlopen
    run.status = STATUS_DONE
    run.updated_at = datetime.now().isoformat(timespec="seconds")
    save_run(run)
    return run
