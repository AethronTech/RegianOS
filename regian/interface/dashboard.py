# regian/interface/dashboard.py
import importlib
import inspect
import json
import pkgutil
import re
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as _components
import regian.skills as _skills_pkg
from regian.core.agent import registry, OrchestratorAgent, RegianAgent, CONFIRM_REQUIRED
from regian.skills.terminal import is_destructive_shell_command, is_destructive_python_code
from regian.core.scheduler import (
    get_scheduler, get_all_jobs, get_next_run,
    add_scheduled_job, remove_scheduled_job, toggle_scheduled_job,
    run_job_now_by_id, parse_schedule,
)
from regian import __version__ as _VERSION
from regian.settings import (
    get_root_dir, set_root_dir,
    get_llm_provider, set_llm_provider,
    get_llm_model, set_llm_model,
    get_confirm_required, set_confirm_required,
    get_dangerous_patterns, set_dangerous_patterns,
    get_user_avatar, set_user_avatar,
    get_agent_name, set_agent_name,
    get_active_project, set_active_project, clear_active_project,
    get_shell_timeout, set_shell_timeout,
    get_log_max_entries, set_log_max_entries,
    get_log_result_max_chars, set_log_result_max_chars,
    get_log_file_name, set_log_file_name,
    get_jobs_file_name, set_jobs_file_name,
    get_agent_max_iterations, set_agent_max_iterations,
    get_gemini_models, set_gemini_models,
    get_ollama_models, set_ollama_models,
    _DEFAULT_GEMINI_MODELS, _DEFAULT_OLLAMA_MODELS,
    get_backup_max_count, set_backup_max_count,
    get_backup_dir, set_backup_dir,
)
import uuid
from regian.core.action_log import log_action, get_log, get_log_grouped, clear_log, log_count


_GEMINI_MODELS = get_gemini_models()
_OLLAMA_MODELS = get_ollama_models()


def _inject_global_styles():
    """Vervang 'Ask ChatGPT' door 'Ask Gemini' + injecteer chat-knop CSS in parent-document."""
    js = """
<script>
(function() {
  var doc = window.parent.document;

  /* ── Injecteer CSS in parent-document ── */
  if (!doc.getElementById('regian-chat-btn-styles')) {
    var s = doc.createElement('style');
    s.id = 'regian-chat-btn-styles';
    s.textContent = `
      [data-testid="stChatMessage"] [data-testid="stHorizontalBlock"]:last-child {
        display: flex !important;
        justify-content: flex-end !important;
        gap: 2px !important;
        margin-top: -4px !important;
        margin-bottom: 0 !important;
        opacity: 0;
        transition: opacity 0.15s ease;
      }
      [data-testid="stChatMessage"]:hover
        [data-testid="stHorizontalBlock"]:last-child {
        opacity: 1;
      }
      [data-testid="stChatMessage"]
        [data-testid="stHorizontalBlock"]:last-child
        [data-testid="stColumn"] {
        flex: 0 0 auto !important;
        min-width: 0 !important;
        width: auto !important;
        padding: 0 2px !important;
      }
      [data-testid="stChatMessage"]
        [data-testid="stHorizontalBlock"]:last-child
        button {
        padding: 1px 6px !important;
        min-height: 0 !important;
        height: 22px !important;
        line-height: 1 !important;
        font-size: 0.78rem !important;
        background: transparent !important;
        border: 1px solid transparent !important;
        box-shadow: none !important;
        color: #666 !important;
        border-radius: 4px !important;
      }
      [data-testid="stChatMessage"]
        [data-testid="stHorizontalBlock"]:last-child
        button:hover {
        background: rgba(255,255,255,0.08) !important;
        border-color: rgba(255,255,255,0.18) !important;
        color: #ddd !important;
      }
    `;
    doc.head.appendChild(s);
  }

  /* ── Patch 'Ask ChatGPT' → 'Ask Gemini' ── */
  function patchChatGPT(root) {
    root.querySelectorAll('a').forEach(function(el) {
      if (el.innerText && el.innerText.includes('ChatGPT')) {
        var errorText = '';
        try {
          var u = new URL(el.href);
          errorText = u.searchParams.get('q') || u.searchParams.get('prompt') || '';
        } catch(e) {}
        el.innerText = el.innerText.replace('ChatGPT', 'Gemini');
        el.href = errorText
          ? 'https://gemini.google.com/app?q=' + encodeURIComponent(errorText)
          : 'https://gemini.google.com/app';
        el.target = '_blank';
      }
    });
    root.querySelectorAll('button, span').forEach(function(el) {
      if (el.childNodes.length === 1 && el.childNodes[0].nodeType === 3
          && el.innerText && el.innerText.includes('ChatGPT')) {
        el.innerText = el.innerText.replace('ChatGPT', 'Gemini');
      }
    });
  }
  var observer = new MutationObserver(function(mutations) {
    mutations.forEach(function(m) {
      m.addedNodes.forEach(function(n) {
        if (n.nodeType === 1) patchChatGPT(n);
      });
    });
  });
  function start() {
    if (doc.body) {
      patchChatGPT(doc.body);
      observer.observe(doc.body, { childList: true, subtree: true });
    } else {
      setTimeout(start, 100);
    }
  }
  start();

  /* ── Scroll-to-top knop ── */
  (function() {
    var BTN_ID = 'regian-scroll-top-btn';
    if (doc.getElementById(BTN_ID)) return;

    /* Stijl */
    var s2 = doc.createElement('style');
    s2.textContent = `
      #regian-scroll-top-btn {
        position: fixed;
        bottom: 28px;
        right: 28px;
        z-index: 99999;
        width: 40px;
        height: 40px;
        border-radius: 50%;
        border: 1px solid rgba(255,255,255,0.18);
        background: #1e1e2e;
        color: #a0a8ff;
        font-size: 1.2rem;
        line-height: 38px;
        text-align: center;
        cursor: pointer;
        box-shadow: 0 2px 8px rgba(0,0,0,0.45);
        opacity: 0;
        transform: translateY(10px);
        transition: opacity 0.25s ease, transform 0.25s ease;
        pointer-events: none;
        user-select: none;
      }
      #regian-scroll-top-btn.visible {
        opacity: 0.85;
        transform: translateY(0);
        pointer-events: auto;
      }
      #regian-scroll-top-btn:hover {
        opacity: 1;
        background: #2a2a4a;
        color: #fff;
      }
    `;
    doc.head.appendChild(s2);

    /* Knop-element */
    var btn = doc.createElement('div');
    btn.id = BTN_ID;
    btn.title = 'Terug naar boven';
    btn.innerHTML = '&#8679;';  /* ⇧ */

    /* Scrollbaar container vinden (Streamlit main area) */
    function getScrollEl() {
      return doc.querySelector('section[data-testid="stMain"]')
          || doc.querySelector('div.main')
          || doc.scrollingElement
          || doc.documentElement;
    }

    btn.addEventListener('click', function() {
      var el = getScrollEl();
      el.scrollTo({ top: 0, behavior: 'smooth' });
    });

    /* Toon/verberg op basis van scrollpositie */
    function onScroll() {
      var el = getScrollEl();
      var top = (el === doc.documentElement || el === doc.scrollingElement)
                ? (doc.documentElement.scrollTop || doc.body.scrollTop)
                : el.scrollTop;
      if (top > 300) {
        btn.classList.add('visible');
      } else {
        btn.classList.remove('visible');
      }
    }

    function attachScroll() {
      var el = getScrollEl();
      if (el) {
        el.addEventListener('scroll', onScroll, { passive: true });
        doc.body.appendChild(btn);
      } else {
        setTimeout(attachScroll, 300);
      }
    }
    attachScroll();
  }());

}());
</script>
"""
    _components.html(js, height=0)

def _inject_autocomplete():
    """Injecteer JS autocomplete dropdown + signature hint voor slash commands."""
    commands = sorted(t.name for t in registry.tools)

    # Bouw {name: {sig: "...", doc: "...", params: [...]}} map
    sig_map = {}
    for t in registry.tools:
        func = registry._functions.get(t.name)
        if not func:
            continue
        sig = inspect.signature(func)
        params = [
            {"name": p.name, "hint": (
                p.name
                + ((
                    f": {p.annotation.__name__ if hasattr(p.annotation, '__name__') else str(p.annotation)}"
                ) if p.annotation != inspect.Parameter.empty else "")
                + (f" = {repr(p.default)}" if p.default != inspect.Parameter.empty else "")
            )}
            for p in sig.parameters.values()
        ]
        sig_map[t.name] = {
            "sig": str(sig),
            "doc": (inspect.getdoc(func) or "").split("\n")[0],
            "params": params,
        }

    cmd_json = json.dumps(commands)
    sig_json = json.dumps(sig_map)

    _components.html(f"""<script>
(function(){{
  var doc = window.parent.document;
  var win = window.parent;
  var COMMANDS = {cmd_json};
  var SIGS = {sig_json};

  function getInput() {{
    return doc.querySelector('textarea[data-testid="stChatInputTextArea"]');
  }}

  // ── Dropdown ──────────────────────────────────────────────
  function getOrCreateDropdown() {{
    var dd = doc.getElementById('regian-ac');
    if (!dd) {{
      dd = doc.createElement('div');
      dd.id = 'regian-ac';
      dd.style.cssText = [
        'position:fixed','background:#1a1a2e','border:1px solid #555',
        'border-radius:8px','box-shadow:0 6px 20px rgba(0,0,0,.6)',
        'z-index:99999','max-height:260px','overflow-y:auto',
        'font-family:monospace','font-size:13px','display:none','min-width:300px'
      ].join(';');
      doc.body.appendChild(dd);
    }}
    return dd;
  }}

  // ── Signature hint bar ────────────────────────────────────
  function getOrCreateHint() {{
    var h = doc.getElementById('regian-hint');
    if (!h) {{
      h = doc.createElement('div');
      h.id = 'regian-hint';
      h.style.cssText = [
        'position:fixed','background:#111','border:1px solid #444',
        'border-radius:6px','padding:5px 12px','font-family:monospace',
        'font-size:12px','color:#888','z-index:99998','display:none',
        'pointer-events:none','white-space:nowrap'
      ].join(';');
      doc.body.appendChild(h);
    }}
    return h;
  }}

  function positionBelow(el, rect) {{
    el.style.left   = rect.left + 'px';
    el.style.bottom = (win.innerHeight - rect.top + 6) + 'px';
    el.style.width  = 'auto';
    el.style.maxWidth = Math.max(rect.width, 300) + 'px';
  }}

  var selectedIdx = -1;

  function setValue(input, val) {{
    var setter = Object.getOwnPropertyDescriptor(win.HTMLTextAreaElement.prototype, 'value').set;
    setter.call(input, val);
    input.dispatchEvent(new win.Event('input', {{bubbles:true}}));
  }}

  function renderDropdown(matches, dd, input) {{
    dd.innerHTML = '';
    selectedIdx = -1;
    if (!matches.length) {{ dd.style.display = 'none'; return; }}
    matches.slice(0, 12).forEach(function(cmd, i) {{
      var info = SIGS[cmd] || {{}};
      var item = doc.createElement('div');
      item.style.cssText = 'padding:7px 14px;cursor:pointer;border-bottom:1px solid #2a2a3a';
      item.innerHTML =
        '<span style="color:#e0e0e0">/' + cmd + '</span>' +
        '<span style="color:#555;font-size:11px">' + (info.sig || '') + '</span>' +
        (info.doc ? '<div style="color:#777;font-size:11px;margin-top:1px">' + info.doc + '</div>' : '');
      item.addEventListener('mouseover', function() {{ selectedIdx = i; highlight(dd); }});
      item.addEventListener('mousedown', function(e) {{
        e.preventDefault();
        setValue(input, '/' + cmd + ' ');
        dd.style.display = 'none';
        input.focus();
      }});
      dd.appendChild(item);
    }});
    var rect = input.getBoundingClientRect();
    positionBelow(dd, rect);
    dd.style.width = Math.max(rect.width, 300) + 'px';
    dd.style.display = 'block';
  }}

  function highlight(dd) {{
    var items = dd.querySelectorAll('div');
    items.forEach(function(it, i) {{
      it.style.background = i === selectedIdx ? '#2d2d5a' : '';
    }});
  }}

  function renderHint(input, cmdName, argsSoFar) {{
    var h = getOrCreateHint();
    var info = SIGS[cmdName];
    if (!info || !info.params.length) {{ h.style.display = 'none'; return; }}
    // Tel komma's buiten aanhalingstekens om huidige param index te bepalen
    var commas = 0, inQ = false, qc = '';
    for (var ci = 0; ci < argsSoFar.length; ci++) {{
      var ch = argsSoFar[ci];
      if ((ch === '"' || ch === "'") && !inQ) {{ inQ = true; qc = ch; }}
      else if (inQ && ch === qc) {{ inQ = false; }}
      else if (!inQ && ch === ',') {{ commas++; }}
    }}
    var html = '(' + info.params.map(function(p, i) {{
      return i === commas
        ? '<span style="color:#ccc;text-decoration:underline">' + p.hint + '</span>'
        : '<span>' + p.hint + '</span>';
    }}).join('<span style="color:#555">, </span>') + ')';
    h.innerHTML = '<span style="color:#6699cc">/' + cmdName + '</span>' + html;
    var rect = input.getBoundingClientRect();
    positionBelow(h, rect);
    h.style.display = 'block';
  }}

  function updateUI(input) {{
    var val = input.value;
    var dd  = getOrCreateDropdown();
    var h   = getOrCreateHint();

    if (!val.startsWith('/')) {{
      dd.style.display = 'none';
      h.style.display  = 'none';
      return;
    }}

    var rest     = val.slice(1);
    var spaceIdx = rest.indexOf(' ');

    if (spaceIdx === -1) {{
      // Nog geen spatie: toon dropdown
      h.style.display = 'none';
      var q = rest.toLowerCase();
      var matches = q ? COMMANDS.filter(function(c) {{ return c.toLowerCase().indexOf(q) !== -1; }}) : COMMANDS;
      renderDropdown(matches, dd, input);
    }} else {{
      // Spatie gevonden: command is ingetypt, toon signature hint
      dd.style.display = 'none';
      var cmdName  = rest.slice(0, spaceIdx);
      var argsSoFar = rest.slice(spaceIdx + 1);
      if (SIGS[cmdName]) {{
        renderHint(input, cmdName, argsSoFar);
      }} else {{
        h.style.display = 'none';
      }}
    }}
  }}

  function setupInput(input) {{
    if (input._regianAC) return;
    input._regianAC = true;

    input.addEventListener('input', function() {{ updateUI(input); }});

    input.addEventListener('keydown', function(e) {{
      var dd = doc.getElementById('regian-ac');
      if (!dd || dd.style.display === 'none') return;
      var items = dd.querySelectorAll('div');
      if (e.key === 'ArrowDown') {{
        e.preventDefault();
        selectedIdx = Math.min(selectedIdx + 1, items.length - 1);
        highlight(dd);
      }} else if (e.key === 'ArrowUp') {{
        e.preventDefault();
        selectedIdx = Math.max(selectedIdx - 1, 0);
        highlight(dd);
      }} else if (e.key === 'Tab') {{
        e.preventDefault();
        var idx = selectedIdx >= 0 ? selectedIdx : 0;
        if (items[idx]) items[idx].dispatchEvent(new MouseEvent('mousedown', {{bubbles:true}}));
      }} else if (e.key === 'Escape') {{
        dd.style.display = 'none';
      }}
    }});

    input.addEventListener('blur', function() {{
      setTimeout(function() {{
        var dd = doc.getElementById('regian-ac');
        var h  = doc.getElementById('regian-hint');
        if (dd) dd.style.display = 'none';
        if (h)  h.style.display  = 'none';
      }}, 200);
    }});
  }}

  setInterval(function() {{
    var input = getInput();
    if (input) setupInput(input);
  }}, 500);

}})();
</script>""", height=0)



