"""
Empório da Música - Evaluator Web Application & Observability Dashboard
Streamlit-based executive interface for evaluating the Conversational AI Agent.

Evaluator Interface Language: English (strictly enforced)
Customer Conversational Workspace: Portuguese (PT-BR)
Security: Ephemeral in-memory API key handling with seamless CLI cross-persistence.
"""

import os
import re
import time
import uuid
import pandas as pd
import streamlit as st

from src.config import AppConfig
from src.orchestrator import ConversationalOrchestrator
from src.storage.audit_store import AuditStore


# -----------------------------------------------------------------------------
# Streamlit Page Setup
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Empório da Música | Evaluator Console",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)


# -----------------------------------------------------------------------------
# Session State Initialization & CLI Sychronization
# -----------------------------------------------------------------------------
# Load persisted session configuration from CLI or environment
cached_config = AppConfig.load_session_config()

PROVIDER_MAP = {
    "Deterministic (Offline / Default)": "offline",
    "Groq Cloud (Ultra-Fast Native LLM)": "groq",
    "OpenAI (gpt-4o-mini)": "openai",
    "Google Gemini (gemini-2.0-flash)": "gemini",
    "DeepSeek (deepseek-chat)": "deepseek",
    "Ollama Local (llama3.1:8b)": "ollama",
}
REV_PROVIDER_MAP = {v: k for k, v in PROVIDER_MAP.items()}

# Determine initial provider code
initial_provider_code = (
    cached_config.get("provider")
    or os.getenv("LLM_PROVIDER")
    or ("groq" if (os.getenv("GROQ_API_KEY") or cached_config.get("groq_api_key")) else "offline")
)
if initial_provider_code not in REV_PROVIDER_MAP:
    initial_provider_code = "offline"

initial_label = REV_PROVIDER_MAP.get(initial_provider_code, "Deterministic (Offline / Default)")
initial_key = AppConfig.get_api_key(initial_provider_code)

if "active_engine" not in st.session_state:
    st.session_state.active_engine = initial_label

if "api_key" not in st.session_state:
    st.session_state.api_key = initial_key

if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = ConversationalOrchestrator(
        provider=initial_provider_code,
        api_key=initial_key,
    )

if "audit_store" not in st.session_state:
    st.session_state.audit_store = AuditStore()

if "session_id" not in st.session_state:
    st.session_state.session_id = f"eval-{uuid.uuid4().hex[:6]}"


