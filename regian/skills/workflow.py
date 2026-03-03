# regian/skills/workflow.py
"""
Workflow-skills: beheer van Regian OS workflows.

Workflows zijn JSON-bestanden die een geordende reeks fasen beschrijven.
Elke fase kan een LLM-aanroep, een agent-taakloop, een menselijke checkpoint
of een tool-keten zijn.

Ingebouwde templates staan in regian/workflows/*.json.
Projectspecifieke templates staan in <project>/.regian_workflow/*.json.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


def _project_path() -> str:
    """Geeft het pad van het actieve project (of leeg als er geen actief project is)."""
    from regian.settings import get_active_project
    name = get_active_project()
    if not name:
        return ""
    try:
        from regian.skills.project import _read_manifest
        return _read_manifest(name)["path"]
    except Exception:
        return ""


# ── Overzicht ─────────────────────────────────────────────────────────────────

def list_workflows() -> str:
    """Toont alle beschikbare workflow-templates (ingebouwd + projectspecifiek)."""
    from regian.core.workflow import list_workflows as _list
    items = _list(_project_path())
    if not items:
        return "Geen workflow-templates gevonden."
    lines = ["**Beschikbare workflows:**\n"]
    for w in items:
        lines.append(f"- `{w['id']}` — **{w['name']}** ({w['phases']} fasen)\n  {w['description']}")
    return "\n".join(lines)


def list_workflow_runs() -> str:
    """Toont alle workflow-runs van het actieve project (actief en afgerond)."""
    from regian.core.workflow import list_runs, STATUS_WAITING, STATUS_RUNNING
    runs = list_runs(_project_path())
    if not runs:
        return "Geen workflow-runs gevonden."
    lines = ["**Workflow-runs:**\n"]
    for r in runs:
        badge = {"running": "🔄", "waiting": "⏸️", "done": "✅", "cancelled": "❌", "error": "💥"}.get(r.status, "❓")
        phase_info = f"fase {r.current_phase_index + 1}" if r.status in (STATUS_WAITING, STATUS_RUNNING) else r.status
        lines.append(f"- `{r.run_id}` {badge} **{r.workflow_name}** — {phase_info} — gestart {r.started_at[:16]}")
    return "\n".join(lines)


# ── Starten en beheren ────────────────────────────────────────────────────────

def start_workflow(name: str, input: str) -> str:
    """
    Start een workflow met een initieel idee of invoer.
    name: ID van de workflow-template (bijv. van_idee_tot_mvp).
    input: het idee of de opdracht die door de workflow verwerkt wordt.
    """
    from regian.core.workflow import start_workflow as _start, STATUS_WAITING, STATUS_DONE, STATUS_ERROR
    try:
        run = _start(name, input, _project_path())
    except FileNotFoundError as e:
        return f"❌ {e}"

    return _format_run_status(run)


def workflow_status(run_id: str) -> str:
    """Toont de huidige fase en alle artifacts van een workflow-run."""
    from regian.core.workflow import load_run
    try:
        run = load_run(run_id, _project_path())
    except FileNotFoundError:
        return f"❌ Run '{run_id}' niet gevonden."
    return _format_run_status(run, verbose=True)


def approve_workflow(run_id: str, feedback: str = "") -> str:
    """
    Bevestig een workflow die wacht op menselijke goedkeuring.
    run_id: ID van de te hervatten run.
    feedback: optionele bijsturingsnotitie voor de volgende fase.
    """
    from regian.core.workflow import advance_run
    try:
        run = advance_run(run_id, feedback, _project_path())
    except (FileNotFoundError, ValueError) as e:
        return f"❌ {e}"
    return _format_run_status(run)


def cancel_workflow(run_id: str) -> str:
    """Annuleert een actieve of wachtende workflow-run."""
    from regian.core.workflow import cancel_run
    try:
        run = cancel_run(run_id, _project_path())
        return f"❌ Run `{run_id}` geannuleerd."
    except FileNotFoundError as e:
        return f"❌ {e}"


# ── Template-beheer ───────────────────────────────────────────────────────────

def create_workflow_template(name: str, description: str) -> str:
    """
    Laat de LLM een nieuw workflow-template genereren en slaat het op als JSON.
    name: technische naam (wordt de bestandsnaam, bijv. code_review).
    description: beschrijving van het doel van de workflow.
    """
    from langchain_core.messages import HumanMessage, SystemMessage
    from regian.core.workflow import _workflow_dir, _builtin_template_dir

    # Laad een bestaand template als voorbeeld
    example_path = _builtin_template_dir() / "van_idee_tot_mvp.json"
    example = example_path.read_text(encoding="utf-8") if example_path.exists() else "{}"

    from regian.core.agent import OrchestratorAgent
    llm = OrchestratorAgent().base_llm

    prompt = f"""Genereer een Regian OS workflow-template als JSON.

