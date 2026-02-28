# regian/interface/dashboard.py
import streamlit as st
from regian.core.agent import registry, OrchestratorAgent, RegianAgent, CONFIRM_REQUIRED
from regian.settings import (
    get_root_dir, set_root_dir,
    get_llm_provider, set_llm_provider,
    get_llm_model, set_llm_model,
    get_confirm_required, set_confirm_required,
)
from regian.skills.help import get_help


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

    # ── Sidebar (minimaal) ────────────────────────────────────
    st.sidebar.caption(f"🔧 {len(registry.tools)} skills geladen")
    if st.sidebar.button("🗑️ Reset Chat"):
        st.session_state.messages = []
        st.rerun()

    # ── Session state defaults (éénmalig laden uit .env) ─────
    if "provider" not in st.session_state:
        st.session_state.provider = get_llm_provider()
    if "model" not in st.session_state:
        st.session_state.model = get_llm_model()

    # ── Tabs ──────────────────────────────────────────────────
    tab_chat, tab_help, tab_settings = st.tabs(["💬 Chat", "📖 Help & Commands", "⚙️ Instellingen"])

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
        st.subheader("📖 Skills & Directe Commands")
        st.markdown(registry.list_commands())
        st.markdown("---")
        st.subheader("🔍 Skill Documentatie")
        search = st.text_input("Filter op skill", placeholder="bijv. github, files, help...")
        st.markdown(get_help(topic=search))

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