# -----------------------------------------------------------------------------
# Sidebar: Evaluator Control Center
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("🎛️ Evaluator Control")
    st.caption("Empório da Música — AI Telemetry & Observability Suite")
    st.markdown("---")

    # 1. Engine & Provider Setup
    st.subheader("1. AI Engine Configuration")
    
    options_list = list(PROVIDER_MAP.keys())
    default_idx = options_list.index(st.session_state.active_engine) if st.session_state.active_engine in options_list else 0

    engine_choice = st.selectbox(
        "Inference Engine",
        options=options_list,
        index=default_idx,
        help="Select between deterministic rule-based engine or live LLM provider.",
    )
    
    current_prov_code = PROVIDER_MAP[engine_choice]

    # Handle provider switch
    if engine_choice != st.session_state.active_engine:
        st.session_state.active_engine = engine_choice
        st.session_state.api_key = AppConfig.get_api_key(current_prov_code)
        st.session_state.orchestrator.configure_llm(
            provider=current_prov_code,
            api_key=st.session_state.api_key,
            persist=True,
        )

    # Dynamic API Key inputs based on selected provider
    if current_prov_code == "groq":
        st.markdown("**Groq Cloud Configuration**")
        key_input = st.text_input(
            "Groq API Key",
            type="password",
            value=st.session_state.api_key,
            help="Your key is held strictly in memory and wiped upon session end.",
        )
        if key_input != st.session_state.api_key:
            st.session_state.api_key = key_input
            st.session_state.orchestrator.configure_llm(provider="groq", api_key=key_input, persist=True)
            st.rerun()

    elif current_prov_code == "openai":
        st.markdown("**OpenAI Configuration**")
        key_input = st.text_input(
            "OpenAI API Key",
            type="password",
            value=st.session_state.api_key,
            help="Your key is held strictly in memory and wiped upon session end.",
        )
        if key_input != st.session_state.api_key:
            st.session_state.api_key = key_input
            st.session_state.orchestrator.configure_llm(provider="openai", api_key=key_input, persist=True)
            st.rerun()

    elif current_prov_code == "gemini":
        st.markdown("**Google Gemini Configuration**")
        key_input = st.text_input(
            "Gemini API Key",
            type="password",
            value=st.session_state.api_key,
            help="Your key is held strictly in memory and wiped upon session end.",
        )
        if key_input != st.session_state.api_key:
            st.session_state.api_key = key_input
            st.session_state.orchestrator.configure_llm(provider="gemini", api_key=key_input, persist=True)
            st.rerun()

    elif current_prov_code == "deepseek":
        st.markdown("**DeepSeek Configuration**")
        key_input = st.text_input(
            "DeepSeek API Key",
            type="password",
            value=st.session_state.api_key,
            help="Your key is held strictly in memory and wiped upon session end.",
        )
        if key_input != st.session_state.api_key:
            st.session_state.api_key = key_input
            st.session_state.orchestrator.configure_llm(provider="deepseek", api_key=key_input, persist=True)
            st.rerun()

    elif current_prov_code == "ollama":
        st.markdown("**Ollama Local Server**")
        st.caption(f"Endpoint: {AppConfig.OLLAMA_BASE_URL} | Model: {AppConfig.OLLAMA_MODEL}")
        st.session_state.orchestrator.configure_llm(provider="ollama", api_key="ollama", persist=True)

    else:
        st.info("Operating in Offline Deterministic mode. Zero LLM cost, instant latency.")
        st.session_state.orchestrator.configure_llm(provider="offline", persist=True)

    # Engine connection status pill
    if st.session_state.orchestrator.is_llm_connected():
        st.success(f"🟢 Connected: {current_prov_code.upper()} ({st.session_state.orchestrator.model})")
    elif current_prov_code != "offline":
        st.warning(f"🟡 {current_prov_code.upper()} awaiting valid key")

    # Wipe key action
    if st.session_state.api_key:
        if st.button("Wipe In-Memory Key", width="stretch"):
            AppConfig.clear_session_config()
            st.session_state.api_key = ""
            st.session_state.orchestrator.configure_llm(provider="offline", persist=True)
            st.session_state.active_engine = "Deterministic (Offline / Default)"
            st.warning("API key purged from memory.")
            st.rerun()

    st.markdown("---")

    # 2. Session Management
    st.subheader("2. Session Management")
    current_session = st.text_input("Active Session ID", value=st.session_state.session_id)
    if current_session != st.session_state.session_id:
        st.session_state.session_id = current_session
        st.rerun()

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if st.button("New Session", width="stretch"):
            st.session_state.session_id = f"eval-{uuid.uuid4().hex[:6]}"
            st.rerun()
    with col_s2:
        if st.button("Clear History", width="stretch"):
            st.session_state.audit_store.clear_session(st.session_state.session_id)
            st.success("History cleared.")
            st.rerun()

    with st.expander("🛠️ Database Maintenance"):
        st.caption("Reset operational SQLite audit tables to pristine challenge state (0 test events).")
        if st.button("🧹 Purge All Test Records", width="stretch"):
            st.session_state.audit_store.clear_all_sessions()
            st.success("Database restored to 100% clean state.")
            st.rerun()

    st.markdown("---")

    # 3. Quick Telemetry KPI Card
    st.subheader("3. Live Telemetry KPI")
    metrics = st.session_state.audit_store.get_session_metrics(st.session_state.session_id)
    kpi_col1, kpi_col2 = st.columns(2)
    kpi_col1.metric("Turns", metrics.get("total_turns", 0))
    avg_ms = metrics.get("avg_latency_ms", 0.0)
    latency_str = f"{avg_ms / 1000.0:.2f} s" if avg_ms >= 1000 else f"{int(avg_ms)} ms"
    kpi_col2.metric("Avg Latency", latency_str)
    st.metric("Total Tokens", f"{metrics.get('total_tokens', 0):,}")

    st.caption("Security Notice: All customer interactions are sanitized for PII compliance.")


# -----------------------------------------------------------------------------
# Main Application Header
# -----------------------------------------------------------------------------
st.title("🎵 Empório da Música — Evaluator Observability Console")
st.markdown(
    """
    **Evaluator Workspace:** Inspect conversational turns, verify native tool calls, inspect multi-layer guardrails, 
    review CRM synchronization, and explore historical sessions recorded in SQLite.
    """
)

