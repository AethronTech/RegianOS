# regian/interface/dashboard.py
import streamlit as st
from regian.core.agent import registry, OrchestratorAgent, RegianAgent, CONFIRM_REQUIRED
from regian.skills.help import get_help


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
    st.set_page_config(page_title="Regian OS Cockpit", page_icon="🚀")
    st.title("🚀 Regian OS - Control Center")

    # ── Sidebar ───────────────────────────────────────────────
    st.sidebar.header("Instellingen")
    provider = st.sidebar.selectbox("LLM Provider (chat)", ["ollama", "gemini"])

    if provider == "gemini":
        model = st.sidebar.selectbox("Gemini Model", ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-flash-latest"])
    else:
        model = st.sidebar.selectbox("Ollama Model", ["mistral", "llama3.1:8b", "llama3.2", "deepseek-r1:8b"])

    st.sidebar.markdown("---")
    st.sidebar.subheader("📁 Werkmap")
    from regian.settings import get_root_dir, set_root_dir
    current_root = get_root_dir()
    new_root = st.sidebar.text_input("Root directory", value=current_root)
    if st.sidebar.button("💾 Opslaan"):
        saved = set_root_dir(new_root)
        st.sidebar.success(f"Opgeslagen: {saved}")
    st.sidebar.caption(f"Huidig: `{current_root}`")
    st.sidebar.markdown("---")
    st.sidebar.caption(f"🔧 {len(registry.tools)} skills geladen")

    if st.sidebar.button("Reset Chat"):
        st.session_state.messages = []
        st.rerun()

    # ── Agent initialisatie ───────────────────────────────────
    agent_key = f"{provider}:{model}"
    if "agent" not in st.session_state or st.session_state.get("agent_key") != agent_key:
        st.session_state.agent = RegianAgent(provider=provider, model=model)
        st.session_state.agent_key = agent_key

    if "orchestrator" not in st.session_state:
        st.session_state.orchestrator = OrchestratorAgent()

    # ── Tabs ──────────────────────────────────────────────────
    tab_chat, tab_help = st.tabs(["💬 Chat", "📖 Help & Commands"])

    # ── CHAT TAB ──────────────────────────────────────────────
    with tab_chat:
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "pending_plan" not in st.session_state:
            st.session_state.pending_plan = None

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
                icon = "🔴" if tool in CONFIRM_REQUIRED else "🟢"
                st.markdown(f"{icon} **Stap {i}:** `{tool}` — {args}")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Bevestigen & uitvoeren", type="primary"):
                    result = st.session_state.orchestrator.execute_plan(plan)
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
                        plan = st.session_state.orchestrator.plan(prompt)

                    # Controleer of plan gevaarlijke stappen bevat
                    dangerous = [s for s in plan if s.get("tool") in CONFIRM_REQUIRED]
                    if dangerous:
                        st.session_state.pending_plan = plan
                        st.rerun()
                    else:
                        with st.spinner("Uitvoeren..."):
                            if plan:
                                response = st.session_state.orchestrator.execute_plan(plan)
                            else:
                                response = st.session_state.orchestrator.run(prompt)
                        st.session_state.messages.append({"role": "assistant", "content": response, "badge": badge})
                        st.rerun()

    # ── HELP TAB ──────────────────────────────────────────────
    with tab_help:
        st.subheader("📖 Skills & Directe Commands")
        st.markdown(registry.list_commands())
        st.markdown("---")
        st.subheader("🔍 Skill Documentatie")
        search = st.text_input("Filter op skill", placeholder="bijv. github, files, help...")
        st.markdown(get_help(topic=search))


if __name__ == "__main__":
    start_gui()