Naam: {name}
Beschrijving: {description}

Gebruik uitsluitend deze fase-types:
- llm_prompt: LLM-aanroep met prompt_template (gebruik {{{{variabele}}}} voor substitutie), output_key, require_approval (bool)
- task_loop: itereert over een takenlijst uit artifacts[source_key], require_approval (bool)
- human_checkpoint: pauzeer voor menselijke beoordeling, prompt-veld met context
- tool_chain: vaste lijst steps met tool en args

Voorbeeld template:
{example}

Geef ENKEL de JSON terug, geen uitleg, geen markdown-blokken."""

    response = llm.invoke([
        SystemMessage(content="Je bent een expert in het ontwerpen van Regian OS workflows. Genereer valide JSON."),
        HumanMessage(content=prompt),
    ])
    content = response.content
    if isinstance(content, list):
        content = " ".join(str(c) for c in content if c)
    content = content.strip()
    content = re.sub(r"^```[a-z]*\n?", "", content)
    content = re.sub(r"\n?```$", "", content)

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return f"❌ LLM genereerde ongeldige JSON: {e}\n\nRuwe output:\n{content[:500]}"

    # Sla op in project of root
    wdir = _workflow_dir(_project_path())
    wdir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^a-z0-9_-]", "_", name.lower())
    dest = wdir / f"{safe_name}.json"
    dest.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return f"✅ Workflow-template '{safe_name}' opgeslagen in `{dest}`."


# ── BPMN import/export ────────────────────────────────────────────────────────

def import_bpmn(xml_path: str) -> str:
    """
    Converteert een BPMN 2.0 XML-bestand (export van bpmn.io) naar een Regian workflow-template JSON.
    xml_path: pad naar het .bpmn XML-bestand (relatief aan projectpad of absoluut).
    """
    from regian.skills.files import _resolve
    from regian.core.workflow import _workflow_dir

    src = _resolve(xml_path)
    if not src.exists():
        return f"❌ Bestand niet gevonden: {src}"

    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(str(src))
        root = tree.getroot()
    except Exception as e:
        return f"❌ Kon XML niet parsen: {e}"

    ns = {
        "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
    }

    # Bepaal het process-element (neemt de eerste)
    process = root.find(".//bpmn:process", ns)
    if process is None:
        process = root.find(".//process")
    if process is None:
        return "❌ Geen BPMN-process element gevonden in het XML-bestand."

    process_name = process.get("name", src.stem)
    phases = []

    # Doorzoek alle flow-elementen in volgorde (sequence flows bepalen de volgorde)
    _BPMN_TYPE_MAP = {
        "userTask":     "human_checkpoint",
        "serviceTask":  "llm_prompt",
        "scriptTask":   "tool_chain",
        "callActivity": "task_loop",
        "task":         "llm_prompt",
    }

    # Bouw een id→element map
    elements: dict[str, ET.Element] = {}
    tag_map: dict[str, str] = {}
    for elem in process:
        eid = elem.get("id", "")
        if eid:
            elements[eid] = elem
            local_tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            tag_map[eid] = local_tag

    # Volg de sequence flows om volgorde te bepalen
    sequence_flows: dict[str, str] = {}  # sourceRef → targetRef
    for elem in process:
        local_tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if local_tag == "sequenceFlow":
            sequence_flows[elem.get("sourceRef", "")] = elem.get("targetRef", "")

    # Zoek startEvent
    visited = set()
    current_id = None
    for eid, tag in tag_map.items():
        if tag == "startEvent":
            current_id = sequence_flows.get(eid)
            break

    # Traverse inclusief fallback (gesorteerd op positie indien geen sequence)
    seen_ids = set()
    if current_id is None:
        # Geen startEvent gevonden: gebruik alle tasks in documentvolgorde
        ordered_ids = [eid for eid, tag in tag_map.items() if tag in _BPMN_TYPE_MAP]
    else:
        ordered_ids = []
        while current_id and current_id not in seen_ids:
            seen_ids.add(current_id)
            if tag_map.get(current_id, "") not in ("endEvent", ""):
                ordered_ids.append(current_id)
            current_id = sequence_flows.get(current_id)

    for eid in ordered_ids:
        elem = elements.get(eid)
        if elem is None:
            continue
        local_tag = tag_map.get(eid, "")
        phase_type = _BPMN_TYPE_MAP.get(local_tag, "llm_prompt")
        elem_name = elem.get("name", eid)

        # Documentatie of extensie-elementen uitlezen als prompt
        doc = ""
        for child in elem:
            child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if child_tag == "documentation" and child.text:
                doc = child.text.strip()
                break

        phase: dict = {
            "id":   re.sub(r"[^a-z0-9_]", "_", elem_name.lower()),
            "name": elem_name,
            "type": phase_type,
            "icon": {"human_checkpoint": "🔍", "llm_prompt": "🧠", "tool_chain": "⚙️", "task_loop": "🔄"}.get(phase_type, "📋"),
        }

        if phase_type == "llm_prompt":
            phase["prompt_template"] = doc or f"Voer uit: {elem_name}\n\nContext: {{{{input}}}}"
            phase["output_key"] = re.sub(r"[^a-z0-9_]", "_", elem_name.lower()) + "_output"
            phase["require_approval"] = False
        elif phase_type == "human_checkpoint":
            phase["prompt"] = doc or f"Controleer: {elem_name}"
        elif phase_type == "task_loop":
            phase["source_key"] = "task_list"
            phase["require_approval"] = True
        elif phase_type == "tool_chain":
            phase["steps"] = []
            phase["require_approval"] = False

        phases.append(phase)

    workflow = {
        "id":          re.sub(r"[^a-z0-9_-]", "_", process_name.lower()),
        "name":        process_name,
        "description": f"Geïmporteerd vanuit BPMN: {src.name}",
        "version":     "1.0",
        "phases":      phases,
    }

    wdir = _workflow_dir(_project_path())
    wdir.mkdir(parents=True, exist_ok=True)
    dest = wdir / f"{workflow['id']}.json"
    dest.write_text(json.dumps(workflow, indent=2, ensure_ascii=False), encoding="utf-8")
    return (
        f"✅ BPMN geïmporteerd: {len(phases)} fasen → `{dest}`\n"
        f"Start met: `/start_workflow {workflow['id']} <invoer>`"
    )


def export_bpmn(workflow_name: str) -> str:
    """
    Exporteert een workflow-template als BPMN 2.0 XML-bestand voor gebruik in bpmn.io.
    workflow_name: ID van de workflow-template.
    """
    from regian.core.workflow import load_workflow, _workflow_dir
    from regian.skills.files import _resolve

    try:
        wf = load_workflow(workflow_name, _project_path())
    except FileNotFoundError as e:
        return f"❌ {e}"

    phases = wf.get("phases", [])
    wf_id = wf.get("id", workflow_name)
    wf_name = wf.get("name", workflow_name)

    # BPMN-type mapping (omgekeerd)
    _TYPE_TO_BPMN = {
        "human_checkpoint": "bpmn:userTask",
        "llm_prompt":       "bpmn:serviceTask",
        "tool_chain":       "bpmn:scriptTask",
        "task_loop":        "bpmn:callActivity",
    }
    _DI_Y_START = 100
    _DI_X_START = 180
    _DI_STEP    = 180
    _DI_W, _DI_H = 140, 60

    nodes: list[str] = []
    shapes: list[str] = []
    flows: list[str] = []
    di_flows: list[str] = []

    prev_id = f"start_{wf_id}"
    nodes.append(f'<bpmn:startEvent id="{prev_id}" name="Start"/>')
    shapes.append(
        f'<bpmndi:BPMNShape id="{prev_id}_di" bpmnElement="{prev_id}">'
        f'<dc:Bounds x="{_DI_X_START}" y="{_DI_Y_START + 15}" width="30" height="30"/>'
        f'</bpmndi:BPMNShape>'
    )

    for i, phase in enumerate(phases):
        pid   = phase.get("id", f"phase_{i}")
        pname = phase.get("name", pid)
        ptype = phase.get("type", "llm_prompt")
        btype = _TYPE_TO_BPMN.get(ptype, "bpmn:task")
        doc   = phase.get("prompt_template") or phase.get("prompt") or ""
        x     = _DI_X_START + (i + 1) * _DI_STEP

        node = f'<{btype} id="{pid}" name="{pname}">'
        if doc:
            node += f'<bpmn:documentation>{_xml_escape(doc[:200])}</bpmn:documentation>'
        node += f'</{btype}>'
        nodes.append(node)

        shapes.append(
            f'<bpmndi:BPMNShape id="{pid}_di" bpmnElement="{pid}">'
            f'<dc:Bounds x="{x}" y="{_DI_Y_START}" width="{_DI_W}" height="{_DI_H}"/>'
            f'</bpmndi:BPMNShape>'
        )

        fid = f"flow_{prev_id}_{pid}"
        flows.append(f'<bpmn:sequenceFlow id="{fid}" sourceRef="{prev_id}" targetRef="{pid}"/>')
        mid_x = _DI_X_START + i * _DI_STEP + _DI_W // 2 + 30
        mid_y = _DI_Y_START + _DI_H // 2
        di_flows.append(
            f'<bpmndi:BPMNEdge id="{fid}_di" bpmnElement="{fid}">'
            f'<di:waypoint x="{mid_x - 20}" y="{mid_y}"/>'
            f'<di:waypoint x="{x}" y="{mid_y}"/>'
            f'</bpmndi:BPMNEdge>'
        )
        prev_id = pid

    end_id = f"end_{wf_id}"
    end_x  = _DI_X_START + (len(phases) + 1) * _DI_STEP
    nodes.append(f'<bpmn:endEvent id="{end_id}" name="Klaar"/>')
    shapes.append(
        f'<bpmndi:BPMNShape id="{end_id}_di" bpmnElement="{end_id}">'
        f'<dc:Bounds x="{end_x}" y="{_DI_Y_START + 15}" width="30" height="30"/>'
        f'</bpmndi:BPMNShape>'
    )
    fid = f"flow_{prev_id}_{end_id}"
    flows.append(f'<bpmn:sequenceFlow id="{fid}" sourceRef="{prev_id}" targetRef="{end_id}"/>')

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions
  xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
  xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
  id="Definitions_{wf_id}"
  targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_{wf_id}" name="{_xml_escape(wf_name)}" isExecutable="true">
    {"".join(nodes)}
    {"".join(flows)}
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_{wf_id}">
    <bpmndi:BPMNPlane id="BPMNPlane_{wf_id}" bpmnElement="Process_{wf_id}">
      {"".join(shapes)}
      {"".join(di_flows)}
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>"""

    from regian.skills.files import _resolve as _res
    from regian.settings import get_root_dir, get_active_project
    proj_path = _project_path()
    out_dir = Path(proj_path) if proj_path else Path(get_root_dir())
    dest = out_dir / f"{wf_id}.bpmn"
    dest.write_text(xml, encoding="utf-8")
    return f"✅ Geëxporteerd naar `{dest}`\nOpen dit bestand in https://bpmn.io om de flow te visualiseren."


