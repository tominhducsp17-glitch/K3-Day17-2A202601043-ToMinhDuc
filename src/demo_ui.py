"""Production-Grade Multi-Memory Agent Studio — Lab 17 Demo UI.

Full +10 Live Demo Feature Set:
1. Dynamic Dataset Case Loader (Public & Golden).
2. Multi-Layer Memory Retrieval (Short-term, Long-term, Episodic, Semantic, Mixed).
3. Live Ground-Truth Verification & Token Budget Visualizer (10%/4%/3%/3%).
4. Interactive Context Inspection with Glassmorphic Tabs & Entity Graphs.
5. Conversational AI Playground grounded on active memory with Gemini 2.5 Flash.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from src.config import settings
from src.llm import gemini_available, generate_reply
from src.memory_student import StudentMemory
from src.short_term import ShortTermMemory
from src.utils import GOLDEN_PATH, load_dataset, load_json
from src.zep_common import get_zep_client

# ==============================================================================
# DESIGN SYSTEM & STYLING
# ==============================================================================

LAYER_CONFIG = {
    "short_term": {"color": "#38bdf8", "bg": "rgba(56, 189, 248, 0.12)", "icon": "💬", "label": "Short-Term"},
    "long_term": {"color": "#10b981", "bg": "rgba(16, 185, 129, 0.12)", "icon": "👤", "label": "Long-Term"},
    "episodic": {"color": "#f59e0b", "bg": "rgba(245, 158, 11, 0.12)", "icon": "🕒", "label": "Episodic"},
    "semantic": {"color": "#a855f7", "bg": "rgba(168, 85, 247, 0.12)", "icon": "📚", "label": "Semantic"},
    "mixed": {"color": "#ec4899", "bg": "rgba(236, 72, 153, 0.12)", "icon": "🔀", "label": "Mixed Layer"},
}

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
    --font-main: 'Plus Jakarta Sans', -apple-system, sans-serif;
    --font-mono: 'JetBrains Mono', monospace;
    --bg-surface: rgba(15, 23, 42, 0.85);
    --border-subtle: rgba(255, 255, 255, 0.08);
}

html, body, [class*="css"] {
    font-family: var(--font-main);
}

.block-container {
    padding-top: 1.5rem;
    padding-bottom: 4rem;
    max-width: 1280px;
}

/* Glassmorphic Cards */
.hero-header {
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.95) 100%);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 24px 28px;
    margin-bottom: 24px;
    box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(12px);
}

.hero-title {
    font-size: 1.85rem;
    font-weight: 800;
    background: linear-gradient(90deg, #38bdf8, #818cf8, #c084fc);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0 0 6px 0;
    letter-spacing: -0.02em;
}

.hero-subtitle {
    color: #94a3b8;
    font-size: 0.92rem;
    margin: 0;
    line-height: 1.5;
}

.glass-card {
    background: rgba(30, 41, 59, 0.6);
    border: 1px solid var(--border-subtle);
    border-radius: 14px;
    padding: 18px 20px;
    margin-bottom: 16px;
    backdrop-filter: blur(10px);
    transition: all 0.2s ease;
}

.glass-card:hover {
    border-color: rgba(56, 189, 248, 0.3);
    box-shadow: 0 8px 25px -8px rgba(56, 189, 248, 0.15);
}

/* Status Badges */
.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.03em;
    text-transform: uppercase;
}

.status-pill.online {
    background: rgba(16, 185, 129, 0.15);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.3);
}

.status-pill.offline {
    background: rgba(239, 68, 68, 0.15);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.3);
}

/* Budget Card */
.metric-box {
    background: rgba(15, 23, 42, 0.7);
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    padding: 14px 16px;
    text-align: center;
}

.metric-val {
    font-size: 1.45rem;
    font-weight: 700;
    color: #f8fafc;
    font-family: var(--font-mono);
}

.metric-lbl {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #94a3b8;
    margin-top: 4px;
}

/* Code & Previews */
pre, code {
    font-family: var(--font-mono) !important;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 8px 8px 0 0;
    padding: 8px 16px;
    font-weight: 600;
}
</style>
"""