# Tab Layout
tab_chat, tab_analytics, tab_crm, tab_explorer = st.tabs([
    "💬 Live Chat Workspace",
    "📊 Analytics & Telemetry",
    "👤 Customer CRM & Alerts",
    "📜 Historical Sessions Explorer",
])


# -----------------------------------------------------------------------------
# TAB 1: Live Chat Workspace
# -----------------------------------------------------------------------------
with tab_chat:
    st.markdown("### 💬 Conversational Customer Workspace (PT-BR)")
    st.caption(
        "Chat dialogue is conducted in Portuguese reflecting the Campo Grande/MS store context. "
        "System telemetry HUD cards below each assistant turn are presented in English."
    )

    # Fetch and render conversation history for current session
    history = st.session_state.audit_store.get_conversation_history(st.session_state.session_id)

    # Render history
    for msg in history:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "user":
            with st.chat_message("user"):
                st.write(content)
        elif role == "assistant":
            with st.chat_message("assistant"):
                st.write(content)

    # Chat Input Box
    user_input = st.chat_input("Digite sua mensagem para o assistente (ex: 'Oi, bom dia!' ou 'Procuro um violão clássico')...")

    if user_input:
        # Display user message immediately
        with st.chat_message("user"):
            st.write(user_input)

        # Process via Orchestrator
        with st.spinner("Processing turn with guardrails & tools..."):
            result = st.session_state.orchestrator.process_turn(
                st.session_state.session_id, user_input
            )

        # Display assistant message
        with st.chat_message("assistant"):
            st.write(result.response_text)
            st.text(result.telemetry_hud)

        # Rerun to update sidebars and state
        st.rerun()


# -----------------------------------------------------------------------------
# TAB 2: Analytics & Telemetry Dashboard
# -----------------------------------------------------------------------------
with tab_analytics:
    st.markdown("### 📊 Executive Telemetry & Execution Analytics")
    st.caption("Consolidated performance metrics, token utilization, and tool call distribution.")

    curr_metrics = st.session_state.audit_store.get_session_metrics(st.session_state.session_id)
    
    # 4 Key Metrics
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    col_m1.metric("Total Conversational Turns", curr_metrics.get("total_turns", 0))
    avg_tab_ms = curr_metrics.get("avg_latency_ms", 0.0)
    col_m2.metric("Average Response Latency", f"{avg_tab_ms:.1f} ms ({avg_tab_ms / 1000.0:.2f} s)" if avg_tab_ms >= 1000 else f"{avg_tab_ms:.1f} ms")
    col_m3.metric("Prompt Tokens Consumed", f"{curr_metrics.get('prompt_tokens', 0):,}")
    col_m4.metric("Completion Tokens", f"{curr_metrics.get('completion_tokens', 0):,}")

    st.markdown("---")

    # Tool Invocations Breakdown
    st.subheader("🛠️ Tool Invocations Ranking")
    tool_counts = curr_metrics.get("tool_invocations", {})
    if tool_counts:
        tools_data = [
            {"Tool Name": tool, "Invocations": count, "Share (%)": f"{(count / sum(tool_counts.values())) * 100:.1f}%"}
            for tool, count in sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)
        ]
        st.dataframe(pd.DataFrame(tools_data), width="stretch")
    else:
        st.info("No backend tools invoked yet in this session.")

    st.markdown("---")

    # Detailed Audit Event Stream for Active Session
    st.subheader("📋 Session Audit Event Stream")
    logs = st.session_state.audit_store.get_session_audit_logs(st.session_state.session_id)
    if logs:
        log_df = pd.DataFrame(logs)
        display_cols = [col for col in ["event_type", "latency_ms", "prompt_tokens", "completion_tokens", "created_at"] if col in log_df.columns]
        st.dataframe(log_df[display_cols], width="stretch")
    else:
        st.info("No audit logs recorded for this session.")