def _xml_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# ── Format helper ─────────────────────────────────────────────────────────────

def _format_run_status(run, verbose: bool = False) -> str:
    from regian.core.workflow import STATUS_WAITING, STATUS_DONE, STATUS_ERROR, _get_phases

    badge = {"running": "🔄", "waiting": "⏸️", "done": "✅", "cancelled": "❌", "error": "💥"}.get(run.status, "❓")
    phases = _get_phases(run)
    total = len(phases)
    current = run.current_phase_index

    lines = [
        f"{badge} **{run.workflow_name}** — run `{run.run_id}`",
        f"Status: **{run.status}** | Fase: {min(current + 1, total)}/{total} | Gestart: {run.started_at[:16]}",
    ]

    if run.status == STATUS_WAITING and current < total:
        phase = phases[current]
        last_log = run.phase_log[-1] if run.phase_log else {}
        lines.append(f"\n⏸️ **Wacht op goedkeuring — Fase: {phase.get('name', phase['id'])}**")
        output = last_log.get("output", "")
        if output:
            lines.append(f"\n{output[:2000]}")
        lines.append(f"\nGebruik: `/approve_workflow {run.run_id}` om door te gaan (optioneel met feedbacktekst).")

    elif run.status == STATUS_DONE:
        lines.append("\n✅ Workflow afgerond.")
        if verbose and run.artifacts:
            for key, val in run.artifacts.items():
                if key != "input":
                    lines.append(f"\n**{key}:**\n{str(val)[:500]}")

    elif run.status == STATUS_ERROR:
        last_log = run.phase_log[-1] if run.phase_log else {}
        lines.append(f"\n💥 Fout: {last_log.get('output', 'onbekend')}")

    if verbose and run.phase_log:
        lines.append("\n**Fase-log:**")
        for entry in run.phase_log:
            icon = "✅" if entry["status"] == "done" else "⏸️" if entry["status"] == "waiting" else "💥"
            lines.append(f"- {icon} `{entry['phase_id']}` — {entry['ts'][:16]}")

    return "\n".join(lines)
