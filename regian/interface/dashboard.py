# regian/interface/dashboard.py
import importlib
import inspect
import pkgutil
import streamlit as st
import regian.skills as _skills_pkg
from regian.core.agent import registry, OrchestratorAgent, RegianAgent, CONFIRM_REQUIRED
from regian.core.scheduler import (
    get_scheduler, get_all_jobs, get_next_run,
    add_scheduled_job, remove_scheduled_job, toggle_scheduled_job,
    run_job_now_by_id, parse_schedule,
)
from regian.settings import (
    get_root_dir, set_root_dir,
    get_llm_provider, set_llm_provider,
    get_llm_model, set_llm_model,
    get_confirm_required, set_confirm_required,
)


_GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-flash-latest"]
_OLLAMA_MODELS = ["mistral", "llama3.1:8b", "llama3.2", "deepseek-r1:8b"]


@st.cache_resource
def get_orchestrator():
    """Éénmalig aangemaakt voor de hele server — niet per sessie."""
    return OrchestratorAgent()


@st.cache_resource
def get_agent(provider: str, model: str):
    """Éénmalig aangemaakt per provider+model combinatie."""
    return RegianAgent(provider=provider, model=model)


@st.cache_resource
def _start_scheduler():
    """Start de achtergrond-scheduler éénmalig bij het laden van de app."""
    return get_scheduler()


def _handle_slash_command(prompt: str) -> tuple:
    """
    Parst '/function_name [args]' en roept de juiste skill aan via de registry.
    Geen hardcoded skill-imports nodig. Verander skills zonder aanpassingen hier.
    """
    parts = prompt[1:].split(" ", 1)
    name = parts[0].strip()
    raw_args = parts[1].strip() if len(parts) > 1 else ""
    result = registry.call_by_string(name, raw_args)
    badge = f"/{name}({raw_args})" if raw_args else f"/{name}()"
    return result, badge