@st.cache_resource
def get_orchestrator(active_project: str = ""):
    """Gecached per actief project. Wis de cache via get_orchestrator.clear() bij projectwissel."""
    return OrchestratorAgent()


@st.cache_resource
def get_agent(provider: str, model: str, active_project: str = ""):
    """Gecached per provider+model+project combinatie."""
    return RegianAgent(provider=provider, model=model)


@st.cache_resource
def _start_scheduler():
    """Start de achtergrond-scheduler éénmalig bij het laden van de app."""
    return get_scheduler()


_TYPE_ICONS_SIDEBAR = {"software": "💻", "docs": "📄", "data": "📊", "generic": "📁"}


def _load_project_list() -> list[dict]:
    """Laad alle projectmanifesten uit de werkmap (directe scan, geen skill-import).
    Injecteert '_folder' (mapnaam) en 'display_name' (leesbare naam) in elke entry.
    """
    root = Path(get_root_dir())
    projects = []
    if root.exists():
        for entry in sorted(root.iterdir()):
            mp = entry / ".regian_project.json"
            if entry.is_dir() and mp.exists():
                try:
                    data = json.loads(mp.read_text(encoding="utf-8"))
                    data["_folder"] = entry.name
                    if not data.get("display_name"):
                        data["display_name"] = data["name"].replace("_", " ")
                    projects.append(data)
                except (json.JSONDecodeError, OSError):
                    pass
    return projects


def _step_needs_confirm(step: dict, confirm_set: set) -> bool:
    """Geeft True als de stap HITL-bevestiging vereist.
    Voor run_shell: enkel bij destructieve commando-patronen.
    Voor andere tools: als de tool in confirm_set staat.
    """
    tool = step.get("tool", "")
    if tool == "run_shell":
        return is_destructive_shell_command(step.get("args", {}).get("command", ""))
    if tool == "run_python":
        return is_destructive_python_code(step.get("args", {}).get("code", ""))
    return tool in confirm_set


def _handle_slash_command(prompt: str) -> tuple:
    """
    Parst '/function_name [args]' en roept de juiste skill aan via de registry.
    Geen hardcoded skill-imports nodig. Verander skills zonder aanpassingen hier.
    """
    parts = prompt[1:].split(" ", 1)
    name = parts[0].strip()
    raw_args = parts[1].strip() if len(parts) > 1 else ""
    result = registry.call_by_string(name, raw_args)
    log_action(name, {"args": raw_args} if raw_args else {}, result, source="direct")
    badge = f"/{name}({raw_args})" if raw_args else f"/{name}()"
    return result, badge


_UPLOAD_FILE_TYPES = [
    "txt", "md", "py", "js", "ts", "jsx", "tsx",
    "json", "csv", "yaml", "yml",
    "html", "xml", "css", "sh", "toml", "ini",
    "rs", "go", "java", "c", "cpp", "h", "sql", "pdf",
]


def _read_uploaded_file(uploaded_file) -> str:
    """Leest de inhoud van een geüpload bestand als platte tekst."""
    name = uploaded_file.name.lower()
    if name.endswith(".pdf"):
        try:
            import pypdf
            reader = pypdf.PdfReader(uploaded_file)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            return text.strip() or "[PDF bevat geen extraheerbare tekst]"
        except Exception as e:
            return f"[Fout bij lezen PDF: {e}]"
    else:
        try:
            raw = uploaded_file.read()
            return raw.decode("utf-8", errors="replace")
        except Exception as e:
            return f"[Fout bij lezen bestand: {e}]"


# ── Chatgeschiedenis persistentie ─────────────────────────────────────────────

def _chat_file() -> "Path":
    """Geeft het pad naar het chatgeschiedenisbestand (project-specifiek of globaal)."""
    from regian.settings import get_active_project, get_root_dir

    root = Path(get_root_dir())
    name = get_active_project()
    if name:
        try:
            from regian.skills.project import _read_manifest

            m = _read_manifest(name)
            return Path(m["path"]) / ".regian_chat.json"
        except Exception:
            pass
    return root / ".regian_chat.json"


def _load_chat_history() -> list:
    """Laadt de persistente chatgeschiedenis van schijf."""
    f = _chat_file()
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_chat_history(messages: list) -> None:
    """Slaat de volledige chatgeschiedenis op naar schijf."""
    try:
        f = _chat_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _append_msg(role: str, content: str, badge=None) -> None:
    """Voegt een bericht toe aan de sessie én slaat op naar schijf."""
    msg: dict = {"role": role, "content": content}
    if badge is not None:
        msg["badge"] = badge
    st.session_state.messages.append(msg)
    _save_chat_history(st.session_state.messages)


def _copy_cb(text: str) -> None:
    """Callback: zet tekst klaar voor kopiëren naar klembord."""
    st.session_state["_pending_copy"] = text


def _edit_cb(idx: int, text: str) -> None:
    """Callback: activeer edit-modus voor bericht op index idx."""
    st.session_state["_edit_idx"] = idx
    st.session_state["_edit_text"] = text


# ── Uploads automatisch opslaan ───────────────────────────────────────────────

def _uploads_dir() -> "Path":
    """Geeft de uploads-map voor het actieve project (of de werkmap-root)."""
    from regian.settings import get_active_project, get_root_dir

    root = Path(get_root_dir())
    name = get_active_project()
    if name:
        try:
            from regian.skills.project import _read_manifest

            m = _read_manifest(name)
            return Path(m["path"]) / "uploads"
        except Exception:
            pass
    return root / "uploads"


def _save_uploaded_file(uf) -> "Path":
    """Slaat een geüpload bestand op in de uploads-map en geeft het pad terug."""
    udir = _uploads_dir()
    udir.mkdir(parents=True, exist_ok=True)
    dest = udir / uf.name
    dest.write_bytes(uf.getvalue())
    return dest


# ── Resultaten opslaan ────────────────────────────────────────────────────────

def _results_dir() -> "Path":
    """Geeft de resultaten-map voor het actieve project (of de werkmap-root)."""
    from regian.settings import get_active_project, get_root_dir

    root = Path(get_root_dir())
    name = get_active_project()
    if name:
        try:
            from regian.skills.project import _read_manifest

            m = _read_manifest(name)
            return Path(m["path"]) / "results"
        except Exception:
            pass
    return root / "results"


def _save_result(content: str) -> "Path":
    """Sla een LLM-resultaat op als Markdown-bestand in de resultaten-map."""
    from datetime import datetime

    rdir = _results_dir()
    rdir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dest = rdir / f"{ts}_resultaat.md"
    dest.write_text(content, encoding="utf-8")
    return dest

_MAX_KNOWLEDGE_CHARS = 8_000
_MAX_UPLOADS_CHARS = 50_000


def _knowledge_dir_dash() -> "Path":
    """Geeft de kennisbank-map voor het actieve project (dashboard variant)."""
    from regian.settings import get_active_project, get_root_dir

    root = Path(get_root_dir())
    name = get_active_project()
    if name:
        try:
            from regian.skills.project import _read_manifest

            m = _read_manifest(name)
            return Path(m["path"]) / ".regian_knowledge"
        except Exception:
            pass
    return root / ".regian_knowledge"


def _load_knowledge_context() -> str:
    """Laadt de kennisbank-bestanden als context-blok voor het LLM (max 8 000 tekens)."""
    kdir = _knowledge_dir_dash()
    if not kdir.exists():
        return ""
    files = sorted(f for f in kdir.iterdir() if f.is_file())
    if not files:
        return ""

    parts: list[str] = []
    total = 0
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
            remaining = _MAX_KNOWLEDGE_CHARS - total
            if len(text) > remaining:
                text = text[:remaining] + "\n[...afgekapt]"
            parts.append(f"--- Kennisbank: {f.name} ---\n{text}\n---")
            total += len(text)
            if total >= _MAX_KNOWLEDGE_CHARS:
                break
        except Exception:
            continue

    if not parts:
        return ""
    return (
        "=== Kennisbank (projectdocumenten) ===\n"
        + "\n\n".join(parts)
        + "\n=== Einde kennisbank ===\n\n"
    )


def _load_uploads_context() -> str:
    """Laadt eerder opgeladen bestanden als context-blok voor het LLM (max 50 000 tekens)."""
    udir = _uploads_dir()
    if not udir.exists():
        return ""
    files = sorted(f for f in udir.iterdir() if f.is_file())
    if not files:
        return ""

    parts: list[str] = []
    total = 0
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
            remaining = _MAX_UPLOADS_CHARS - total
            if len(text) > remaining:
                text = text[:remaining] + "\n[...afgekapt]"
            parts.append(f"--- Upload: {f.name} ---\n{text}\n---")
            total += len(text)
            if total >= _MAX_UPLOADS_CHARS:
                break
        except Exception:
            continue

    if not parts:
        return ""
    return (
        "=== Eerder opgeladen bestanden ===\n"
        + "\n\n".join(parts)
        + "\n=== Einde uploads ===\n\n"
    )