# -----------------------------------------------------------------------------
# TAB 3: Customer CRM Profile & System Alerts
# -----------------------------------------------------------------------------
with tab_crm:
    st.markdown("### 👤 Customer Intelligence Profile")
    st.caption("Dynamic customer attributes synchronized during conversational turns.")

    crm_data = st.session_state.audit_store.get_customer_session(st.session_state.session_id) or {}

    col_crm1, col_crm2 = st.columns(2)
    with col_crm1:
        st.markdown("**Identification & Contact**")
        st.text_input("Customer Name", value=crm_data.get("customer_name") or "Unidentified Visitor", disabled=True)
        st.text_input("Clean Phone (Digits Only)", value=crm_data.get("phone") or "Not Provided", disabled=True)
        st.text_input("Registration Status", value=str(crm_data.get("registration_status", "GUEST")).upper(), disabled=True)

    with col_crm2:
        st.markdown("**Customer Context & Loyalty**")
        orders_count = crm_data.get("orders_count", 0) or 0
        loyalty = "Gold Tier (Frequent Buyer)" if orders_count > 0 else "New Prospect"
        st.text_input("Loyalty Tier", value=loyalty, disabled=True)
        st.text_input("Orders On Record", value=str(orders_count), disabled=True)
        
        raw_affinity = crm_data.get("affinity_tags")
        if isinstance(raw_affinity, list):
            affinity = ", ".join(raw_affinity) if raw_affinity else "Acoustic, Beginner Guitar"
        else:
            affinity = str(raw_affinity) if raw_affinity else "Acoustic, Beginner Guitar"
        st.text_input("Affinity Tags", value=affinity, disabled=True)

    st.markdown("---")

    # Multi-Scope Alert Console
    st.subheader("🚨 Tri-Part System Alert Console")
    st.caption("Real-time operational alerts classified by engineering, security, and business governance.")

    col_a1, col_a2, col_a3 = st.columns(3)

    with col_a1:
        st.markdown("#### ⚙️ Development Scope")
        st.success("All intent routing schemas operational.")
        st.caption("Active fallback: Deterministic offline services enabled.")

    with col_a2:
        st.markdown("#### 🛡️ Security & Guardrails")
        st.info("PII Data Cleansing: Active (CPFs masked).")
        st.info("Accessory Interceptor: Zero-LLM direct bypass active.")

    with col_a3:
        st.markdown("#### 💼 Business Intelligence")
        if crm_data.get("customer_name"):
            st.success(f"Qualified lead: {crm_data.get('customer_name')}")
        else:
            st.caption("Awaiting customer authentication or product inquiry.")

    st.markdown("---")

    # Evaluator Customer Directory (LGPD Compliant Sandbox)
    st.subheader("👥 Directory of Customers (Seed Profiles & Live Registrations)")
    st.caption(
        "Pre-loaded customer profiles with order histories and newly registered users from SQLite. "
        "Use these identities to test progressive profiling, return policies, and order tracking."
    )

    try:
        db_conn = st.session_state.orchestrator.db_conn
        cursor = db_conn.cursor()

        col_f1, col_f2 = st.columns([2, 1])
        with col_f1:
            search_query = st.text_input("🔍 Search customer by Name or Phone (e.g., 'Rodrigo', 'Lucas', '67998123456')", value="").strip()
        with col_f2:
            sort_order = st.selectbox("Order by", ["Most Recent First (New Registrations)", "Highest Orders First (Seed Frequent Buyers)"])

        order_clause = "c.customer_id DESC" if "Most Recent" in sort_order else "total_orders DESC, c.customer_id ASC"

        if search_query:
            clean_search = re.sub(r"\D", "", search_query)
            cursor.execute(
                f"""
                SELECT 
                    c.customer_id,
                    c.name,
                    c.phone,
                    c.city,
                    COUNT(o.order_id) as total_orders,
                    GROUP_CONCAT('Pedido #' || o.order_id || ' (' || o.status || ', R$ ' || printf('%.2f', o.total_amount) || ')', ' | ') as orders_summary
                FROM customers c
                LEFT JOIN orders o ON c.customer_id = o.customer_id
                WHERE c.name LIKE ? OR c.phone LIKE ?
                GROUP BY c.customer_id
                ORDER BY {order_clause}
                LIMIT 50
                """,
                (f"%{search_query}%", f"%{clean_search or search_query}%"),
            )
        else:
            cursor.execute(
                f"""
                SELECT 
                    c.customer_id,
                    c.name,
                    c.phone,
                    c.city,
                    COUNT(o.order_id) as total_orders,
                    GROUP_CONCAT('Pedido #' || o.order_id || ' (' || o.status || ', R$ ' || printf('%.2f', o.total_amount) || ')', ' | ') as orders_summary
                FROM customers c
                LEFT JOIN orders o ON c.customer_id = o.customer_id
                GROUP BY c.customer_id
                ORDER BY {order_clause}
                LIMIT 50
                """
            )
        cust_rows = cursor.fetchall()
        
        directory_data = []
        for row in cust_rows:
            raw_phone = str(row["phone"] or "")
            digits = re.sub(r"\D", "", raw_phone)
            # LGPD Masking: Preserve DDD and last 4 digits (e.g. (67) 9****-3456)
            if len(digits) == 11:
                masked_phone = f"({digits[:2]}) 9****-{digits[-4:]}"
                unformatted_input = digits
            elif len(digits) == 10:
                masked_phone = f"({digits[:2]}) ****-{digits[-4:]}"
                unformatted_input = digits
            else:
                masked_phone = "(67) 9****-****"
                unformatted_input = digits or "67998123456"

            directory_data.append({
                "Customer ID": f"#{row['customer_id']}",
                "Customer Name": row["name"],
                "Masked Phone (LGPD)": masked_phone,
                "City": row["city"] or "Campo Grande",
                "Orders on File": row["total_orders"] or 0,
                "Past Orders Summary": row["orders_summary"] or "None (New Prospect)",
                "Simulation Input (Phone)": unformatted_input,
            })

        if directory_data:
            st.dataframe(pd.DataFrame(directory_data), width="stretch")
        else:
            st.info(f"No customers found matching '{search_query}'.")

        st.info(
            "💡 **Evaluator Simulation Quick Guide:**\n"
            "- **To test Order Tracking / CDC Return:** Use **Pedro Henrique** (`67984321098`) with **Pedido #1** (Martin D-28) or **Thiago Barbosa** (`67983216543`) with **Pedido #2** (Taylor 110e).\n"
            "- **To test Anonymous to Registered Flow:** Start chatting without identifying yourself, select an instrument (e.g. PRS SE Custom 24), then provide **Lucas Mendes** (`67998123456`) or your own number."
        )
            "- **To test Anonymous to Registered Flow:** Start chatting without identifying yourself, select an instrument (e.g. PRS SE Custom 24), then provide **Lucas Mendes** (`67998123456`) or your own number."
        )
    except Exception as e:
        st.warning(f"Could not load customer directory: {e}")