def start_gui():
    st.set_page_config(page_title="Regian OS Cockpit", page_icon="🚀", layout="wide")
    st.title("🚀 Regian OS - Control Center")

    # ── Sidebar (minimaal) ────────────────────────────────────
    _start_scheduler()  # start achtergrond-scheduler éénmalig
    st.sidebar.caption(f"🔧 {len(registry.tools)} skills geladen")
    if st.sidebar.button("🗑️ Reset Chat"):
        st.session_state.messages = []
        st.rerun()

    # ── Cron notificaties ─────────────────────────────────────
    if "notif_last_seen" not in st.session_state:
        st.session_state.notif_last_seen = ""

    all_jobs = get_all_jobs()
    recent = sorted(
        [
            (jid, j) for jid, j in all_jobs.items()
            if j.get("last_run") and j["last_run"] > st.session_state.notif_last_seen
        ],
        key=lambda x: x[1]["last_run"],
        reverse=True,
    )
    badge = f" ({len(recent)} nieuw)" if recent else ""
    with st.sidebar.expander(f"🔔 Notificaties{badge}", expanded=False):
        if recent:
            for jid, j in recent:
                icon = j.get("last_status", "")
                when = j["last_run"].replace("T", " ")
                st.markdown(f"**{icon} {jid}** — {when}")
                output = j.get("last_output", "")
                if output:
                    st.code(output[:300], language=None)
            if st.button("✅ Markeer als gelezen", key="notif_clear"):
                from datetime import datetime as _dt
                st.session_state.notif_last_seen = _dt.now().isoformat(timespec="seconds")
                st.rerun()
        else:
            st.caption("Geen nieuwe meldingen.")

    # ── Session state defaults (éénmalig laden uit .env) ─────
    if "provider" not in st.session_state:
        st.session_state.provider = get_llm_provider()
    if "model" not in st.session_state:
        st.session_state.model = get_llm_model()

    # ── Tabs ──────────────────────────────────────────────────
    tab_chat, tab_help, tab_cron, tab_settings = st.tabs([
        "💬 Chat", "📖 Help & Commands", "📅 Cron", "⚙️ Instellingen"
    ])

    # ── CHAT TAB ──────────────────────────────────────────────
    with tab_chat:
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "pending_plan" not in st.session_state:
            st.session_state.pending_plan = None

        confirm_set = CONFIRM_REQUIRED()

        # ── HITL: bevestiging afwachten ────────────────────────
        if st.session_state.pending_plan is not None:
            plan = st.session_state.pending_plan

            # Toon chatgeschiedenis als context
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            st.warning("⚠️ **Bevestiging vereist** — dit plan bevat destructieve operaties:")
            for i, step in enumerate(plan, 1):
                tool = step.get("tool", "")
                args = step.get("args", {})
                icon = "🔴" if tool in confirm_set else "🟢"
                st.markdown(f"{icon} **Stap {i}:** `{tool}` — {args}")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Bevestigen & uitvoeren", type="primary"):
                    result = get_orchestrator().execute_plan(plan)
                    st.session_state.messages.append({"role": "assistant", "content": result})
                    st.session_state.pending_plan = None
                    st.rerun()
            with col2:
                if st.button("❌ Annuleren"):
                    st.session_state.messages.append({"role": "assistant", "content": "❌ Opdracht geannuleerd."})
                    st.session_state.pending_plan = None
                    st.rerun()

        else:
            # ── Normale chat ───────────────────────────────────────
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    if message.get("badge"):
                        st.info(f"Direct: {message['badge']}")
                    st.markdown(message["content"])

            if prompt := st.chat_input("Wat gaan we doen? (Typ / voor directe commands)"):
                st.session_state.messages.append({"role": "user", "content": prompt})

                badge = None
                if prompt.startswith("/"):
                    stripped = prompt[1:].strip()
                    if not stripped:
                        response = registry.list_commands()
                    else:
                        response, badge = _handle_slash_command(prompt)
                    st.session_state.messages.append({"role": "assistant", "content": response, "badge": badge})
                    st.rerun()
                else:
                    with st.spinner("Planner is aan het werk..."):
                        plan = get_orchestrator().plan(prompt)

                    # Controleer of plan gevaarlijke stappen bevat
                    dangerous = [s for s in plan if s.get("tool") in confirm_set]
                    if dangerous:
                        st.session_state.pending_plan = plan
                        st.rerun()
                    else:
                        with st.spinner("Uitvoeren..."):
                            if plan:
                                response = get_orchestrator().execute_plan(plan)
                            else:
                                response = get_orchestrator().run(prompt)
                        st.session_state.messages.append({"role": "assistant", "content": response, "badge": badge})
                        st.rerun()

    # ── HELP TAB ──────────────────────────────────────────────
    with tab_help:
        sub = st.radio(
            "",
            ["📋 Commands", "📚 Documentatie"],
            horizontal=True,
            label_visibility="collapsed",
            key="help_sub",
        )

        if sub == "📋 Commands":
            st.subheader("📋 Skills & Directe Commands")
            cmd_filter = st.text_input(
                "🔍 Filter",
                placeholder="bijv. github, delete, schedule...",
                key="help_cmd_filter",
            )
            q = cmd_filter.strip().lower()
            html_items = []
            for t in sorted(registry.tools, key=lambda x: x.name):
                func = registry._functions.get(t.name)
                if not func:
                    continue
                module = func.__module__.split(".")[-1]
                sig = str(inspect.signature(func))
                doc = (inspect.getdoc(func) or "").split("\n")[0]
                if q and q not in module and q not in t.name and q not in doc.lower():
                    continue
                html_items.append(
                    f"<div style='padding:6px 4px 8px;border-bottom:1px solid #2a2a2a'>"
                    f"<span style='font-size:0.75rem;color:#888;margin-right:8px'>{module}</span>"
                    f"<code style='font-size:0.85rem'>/{t.name}{sig}</code>"
                    f"<div style='margin-top:2px;font-size:0.82rem;color:#bbb'>{doc}</div>"
                    f"</div>"
                )
            if html_items:
                st.markdown(
                    "<div style='font-family:sans-serif'>" + "".join(html_items) + "</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.info(f"Geen commands gevonden voor '{cmd_filter}'.")

        else:  # Documentatie
            st.subheader("📚 Skill Documentatie")
            search = st.text_input(
                "🔍 Filter",
                placeholder="bijv. github, files, cron, create_skill...",
                key="help_doc_filter",
            )
            q = search.strip().lower()

            for _, mod_name, _ in pkgutil.iter_modules(
                _skills_pkg.__path__, _skills_pkg.__name__ + "."
            ):
                module = importlib.import_module(mod_name)
                short = mod_name.split(".")[-1]

                all_funcs = [
                    (name, func)
                    for name, func in inspect.getmembers(module, inspect.isfunction)
                    if not name.startswith("_") and func.__module__ == module.__name__
                ]
                if not all_funcs:
                    continue

                if q:
                    funcs = [
                        (n, f) for n, f in all_funcs
                        if q in short.lower() or q in n.lower() or q in (inspect.getdoc(f) or "").lower()
                    ]
                    if not funcs:
                        continue
                else:
                    funcs = all_funcs

                with st.expander(f"🔧 **{short}** &nbsp;·&nbsp; {len(funcs)} functie(s)"):
                    for name, func in funcs:
                        sig = str(inspect.signature(func))
                        doc = inspect.getdoc(func) or "Geen beschrijving."
                        st.markdown(f"**`/{name}{sig}`**")
                        st.caption(doc)

    # ── CRON TAB ─────────────────────────────────────────────────
    with tab_cron:
        st.subheader("📅 Geplande Taken")

        # ── Nieuwe taak aanmaken ─────────────────────────────
        with st.expander("➕ Nieuwe taak toevoegen", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                new_id = st.text_input("Naam (job_id)", placeholder="bijv. dagelijkse_backup", key="cron_new_id")
                new_type = st.selectbox("Type", ["/command", "shell", "AI-prompt"], key="cron_new_type")
                new_schedule = st.text_input(
                    "Schema",
                    placeholder="bijv. dagelijks om 09:00 | elke 15 minuten | 0 9 * * 1-5",
                    key="cron_new_schedule",
                )
            with col2:
                new_task = st.text_area(
                    "Taak",
                    placeholder={
                        "/command": "/repo_list  of  /run_shell git status",
                        "shell":    "git pull  of  python3 script.py",
                        "AI-prompt": "Controleer open issues en maak een samenvatting",
                    }.get(new_type, ""),
                    key="cron_new_task",
                    height=80,
                )
                new_desc = st.text_input("Beschrijving (optioneel)", key="cron_new_desc")

            # Schedule-formaten helper
            with st.expander("ℹ️ Geldige schema-formaten"):
                st.markdown("""
| Formaat | Voorbeeld |
|---|---|
| Interval | `elke 5 minuten` \u00b7 `elk uur` \u00b7 `elke 2 uur` |
| Dagelijks | `dagelijks om 09:00` |
| Dag van week | `elke maandag om 08:00` |
| Werkdagen | `werkdagen om 07:30` |
| Cron expressie | `0 9 * * 1-5` |
""")

            if st.button("💾 Taak opslaan", key="cron_save"):
                if not new_id or not new_task or not new_schedule:
                    st.error("❌ Vul naam, taak en schema in.")
                else:
                    type_map = {"/command": "command", "shell": "shell", "AI-prompt": "prompt"}
                    job_type = type_map[new_type]
                    task = new_task.strip()
                    if job_type == "command" and not task.startswith("/"):
                        task = "/" + task
                    try:
                        parse_schedule(new_schedule)  # valideer eerst
                        result = add_scheduled_job(
                            job_id=new_id.strip().replace(" ", "_"),
                            task=task,
                            job_type=job_type,
                            schedule=new_schedule.strip(),
                            description=new_desc.strip(),
                        )
                        st.success(f"✅ Taak '{result}' aangemaakt!")
                        st.rerun()
                    except ValueError as e:
                        st.error(f"❌ Ongeldig schema: {e}")

        st.markdown("---")

        # ── Overzicht bestaande taken ──────────────────────────
        jobs = get_all_jobs()
        if not jobs:
            st.info("Geen geplande taken. Voeg er een toe via het formulier hierboven.")
        else:
            st.caption(f"{len(jobs)} taak(en) geconfigureerd")
            for job_id, job in sorted(jobs.items()):
                enabled = job.get("enabled", True)
                job_type = job.get("type", "command")
                type_icon = {"⚡", "🖥️", "🧠"}.pop if False else {
                    "command": "⚡", "shell": "🖥️", "prompt": "🧠"
                }.get(job_type, "📅")
                status_icon = "🟢" if enabled else "⏸️"
                next_run = get_next_run(job_id) if enabled else "—"
                last_run = job.get("last_run") or "—"
                last_status = job.get("last_status") or ""

                with st.container(border=True):
                    h1, h2, h3, h4, h5 = st.columns([3, 2, 2, 2, 3])
                    with h1:
                        st.markdown(f"{status_icon} **{job_id}** {type_icon}")
                        st.caption(job.get("description", ""))
                    with h2:
                        st.caption("Schema")
                        st.code(job.get("schedule", ""), language=None)
                    with h3:
                        st.caption("Volgende run")
                        st.text(next_run)
                    with h4:
                        st.caption("Laatste run")
                        st.text(f"{last_run} {last_status}")
                    with h5:
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            if st.button("▶️", key=f"run_{job_id}", help="Nu uitvoeren"):
                                run_job_now_by_id(job_id)
                                st.toast(f"⚡ '{job_id}' uitgevoerd")
                                st.rerun()
                        with c2:
                            lbl = "⏸️" if enabled else "▶️"
                            hlp = "Pauzeren" if enabled else "Activeren"
                            if st.button(lbl, key=f"tog_{job_id}", help=hlp):
                                toggle_scheduled_job(job_id, not enabled)
                                st.rerun()
                        with c3:
                            if st.button("🗑️", key=f"del_{job_id}", help="Verwijderen"):
                                remove_scheduled_job(job_id)
                                st.rerun()

                    # Output van laatste run
                    last_output = job.get("last_output")
                    if last_output:
                        with st.expander("📄 Laatste output"):
                            st.code(last_output, language=None)

    # ── INSTELLINGEN TAB ──────────────────────────────────────
    with tab_settings:
        st.subheader("⚙️ Instellingen")

        # 1. Werkmap
        st.markdown("### 📁 Werkmap (Root Directory)")
        current_root = get_root_dir()
        new_root = st.text_input("Root directory", value=current_root, key="settings_root")
        if st.button("💾 Opslaan", key="save_root"):
            saved = set_root_dir(new_root)
            st.success(f"✅ Opgeslagen: `{saved}`")
            st.rerun()

        st.markdown("---")

        # 2. Chat Model
        st.markdown("### 🤖 Chat Model")
        provider_options = ["gemini", "ollama"]
        current_provider = st.session_state.provider
        new_provider = st.selectbox(
            "LLM Provider",
            provider_options,
            index=provider_options.index(current_provider) if current_provider in provider_options else 0,
            key="settings_provider",
        )
        model_options = _GEMINI_MODELS if new_provider == "gemini" else _OLLAMA_MODELS
        current_model = st.session_state.model if st.session_state.model in model_options else model_options[0]
        new_model = st.selectbox(
            "Model",
            model_options,
            index=model_options.index(current_model),
            key="settings_model",
        )
        if st.button("💾 Model opslaan", key="save_model"):
            set_llm_provider(new_provider)
            set_llm_model(new_model)
            st.session_state.provider = new_provider
            st.session_state.model = new_model
            get_agent.clear()  # verwijder gecachede agent zodat nieuwe aangemaakt wordt
            st.success(f"✅ Model opgeslagen: `{new_provider} / {new_model}`")
            st.rerun()

        st.markdown("---")

        # 3. HITL
        st.markdown("### 🔐 Bevestiging vereist (HITL)")
        st.caption("Skills waarbij de gebruiker expliciet moet bevestigen vóór uitvoering.")
        all_skill_names = sorted(t.name for t in registry.tools)
        current_confirm = get_confirm_required()
        new_confirm = st.multiselect(
            "Skills die bevestiging vereisen",
            options=all_skill_names,
            default=[s for s in current_confirm if s in all_skill_names],
            key="settings_confirm",
        )
        if st.button("💾 HITL opslaan", key="save_confirm"):
            set_confirm_required(set(new_confirm))
            st.success(f"✅ Opgeslagen: {', '.join(sorted(new_confirm)) or '(geen)'}")


if __name__ == "__main__":
    start_gui()