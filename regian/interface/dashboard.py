# regian/interface/dashboard.py
import streamlit as st
from regian.core.agent import registry, OrchestratorAgent, RegianAgent
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
        model = st.sidebar.selectbox("Gemini Model", ["gemini-1.5-flash", "gemini-1.5-pro"])
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

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("Wat gaan we doen? (Typ / voor directe commands)"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                if prompt.startswith("/"):
                    # Dynamisch via registry — geen hardcoded skill-imports
                    response, badge = _handle_slash_command(prompt)
                    st.info(f"Direct: {badge}")
                else:
                    with st.spinner("Orchestrator is aan het werk..."):
                        response = st.session_state.orchestrator.run(prompt)

                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

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