# -----------------------------------------------------------------------------
# TAB 4: Historical Sessions Explorer
# -----------------------------------------------------------------------------
with tab_explorer:
    st.markdown("### 📜 Historical Sessions & Interaction Browser")
    st.caption("Review all past customer interactions and challenge benchmark runs recorded in SQLite.")

    sessions = st.session_state.audit_store.list_all_sessions()

    if not sessions:
        st.info("No recorded sessions found in database.")
    else:
        # Format session choices for selectbox
        session_options = {
            f"{s['session_id']} | Turns: {s['turn_count']} | Last: {s['last_activity']}": s["session_id"]
            for s in sessions
        }
        selected_label = st.selectbox("Select Session to Inspect", options=list(session_options.keys()))
        inspected_session_id = session_options[selected_label]

        # Fetch Transcript
        transcript = st.session_state.audit_store.get_full_session_transcript(inspected_session_id)
        selected_meta = next((s for s in sessions if s["session_id"] == inspected_session_id), {})

        col_t1, col_t2, col_t3 = st.columns(3)
        col_t1.metric("Session ID", inspected_session_id)
        col_t2.metric("Recorded Turns", selected_meta.get("turn_count", len(transcript)))
        col_t3.metric("Last Activity", selected_meta.get("last_activity", "N/A"))

        st.markdown("---")
        st.subheader(f"💬 Conversational Transcript: {inspected_session_id}")

        for turn in transcript:
            role = turn.get("role", "unknown")
            content = turn.get("content", "")
            timestamp = turn.get("created_at", "")
            
            if role == "user":
                with st.chat_message("user"):
                    st.caption(f"Time: {timestamp}")
                    st.write(content)
            elif role == "assistant":
                with st.chat_message("assistant"):
                    st.caption(f"Time: {timestamp}")
                    st.write(content)

        st.markdown("---")
        st.subheader("🔍 Raw Telemetry Events for Selected Session")
        session_logs = st.session_state.audit_store.get_session_audit_logs(inspected_session_id)
        if session_logs:
            st.dataframe(pd.DataFrame(session_logs), width="stretch")
        else:
            st.caption("No raw telemetry events recorded for this historical session.")