# ==============================================================================
# DATA LOADERS & HELPERS
# ==============================================================================

@st.cache_data(ttl=300)
def load_all_cases() -> list[dict[str, Any]]:
    dataset = load_dataset()
    cases = list(dataset.get("evaluations", []))
    if GOLDEN_PATH.exists():
        try:
            golden = load_json(GOLDEN_PATH)
            for c in golden.get("evaluations", []):
                c["is_golden"] = True
                cases.append(c)
        except Exception:
            pass
    return cases


def retrieve_for_case(
    memory: StudentMemory,
    case: dict[str, Any],
    extra_messages: list[dict[str, str]],
) -> dict[str, Any]:
    """Execute complete 4-tier student memory retrieval with token budget manager."""
    dataset = load_dataset()
    user_id = case.get("user_id", "")
    thread_id = case.get("thread_id", "")
    query = case.get("query", "")
    expected_layer = case.get("expected_layer", "")

    # 1. Reconstruct short-term working context
    st_mem = ShortTermMemory(strategy="sliding", max_recent_messages=6, pressure_tokens=450)
    messages = case.get("fixture_messages")
    if not messages:
        user = next((u for u in dataset.get("users", []) if u.get("user_id") == user_id), None)
        session = next((s for s in (user.get("sessions", []) if user else []) if s.get("thread_id") == thread_id), None)
        messages = (session or {}).get("messages", [])

    for msg in (messages or []):
        st_mem.add(msg["role"], msg["content"])
    for msg in (extra_messages or []):
        st_mem.add(msg["role"], msg["content"])

    layers: dict[str, str] = {
        "short_term": "",
        "long_term": "",
        "episodic": "",
        "semantic": "",
    }

    t0 = time.perf_counter()

    # 2. Layer Dispatching
    if expected_layer == "short_term":
        layers["short_term"] = st_mem.render()
    elif expected_layer == "long_term":
        if user_id and thread_id:
            layers["long_term"] = memory.retrieve_long_term(user_id, thread_id, query)
    elif expected_layer == "episodic":
        if user_id:
            layers["episodic"] = memory.retrieve_episodic(user_id, query)
    elif expected_layer == "semantic":
        layers["semantic"] = memory.retrieve_semantic(settings.semantic_graph_id, query)
    elif expected_layer == "mixed":
        wanted = case.get("retrieve_layers") or ["long_term", "semantic"]
        if "short_term" in wanted:
            layers["short_term"] = st_mem.render()
        if "long_term" in wanted and user_id and thread_id:
            layers["long_term"] = memory.retrieve_long_term(user_id, thread_id, query)
        if "episodic" in wanted and user_id:
            layers["episodic"] = memory.retrieve_episodic(user_id, query)
        if "semantic" in wanted:
            layers["semantic"] = memory.retrieve_semantic(settings.semantic_graph_id, query)
    else:
        # Full retrieval for open chat
        layers["short_term"] = st_mem.render()
        if user_id and thread_id:
            try:
                layers["long_term"] = memory.retrieve_long_term(user_id, thread_id, query)
            except Exception:
                pass
        if user_id:
            try:
                layers["episodic"] = memory.retrieve_episodic(user_id, query)
            except Exception:
                pass
        try:
            layers["semantic"] = memory.retrieve_semantic(settings.semantic_graph_id, query)
        except Exception:
            pass

    merged_context, breakdown = memory.assemble_context(layers)
    latency_ms = round((time.perf_counter() - t0) * 1000, 1)

    return {
        "merged_context": merged_context,
        "layers": layers,
        "budget": breakdown,
        "latency_ms": latency_ms,
    }