def start_gui():
    st.set_page_config(page_title="Regian OS Cockpit", page_icon="🚀", layout="wide")
    st.title("🚀 Regian OS - Control Center")
    _inject_global_styles()

    # ── Sidebar ───────────────────────────────────────────────
    _start_scheduler()  # start achtergrond-scheduler éénmalig
    _active_proj_now = get_active_project()
    _proj_type_icon = ""
    _active_display_name = ""
    if _active_proj_now:
        _all_manifests = _load_project_list()
        _active_manifest = next(
            (p for p in _all_manifests if p.get("_folder", p["name"]) == _active_proj_now), None
        )
        if _active_manifest:
            _proj_type_icon = _TYPE_ICONS_SIDEBAR.get(_active_manifest.get("type", ""), "📁")
            _active_display_name = _active_manifest.get("display_name") or _active_proj_now.replace("_", " ")

    st.sidebar.markdown(
        f"""
<div style="
    background:#1e1e2e;
    border:1px solid #333;
    border-radius:8px;
    padding:10px 14px 10px;
    margin-bottom:8px;
    font-family:sans-serif;
">
  <div style="font-size:1.05rem;font-weight:700;color:#e0e0e0;margin-bottom:6px;">
    🚀 Regian OS
  </div>
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:{'6px' if _active_proj_now else '0'};">
    <span style="font-size:0.78rem;color:#888;">🔧 {len(registry.tools)} skills</span>
    <span style="font-size:0.75rem;background:#2a2a3e;color:#7c8cff;
                 padding:2px 7px;border-radius:10px;font-weight:600;">v{_VERSION}</span>
  </div>
  {f'''<div style="font-size:0.8rem;background:#1a2a1a;border:1px solid #2a4a2a;
               border-radius:6px;padding:4px 8px;color:#7ddb7d;">
    {_proj_type_icon} <strong>{_active_display_name}</strong>
  </div>''' if _active_proj_now else ''}
</div>
""",
        unsafe_allow_html=True,
    )

    # ── Project selector ──────────────────────────────────────
    _all_projects = _load_project_list()
    _proj_folders = [p.get("_folder", p["name"]) for p in _all_projects]
    _proj_labels  = [p.get("display_name") or p["name"].replace("_", " ") for p in _all_projects]
    _folder_to_label = dict(zip(_proj_folders, _proj_labels))
    _label_to_folder = dict(zip(_proj_labels, _proj_folders))
    _NO_PROJECT = "(geen project)"
    _current_label = _folder_to_label.get(_active_proj_now, _NO_PROJECT)
    _selector_options = [_NO_PROJECT] + _proj_labels
    # Sync session state als project hernoemd werd via chat (buiten de selectbox om)
    if st.session_state.get("sidebar_project_select", _current_label) != _current_label:
        st.session_state["sidebar_project_select"] = _current_label
    _selected = st.sidebar.selectbox(
        "📁 Project",
        _selector_options,
        index=_selector_options.index(_current_label),
        key="sidebar_project_select",
        label_visibility="collapsed",
    )
    if _selected != _current_label:
        if _selected == _NO_PROJECT:
            clear_active_project()
            st.session_state.active_project = ""
        else:
            _sel_folder = _label_to_folder.get(_selected, _selected)
            from regian.settings import set_active_project as _sap
            _sap(_sel_folder)
            # activeer ook het manifest-vlag
            from regian.skills.project import activate_project as _ap
            _ap(_sel_folder)
            st.session_state.active_project = _sel_folder
        get_orchestrator.clear()
        get_agent.clear()
        # Wis chatgeschiedenis zodat de chat van het nieuwe project geladen wordt
        st.session_state.pop("messages", None)
        st.rerun()

    if st.sidebar.button("🗑️ Reset Chat", use_container_width=True):
        st.session_state.messages = []
        _save_chat_history([])
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

    # ── Uploads-widget ────────────────────────────────────────
    _udir = _uploads_dir()
    _ufiles = sorted(_udir.iterdir()) if _udir.exists() else []
    _up_label = f"📎 Uploads ({len(_ufiles)})" if _ufiles else "📎 Uploads (leeg)"
    with st.sidebar.expander(_up_label, expanded=False):
        if _ufiles:
            for _uf2 in _ufiles:
                _usz = _uf2.stat().st_size
                _usz_s = f"{_usz / 1024:.1f} KB" if _usz >= 1024 else f"{_usz} B"
                st.markdown(f"📄 `{_uf2.name}` — {_usz_s}")
            st.caption("Inhoud wordt automatisch als context meegegeven bij elke vraag.")
        else:
            st.caption("Nog geen uploads.")

    # ── Kennisbank-widget ─────────────────────────────────────
    _kdir = _knowledge_dir_dash()
    _kfiles = sorted(_kdir.iterdir()) if _kdir.exists() else []
    _kb_label = f"📚 Kennisbank ({len(_kfiles)})" if _kfiles else "📚 Kennisbank (leeg)"
    with st.sidebar.expander(_kb_label, expanded=False):
        if _kfiles:
            for _kf in _kfiles:
                _ksz = _kf.stat().st_size
                _ksz_s = f"{_ksz / 1024:.1f} KB" if _ksz >= 1024 else f"{_ksz} B"
                st.markdown(f"📄 `{_kf.name}` — {_ksz_s}")
            st.caption("Context wordt automatisch bij elke LLM-vraag meegegeven.")
        else:
            st.caption("Nog geen kennisbestanden.")
        st.caption("Gebruik `/add_to_knowledge <pad>` om bestanden toe te voegen.")

    # ── Session state defaults (éénmalig laden uit .env) ─────
    if "provider" not in st.session_state:
        st.session_state.provider = get_llm_provider()
    if "model" not in st.session_state:
        st.session_state.model = get_llm_model()
    if "active_project" not in st.session_state:
        st.session_state.active_project = get_active_project()

    # ── Tabs ──────────────────────────────────────────────────
    tab_chat, tab_help, tab_cron, tab_log, tab_settings, tab_workflows, tab_tokens = st.tabs([
        "💬 Chat", "📖 Help & Commands", "📅 Cron", "📋 Log", "⚙️ Instellingen", "🔄 Workflows", "📊 Tokens"
    ])

    # ── CHAT TAB ──────────────────────────────────────────────
    with tab_chat:
        _inject_autocomplete()
        if "messages" not in st.session_state:
            st.session_state.messages = _load_chat_history()
        if "pending_plan" not in st.session_state:
            st.session_state.pending_plan = None
        if "_exec_plan" not in st.session_state:
            st.session_state._exec_plan = None
            st.session_state._exec_idx = 0
            st.session_state._exec_results = []
            st.session_state._exec_n = 0
            st.session_state._exec_gid = None

        confirm_set = CONFIRM_REQUIRED()

        # ── Kopiëren naar klembord (JS, vanuit on_click callback) ─────────────
        if st.session_state.get("_pending_copy"):
            _cp_text = st.session_state["_pending_copy"]
            st.session_state["_pending_copy"] = None
            _components.html(
                "<script>(function(){var t=window.parent.document"
                ".createElement('textarea');t.value="
                + json.dumps(_cp_text)
                + ";t.style.cssText='position:fixed;opacity:0;top:0;left:0';"
                "window.parent.document.body.appendChild(t);"
                "t.focus();t.select();"
                "try{window.parent.document.execCommand('copy');}catch(e){}"
                "window.parent.document.body.removeChild(t);"
                "})();</script>",
                height=0,
            )

        # ── HITL: bevestiging afwachten ────────────────────────
        if st.session_state.pending_plan is not None:
            plan = st.session_state.pending_plan

            # Toon chatgeschiedenis als context
            _avatar = get_user_avatar()
            _agent_name = get_agent_name()
            for i, message in enumerate(st.session_state.messages):
                if message["role"] == "user":
                    with st.chat_message("user", avatar=_avatar):
                        st.markdown(message["content"])
                        _bc1, _bc2 = st.columns([1, 9])
                        with _bc1:
                            st.button("📋", key=f"hcp_u_{i}", help="Kopiëren",
                                      on_click=_copy_cb, args=(message["content"],))
                else:
                    with st.chat_message(_agent_name, avatar="🤖"):
                        if message.get("badge"):
                            st.info(f"Direct: {message['badge']}")
                        st.markdown(message["content"])
                        _bc1, _bc2 = st.columns([1, 9])
                        with _bc1:
                            st.button("📋", key=f"hcp_a_{i}", help="Kopiëren",
                                      on_click=_copy_cb, args=(message["content"],))

            st.warning("⚠️ **Bevestiging vereist** — dit plan bevat destructieve operaties:")
            for i, step in enumerate(plan, 1):
                tool = step.get("tool", "")
                args = step.get("args", {})
                icon = "🔴" if _step_needs_confirm(step, confirm_set) else "🟢"
                if tool == "run_python" and "code" in args:
                    st.markdown(f"{icon} **Stap {i}:** `run_python`")
                    st.code(args["code"], language="python")
                elif tool == "run_shell" and "command" in args:
                    st.markdown(f"{icon} **Stap {i}:** `run_shell`")
                    st.code(args["command"], language="bash")
                    if args.get("cwd"):
                        st.caption(f"Werkmap: `{args['cwd']}`")
                else:
                    _arg_str = "  \n".join(f"**{k}**: `{v}`" for k, v in args.items()) if args else "—"
                    st.markdown(f"{icon} **Stap {i}:** `{tool}`  \n{_arg_str}")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Bevestigen & uitvoeren", type="primary"):
                    gid = st.session_state.get("pending_group_id")
                    result = get_orchestrator(st.session_state.active_project).execute_plan(plan, group_id=gid)
                    _append_msg("assistant", result)
                    st.session_state.pending_plan = None
                    st.session_state.pending_group_id = None
                    st.rerun()
            with col2:
                if st.button("❌ Annuleren"):
                    _append_msg("assistant", "❌ Opdracht geannuleerd.")
                    st.session_state.pending_plan = None
                    st.rerun()

        elif st.session_state.get("_exec_plan"):
            # ── Stapsgewijze uitvoering (stop-knop ondersteund) ────
            _exec_p = st.session_state._exec_plan
            _exec_i = st.session_state._exec_idx
            _exec_n = st.session_state._exec_n
            _exec_gid = st.session_state._exec_gid
            _avatar = get_user_avatar()
            _agent_name = get_agent_name()

            # Toon bestaande berichten
            for i, message in enumerate(st.session_state.messages):
                if message["role"] == "user":
                    with st.chat_message("user", avatar=_avatar):
                        st.markdown(message["content"])
                        _bc1, _bc2, _bc3 = st.columns([1, 1, 8])
                        with _bc1:
                            st.button("📋", key=f"ecp_u_{i}", help="Kopiëren",
                                      on_click=_copy_cb, args=(message["content"],))
                        with _bc2:
                            st.button("✏️", key=f"eed_{i}", help="Bewerken",
                                      on_click=_edit_cb, args=(i, message["content"]))
                else:
                    with st.chat_message(_agent_name, avatar="🤖"):
                        if message.get("badge"):
                            st.info(f"Direct: {message['badge']}")
                        st.markdown(message["content"])
                        _bc1, _bc2 = st.columns([1, 9])
                        with _bc1:
                            st.button("📋", key=f"ecp_a_{i}", help="Kopiëren",
                                      on_click=_copy_cb, args=(message["content"],))

            # Voortgangsbalk + stop-knop
            st.progress(_exec_i / _exec_n,
                        text=f"▶️ Uitvoeren... stap {_exec_i}/{_exec_n}")
            if st.button("⏹️ Stop uitvoering", type="secondary"):
                partial = "\n\n".join(st.session_state._exec_results)
                stopped_msg = (
                    partial + f"\n\n⏹️ **Gestopt na stap {_exec_i} van {_exec_n}.**"
                ) if partial else "⏹️ **Gestopt door gebruiker.**"
                _append_msg("assistant", stopped_msg)
                st.session_state._exec_plan = None
                st.session_state._exec_idx = 0
                st.session_state._exec_results = []
                st.session_state._exec_n = 0
                st.rerun()

            if _exec_i < _exec_n:
                step = _exec_p[_exec_i]
                tool_name = step.get("tool", "")
                args = step.get("args", {})
                with st.spinner(f"▶️ Stap {_exec_i + 1}/{_exec_n}: `{tool_name}`..."):
                    result = registry.call(tool_name, args)
                log_action(tool_name, args, result, source="chat", group_id=_exec_gid)
                _prev = result[:120] + ("…" if len(result) > 120 else "")
                st.toast(f"✅ {tool_name}: {_prev}")
                st.session_state._exec_results.append(f"✅ **{tool_name}**: {result}")
                st.session_state._exec_idx += 1
                st.rerun()
            else:
                response = "\n\n".join(st.session_state._exec_results)
                _append_msg("assistant", response)
                try:
                    _saved_path = _save_result(response)
                except Exception:
                    pass
                st.session_state._exec_plan = None
                st.session_state._exec_idx = 0
                st.session_state._exec_results = []
                st.session_state._exec_n = 0
                st.rerun()

        else:
            # ── Normale chat ───────────────────────────────────────
            _avatar = get_user_avatar()
            _agent_name = get_agent_name()
            for i, message in enumerate(st.session_state.messages):
                if message["role"] == "user":
                    with st.chat_message("user", avatar=_avatar):
                        st.markdown(message["content"])
                        _bc1, _bc2, _bc3 = st.columns([1, 1, 8])
                        with _bc1:
                            st.button("📋", key=f"cp_u_{i}", help="Kopiëren",
                                      on_click=_copy_cb, args=(message["content"],))
                        with _bc2:
                            st.button("✏️", key=f"ed_{i}", help="Bewerken en opnieuw uitvoeren",
                                      on_click=_edit_cb, args=(i, message["content"]))
                else:
                    with st.chat_message(_agent_name, avatar="🤖"):
                        if message.get("badge"):
                            st.info(f"Direct: {message['badge']}")
                        st.markdown(message["content"])
                        _bc1, _bc2 = st.columns([1, 9])
                        with _bc1:
                            st.button("📋", key=f"cp_a_{i}", help="Kopiëren",
                                      on_click=_copy_cb, args=(message["content"],))

            # ── Edit-modus ─────────────────────────────────────────────────────
            _edit_pending = st.session_state.get("_edit_idx") is not None
            if _edit_pending:
                _ei = st.session_state["_edit_idx"]
                st.info(f"✏️ **Bericht #{_ei + 1} bewerken** — wijzig hieronder en klik Uitvoeren:")
                _edit_val = st.text_area(
                    "Bericht",
                    value=st.session_state.get("_edit_text", ""),
                    key="_edit_ta",
                    height=80,
                    label_visibility="collapsed",
                )
                _ec1, _ec2 = st.columns(2)
                with _ec1:
                    if st.button("▶️ Uitvoeren", type="primary", use_container_width=True):
                        st.session_state.messages = st.session_state.messages[:_ei]
                        _save_chat_history(st.session_state.messages)
                        st.session_state["_edit_idx"] = None
                        st.session_state["_edit_text"] = None
                        st.session_state["_queued_prompt"] = _edit_val.strip()
                        st.rerun()
                with _ec2:
                    if st.button("✖️ Annuleren", use_container_width=True):
                        st.session_state["_edit_idx"] = None
                        st.session_state["_edit_text"] = None
                        st.rerun()

            # ── Chat-input of queued prompt (vanuit edit-submit) ────────────────
            _queued_prompt = st.session_state.get("_queued_prompt")
            if _queued_prompt:
                del st.session_state["_queued_prompt"]
            if not _edit_pending and not _queued_prompt:
                prompt = st.chat_input(
                    "Wat gaan we doen? (Typ / voor directe commands)",
                    accept_file="multiple",
                    file_type=_UPLOAD_FILE_TYPES,
                )
            else:
                prompt = None
            if _queued_prompt or prompt:
                # Haal tekst en bestanden op (ChatInputValue óf plain string)
                if _queued_prompt:
                    typed_prompt = _queued_prompt
                    uploaded_files: list = []
                elif isinstance(prompt, str):
                    typed_prompt = prompt
                    uploaded_files: list = []
                else:
                    typed_prompt = prompt.text or ""
                    uploaded_files = list(prompt.files or [])

                # Guard: niets om te verwerken
                if not typed_prompt and not uploaded_files:
                    st.rerun()

                # Weergavetekst (gebruikt alleen bestandsnamen, niet de inhoud)
                _file_names = ", ".join(_uf.name for _uf in uploaded_files)
                if uploaded_files and typed_prompt:
                    display_prompt = f"{typed_prompt}\n\n📎 *{_file_names}*"
                elif uploaded_files:
                    display_prompt = f"📎 *{_file_names}*"
                else:
                    display_prompt = typed_prompt

                # ── Toon de gebruikersvraag meteen, nog vóór verwerking ──
                with st.chat_message("user", avatar=_avatar):
                    st.markdown(display_prompt)
                _append_msg("user", display_prompt)

                badge = None
                if typed_prompt.startswith("/"):
                    stripped = typed_prompt[1:].strip()
                    with st.chat_message(_agent_name, avatar="🤖"):
                        if uploaded_files:
                            response = "⚠️ Bestandsbijlagen worden genegeerd bij directe commands. Verwijder / voor LLM-verwerking van bestanden."
                            st.warning(response)
                            _append_msg("assistant", response)
                            st.rerun()
                        if not stripped:
                            response = registry.list_commands()
                            st.markdown(response)
                            _append_msg("assistant", response)
                        else:
                            # HITL voor destructieve /run_shell commando's
                            _parts = stripped.split(" ", 1)
                            _slash_name = _parts[0].strip()
                            _slash_arg = _parts[1].strip() if len(_parts) > 1 else ""
                            if _slash_name == "run_shell" and is_destructive_shell_command(_slash_arg):
                                st.session_state.pending_plan = [{"tool": "run_shell", "args": {"command": _slash_arg}}]
                                st.rerun()
                            else:
                                response, badge = _handle_slash_command(typed_prompt)
                                if badge:
                                    st.info(f"Direct: {badge}")
                                st.markdown(response)
                                _append_msg("assistant", response, badge)
                else:
                    # ── Fase 1 + 2: Bestanden lezen → Plan opstellen → Uitvoeren ─────
                    with st.chat_message(_agent_name, avatar="🤖"):
                        _n_files = len(uploaded_files)
                        _n_prep = _n_files + 1  # N bestanden + 1 plan-stap
                        with st.status(f"🧠 Voorbereiden... (0/{_n_prep})", expanded=True) as _status:

                            # ── Bestanden lezen (stap 1 t/m N) ────────────────────
                            file_parts = []
                            for _fi, _uf in enumerate(uploaded_files, 1):
                                st.write(f"📂 Stap {_fi}/{_n_prep}: `{_uf.name}` lezen...")
                                _status.update(label=f"📂 Bestanden lezen... ({_fi}/{_n_prep})")
                                _content = _read_uploaded_file(_uf)
                                file_parts.append(f"--- Bijlage: {_uf.name} ---\n{_content}\n---")
                                try:
                                    _save_uploaded_file(_uf)
                                except Exception:
                                    pass

                            # Bouw effective_prompt
                            if file_parts:
                                _file_block = "\n\n".join(file_parts)
                                effective_prompt = f"{_file_block}\n\n{typed_prompt}".strip() if typed_prompt else _file_block
                            else:
                                effective_prompt = typed_prompt

                            # Uploads-context toevoegen (eerder opgeladen bestanden)
                            _up_ctx = _load_uploads_context()
                            if _up_ctx:
                                effective_prompt = _up_ctx + effective_prompt

                            # Kennisbank-context toevoegen
                            _kb_ctx = _load_knowledge_context()
                            if _kb_ctx:
                                effective_prompt = _kb_ctx + effective_prompt

                            # ── Plan genereren (laatste prep-stap) ─────────────────
                            st.write(f"🧠 Stap {_n_prep}/{_n_prep}: Plan genereren...")
                            _status.update(label=f"🧠 Plan genereren... ({_n_prep}/{_n_prep})")
                            plan = get_orchestrator(st.session_state.active_project).plan(effective_prompt)
                            gid = str(uuid.uuid4())[:8]
                            log_action("__prompt__", {"prompt": display_prompt}, "", source="chat", group_id=gid)
                            dangerous = [s for s in plan if _step_needs_confirm(s, confirm_set)]

                            if dangerous:
                                _status.update(label="⚠️ Bevestiging vereist", state="error", expanded=True)
                                st.session_state.pending_plan = plan
                                st.session_state.pending_group_id = gid
                                st.rerun()
                            elif not plan:
                                # Geen tool-plan → directe LLM-respons
                                _status.update(label=f"💬 {_agent_name} antwoordt...", state="running", expanded=False)

                            if plan and not dangerous:
                                n = len(plan)
                                st.write(f"📋 **{n} stap{'pen' if n > 1 else ''} gepland**")
                                for i, step in enumerate(plan, 1):
                                    st.write(f"⚙️ Stap {i}/{n}: `{step.get('tool', '')}`")
                                _status.update(
                                    label=f"🚀 {n} stap{'pen' if n > 1 else ''} gepland, uitvoering start...",
                                    state="complete", expanded=False,
                                )
                                # Plan opslaan voor stapsgewijze uitvoering (stop-knop ondersteund)
                                st.session_state._exec_plan = plan
                                st.session_state._exec_idx = 0
                                st.session_state._exec_gid = gid
                                st.session_state._exec_results = []
                                st.session_state._exec_n = n
                                st.rerun()

                            elif not plan and not dangerous:
                                response = get_orchestrator(st.session_state.active_project).run(effective_prompt)
                                _status.update(label="✅ Klaar", state="complete", expanded=False)
                                st.markdown(response)
                                try:
                                    _saved_path = _save_result(response)
                                    st.caption(f"💾 Opgeslagen als `results/{_saved_path.name}`")
                                except Exception:
                                    pass
                                _append_msg("assistant", response)

    # ── HELP TAB ──────────────────────────────────────────────
    with tab_help:
        sub = st.radio(
            "Weergave",
            ["📋 Commands", "📚 Documentatie", "📘 Handleiding"],
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

        elif sub == "📚 Documentatie":  # Documentatie
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

        elif sub == "📘 Handleiding":
            _HANDLEIDING = Path(__file__).parent.parent.parent / "docs" / "handleiding.md"
            st.markdown("""
<style>
.handleiding h1 { font-size: 1.7rem; font-weight: 700; margin-top: 0.2rem; margin-bottom: 0.4rem; border-bottom: 2px solid #444; padding-bottom: 0.3rem; }
.handleiding h2 { font-size: 1.25rem; font-weight: 700; margin-top: 1.6rem; margin-bottom: 0.3rem; color: #e0e0e0; }
.handleiding h3 { font-size: 1.05rem; font-weight: 600; margin-top: 1.1rem; margin-bottom: 0.2rem; color: #c0c0c0; }
.handleiding p  { line-height: 1.65; margin-bottom: 0.5rem; }
.handleiding table { width: 100%; border-collapse: collapse; margin: 0.8rem 0; font-size: 0.88rem; }
.handleiding th { background: #2a2a2a; color: #ddd; text-align: left; padding: 6px 10px; border: 1px solid #444; }
.handleiding td { padding: 5px 10px; border: 1px solid #333; vertical-align: top; }
.handleiding tr:nth-child(even) td { background: #1e1e1e; }
.handleiding code { background: #2a2a2a; color: #e06c75; padding: 1px 5px; border-radius: 3px; font-size: 0.85rem; }
.handleiding pre  { background: #1e1e1e; border: 1px solid #333; border-radius: 6px; padding: 10px 14px; overflow-x: auto; }
.handleiding pre code { background: none; color: #abb2bf; padding: 0; font-size: 0.82rem; }
.handleiding blockquote { border-left: 3px solid #555; margin: 0.5rem 0; padding: 0.3rem 0.8rem; color: #aaa; font-style: italic; }
.handleiding ul, .handleiding ol { padding-left: 1.4rem; margin-bottom: 0.5rem; }
.handleiding li { margin-bottom: 0.2rem; line-height: 1.6; }
.handleiding hr { border: none; border-top: 1px solid #333; margin: 1.2rem 0; }
</style>
""", unsafe_allow_html=True)
            if _HANDLEIDING.exists():
                content = _HANDLEIDING.read_text(encoding="utf-8")
                st.markdown(f'<div class="handleiding">\n\n{content}\n\n</div>', unsafe_allow_html=True)
            else:
                st.error(f"Handleiding niet gevonden: `{_HANDLEIDING}`")

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

    # ── LOG TAB ───────────────────────────────────────────────
    with tab_log:
        st.subheader("📋 Actie-log")

        total = log_count()
        col_info, col_clear = st.columns([4, 1])
        with col_info:
            st.caption(f"{total} entries in log")
        with col_clear:
            if st.button("🗑️ Log wissen", key="clear_action_log"):
                clear_log()
                st.success("Log gewist.")
                st.rerun()

        log_view = st.radio(
            "Weergave",
            ["🕐 Chronologisch", "💬 Per opdracht"],
            horizontal=True,
            key="log_view",
            label_visibility="collapsed",
        )

        _SOURCE_ICONS = {"chat": "💬", "direct": "⚡", "cron": "📅", "cli": "🖥️"}

        if log_view == "💬 Per opdracht":
            groups = get_log_grouped(limit_groups=100)
            if not groups:
                st.info("Nog geen gegroepeerde opdrachten in de log.")
            else:
                st.caption(f"{len(groups)} opdrachten gevonden")
                for grp in groups:
                    prompt_text = grp["prompt"] or "(geen prompt)"
                    steps = grp["steps"]
                    src_icon = _SOURCE_ICONS.get(grp.get("source", ""), "❓")
                    label = f"{src_icon} {grp['ts']}  ·  {prompt_text[:80]}"
                    with st.expander(label, expanded=False):
                        st.markdown(f"**Prompt:** {prompt_text}")
                        if not steps:
                            st.caption("(geen tool-aanroepen)")
                        for i, e in enumerate(steps, 1):
                            tool = e.get("tool", "")
                            args = e.get("args", {})
                            result = e.get("result", "")
                            st.markdown(f"**Stap {i}: `{tool}`**")
                            if args:
                                st.json(args)
                            st.code(result, language=None)

        else:
            entries = get_log(limit=200)
            if not entries:
                st.info("Nog geen acties gelogd.")
            else:
                sources = sorted({e.get("source", "") for e in entries})
                filter_source = st.selectbox(
                    "Filter op bron",
                    ["Alle"] + sources,
                    key="log_filter_source",
                    label_visibility="collapsed",
                )
                filter_tool = st.text_input(
                    "Filter op skill",
                    placeholder="bijv. run_shell, write_file …",
                    key="log_filter_tool",
                )
                filtered = [
                    e for e in entries
                    if (filter_source == "Alle" or e.get("source") == filter_source)
                    and (not filter_tool or filter_tool.lower() in e.get("tool", "").lower())
                    and e.get("tool") != "__prompt__"
                ]
                st.caption(f"{len(filtered)} entries weergegeven")
                for e in filtered:
                    src_icon = _SOURCE_ICONS.get(e.get("source", ""), "❓")
                    tool = e.get("tool", "")
                    ts = e.get("ts", "")
                    args = e.get("args", {})
                    result = e.get("result", "")
                    with st.expander(f"{src_icon} `{tool}` — {ts}", expanded=False):
                        if args:
                            st.markdown("**Args:**")
                            st.json(args)
                        st.markdown("**Resultaat:**")
                        st.code(result, language=None)

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
        model_options = get_gemini_models() if new_provider == "gemini" else get_ollama_models()
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
            get_agent.clear()
            get_orchestrator.clear()
            st.success(f"✅ Model opgeslagen: `{new_provider} / {new_model}`")
            st.rerun()

        with st.expander("✏️ Beschikbare modellen bewerken"):
            st.caption("Pas de modellijsten aan. Één modelnaam per regel.")
            # Sync sessie-state met de actueel opgeslagen waarde zodra die wijzigt
            # (voorkomt verouderde weergave na code-update of na opslaan)
            _gemini_saved = "\n".join(get_gemini_models())
            _ollama_saved = "\n".join(get_ollama_models())
            if st.session_state.get("_gemini_models_hash") != hash(_gemini_saved):
                st.session_state["settings_gemini_models"] = _gemini_saved
                st.session_state["_gemini_models_hash"] = hash(_gemini_saved)
            if st.session_state.get("_ollama_models_hash") != hash(_ollama_saved):
                st.session_state["settings_ollama_models"] = _ollama_saved
                st.session_state["_ollama_models_hash"] = hash(_ollama_saved)
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.markdown("**Gemini**")
                gemini_text = st.text_area(
                    "Gemini-modellen",
                    value=_gemini_saved,
                    height=120,
                    key="settings_gemini_models",
                    label_visibility="collapsed",
                )
            with col_m2:
                st.markdown("**Ollama**")
                ollama_text = st.text_area(
                    "Ollama-modellen",
                    value=_ollama_saved,
                    height=120,
                    key="settings_ollama_models",
                    label_visibility="collapsed",
                )
            col_ms1, col_ms2 = st.columns(2)
            with col_ms1:
                if st.button("💾 Gemini opslaan", key="save_gemini_models"):
                    new_gemini = [m.strip() for m in gemini_text.splitlines() if m.strip()]
                    set_gemini_models(new_gemini)
                    st.session_state["_gemini_models_hash"] = None  # force re-sync
                    st.success(f"✅ {len(new_gemini)} Gemini-modellen opgeslagen")
                    st.rerun()
            with col_ms2:
                if st.button("💾 Ollama opslaan", key="save_ollama_models"):
                    new_ollama = [m.strip() for m in ollama_text.splitlines() if m.strip()]
                    set_ollama_models(new_ollama)
                    st.session_state["_ollama_models_hash"] = None  # force re-sync
                    st.success(f"✅ {len(new_ollama)} Ollama-modellen opgeslagen")
                    st.rerun()
            col_mr1, col_mr2 = st.columns(2)
            with col_mr1:
                if st.button("↩️ Gemini standaard", key="reset_gemini_models"):
                    set_gemini_models([m.strip() for m in _DEFAULT_GEMINI_MODELS.split(",")])
                    st.session_state["_gemini_models_hash"] = None  # force re-sync
                    st.success("✅ Gemini-modellen hersteld")
                    st.rerun()
            with col_mr2:
                if st.button("↩️ Ollama standaard", key="reset_ollama_models"):
                    set_ollama_models([m.strip() for m in _DEFAULT_OLLAMA_MODELS.split(",")])
                    st.session_state["_ollama_models_hash"] = None  # force re-sync
                    st.success("✅ Ollama-modellen hersteld")
                    st.rerun()

        with st.expander("💰 Token prijzen bewerken"):
            st.caption(
                "Stel de prijs per model in (EUR / 1 000 000 tokens). "
                "Voeg meerdere rijen toe voor één model om prijswijzigingen bij te houden. "
                "'Tot datum' leeg = momenteel geldig. Datumformaat: **JJJJ-MM-DD**."
            )
            from regian.core.token_log import get_pricing, set_pricing as _set_pricing
            import pandas as _pd_pr
            # Toegestane modellen = unie van Gemini + Ollama lijst
            _allowed_models = sorted(set(get_gemini_models()) | set(get_ollama_models()))
            _pricing_now = get_pricing()
            _pr_rows = []
            for _pr_model, _pr_entries in _pricing_now.items():
                if _pr_model not in _allowed_models:
                    continue  # modellen die niet meer in de lijst staan, niet tonen
                if isinstance(_pr_entries, dict):
                    # backward compat: oud formaat
                    _pr_rows.append({
                        "Model": _pr_model,
                        "Van datum": "2025-01-01",
                        "Tot datum": "",
                        "Input EUR/1M": float(_pr_entries.get("input", 0)),
                        "Output EUR/1M": float(_pr_entries.get("output", 0)),
                    })
                else:
                    for _pr_e in _pr_entries:
                        _pr_rows.append({
                            "Model": _pr_model,
                            "Van datum": _pr_e.get("from", ""),
                            "Tot datum": _pr_e.get("to") or "",
                            "Input EUR/1M": float(_pr_e.get("input", 0)),
                            "Output EUR/1M": float(_pr_e.get("output", 0)),
                        })
            if not _pr_rows:
                _pr_rows = [{"Model": _allowed_models[0] if _allowed_models else "", "Van datum": "", "Tot datum": "", "Input EUR/1M": 0.0, "Output EUR/1M": 0.0}]
            _df_pr = _pd_pr.DataFrame(_pr_rows)
            _edited_pr = st.data_editor(
                _df_pr,
                num_rows="dynamic",
                use_container_width=True,
                key="settings_pricing_editor",
                column_config={
                    "Model": st.column_config.SelectboxColumn(
                        "Model", options=_allowed_models, required=True,
                    ),
                    "Van datum": st.column_config.TextColumn("Van (JJJJ-MM-DD)", required=True),
                    "Tot datum": st.column_config.TextColumn("Tot (leeg = huidig)"),
                    "Input EUR/1M": st.column_config.NumberColumn("Input EUR/1M", min_value=0.0, format="%.4f"),
                    "Output EUR/1M": st.column_config.NumberColumn("Output EUR/1M", min_value=0.0, format="%.4f"),
                },
            )
            if st.button("💾 Prijzen opslaan", key="save_pricing"):
                _new_pricing: dict = {}
                _skipped = []
                for _, _pr_row in _edited_pr.iterrows():
                    _pm = str(_pr_row.get("Model", "")).strip()
                    if not _pm or _pm not in _allowed_models:
                        if _pm:
                            _skipped.append(_pm)
                        continue
                    if _pm not in _new_pricing:
                        _new_pricing[_pm] = []
                    _new_pricing[_pm].append({
                        "from": str(_pr_row.get("Van datum", "")).strip(),
                        "to": str(_pr_row.get("Tot datum", "")).strip() or None,
                        "input": float(_pr_row.get("Input EUR/1M", 0)),
                        "output": float(_pr_row.get("Output EUR/1M", 0)),
                    })
                _set_pricing(_new_pricing)
                if _skipped:
                    st.warning(f"⚠️ Overgeslagen (niet in modellenlijst): {', '.join(set(_skipped))}")
                st.success(f"✅ Prijzen opgeslagen voor {len(_new_pricing)} modellen.")
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

        st.markdown("---")

        # 4. Gebruikers-avatar
        st.markdown("### 🙂 Gebruikers-avatar")
        st.caption("Kies een emoji die als avatar in de chat verschijnt.")
        _AVATAR_OPTIONS = ["🧑", "👤", "🙋", "😊", "🧑‍💻", "🧔", "👩", "🧑‍🎤", "🤓", "😎", "🦊", "🐱", "🐶", "🤖", "👾"]
        current_avatar = get_user_avatar()
        if current_avatar not in _AVATAR_OPTIONS:
            _AVATAR_OPTIONS.insert(0, current_avatar)
        new_avatar = st.selectbox(
            "Avatar emoji",
            _AVATAR_OPTIONS,
            index=_AVATAR_OPTIONS.index(current_avatar),
            key="settings_avatar",
            format_func=lambda e: f"{e}  ({e})",
        )
        if st.button("💾 Avatar opslaan", key="save_avatar"):
            set_user_avatar(new_avatar)
            st.success(f"✅ Avatar opgeslagen: {new_avatar}")
            st.rerun()

        st.markdown("---")

        # 5. Chat-agentnaam
        st.markdown("### 🤖 Naam van de chat-agent")
        st.caption(
            "De agent wordt in de chat aangesproken met deze naam. "
            "De tool zelf heet altijd **Regian OS** — alleen de chat-persona verandert."
        )
        current_agent_name = get_agent_name()
        new_agent_name = st.text_input(
            "Agentnaam",
            value=current_agent_name,
            max_chars=30,
            key="settings_agent_name",
        )
        col_an1, col_an2 = st.columns([1, 1])
        with col_an1:
            if st.button("💾 Naam opslaan", key="save_agent_name"):
                _clean = new_agent_name.strip()
                if _clean:
                    set_agent_name(_clean)
                    st.success(f"✅ Agentnaam opgeslagen: **{_clean}**")
                    st.rerun()
                else:
                    st.error("Agentnaam mag niet leeg zijn.")
        with col_an2:
            if st.button("↩️ Standaard (Reggy)", key="reset_agent_name"):
                from regian.settings import _DEFAULT_AGENT_NAME
                set_agent_name(_DEFAULT_AGENT_NAME)
                st.success(f"✅ Agentnaam hersteld naar **{_DEFAULT_AGENT_NAME}**")
                st.rerun()

        st.markdown("---")

        # 6. Destructieve shell-patronen
        st.markdown("### ⚠️ Destructieve shell-patronen")
        st.caption(
            "Regex-patronen die HITL triggeren bij `run_shell`. Één patroon per regel. "
            "Leeg laten herstelt de standaard-patronen bij de volgende opstart."
        )
        current_patterns = get_dangerous_patterns()
        new_patterns_text = st.text_area(
            "Patronen (één per regel)",
            value="\n".join(current_patterns),
            height=230,
            key="settings_patterns",
        )
        col_pat1, col_pat2 = st.columns([1, 1])
        with col_pat1:
            if st.button("💾 Patronen opslaan", key="save_patterns"):
                new_patterns = [p.strip() for p in new_patterns_text.splitlines() if p.strip()]
                set_dangerous_patterns(new_patterns)
                st.success(f"✅ {len(new_patterns)} patronen opgeslagen.")
        with col_pat2:
            if st.button("↩️ Herstel standaard", key="reset_patterns"):
                from regian.settings import _DEFAULT_DANGEROUS_PATTERNS
                set_dangerous_patterns(list(_DEFAULT_DANGEROUS_PATTERNS))
                st.success("✅ Standaard-patronen hersteld.")
                st.rerun()

        st.markdown("---")

        # 7. Shell timeout
        st.markdown("### ⏱️ Shell Timeout")
        st.caption("`run_shell` en cron-shelltaken worden na deze tijd afgebroken (seconden).")
        current_timeout = get_shell_timeout()
        new_timeout = st.number_input(
            "Timeout (seconden)",
            min_value=5,
            max_value=600,
            value=current_timeout,
            step=5,
            key="settings_timeout",
        )
        if st.button("💾 Timeout opslaan", key="save_timeout"):
            set_shell_timeout(int(new_timeout))
            st.success(f"✅ Shell timeout opgeslagen: {int(new_timeout)}s")

        st.markdown("---")

        # 8. Agent iteraties
        st.markdown("### 🔁 Agent max. iteraties")
        st.caption("Maximale ReAct-lussen voordat de agent opgeeft (standaard: 5).")
        current_max_iter = get_agent_max_iterations()
        new_max_iter = st.number_input(
            "Max. iteraties",
            min_value=1,
            max_value=20,
            value=current_max_iter,
            step=1,
            key="settings_max_iter",
        )
        if st.button("💾 Iteraties opslaan", key="save_max_iter"):
            set_agent_max_iterations(int(new_max_iter))
            st.success(f"✅ Agent max. iteraties opgeslagen: {int(new_max_iter)}")

        st.markdown("---")

        # 9. Log instellingen
        st.markdown("### 📋 Log instellingen")
        st.caption("Bepaal hoeveel log-entries bewaard worden en hoeveel tekens per resultaat.")
        col_log1, col_log2 = st.columns(2)
        with col_log1:
            current_max_entries = get_log_max_entries()
            new_max_entries = st.number_input(
                "Max. log-entries",
                min_value=50,
                max_value=10000,
                value=current_max_entries,
                step=50,
                key="settings_log_entries",
            )
        with col_log2:
            current_max_chars = get_log_result_max_chars()
            new_max_chars = st.number_input(
                "Max. tekens per resultaat",
                min_value=50,
                max_value=5000,
                value=current_max_chars,
                step=50,
                key="settings_log_chars",
            )
        if st.button("💾 Log instellingen opslaan", key="save_log_settings"):
            set_log_max_entries(int(new_max_entries))
            set_log_result_max_chars(int(new_max_chars))
            st.success(f"✅ Opgeslagen: max {int(new_max_entries)} entries, {int(new_max_chars)} tekens/resultaat")

        st.markdown("---")

        # 10. Bestandsnamen
        st.markdown("### 🗂️ Bestandsnamen")
        st.caption("Pas de namen aan van het actie-logbestand en het jobs-bestand.")
        col_fn1, col_fn2 = st.columns(2)
        with col_fn1:
            current_log_file = get_log_file_name()
            new_log_file = st.text_input(
                "Actie-logbestand",
                value=current_log_file,
                key="settings_log_file_name",
            )
        with col_fn2:
            current_jobs_file = get_jobs_file_name()
            new_jobs_file = st.text_input(
                "Jobs-bestand",
                value=current_jobs_file,
                key="settings_jobs_file_name",
            )
        col_fn_btn1, col_fn_btn2 = st.columns(2)
        with col_fn_btn1:
            if st.button("💾 Bestandsnamen opslaan", key="save_file_names"):
                set_log_file_name(new_log_file.strip())
                set_jobs_file_name(new_jobs_file.strip())
                st.success(f"✅ Opgeslagen: log='{new_log_file.strip()}', jobs='{new_jobs_file.strip()}'")
        with col_fn_btn2:
            if st.button("🔄 Reset bestandsnamen", key="reset_file_names"):
                from regian.settings import _DEFAULT_LOG_FILE_NAME, _DEFAULT_JOBS_FILE_NAME
                set_log_file_name(_DEFAULT_LOG_FILE_NAME)
                set_jobs_file_name(_DEFAULT_JOBS_FILE_NAME)
                st.success(f"✅ Bestandsnamen gereset naar standaard.")
                st.rerun()

        st.markdown("---")

        # 11. Backup instellingen
        st.markdown("### 💾 Backup")
        st.caption(
            "Maak een zip-backup van de volledige werkmap. "
            "Stel een dagelijkse backup in via de **Cron**-tab met schema `dagelijks om 02:00` en commando `/backup_workspace`."
        )
        _bk_col1, _bk_col2 = st.columns(2)
        with _bk_col1:
            _bk_max = st.number_input(
                "Max. te bewaren backups",
                min_value=1, max_value=100,
                value=get_backup_max_count(),
                step=1,
                key="settings_backup_max",
            )
        with _bk_col2:
            _bk_dir = st.text_input(
                "Backup-map",
                value=get_backup_dir(),
                key="settings_backup_dir",
            )
        _bk_c1, _bk_c2, _bk_c3 = st.columns(3)
        with _bk_c1:
            if st.button("💾 Backup instellingen opslaan", key="save_backup_settings"):
                set_backup_max_count(int(_bk_max))
                set_backup_dir(_bk_dir.strip())
                st.success("✅ Backup-instellingen opgeslagen.")
        with _bk_c2:
            if st.button("📦 Nu backup maken", key="backup_now_btn"):
                with st.spinner("Backup aan het maken…"):
                    from regian.skills.backup import backup_workspace as _do_backup
                    _bk_result = _do_backup()
                st.info(_bk_result)
        with _bk_c3:
            if st.button("📋 Backups bekijken", key="list_backups_btn"):
                from regian.skills.backup import list_backups as _lb
                st.info(_lb())

        # Restore sectie
        st.markdown("#### 🔄 Werkmap herstellen vanuit backup")
        _restore_bdir = Path(get_backup_dir())
        _restore_zips = sorted(_restore_bdir.glob("*.zip"), reverse=True) if _restore_bdir.exists() else []
        if not _restore_zips:
            st.caption("Geen backups beschikbaar om te herstellen.")
        else:
            st.warning(
                "⚠️ **Let op**: dit overschrijft bestanden in de werkmap met de inhoud van de geselecteerde backup. "
                "Zorg dat je zeker bent voor je verder gaat."
            )
            _restore_selected = st.selectbox(
                "Kies een backup om te herstellen",
                options=[z.name for z in _restore_zips],
                key="restore_backup_select",
            )
            _restore_confirm = st.checkbox(
                "Ik begrijp dat bestaande bestanden worden overschreven",
                key="restore_confirm_cb",
            )
            if st.button("🔄 Restore uitvoeren", key="restore_btn", disabled=not _restore_confirm):
                with st.spinner("Werkmap aan het herstellen…"):
                    from regian.skills.backup import restore_workspace as _do_restore
                    _restore_result = _do_restore(_restore_selected)
                st.info(_restore_result)

        st.markdown("---")

        # 12. Projectbeheer — hernoemen
        st.markdown("### 📁 Projectbeheer")
        _pm_all_projects = []
        _pm_root = Path(get_root_dir())
        if _pm_root.exists():
            for _pm_entry in sorted(_pm_root.iterdir()):
                if _pm_entry.is_dir() and (_pm_entry / ".regian_project.json").exists():
                    _pm_all_projects.append(_pm_entry.name)

        if not _pm_all_projects:
            st.caption("Geen projecten gevonden in de werkmap.")
        else:
            st.caption("Hernoem een project. De mapnaam, het manifest en eventuele workflow-state worden bijgewerkt.")
            _pm_col1, _pm_col2 = st.columns(2)
            with _pm_col1:
                _pm_old = st.selectbox(
                    "Project om te hernoemen",
                    _pm_all_projects,
                    key="pm_rename_old",
                )
            with _pm_col2:
                _pm_new = st.text_input(
                    "Nieuwe naam",
                    placeholder="nieuwe_naam",
                    key="pm_rename_new",
                )
            if st.button("✏️ Hernoem project", key="pm_rename_btn"):
                if not _pm_new.strip():
                    st.warning("Geef een nieuwe naam op.")
                else:
                    from regian.skills.project import rename_project as _rp
                    _rp_result = _rp(_pm_old, _pm_new.strip())
                    if "✅" in _rp_result:
                        st.success(_rp_result)
                        st.rerun()
                    else:
                        st.error(_rp_result)

    # ── WORKFLOWS TAB ─────────────────────────────────────────
    with tab_workflows:
        from regian.core.workflow import (
            list_workflows as _wf_list_templates,
            list_runs as _wf_list_runs,
            advance_run as _wf_advance,
            cancel_run as _wf_cancel,
            start_workflow as _wf_start,
            create_run as _wf_create,
            advance_one_phase as _wf_advance_one,
            revise_run as _wf_revise,
            load_run as _wf_load_run,
            _get_phases,
            STATUS_WAITING, STATUS_DONE, STATUS_ERROR, STATUS_RUNNING,
        )
        from regian.skills.workflow import _project_path as _wf_proj_path, _format_run_status

        _wf_pp = _wf_proj_path()
        st.subheader("🔄 Workflows")

        wf_sub = st.radio(
            "Sectie",
            ["▶️ Starten", "📋 Actieve runs", "🐛 Tickets", "▶️ Project uitvoeren",
             "📚 Templates", "✏️ Visuele editor"],
            horizontal=True,
            label_visibility="collapsed",
            key="wf_sub",
        )

        # ── Sectie 1: Starten ─────────────────────────────────
        if wf_sub == "▶️ Starten":
            st.markdown("### ▶️ Workflow starten")
            _wf_templates = _wf_list_templates(_wf_pp)
            if not _wf_templates:
                st.info("Geen workflow-templates gevonden.")
            else:
                _wf_names = {w["name"]: w["id"] for w in _wf_templates}
                _wf_sel_name = st.selectbox(
                    "Kies een workflow-template",
                    options=list(_wf_names.keys()),
                    key="wf_select_template",
                )
                _wf_sel = _wf_templates[[w["name"] for w in _wf_templates].index(_wf_sel_name)]
                st.caption(f"**{_wf_sel['description']}** — {_wf_sel['phases']} fasen")
                _wf_input = st.text_area(
                    "Invoer / idee",
                    placeholder="Beschrijf je idee of opdracht...",
                    height=120,
                    key="wf_input",
                )
                if st.button("🚀 Start workflow", type="primary", key="wf_start_btn"):
                    if not _wf_input.strip():
                        st.warning("Voer een idee of opdracht in.")
                    else:
                        with st.spinner("Workflow wordt gestart..."):
                            try:
                                _wfrun = _wf_start(_wf_names[_wf_sel_name], _wf_input.strip(), _wf_pp)
                                st.toast(f"✅ Run `{_wfrun.run_id}` gestart — schakel over naar Actieve runs.")
                            except Exception as _wferr:
                                st.error(f"❌ {_wferr}")
                                st.stop()
                        st.session_state["wf_sub"] = "📋 Actieve runs"
                        st.rerun()

        # ── Sectie 2: Actieve runs ─────────────────────────────
        elif wf_sub == "📋 Actieve runs":
            _wf_proj_label = Path(_wf_pp).name if _wf_pp else ""
            st.markdown(
                f"### 📋 Actieve runs"
                + (f" — 📁 `{_wf_proj_label}`" if _wf_proj_label else "")
            )

            # Multi-rerun fase-voor-fase na Goedkeuren
            if "_wf_adv_id" in st.session_state:
                _adv_id = st.session_state["_wf_adv_id"]
                _adv_pp = st.session_state.get("_wf_adv_pp", _wf_pp)
                try:
                    _adv_run = _wf_load_run(_adv_id, _adv_pp)
                    _adv_phases = _get_phases(_adv_run)
                    _adv_total = len(_adv_phases)
                    _adv_cur = _adv_run.current_phase_index
                    _adv_name = (
                        _adv_phases[_adv_cur].get("name", f"Fase {_adv_cur + 1}")
                        if _adv_cur < _adv_total else "Afronden"
                    )
                    st.info(
                        f"▶️ **Fase {_adv_cur + 1}/{_adv_total} uitvoeren:** {_adv_name}…",
                        icon="⚙️",
                    )
                    try:
                        _adv_run = _wf_advance_one(_adv_id, _adv_pp)
                        if _adv_run.status == STATUS_RUNNING:
                            st.rerun()
                        elif _adv_run.status == STATUS_WAITING:
                            del st.session_state["_wf_adv_id"]
                            st.session_state.pop("_wf_adv_pp", None)
                            st.toast("⏸️ Volgende checkpoint — jouw goedkeuring is vereist.")
                            st.rerun()
                        elif _adv_run.status == STATUS_DONE:
                            del st.session_state["_wf_adv_id"]
                            st.session_state.pop("_wf_adv_pp", None)
                            st.toast("🎉 Workflow voltooid!")
                            st.rerun()
                        else:  # ERROR of onbekend
                            del st.session_state["_wf_adv_id"]
                            st.session_state.pop("_wf_adv_pp", None)
                            st.rerun()
                    except Exception as _adv_err:
                        st.error(f"❌ Fout tijdens uitvoering: {_adv_err}")
                        del st.session_state["_wf_adv_id"]
                        st.session_state.pop("_wf_adv_pp", None)
                except Exception:
                    del st.session_state["_wf_adv_id"]
                    st.session_state.pop("_wf_adv_pp", None)

            _wf_runs = _wf_list_runs(_wf_pp)
            if not _wf_runs:
                st.info("Geen workflow-runs gevonden voor dit project.")
            else:
                for _wfr in _wf_runs:
                    _wfbadge = {"running": "🔄", "waiting": "⏸️", "done": "✅",
                                "cancelled": "❌", "error": "💥"}.get(_wfr.status, "❓")
                    with st.expander(
                        f"{_wfbadge} **{_wfr.workflow_name}** — {_wfr.started_at[:16]} · `{_wfr.run_id[:8]}`",
                        expanded=(_wfr.status in (STATUS_WAITING, STATUS_RUNNING)),
                    ):
                        _wf_phases = _get_phases(_wfr)
                        _wf_total = len(_wf_phases)
                        _wf_cur = _wfr.current_phase_index
                        if _wf_total:
                            _wf_cols = st.columns(_wf_total)
                            for _wfpi, (_wfph, _wfcol) in enumerate(zip(_wf_phases, _wf_cols)):
                                _wfph_done = _wfpi < _wf_cur or _wfr.status == STATUS_DONE
                                _wfph_active = _wfpi == _wf_cur and _wfr.status in (STATUS_WAITING, STATUS_RUNNING)
                                _wficon = _wfph.get("icon", "📋")
                                if _wfph_done:
                                    _wfcol.markdown(f"✅ {_wficon} **{_wfph.get('name', _wfph['id'])}**")
                                elif _wfph_active:
                                    _wfcol.markdown(f"▶️ {_wficon} **{_wfph.get('name', _wfph['id'])}**")
                                else:
                                    _wfcol.markdown(f"⬜ {_wficon} {_wfph.get('name', _wfph['id'])}")

                        # ── Artifacts bovenaan, altijd zichtbaar ───────────
                        _wf_art_keys = [k for k in _wfr.artifacts if k != "input"]
                        if _wf_art_keys:
                            st.markdown("**📦 Artifacts**")
                            for _wfk in _wf_art_keys:
                                _wf_art_val = str(_wfr.artifacts[_wfk])
                                _wf_art_lines = len(_wf_art_val.splitlines())
                                _wf_art_preview = _wf_art_val[:60].replace("\n", " ").strip()
                                _wf_art_label = (
                                    f"📄 **{_wfk}** · {_wf_art_lines} regels"
                                    f" · _{_wf_art_preview}…_"
                                )
                                with st.expander(_wf_art_label, expanded=True):
                                    st.markdown(_wf_art_val)

                        # ── Laatste uitvoer: taken als inklapbare regels ───
                        if _wfr.phase_log:
                            _wf_last_entry = _wfr.phase_log[-1]
                            if _wf_last_entry.get("revised"):
                                st.caption(
                                    f"🔄 *Herzien op basis van feedback:* "
                                    f"`{_wf_last_entry.get('feedback', '')[:80]}`"
                                )
                            _wf_last_out = _wf_last_entry.get("output", "")
                            import re as _wf_re
                            _wf_task_blocks = _wf_re.split(
                                r'(?=\*\*Taak \d+/\d+:\*\*)', _wf_last_out
                            )
                            _wf_task_blocks = [b for b in _wf_task_blocks if b.strip()]
                            if len(_wf_task_blocks) > 1:
                                st.markdown("**Uitgevoerde taken:**")
                                for _wftb in _wf_task_blocks:
                                    _wftb_lines = _wftb.strip().splitlines()
                                    _wftb_header = _wftb_lines[0] if _wftb_lines else "(taak)"
                                    _wftb_body = "\n".join(_wftb_lines[1:]).strip()
                                    with st.expander(_wftb_header, expanded=False):
                                        if _wftb_body:
                                            st.markdown(_wftb_body)
                            else:
                                st.markdown("**Laatste uitvoer:**")
                                st.markdown(_wf_last_out[:3000])

                        if _wfr.status == STATUS_WAITING:
                            # Toon welke fase wacht op goedkeuring
                            _wf_cur_ph = _wf_phases[_wf_cur] if _wf_cur < _wf_total else {}
                            st.info(
                                f"⏸️ **Wacht op goedkeuring \u2014 "
                                f"Fase {_wf_cur + 1}/{_wf_total}: "
                                f"{_wf_cur_ph.get('name', '')}** "
                                f"(`{_wf_cur_ph.get('type', '')}`)"
                            )
                            st.markdown("---")
                            # Toon vorige bijsturing als herinnering
                            _wf_prev_fb = ""
                            if _wfr.phase_log and _wfr.phase_log[-1].get("revised"):
                                _wf_prev_fb = _wfr.phase_log[-1].get("feedback", "")
                            if _wf_prev_fb:
                                st.caption(f"🔄 *Bijgestuurd:* {_wf_prev_fb[:140]}")
                            _wf_feedback = st.text_area(
                                "Feedback (optioneel)",
                                key=f"wf_feedback_{_wfr.run_id}",
                                placeholder="Bijsturing voor de volgende fase...",
                                height=80,
                            )
                            _wfc1, _wfc2, _wfc3 = st.columns(3)
                            with _wfc1:
                                if st.button("✅ Goedkeuren & doorgaan",
                                             key=f"wf_approve_{_wfr.run_id}", type="primary"):
                                    st.session_state["_wf_adv_id"] = _wfr.run_id
                                    st.session_state["_wf_adv_pp"] = _wf_pp
                                    st.rerun()
                            with _wfc2:
                                if _wf_feedback.strip():
                                    if st.button("🔄 Bijsturen & opnieuw genereren",
                                                 key=f"wf_revise_{_wfr.run_id}"):
                                        with st.spinner("🧠 Fase opnieuw uitvoeren met feedback..."):
                                            try:
                                                _wf_revise(_wfr.run_id, _wf_feedback.strip(), _wf_pp)
                                                _wf_fb_key = f"wf_feedback_{_wfr.run_id}"
                                                if _wf_fb_key in st.session_state:
                                                    del st.session_state[_wf_fb_key]
                                                st.toast("🔄 Uitvoer bijgewerkt — bekijk het resultaat hierboven.")
                                            except Exception as _wfe:
                                                st.error(f"❌ {_wfe}")
                                                st.stop()
                                        st.rerun()
                                else:
                                    st.button("🔄 Bijsturen & opnieuw genereren",
                                              key=f"wf_revise_{_wfr.run_id}",
                                              disabled=True,
                                              help="Voer eerst feedback in")
                            with _wfc3:
                                if st.button("❌ Annuleren", key=f"wf_cancel_{_wfr.run_id}"):
                                    _wf_cancel(_wfr.run_id, _wf_pp)
                                    st.rerun()

        # ── Sectie 3: Templates ────────────────────────────────
        elif wf_sub == "📚 Templates":
            st.markdown("### 📚 Workflow-templates")
            _wf_tmpl_list = _wf_list_templates(_wf_pp)
            if not _wf_tmpl_list:
                st.info("Geen templates gevonden.")
            else:
                for _wft in _wf_tmpl_list:
                    with st.expander(f"**{_wft['name']}** (`{_wft['id']}`)", expanded=False):
                        st.caption(_wft["description"])
                        st.caption(f"📍 Bron: `{_wft['source']}`")
                        try:
                            from regian.core.workflow import load_workflow as _wf_lw
                            _wftdata = _wf_lw(_wft["id"], _wf_pp)
                            for _wfpi2, _wfph2 in enumerate(_wftdata.get("phases", []), 1):
                                _wfico2 = _wfph2.get("icon", "📋")
                                _wfreq = "⏸️ goedkeuring" if _wfph2.get("require_approval") or _wfph2.get("type") == "human_checkpoint" else ""
                                st.markdown(f"{_wfpi2}. {_wfico2} **{_wfph2.get('name', _wfph2['id'])}** `{_wfph2.get('type', '')}` {_wfreq}")
                        except Exception:
                            pass
                        if st.button(f"📤 Exporteer als BPMN", key=f"wf_export_{_wft['id']}"):
                            from regian.skills.workflow import export_bpmn as _wf_expbpmn
                            st.success(_wf_expbpmn(_wft["id"]))

            st.markdown("---")
            st.markdown("### ➕ Nieuw template genereren")
            _wf_new_name = st.text_input("Template-naam (technisch, bijv. code_review)", key="wf_new_name")
            _wf_new_desc = st.text_area("Beschrijving", key="wf_new_desc", height=80,
                                         placeholder="Wat doet deze workflow?")
            if st.button("🧠 Genereer template via LLM", key="wf_gen_btn"):
                if not _wf_new_name.strip() or not _wf_new_desc.strip():
                    st.warning("Vul naam en beschrijving in.")
                else:
                    with st.spinner("Template genereren..."):
                        from regian.skills.workflow import create_workflow_template as _wf_cwt
                        st.success(_wf_cwt(_wf_new_name.strip(), _wf_new_desc.strip()))
                        st.rerun()

            st.markdown("---")
            st.markdown("### 📥 BPMN importeren")
            _wf_bpmn_path = st.text_input("Pad naar .bpmn XML-bestand", key="wf_bpmn_path",
                                           placeholder="bijv. mijn_flow.bpmn")
            if st.button("📥 Importeer BPMN", key="wf_bpmn_import_btn"):
                if not _wf_bpmn_path.strip():
                    st.warning("Voer een bestandspad in.")
                else:
                    from regian.skills.workflow import import_bpmn as _wf_ibpmn
                    _wf_imp = _wf_ibpmn(_wf_bpmn_path.strip())
                    (st.success if "✅" in _wf_imp else st.error)(_wf_imp)
                    if "✅" in _wf_imp:
                        st.rerun()

        # ── Sectie 4: Project uitvoeren ────────────────────────
        elif wf_sub == "▶️ Project uitvoeren":
            import subprocess as _wfsp

            _pp_run = _wf_pp
            _wf_run_label = Path(_pp_run).name if _pp_run else ""
            st.markdown(
                "### ▶️ Project uitvoeren"
                + (f" — 📁 `{_wf_run_label}`" if _wf_run_label else "")
            )
            if not _pp_run:
                st.info("Geen actief project. Activeer een project via de zijbalk.")
            else:
                from pathlib import Path as _wfPath
                _pp_path = _wfPath(_pp_run)

                # ── Detecteer run-scripts ─────────────────────
                _run_options = []
                if (_pp_path / "build.sh").exists():
                    _run_options.append(("🔨 build.sh", "bash build.sh", False))
                if (_pp_path / "dev.sh").exists():
                    _run_options.append(("🚀 dev.sh", "bash dev.sh", False))
                if (_pp_path / "start.sh").exists():
                    _run_options.append(("▶️ start.sh", "bash start.sh", False))
                if (_pp_path / "Makefile").exists():
                    _run_options.append(("⚙️ make", "make", False))
                if (_pp_path / "package.json").exists():
                    try:
                        import json as _rj
                        _pkg = _rj.loads((_pp_path / "package.json").read_text())
                        _scripts = _pkg.get("scripts", {})
                        if "build" in _scripts:
                            _run_options.append(("📦 npm run build", "npm run build", False))
                        if "dev" in _scripts:
                            _run_options.append(("🚀 npm run dev", "npm run dev", True))
                        elif "start" in _scripts:
                            _run_options.append(("▶️ npm start", "npm start", True))
                        if "test" in _scripts:
                            _run_options.append(("🧪 npm test", "npm test", False))
                    except Exception:
                        pass
                if (_pp_path / "requirements.txt").exists():
                    _run_options.append(("🧪 pytest", "python -m pytest", False))
                    if (_pp_path / "main.py").exists():
                        _run_options.append(("▶️ python main.py", "python main.py", True))

                if not _run_options:
                    st.info("Geen bekende run-scripts gevonden. Voeg een `build.sh` of `package.json` toe.")
                    if st.button("🔨 Maak build.sh aan", key="wf_mk_build"):
                        from regian.core.agent import OrchestratorAgent as _wfOrch
                        with st.spinner("build.sh genereren..."):
                            _wfoa = _wfOrch()
                            _wfbr = _wfoa.run(
                                f"Maak een passend build.sh en/of start script aan voor het project op `{_pp_run}`. "
                                "Kijk naar de bestaande bestanden (package.json, requirements.txt, main.py, etc.) "
                                "en schrijf een script dat het project bouwt en/of start."
                            )
                        st.success(_wfbr)
                        st.rerun()
                else:
                    _run_labels = [o[0] for o in _run_options]
                    _run_sel_label = st.selectbox("Kies actie", _run_labels, key="wf_run_sel")
                    _run_sel = _run_options[_run_labels.index(_run_sel_label)]
                    _run_label, _run_cmd, _run_is_server = _run_sel

                    st.code(f"$ {_run_cmd}", language="bash")

                    if _run_is_server:
                        # ── Poort detectie ──────────────────────────────────────────
                        _port = "3000" if "react" in _run_cmd.lower() or "next" in _run_cmd.lower() else "5173" if "vite" in _run_cmd.lower() else "8080"
                        if "npm" in _run_cmd and (_pp_path / "package.json").exists():
                            try:
                                import re as _wf_re_port, json as _wf_port_json
                                _pkg_scripts = _wf_port_json.loads(
                                    (_pp_path / "package.json").read_text()
                                ).get("scripts", {})
                                _script_key = _run_cmd.replace("npm run ", "").replace("npm ", "").strip()
                                _script_body = _pkg_scripts.get(_script_key, "")
                                _port_match = _wf_re_port.search(r"-p\s+(\d+)|--port[= ](\d+)|:(\d{4,5})", _script_body)
                                if _port_match:
                                    _port = next(g for g in _port_match.groups() if g)
                            except Exception:
                                pass

                        # ── Server start/stop via Popen ─────────────────────────────
                        import os as _wf_os, signal as _wf_signal
                        _srv_key = f"srv_pid_{_pp_run}_{_run_cmd}"
                        _srv_pid = st.session_state.get(_srv_key)
                        _srv_log = str(_pp_path / ".regian_server.log")
                        _srv_log_key = f"srv_log_{_pp_run}"
                        st.session_state[_srv_log_key] = _srv_log

                        # Controleer of process nog leeft
                        _srv_running = False
                        if _srv_pid:
                            try:
                                _wf_os.kill(_srv_pid, 0)
                                _srv_running = True
                            except OSError:
                                _srv_running = False
                                st.session_state.pop(_srv_key, None)
                                _srv_pid = None

                        _srv_col1, _srv_col2, _srv_col3 = st.columns([2, 2, 2])
                        with _srv_col1:
                            if not _srv_running:
                                if st.button(f"▶️ Start {_run_label}", key="wf_srv_start", type="primary", use_container_width=True):
                                    import subprocess as _wf_popen
                                    _srv_logf = open(_srv_log, "a")
                                    _srv_proc = _wf_popen.Popen(
                                        _run_cmd, shell=True, cwd=_pp_run,
                                        stdout=_srv_logf, stderr=_srv_logf,
                                    )
                                    st.session_state[_srv_key] = _srv_proc.pid
                                    import time as _wf_time; _wf_time.sleep(1)
                                    st.rerun()
                            else:
                                st.success(f"✅ Server actief (PID {_srv_pid})", icon="🟢")
                        with _srv_col2:
                            if _srv_running:
                                if st.button("🔴 Stop server", key="wf_srv_stop", use_container_width=True):
                                    try:
                                        _wf_os.kill(_srv_pid, _wf_signal.SIGTERM)
                                    except ProcessLookupError:
                                        pass
                                    st.session_state.pop(_srv_key, None)
                                    st.rerun()
                        with _srv_col3:
                            if _srv_running:
                                st.link_button(f"🌐 Open 127.0.0.1:{_port}", f"http://127.0.0.1:{_port}", use_container_width=True)

                        if not _srv_running:
                            st.caption(f"Of handmatig: `cd {_pp_run}` → `{_run_cmd}`")

                        # ── Log viewer ──────────────────────────────────────────────
                        from pathlib import Path as _srvLogPath
                        _log_p = _srvLogPath(_srv_log)
                        if _log_p.exists() and _log_p.stat().st_size > 0:
                            _lv_col1, _lv_col2 = st.columns([5, 1])
                            with _lv_col1:
                                st.caption(f"📄 Log: `{_log_p.name}`")
                            with _lv_col2:
                                if st.button("🗑️ Wis log", key="wf_srv_clearlog",
                                             use_container_width=True, help="Logbestand leegmaken"):
                                    _log_p.write_text("", encoding="utf-8")
                                    st.rerun()
                            with st.expander("📋 Server log", expanded=_srv_running):
                                _log_lines = _log_p.read_text(encoding="utf-8", errors="replace")
                                # Toon laatste 200 regels
                                _log_tail = "\n".join(_log_lines.splitlines()[-200:])
                                st.code(_log_tail or "(leeg)", language="bash")
                                if _srv_running:
                                    st.caption("↻ Ververs de pagina voor nieuwe regels")
                    else:
                        if st.button(f"▶️ Uitvoeren: {_run_label}",
                                     key="wf_run_exec", type="primary"):
                            with st.spinner(f"{_run_label} uitvoeren..."):
                                try:
                                    _proc = _wfsp.run(
                                        _run_cmd, shell=True, cwd=_pp_run,
                                        capture_output=True, text=True, timeout=120,
                                    )
                                    _rc = _proc.returncode
                                    _out = _proc.stdout + _proc.stderr
                                    if _rc == 0:
                                        st.success(f"✅ Geslaagd (exit 0)")
                                    else:
                                        st.error(f"❌ Exit code {_rc}")
                                    with st.expander("📄 Output", expanded=(_rc != 0)):
                                        st.code(_out[:8000], language="bash")
                                except _wfsp.TimeoutExpired:
                                    st.warning("⏱️ Timeout (>120s) — mogelijk een live server?")
                                except Exception as _wfre:
                                    st.error(f"❌ {_wfre}")

        # ── Sectie 5: Tickets (Kanban) ────────────────────────
        elif wf_sub == "🐛 Tickets":
            from regian.skills.tickets import (
                create_ticket as _tk_create,
                list_tickets as _tk_list,
                move_ticket as _tk_move,
                delete_ticket as _tk_del,
                fix_ticket as _tk_fix,
                fix_all_tickets as _tk_fix_all,
                _tickets_file as _tk_file,
                _load as _tk_load,
                STATUSES as _TK_STATUSES,
            )

            st.markdown("### 🐛 Tickets — Kanban")

            _tk_f = _tk_file()
            if _tk_f is None:
                st.info("Geen actief project. Activeer een project via de zijbalk.")
            else:
                from pathlib import Path as _tkPath
                _tk_all = _tk_load(_tkPath(str(_tk_f)))
                _tk_todo   = [t for t in _tk_all if t["status"] == "todo"]
                _tk_inprog = [t for t in _tk_all if t["status"] == "in_progress"]
                _tk_review = [t for t in _tk_all if t["status"] == "review"]
                _tk_done   = [t for t in _tk_all if t["status"] == "done"]

                # Fix-all knop bovenaan
                _tk_top1, _tk_top2 = st.columns([3, 1])
                with _tk_top1:
                    st.caption(
                        f"📋 {len(_tk_todo)} to do  ·  "
                        f"🔄 {len(_tk_inprog)} in progress  ·  "
                        f"👀 {len(_tk_review)} review  ·  "
                        f"✅ {len(_tk_done)} done"
                    )
                with _tk_top2:
                    if _tk_todo and st.button(
                        f"🤖 Fix alle ({len(_tk_todo)})", key="tk_fix_all_btn",
                        type="primary", use_container_width=True
                    ):
                        with st.spinner("AI aan het werk..."):
                            _tk_fix_all()
                        st.rerun()

                st.markdown("---")

                # ── Nieuw ticket formulier ─────────────────────────────
                with st.expander("➕ Nieuw ticket aanmaken", expanded=(len(_tk_all) == 0)):
                    with st.form("tk_new_form", clear_on_submit=True):
                        _tk_nt = st.text_input("Titel", placeholder="Korte beschrijving...")
                        _tk_nd = st.text_area("Beschrijving", height=80,
                                              placeholder="Stappen, verwacht gedrag, etc.")
                        _tk_submitted = st.form_submit_button("➕ Aanmaken",
                                                              use_container_width=True,
                                                              type="primary")
                    if _tk_submitted:
                        if _tk_nt.strip():
                            _tk_res = _tk_create(_tk_nt.strip(), _tk_nd.strip())
                            st.toast(_tk_res)
                            st.rerun()
                        else:
                            st.warning("Voer een titel in.")

                st.markdown("---")

                # ── Kanban kolommen ─────────────────────────────────────
                _tkc1, _tkc2, _tkc3, _tkc4 = st.columns(4)

                # ── TO DO ──────────────────────────────────────
                with _tkc1:
                    st.markdown("**📋 To Do**")
                    for _tkt in _tk_todo:
                        with st.container(border=True):
                            st.markdown(f"**{_tkt['title']}**")
                            st.caption(f"`{_tkt['id']}` · {_tkt['updated_at'][:10]}")
                            if _tkt.get("description"):
                                st.caption(_tkt["description"][:120])
                            _tkb1, _tkb2 = st.columns(2)
                            if _tkb1.button("🤖 Fix", key=f"tk_fix_{_tkt['id']}",
                                            use_container_width=True):
                                with st.spinner(f"AI werkt aan '{_tkt['title']}'..."):
                                    _tk_fix(_tkt["id"])
                                st.rerun()
                            if _tkb2.button("🗑️", key=f"tk_del_{_tkt['id']}",
                                            use_container_width=True):
                                _tk_del(_tkt["id"])
                                st.rerun()

                # ── IN PROGRESS ────────────────────────────────
                with _tkc2:
                    st.markdown("**🔄 In Progress**")
                    if not _tk_inprog:
                        st.caption("_Geen tickets bezig_")
                    for _tkt in _tk_inprog:
                        with st.container(border=True):
                            st.markdown(f"**{_tkt['title']}**")
                            st.caption(f"`{_tkt['id']}` · AI is bezig...")
                            st.progress(0.5, text="AI verwerkt...")

                # ── REVIEW ─────────────────────────────────────
                with _tkc3:
                    st.markdown("**👀 Review**")
                    if not _tk_review:
                        st.caption("_Niets te reviewen_")
                    for _tkt in _tk_review:
                        with st.container(border=True):
                            st.markdown(f"**{_tkt['title']}**")
                            st.caption(f"`{_tkt['id']}` · {_tkt['updated_at'][:10]}")
                            if _tkt.get("ai_output"):
                                with st.expander("🤖 AI samenvatting", expanded=False):
                                    st.markdown(_tkt["ai_output"])
                            # ── Agent stappen uit de actie-log ──────────
                            try:
                                from regian.core.action_log import get_log_grouped as _tk_alg
                                _tk_groups = _tk_alg(limit_groups=500)
                                _tk_steps = next(
                                    (g["steps"] for g in _tk_groups if g["group_id"] == _tkt["id"]),
                                    None
                                )
                                if _tk_steps:
                                    with st.expander(f"📋 Agent log ({len(_tk_steps)} stappen)", expanded=False):
                                        for _s in _tk_steps:
                                            _icon = "✅" if not str(_s.get("result","")).startswith("❌") else "❌"
                                            st.markdown(f"**{_icon} `{_s['tool']}`**")
                                            if _s.get("args"):
                                                _args_preview = {k: str(v)[:120] for k, v in _s["args"].items()}
                                                st.caption(str(_args_preview))
                                            if _s.get("result"):
                                                st.code(str(_s["result"])[:400], language="bash")
                                            st.divider()
                            except Exception:
                                pass
                            _tkr1, _tkr2 = st.columns(2)
                            if _tkr1.button("✅ Done", key=f"tk_done_{_tkt['id']}",
                                            use_container_width=True, type="primary"):
                                _tk_move(_tkt["id"], "done")
                                st.rerun()
                            _tk_back_key = f"tk_back_comment_{_tkt['id']}"
                            _tk_back_cmt = st.text_input(
                                "Opmerking", key=_tk_back_key,
                                placeholder="Wat klopt er niet?",
                                label_visibility="collapsed",
                            )
                            if _tkr2.button("🔙 To Do", key=f"tk_back_{_tkt['id']}",
                                            use_container_width=True):
                                _tk_move(_tkt["id"], "todo",
                                         comment=_tk_back_cmt or "Terug voor aanpassing")
                                st.rerun()

                # ── DONE ───────────────────────────────────────
                with _tkc4:
                    st.markdown("**✅ Done**")
                    if not _tk_done:
                        st.caption("_Nog niets afgerond_")
                    for _tkt in _tk_done:
                        with st.container(border=True):
                            st.markdown(f"~~{_tkt['title']}~~")
                            st.caption(f"`{_tkt['id']}` · {_tkt['updated_at'][:10]}")
                            if st.button("🔙", key=f"tk_undone_{_tkt['id']}",
                                         help="Terug naar To Do",
                                         use_container_width=True):
                                _tk_move(_tkt["id"], "todo")
                                st.rerun()

        # ── Sectie 6: Visuele editor ───────────────────────────
        elif wf_sub == "✏️ Visuele editor":
            st.markdown("### ✏️ Visuele workflow-editor")
            import json as _wfjson

            _WFED_TYPES  = ["llm_prompt", "task_loop", "human_checkpoint", "tool_chain"]
            _WFED_ICONS  = {"llm_prompt": "🧠", "task_loop": "🔄",
                            "human_checkpoint": "🔍", "tool_chain": "⚙️"}
            _WFED_COLORS = {"llm_prompt": "lightblue", "task_loop": "lightgreen",
                            "human_checkpoint": "lightyellow", "tool_chain": "lightgray"}

            # Template kiezen
            _wfed_all = _wf_list_templates(_wf_pp)
            _wfed_opts = ["➕ Nieuw template"] + [w["id"] for w in _wfed_all]
            _wfed_sel = st.selectbox("Template laden of nieuw beginnen",
                                     _wfed_opts, key="wfed_sel")

            # Laad bij keuzewijziging
            if ("wf_editor_data" not in st.session_state
                    or st.session_state.get("wf_editor_sel") != _wfed_sel):
                st.session_state["wf_editor_sel"] = _wfed_sel
                if _wfed_sel == "➕ Nieuw template":
                    st.session_state["wf_editor_data"] = {
                        "id": "nieuwe_workflow",
                        "name": "Nieuwe Workflow",
                        "description": "",
                        "version": "1.0",
                        "phases": [],
                    }
                else:
                    try:
                        from regian.core.workflow import load_workflow as _wf_lw
                        _ld = _wf_lw(_wfed_sel, _wf_pp)
                        import copy as _wfcopy
                        st.session_state["wf_editor_data"] = _wfcopy.deepcopy(_ld)
                    except Exception as _wflerr:
                        st.error(f"❌ {_wflerr}")
                        st.session_state["wf_editor_data"] = None

            _wfed = st.session_state.get("wf_editor_data")
            if _wfed is None:
                st.stop()

            # ── Metadata ──────────────────────────────────────
            _wfem1, _wfem2 = st.columns(2)
            with _wfem1:
                _wfed["id"] = st.text_input("Template-ID", value=_wfed["id"], key="wfed_id")
                _wfed["name"] = st.text_input("Naam", value=_wfed["name"], key="wfed_name")
            with _wfem2:
                _wfed["description"] = st.text_input(
                    "Beschrijving", value=_wfed.get("description", ""), key="wfed_desc")
                _wfed["version"] = st.text_input(
                    "Versie", value=_wfed.get("version", "1.0"), key="wfed_ver")

            st.markdown("---")

            # ── Flowchart visualisatie ────────────────────────
            _wfed_phases = _wfed.get("phases", [])
            if _wfed_phases:
                _dot = ['digraph G {',
                        '  rankdir=LR;',
                        '  node [shape=box, style="filled,rounded", fontname="Helvetica", fontsize=11];',
                        '  edge [fontsize=9];',
                        '  START [shape=circle, label="▶", fillcolor="#27ae60", fontcolor=white, '
                        'width=0.5, fixedsize=true];']
                _prev_id = "START"
                for _wfeph in _wfed_phases:
                    _eid  = re.sub(r"[^a-zA-Z0-9_]", "_", _wfeph.get("id", "fase"))
                    _ename = _wfeph.get("name", _eid).replace('"', "'")
                    _etype = _wfeph.get("type", "llm_prompt")
                    _ecolor = _WFED_COLORS.get(_etype, "white")
                    _eicon  = _WFED_ICONS.get(_etype, "📋")
                    _eappr  = " ⏸️" if _wfeph.get("require_approval") or _etype == "human_checkpoint" else ""
                    _dot.append(f'  {_eid} [label="{_eicon} {_ename}\\n({_etype}){_eappr}", '
                                f'fillcolor="{_ecolor}"];')
                    _dot.append(f'  {_prev_id} -> {_eid};')
                    _prev_id = _eid
                _dot.append('  EINDE [shape=doublecircle, label="■", fillcolor="#e74c3c", '
                            'fontcolor=white, width=0.5, fixedsize=true];')
                _dot.append(f'  {_prev_id} -> EINDE;')
                _dot.append("}")
                st.graphviz_chart("\n".join(_dot), use_container_width=True)
            else:
                st.info("Nog geen fasen — voeg er hieronder een toe.")

            # ── Fase-editor ───────────────────────────────────
            st.markdown("#### 📋 Fasen")
            _wfed_del = _wfed_up = _wfed_dn = None

            for _wfei, _wfeph in enumerate(_wfed_phases):
                _wfeph_type = _wfeph.get("type", "llm_prompt")
                _wfeph_icon = _WFED_ICONS.get(_wfeph_type, "📋")
                with st.expander(
                    f"{_wfei + 1}. {_wfeph_icon} **{_wfeph.get('name', _wfeph.get('id', ''))}**"
                    f" `{_wfeph_type}`",
                    expanded=False,
                ):
                    _wfec1, _wfec2 = st.columns(2)
                    with _wfec1:
                        _wfeph["id"] = st.text_input(
                            "ID", value=_wfeph.get("id", ""), key=f"wfed_ph_id_{_wfei}")
                        _wfeph["name"] = st.text_input(
                            "Naam", value=_wfeph.get("name", ""), key=f"wfed_ph_name_{_wfei}")
                    with _wfec2:
                        _wfeph["type"] = st.selectbox(
                            "Type", _WFED_TYPES,
                            index=_WFED_TYPES.index(_wfeph.get("type", "llm_prompt")),
                            key=f"wfed_ph_type_{_wfei}")
                        _wfeph["icon"] = st.text_input(
                            "Icoon", value=_wfeph.get("icon", _WFED_ICONS.get(_wfeph["type"], "📋")),
                            key=f"wfed_ph_icon_{_wfei}")

                    _ept = _wfeph["type"]
                    if _ept == "llm_prompt":
                        _wfeph["prompt_template"] = st.text_area(
                            "Prompt-template (gebruik {{sleutel}} voor substitutie)",
                            value=_wfeph.get("prompt_template", ""),
                            height=100, key=f"wfed_ph_pt_{_wfei}")
                        _wfeph["output_key"] = st.text_input(
                            "Output-sleutel", value=_wfeph.get("output_key", ""),
                            key=f"wfed_ph_ok_{_wfei}",
                            help="Naam waaronder het LLM-antwoord bewaard wordt als artifact")
                        _wfeph["require_approval"] = st.checkbox(
                            "Vereist goedkeuring na deze fase",
                            value=_wfeph.get("require_approval", False),
                            key=f"wfed_ph_ra_{_wfei}")
                    elif _ept == "task_loop":
                        _wfeph["source_key"] = st.text_input(
                            "Bron-sleutel (artifact met takenlijst)",
                            value=_wfeph.get("source_key", "task_list"),
                            key=f"wfed_ph_sk_{_wfei}")
                        _wfeph["require_approval"] = st.checkbox(
                            "Vereist goedkeuring na uitvoering",
                            value=_wfeph.get("require_approval", True),
                            key=f"wfed_ph_ra_{_wfei}")
                    elif _ept == "human_checkpoint":
                        _wfeph["prompt"] = st.text_area(
                            "Checkpoint-prompt (wat moet de gebruiker beoordelen?)",
                            value=_wfeph.get("prompt", ""),
                            height=80, key=f"wfed_ph_cp_{_wfei}")
                    elif _ept == "tool_chain":
                        _wfeph["require_approval"] = st.checkbox(
                            "Vereist goedkeuring na uitvoering",
                            value=_wfeph.get("require_approval", False),
                            key=f"wfed_ph_ra_{_wfei}")
                        _wf_steps_raw = st.text_area(
                            "Stappen (JSON-lijst van {tool, args} objecten)",
                            value=_wfjson.dumps(_wfeph.get("steps", []), indent=2, ensure_ascii=False),
                            height=120, key=f"wfed_ph_steps_{_wfei}")
                        try:
                            _wfeph["steps"] = _wfjson.loads(_wf_steps_raw)
                        except Exception:
                            st.caption("⚠️ Ongeldige JSON voor stappen")

                    _wfeb1, _wfeb2, _wfeb3 = st.columns(3)
                    with _wfeb1:
                        if _wfei > 0 and st.button("⬆️ Omhoog", key=f"wfed_up_{_wfei}"):
                            _wfed_up = _wfei
                    with _wfeb2:
                        if _wfei < len(_wfed_phases) - 1 and st.button(
                                "⬇️ Omlaag", key=f"wfed_dn_{_wfei}"):
                            _wfed_dn = _wfei
                    with _wfeb3:
                        if st.button("🗑️ Verwijder", key=f"wfed_del_{_wfei}"):
                            _wfed_del = _wfei

            # Fase-acties verwerken
            if _wfed_del is not None:
                _wfed_phases.pop(_wfed_del)
                st.rerun()
            if _wfed_up is not None:
                _wfed_phases[_wfed_up], _wfed_phases[_wfed_up - 1] = (
                    _wfed_phases[_wfed_up - 1], _wfed_phases[_wfed_up])
                st.rerun()
            if _wfed_dn is not None:
                _wfed_phases[_wfed_dn], _wfed_phases[_wfed_dn + 1] = (
                    _wfed_phases[_wfed_dn + 1], _wfed_phases[_wfed_dn])
                st.rerun()

            # ── Fase toevoegen ────────────────────────────────
            st.markdown("---")
            with st.expander("➕ Nieuwe fase toevoegen"):
                _wfna1, _wfna2 = st.columns(2)
                with _wfna1:
                    _new_ph_id   = st.text_input("Fase-ID", key="wfed_new_id",
                                                  placeholder="bijv. analyse")
                    _new_ph_name = st.text_input("Naam", key="wfed_new_name",
                                                  placeholder="bijv. Analyse")
                with _wfna2:
                    _new_ph_type = st.selectbox("Type", _WFED_TYPES, key="wfed_new_type")
                if st.button("➕ Voeg fase toe", key="wfed_add_ph"):
                    if _new_ph_id.strip():
                        _wfed_phases.append({
                            "id":   _new_ph_id.strip(),
                            "name": _new_ph_name.strip() or _new_ph_id.strip(),
                            "type": _new_ph_type,
                            "icon": _WFED_ICONS.get(_new_ph_type, "📋"),
                        })
                        st.rerun()
                    else:
                        st.warning("Vul een fase-ID in.")

            # ── Opslaan / Reset ───────────────────────────────
            st.markdown("---")
            _wfes1, _wfes2, _wfes3 = st.columns(3)
            with _wfes1:
                if st.button("💾 Opslaan als template", type="primary", key="wfed_save"):
                    try:
                        from regian.core.workflow import _workflow_dir as _wfed_wdir
                        _save_data = {k: v for k, v in _wfed.items() if not k.startswith("_")}
                        _save_dir  = _wfed_wdir(_wf_pp)
                        _save_dir.mkdir(parents=True, exist_ok=True)
                        _save_path = _save_dir / f"{_wfed['id']}.json"
                        _save_path.write_text(
                            _wfjson.dumps(_save_data, indent=2, ensure_ascii=False),
                            encoding="utf-8")
                        st.success(f"✅ Template opgeslagen: `{_save_path}`")
                        del st.session_state["wf_editor_data"]
                        del st.session_state["wf_editor_sel"]
                        st.rerun()
                    except Exception as _wfse:
                        st.error(f"❌ {_wfse}")
            with _wfes2:
                if st.button("📤 Exporteer als BPMN", key="wfed_export_bpmn"):
                    from regian.skills.workflow import export_bpmn as _wfed_xbpmn
                    # Sla eerst op, exporteer dan de opgeslagen versie
                    try:
                        from regian.core.workflow import _workflow_dir as _wfed_wdir2
                        _save_data2 = {k: v for k, v in _wfed.items() if not k.startswith("_")}
                        _save_dir2  = _wfed_wdir2(_wf_pp)
                        _save_dir2.mkdir(parents=True, exist_ok=True)
                        (_save_dir2 / f"{_wfed['id']}.json").write_text(
                            _wfjson.dumps(_save_data2, indent=2, ensure_ascii=False),
                            encoding="utf-8")
                        st.success(_wfed_xbpmn(_wfed["id"]))
                    except Exception as _wfxe:
                        st.error(f"❌ {_wfxe}")
            with _wfes3:
                if st.button("🔄 Reset editor", key="wfed_reset"):
                    if "wf_editor_data" in st.session_state:
                        del st.session_state["wf_editor_data"]
                    if "wf_editor_sel" in st.session_state:
                        del st.session_state["wf_editor_sel"]
                    st.rerun()

    # ── TOKENS TAB ────────────────────────────────────────────
    with tab_tokens:
        st.header("📊 Token-verbruik & Kosten")
        from regian.core.token_log import (
            get_totals, get_summary_by_model, get_summary_by_project,
            get_monthly_evolution, get_daily_evolution, get_summary_by_prompt,
            clear_token_log,
        )

        totals = get_totals()

        # KPI-rij
        _kc1, _kc2, _kc3, _kc4 = st.columns(4)
        _kc1.metric("Aanroepen", f"{totals['calls']:,}")
        _kc2.metric("Totaal tokens", f"{totals['total_tokens']:,}")
        _kc3.metric("Input tokens", f"{totals['input_tokens']:,}")
        _kc4.metric("Kostprijs EUR", f"€ {totals['cost_eur']:.6f}")

        st.markdown("---")

        # Per provider / model
        with st.expander("📋 Per provider / model", expanded=True):
            model_rows = get_summary_by_model()
            if model_rows:
                import pandas as _tkpd
                _df_model = _tkpd.DataFrame(model_rows).rename(columns={
                    "provider": "Provider", "model": "Model", "calls": "Aanroepen",
                    "input_tokens": "Input tokens", "output_tokens": "Output tokens",
                    "total_tokens": "Totaal tokens", "cost_eur": "Kostprijs EUR",
                })[["Provider", "Model", "Aanroepen", "Input tokens", "Output tokens", "Totaal tokens", "Kostprijs EUR"]]
                _df_model["Kostprijs EUR"] = _df_model["Kostprijs EUR"].map(
                    lambda x: f"€ {x:.6f}"
                )
                st.dataframe(_df_model, use_container_width=True, hide_index=True)
            else:
                st.info("Nog geen tokendata beschikbaar.")

        # Per project
        with st.expander("🗂️ Per project", expanded=False):
            proj_rows = get_summary_by_project()
            if proj_rows:
                import pandas as _tkpd2
                _df_proj = _tkpd2.DataFrame(proj_rows).rename(columns={
                    "project": "Project", "calls": "Aanroepen",
                    "input_tokens": "Input tokens", "output_tokens": "Output tokens",
                    "total_tokens": "Totaal tokens", "cost_eur": "Kostprijs EUR",
                })[["Project", "Aanroepen", "Input tokens", "Output tokens", "Totaal tokens", "Kostprijs EUR"]]
                _df_proj["Kostprijs EUR"] = _df_proj["Kostprijs EUR"].map(
                    lambda x: f"€ {x:.6f}"
                )
                st.dataframe(_df_proj, use_container_width=True, hide_index=True)
            else:
                st.info("Nog geen projectdata beschikbaar.")

        # Per opdracht / prompt
        with st.expander("💬 Per opdracht", expanded=False):
            prompt_rows = get_summary_by_prompt()
            if prompt_rows:
                import pandas as _tkpd4
                _df_prompt = _tkpd4.DataFrame(prompt_rows).rename(columns={
                    "prompt": "Opdracht", "modellen": "Provider/Model",
                    "projecten": "Project",
                    "calls": "Aanroepen", "last_ts": "Laatste aanroep",
                    "input_tokens": "Input tokens", "output_tokens": "Output tokens",
                    "total_tokens": "Totaal tokens", "cost_eur": "Kostprijs EUR",
                })[["Opdracht", "Project", "Provider/Model", "Aanroepen", "Laatste aanroep", "Input tokens", "Output tokens", "Totaal tokens", "Kostprijs EUR"]]
                _df_prompt["Kostprijs EUR"] = _df_prompt["Kostprijs EUR"].map(
                    lambda x: f"€ {x:.6f}"
                )
                st.dataframe(_df_prompt, use_container_width=True, hide_index=True)
            else:
                st.info("Nog geen opdrachtdata beschikbaar.")

        # Evolutie
        with st.expander("📈 Evolutie", expanded=False):
            _ev_tab1, _ev_tab2 = st.tabs(["Per maand", "Per dag"])

            with _ev_tab1:
                monthly = get_monthly_evolution()
                if monthly:
                    import pandas as _tkpd3
                    _df_month = _tkpd3.DataFrame(monthly).rename(columns={
                        "month": "Maand", "calls": "Aanroepen",
                        "total_tokens": "Totaal tokens", "cost_eur": "Kostprijs EUR",
                    })
                    _df_month = _df_month.set_index("Maand")
                    st.bar_chart(_df_month[["Totaal tokens"]])
                    _df_month["Kostprijs EUR"] = _df_month["Kostprijs EUR"].map(
                        lambda x: f"€ {x:.6f}"
                    )
                    st.dataframe(_df_month, use_container_width=True)
                else:
                    st.info("Nog geen maandelijkse data beschikbaar.")

            with _ev_tab2:
                daily = get_daily_evolution()
                if daily:
                    import pandas as _tkpd5
                    _df_day = _tkpd5.DataFrame(daily).rename(columns={
                        "day": "Dag", "calls": "Aanroepen",
                        "total_tokens": "Totaal tokens", "cost_eur": "Kostprijs EUR",
                    })
                    _df_day = _df_day.set_index("Dag")
                    st.bar_chart(_df_day[["Totaal tokens"]])
                    _df_day["Kostprijs EUR"] = _df_day["Kostprijs EUR"].map(
                        lambda x: f"€ {x:.6f}"
                    )
                    st.dataframe(_df_day, use_container_width=True)
                else:
                    st.info("Nog geen dagelijkse data beschikbaar.")

        st.markdown("---")

        # Token-log wissen
        if st.button("🗑️ Wis token-log", key="clear_token_log"):
            clear_token_log()
            st.success("✅ Token-log gewist.")
            st.rerun()


if __name__ == "__main__":
    start_gui()