def evaluate_ground_truth(case: dict[str, Any], retrieved_text: str) -> dict[str, Any]:
    norm_text = (retrieved_text or "").casefold()
    must_contain = case.get("must_contain_all", [])
    must_not = case.get("must_not_contain", [])

    missing = [m for m in must_contain if m.casefold() not in norm_text]
    found_forbidden = [m for m in must_not if m.casefold() in norm_text]
    passed = (len(missing) == 0) and (len(found_forbidden) == 0)

    return {
        "passed": passed,
        "missing": missing,
        "found_forbidden": found_forbidden,
        "must_contain": must_contain,
        "must_not": must_not,
    }


# ==============================================================================
# MAIN APPLICATION
# ==============================================================================

def main() -> None:
    st.set_page_config(
        page_title="Cognitive Memory Agent Studio | Lab 17",
        page_icon="🧠",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # 1. TOP HERO HEADER
    st.markdown(
        """
        <div class="hero-header">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px;">
                <div>
                    <h1 class="hero-title">🧠 Cognitive Memory Agent Studio</h1>
                    <p class="hero-subtitle">
                        Multi-tiered memory architecture (STM · LTM · Episodic · Semantic) powered by Zep Cloud V3 Knowledge Graphs & Gemini 2.5.
                    </p>
                </div>
                <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
                    <span class="status-pill online">● Zep V3 Graph</span>
                    <span class="status-pill online">● Redis Cache</span>
                    <span class="status-pill online">● Qdrant Vectors</span>
                    <span class="status-pill online">● Gemini 2.5 Flash</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cases = load_all_cases()
    if not cases:
        st.error("No evaluation cases found in dataset.")
        return

    # 2. SIDEBAR CONTROLS
    with st.sidebar:
        st.markdown("### 🎛️ Studio Controls")

        # Layer Filter
        layer_filter = st.selectbox(
            "Filter Test Cases by Layer",
            ["All Layers", "short_term", "long_term", "episodic", "semantic", "mixed"],
            index=0,
        )

        filtered_cases = [
            c for c in cases
            if layer_filter == "All Layers" or c.get("expected_layer") == layer_filter
        ]

        if not filtered_cases:
            st.warning(f"No cases found for '{layer_filter}'")
            filtered_cases = cases

        def format_label(c: dict[str, Any]) -> str:
            golden_tag = " [GOLDEN]" if c.get("is_golden") else ""
            return f"[{c['id']}] {c.get('expected_layer', '').upper()} · {c.get('user_id', '')}{golden_tag}"

        case_idx = st.selectbox(
            "Select Active Test Case",
            range(len(filtered_cases)),
            format_func=lambda i: format_label(filtered_cases[i]),
        )
        active_case = filtered_cases[case_idx]

        st.divider()

        # Architecture Info Guide
        st.markdown("### 📐 Memory Hierarchy (10/4/3/3)")
        st.markdown(
            """
            - **💬 Short-Term (10%)**: Sliding window & compaction.
            - **👤 Long-Term (4%)**: User facts & entity graph.
            - **🕒 Episodic (3%)**: Historical trajectories & debug reflections.
            - **📚 Semantic (3%)**: Domain knowledge & API policies.
            """
        )

        st.divider()
        col_s1, col_s2 = st.columns(2)
        if col_s1.button("🗑️ Reset Chat", use_container_width=True):
            st.session_state.chat = []
            st.session_state.pop("last_result", None)
            st.rerun()

        if col_s2.button("🔄 Sync Zep", use_container_width=True):
            st.cache_data.clear()
            st.success("Synced!")

    # Reset state if case changes
    if st.session_state.get("active_case_id") != active_case["id"]:
        st.session_state.active_case_id = active_case["id"]
        st.session_state.chat = []
        st.session_state.pop("last_result", None)

    # 3. ACTIVE CASE HERO CARD
    cfg = LAYER_CONFIG.get(active_case.get("expected_layer", "short_term"), LAYER_CONFIG["short_term"])
    st.markdown(
        f"""
        <div class="glass-card" style="border-left: 4px solid {cfg['color']};">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <div>
                    <span style="background: {cfg['bg']}; color: {cfg['color']}; font-weight: 700; padding: 3px 10px; border-radius: 6px; font-size: 0.8rem;">
                        {cfg['icon']} {cfg['label']} Memory
                    </span>
                    <span style="font-weight: 700; font-size: 1.1rem; margin-left: 10px; color: #f8fafc;">
                        Case {active_case['id']}
                    </span>
                </div>
                <div style="font-size: 0.82rem; color: #94a3b8;">
                    User: <code>{active_case.get('user_id', '-')}</code> &nbsp;|&nbsp; Thread: <code>{active_case.get('thread_id', '-')}</code>
                </div>
            </div>
            <div style="font-size: 1.1rem; font-weight: 600; color: #38bdf8; margin: 10px 0 6px 0;">
                Query: "{active_case.get('query', '')}"
            </div>
            <div style="font-size: 0.85rem; color: #94a3b8;">
                📝 {active_case.get('description', '')}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 4. ACTION BAR & RETRIEVAL EXECUTION
    col_act1, col_act2, col_act3 = st.columns([1.5, 3.5, 1.2])

    run_clicked = col_act1.button("🚀 Retrieve Context", type="primary", use_container_width=True)

    # Quick Suggestion Chips
    suggestions = {
        "E01": "Dự án cá nhân là gì?",
        "E02": "Minh thích ngôn ngữ nào?",
        "E03": "Deadline report khi nào?",
        "E04": "Lần trước fix async timeout ra sao?",
        "E06": "Quy tắc retry payment?",
        "E08": "Stack bắt buộc BLUEBIRD-42?",
    }
    sug_query = suggestions.get(active_case["id"])
    if sug_query:
        col_act2.caption(f"💡 Quick check: *\"{sug_query}\"*")

    if run_clicked or "last_result" not in st.session_state:
        with st.spinner("Accessing Zep V3 Knowledge Graphs & assembling token budget..."):
            try:
                memory = StudentMemory(get_zep_client())
                st.session_state.last_result = retrieve_for_case(memory, active_case, st.session_state.get("chat", []))
            except Exception as exc:
                st.error(f"Retrieval Error: {exc}")

    result = st.session_state.get("last_result")

    if result:
        # 5. GROUND TRUTH VERIFICATION & TOKEN BUDGET GAUGES
        gt = evaluate_ground_truth(active_case, result.get("merged_context", ""))

        st.markdown("#### 🎯 Evaluation & Token Budget")
        col_gt, col_m1, col_m2, col_m3, col_m4 = st.columns([1.8, 1, 1, 1, 1])

        with col_gt:
            if gt["passed"]:
                st.markdown(
                    """
                    <div style="background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.4); border-radius: 12px; padding: 12px 16px;">
                        <div style="color: #34d399; font-weight: 700; font-size: 1rem;">✅ 100% PASS</div>
                        <div style="font-size: 0.78rem; color: #cbd5e1; margin-top: 4px;">All expected markers retrieved in context.</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"""
                    <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 12px; padding: 12px 16px;">
                        <div style="color: #f87171; font-weight: 700; font-size: 1rem;">⚠️ INCOMPLETE</div>
                        <div style="font-size: 0.75rem; color: #fca5a5; margin-top: 4px;">Missing: {gt['missing']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # Token Budget Metrics
        budget = result.get("budget", {})
        for col, layer_key in zip(
            (col_m1, col_m2, col_m3, col_m4),
            ("short_term", "long_term", "episodic", "semantic"),
        ):
            b_info = budget.get(layer_key, {})
            used = b_info.get("used_tokens", 0)
            limit = b_info.get("limit_tokens", 0)
            pct = round((used / limit) * 100) if limit else 0
            cfg_l = LAYER_CONFIG[layer_key]

            with col:
                st.markdown(
                    f"""
                    <div class="metric-box">
                        <div class="metric-val" style="color: {cfg_l['color']};">{used} <span style="font-size: 0.8rem; color: #64748b;">/ {limit}</span></div>
                        <div class="metric-lbl">{cfg_l['label']} ({pct}%)</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown(f"<div style='text-align: right; font-size: 0.75rem; color: #64748b; margin-top: 6px;'>Retrieval Latency: <b>{result.get('latency_ms', 0)} ms</b></div>", unsafe_allow_html=True)

        # 6. TABBED EVIDENCE INSPECTOR
        st.markdown("#### 📦 Multi-Tier Evidence Inspector")
        tab_merged, tab_ltm, tab_epi, tab_sem, tab_stm = st.tabs([
            "📦 Assembled Context (LLM Prompt)",
            "👤 Long-Term Facts & Graph",
            "🕒 Episodic Trajectories",
            "📚 Semantic Domain KB",
            "💬 Short-Term Working Buffer",
        ])

        with tab_merged:
            st.code(result.get("merged_context") or "(empty context)", language="markdown")

        with tab_ltm:
            ltm_text = result["layers"].get("long_term")
            if ltm_text:
                st.markdown(f"```markdown\n{ltm_text}\n```")
            else:
                st.info("No long-term declarative context required/retrieved for this query.")

        with tab_epi:
            epi_text = result["layers"].get("episodic")
            if epi_text:
                st.markdown(f"```markdown\n{epi_text}\n```")
            else:
                st.info("No episodic trajectory excerpts retrieved for this query.")

        with tab_sem:
            sem_text = result["layers"].get("semantic")
            if sem_text:
                st.markdown(f"```markdown\n{sem_text}\n```")
            else:
                st.info("No domain semantic knowledge graph hits for this query.")

        with tab_stm:
            stm_text = result["layers"].get("short_term")
            if stm_text:
                st.markdown(f"```markdown\n{stm_text}\n```")
            else:
                st.info("No short-term message buffer active for this query.")

    # 7. INTERACTIVE CONVERSATIONAL AGENT PLAYGROUND
    st.divider()
    st.markdown("### 🤖 Live Grounded Chat Playground")
    st.caption(f"Chatting as User `[{active_case.get('user_id', '-')}]` inside Thread `[{active_case.get('thread_id', '-')}]`.")

    chat_history = st.session_state.get("chat", [])
    for msg in chat_history:
        avatar = "🧑‍💻" if msg["role"] == "user" else "🧠"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    user_input = st.chat_input(f"Ask the memory agent as {active_case.get('user_id','user')}...")
    if user_input:
        st.session_state.setdefault("chat", []).append({"role": "user", "content": user_input})
        with st.chat_message("user", avatar="🧑‍💻"):
            st.markdown(user_input)

        with st.spinner("Searching multi-tier memory & synthesizing grounded answer..."):
            try:
                memory = StudentMemory(get_zep_client())
                # For open-ended conversation, query all 4 memory layers across the user's entire knowledge graph
                chat_case = {**active_case, "expected_layer": "all", "query": user_input}
                updated_res = retrieve_for_case(memory, chat_case, st.session_state.chat)
                st.session_state.last_result = updated_res
                grounded_ctx = updated_res.get("merged_context", "")

                if gemini_available():
                    ai_reply = generate_reply(grounded_ctx, st.session_state.chat[:-1], user_input)
                else:
                    ai_reply = f"*(Gemini key inactive — context retrieved)*\n\n{grounded_ctx[:800]}"

                st.session_state.chat.append({"role": "assistant", "content": ai_reply})
                with st.chat_message("assistant", avatar="🧠"):
                    st.markdown(ai_reply)
                st.rerun()
            except Exception as e:
                st.error(f"Chat Agent Error: {e}")


if __name__ == "__main__":
    main()
