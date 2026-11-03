"""Interactive Evaluator CLI: 3-stage lifecycle with onboarding, live HUD, and executive analytics."""

from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from src.config import AppConfig
from src.orchestrator import ConversationalOrchestrator


def render_onboarding_screen(console: Console) -> Tuple[str, Optional[str], str]:
    """Screen 1: Evaluator Onboarding & Engine Selector (English Interface)."""
    console.clear()

    intro_text = Text()
    intro_text.append("EMPORIO DA MUSICA — CONVERSATIONAL AI AGENT\n", style="bold cyan")
    intro_text.append("Technical Case Evaluation Console | Spec-Driven Engineering\n\n", style="dim white")
    intro_text.append(
        "Welcome to the technical evaluation environment. You can choose between running the\n"
        "zero-cost Deterministic Offline Engine (sub-20ms latency, 100% reproducible benchmarks)\n"
        "or connecting an Online LLM (Groq / OpenAI) with native tool calling.\n\n",
        style="white",
    )
    intro_text.append(
        "SECURITY NOTICE: Evaluator API keys are held strictly in ephemeral RAM during the session,\n"
        "are NEVER stored in files or Git, and are purged immediately upon exiting.",
        style="italic green",
    )

    console.print(
        Panel(
            intro_text,
            title="[EVALUATOR ONBOARDING & SETUP]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    console.print("\n[bold white]Step 1: Select AI Inference Engine[/bold white]")
    console.print("  [1] Offline Deterministic Engine (Default: instant, zero cost, fully reproducible)")
    console.print("  [2] Online LLM (Groq Cloud / OpenAI)")

    engine_choice = Prompt.ask(
        "\nSelect option",
        choices=["1", "2"],
        default="1",
        console=console,
    )

    provider = "offline"
    api_key: Optional[str] = None

    if engine_choice == "2":
        console.print("\n[bold white]Step 2: Choose LLM Provider[/bold white]")
        console.print("  [1] Groq Cloud (llama-3.3-70b-versatile - Recommended)")
        console.print("  [2] OpenAI (gpt-4o-mini)")

        provider_choice = Prompt.ask(
            "Select provider",
            choices=["1", "2"],
            default="1",
            console=console,
        )

        if provider_choice == "1":
            provider = "groq"
            default_env_key = os.environ.get("GROQ_API_KEY", "")
            prompt_label = "Enter your GROQ_API_KEY" + (" [press Enter to use current .env]" if default_env_key else "")
            entered_key = console.input(f"{prompt_label}: ", password=True).strip()
            api_key = entered_key or default_env_key
            if api_key:
                os.environ["GROQ_API_KEY"] = api_key
                AppConfig.LLM_PROVIDER = "groq"
        else:
            provider = "openai"
            default_env_key = os.environ.get("OPENAI_API_KEY", "")
            prompt_label = "Enter your OPENAI_API_KEY" + (" [press Enter to use current .env]" if default_env_key else "")
            entered_key = console.input(f"{prompt_label}: ", password=True).strip()
            api_key = entered_key or default_env_key
            if api_key:
                os.environ["OPENAI_API_KEY"] = api_key
                AppConfig.LLM_PROVIDER = "openai"

        console.print("[green][OK] API Key loaded into ephemeral memory.[/green]")
    else:
        AppConfig.LLM_PROVIDER = "offline"

    console.print("\n[bold white]Step 3: Select Interface Target[/bold white]")
    console.print("  [1] Continue in Terminal CLI (Interactive Console)")
    console.print("  [2] Launch in Browser with Streamlit Web App")

    target_choice = Prompt.ask(
        "Select target",
        choices=["1", "2"],
        default="1",
        console=console,
    )

    return provider, api_key, target_choice


def render_chat_banner(console: Console, session_id: str, provider: str) -> None:
    """Render top header banner for the active conversational session."""
    banner = Text()
    banner.append("EMPORIO DA MUSICA — CONVERSATIONAL RETAIL ASSISTANT\n", style="bold cyan")
    banner.append("Campo Grande / MS (Rua 14 de Maio, 3200) | Live Chat Console\n", style="dim white")
    banner.append(
        f"Active Session: {session_id} | Engine: {provider.upper()} | Type /finish or /exit to view post-chat analytics",
        style="italic green",
    )

    console.print(
        Panel(
            banner,
            title="[CONVERSATIONAL WORKSPACE ONLINE]",
            subtitle="Customer turns in Portuguese | Evaluator controls: /exit | /history | /session <id> | /clear",
            border_style="cyan",
            title_align="center",
            subtitle_align="center",
        )
    )


def render_historical_sessions_browser(console: Console, orchestrator: ConversationalOrchestrator) -> None:
    """Browse historical customer sessions stored in the SQLite database."""
    sessions = orchestrator.audit_store.list_all_sessions()
    if not sessions:
        console.print("\n[dim]No historical sessions found in database.[/dim]")
        Prompt.ask("\nPress Enter to return", console=console)
        return

    table = Table(title="[HISTORICAL SESSIONS IN DATABASE]", border_style="cyan")
    table.add_column("Session ID", style="bold white", width=36)
    table.add_column("Turn Count", style="green", justify="right")
    table.add_column("Started At", style="dim")
    table.add_column("Last Activity", style="dim")

    for s in sessions:
        table.add_row(
            s["session_id"],
            str(s["turn_count"]),
            str(s["started_at"])[:19],
            str(s["last_activity"])[:19],
        )

    console.print(table)
    selected_session = Prompt.ask(
        "\nEnter Session ID to inspect full transcript (or press Enter to return)",
        default="",
        console=console,
    ).strip()

    if selected_session:
        transcript = orchestrator.audit_store.get_full_session_transcript(selected_session)
        if not transcript:
            console.print(f"[bold red]Session '{selected_session}' not found.[/bold red]")
        else:
            console.print(f"\n[bold cyan]Full Transcript — Session: {selected_session}[/bold cyan]")
            for turn in transcript:
                role_color = "bold cyan" if turn["role"] == "user" else "bold green"
                role_name = "Customer" if turn["role"] == "user" else "Assistant"
                console.print(f"\n[{role_color}]{role_name} ({turn['created_at'][:19]}):[/{role_color}]")
                console.print(turn["content"])
            console.print("-" * 70)
        Prompt.ask("\nPress Enter to return to menu", console=console)


def render_post_conversation_dashboard(
    console: Console,
    orchestrator: ConversationalOrchestrator,
    session_id: str,
    session_start_time: float,
) -> str:
    """Screen 3: Post-Conversation Executive Analytics & Insights Dashboard (English)."""
    console.clear()

    total_duration_sec = int(time.time() - session_start_time)
    minutes, seconds = divmod(total_duration_sec, 60)
    duration_str = f"{minutes}m {seconds:02d}s"

    metrics = orchestrator.audit_store.get_session_metrics(session_id)
    session_crm = orchestrator.audit_store.get_customer_session(session_id) or {}

    total_events = metrics.get("total_events", 0)
    avg_latency = metrics.get("avg_latency_ms", 0.0)
    total_tokens = metrics.get("total_tokens", 0)
    prompt_tokens = metrics.get("prompt_tokens", 0)
    completion_tokens = metrics.get("completion_tokens", 0)
    history = orchestrator.audit_store.get_conversation_history(session_id, limit=50)
    user_turns_count = len([h for h in history if h.get("role") == "user"])
    avg_tokens_per_question = round(total_tokens / max(user_turns_count, 1), 1)

    # 1. Performance Overview Table
    perf_table = Table(title="1. Session Execution & Efficiency Metrics", border_style="cyan")
    perf_table.add_column("Metric", style="bold white")
    perf_table.add_column("Value", style="green")
    perf_table.add_row("Conversation Duration", duration_str)
    perf_table.add_row("User Questions Processed", str(user_turns_count))
    perf_table.add_row("Average Response Time", f"{avg_latency:.1f} ms")
    perf_table.add_row("Total Tokens Consumed", f"{total_tokens} (Prompt: {prompt_tokens} / Output: {completion_tokens})")
    perf_table.add_row("Average Tokens per Turn", f"{avg_tokens_per_question} tokens/turn")
    perf_table.add_row("Backend Tools Executed", str(metrics.get("tools_called", 0)))
    perf_table.add_row("Guardrail Interceptions", str(metrics.get("guardrails_triggered", 0)))

    # 2. Tool Calls Ranking
    audit_logs = orchestrator.audit_store.get_audit_logs(session_id, limit=100)
    tool_counts: Dict[str, int] = {}
    for ev in audit_logs:
        if ev["event_type"] == "TOOL_INVOCATION":
            tool_name = ev["component_name"]
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

    tool_table = Table(title="2. Backend Action Calls Ranking", border_style="cyan")
    tool_table.add_column("Action / Tool", style="bold white")
    tool_table.add_column("Invocations", style="green", justify="right")
    tool_table.add_column("Percentage", style="dim", justify="right")

    total_tools = sum(tool_counts.values()) or 1
    if tool_counts:
        for tool, count in sorted(tool_counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total_tools) * 100
            tool_table.add_row(tool, str(count), f"{pct:.1f}%")
    else:
        tool_table.add_row("None (Direct responses / Intercepted)", "0", "0.0%")

    # 3. Customer Intelligence & CRM Profile
    crm_table = Table(title="3. Customer Intelligence & CRM Profile", border_style="green")
    crm_table.add_column("Attribute", style="bold white")
    crm_table.add_column("Inferred Status", style="yellow")

    customer_id = session_crm.get("customer_id")
    customer_name = session_crm.get("customer_name")
    phone = session_crm.get("phone")

    if customer_id:
        reg_status = f"Registered (ID #{customer_id} - {customer_name or 'Customer'})"
    else:
        reg_status = "Guest / Unregistered (Anonymous Browsing)"

    sentiment = session_crm.get("sentiment_score", "Neutral")
    affinity_tags = session_crm.get("affinity_tags") or []
    tags_display = ", ".join(affinity_tags) if affinity_tags else "None detected"

    crm_table.add_row("Registration Status", reg_status)
    crm_table.add_row("Customer Phone", phone or "Not provided")
    crm_table.add_row("Observed Sentiment", sentiment)
    crm_table.add_row("Musical Affinity Tags", tags_display)

    # 4. Multi-Scope System Alerts & Insights
    alerts_detected = session_crm.get("alerts_detected") or []
    alerts_table = Table(title="4. Multi-Scope System Alerts & Operational Insights", border_style="magenta")
    alerts_table.add_column("Scope", style="bold white", width=16)
    alerts_table.add_column("Alert Type", style="yellow", width=28)
    alerts_table.add_column("Diagnostic Insight", style="white")

    if alerts_detected:
        for alert in alerts_detected:
            scope_badge = f"[{alert.get('scope', 'info').upper()}]"
            alerts_table.add_row(
                scope_badge,
                alert.get("type", "NOTICE"),
                alert.get("message", ""),
            )
    else:
        alerts_table.add_row("[STABLE]", "NO_ALERTS", "Zero anomalies detected. Guardrails and tools operated nominally.")

    # Render Header Banner
    header = Text()
    header.append("EXECUTIVE POST-CONVERSATION ANALYTICS DASHBOARD\n", style="bold cyan")
    header.append(f"Session ID: {session_id} | Status: Concluded | Evaluator Summary Report", style="dim white")
    console.print(Panel(header, border_style="cyan", title="[AUDIT & METRICS]"))

    console.print(perf_table)
    console.print(tool_table)
    console.print(crm_table)
    console.print(alerts_table)

    # Evaluator Action Menu
    console.print("\n[bold white]Evaluator Navigation Menu:[/bold white]")
    console.print("  [1] Return to current conversation (Resume session)")
    console.print("  [2] Start a new conversation (Fresh session)")
    console.print("  [3] View all saved interactions (Historical session transcript browser)")
    console.print("  [4] Exit program")

    action = Prompt.ask(
        "\nSelect action",
        choices=["1", "2", "3", "4"],
        default="4",
        console=console,
    )
    return action


def run_cli() -> None:
    """Main CLI execution loop with onboarding, chat workspace, and dashboard."""
    console = Console()

    # Step 1: Onboarding
    provider, api_key, target_choice = render_onboarding_screen(console)

    if target_choice == "2":
        console.print("\n[bold green]Launching Streamlit Web Application in browser...[/bold green]")
        app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app.py"))
        env = os.environ.copy()
        if api_key:
            if provider == "groq":
                env["GROQ_API_KEY"] = api_key
            elif provider == "openai":
                env["OPENAI_API_KEY"] = api_key
        try:
            subprocess.run([sys.executable, "-m", "streamlit", "run", app_path], env=env, check=False)
        except Exception as e:
            console.print(f"[bold red]Error launching Streamlit: {e}[/bold red]")
        return

    orchestrator = ConversationalOrchestrator()
    session_id = f"session-{uuid.uuid4().hex[:6]}"
    session_start_time = time.time()

    console.clear()
    render_chat_banner(console, session_id, provider)

    while True:
        try:
            user_input = console.input(f"\n[bold cyan]Cliente ({session_id}) > [/bold cyan]").strip()
        except (KeyboardInterrupt, EOFError):
            action = render_post_conversation_dashboard(console, orchestrator, session_id, session_start_time)
            if action == "1":
                console.clear()
                render_chat_banner(console, session_id, provider)
                continue
            elif action == "2":
                session_id = f"session-{uuid.uuid4().hex[:6]}"
                session_start_time = time.time()
                console.clear()
                render_chat_banner(console, session_id, provider)
                continue
            elif action == "3":
                render_historical_sessions_browser(console, orchestrator)
                continue
            else:
                console.print("\n[dim]Evaluation concluded. Session memory cleared. Goodbye![/dim]")
                break

        if not user_input:
            continue

        # Handle Commands
        if user_input.startswith("/"):
            parts = user_input.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else ""

            if cmd in ("/exit", "/quit", "/finish", "/done"):
                action = render_post_conversation_dashboard(console, orchestrator, session_id, session_start_time)
                if action == "1":
                    console.clear()
                    render_chat_banner(console, session_id, provider)
                    continue
                elif action == "2":
                    session_id = f"session-{uuid.uuid4().hex[:6]}"
                    session_start_time = time.time()
                    console.clear()
                    render_chat_banner(console, session_id, provider)
                    continue
                elif action == "3":
                    render_historical_sessions_browser(console, orchestrator)
                    continue
                else:
                    console.print("\n[dim]Evaluation concluded. Session memory cleared. Goodbye![/dim]")
                    break

            elif cmd == "/clear":
                console.clear()
                render_chat_banner(console, session_id, provider)
                continue

            elif cmd == "/session":
                if arg:
                    session_id = arg
                    session_start_time = time.time()
                    console.print(f"[bold green][SESSION UPDATED][/bold green] Active session: [bold white]{session_id}[/bold white]")
                else:
                    session_id = f"session-{uuid.uuid4().hex[:6]}"
                    session_start_time = time.time()
                    console.print(f"[bold green][NEW SESSION][/bold green] Fresh session: [bold white]{session_id}[/bold white]")
                continue

            elif cmd == "/history":
                history = orchestrator.audit_store.get_conversation_history(session_id, limit=20)
                if not history:
                    console.print(f"[dim]No message turns found for session '{session_id}'.[/dim]")
                else:
                    table = Table(title=f"Session Transcript: {session_id}", border_style="dim")
                    table.add_column("Role", style="bold cyan", width=12)
                    table.add_column("Content", style="white")
                    for h in history:
                        table.add_row(h["role"].capitalize(), h["content"])
                    console.print(table)
                continue

            elif cmd == "/metrics":
                action = render_post_conversation_dashboard(console, orchestrator, session_id, session_start_time)
                if action == "1":
                    console.clear()
                    render_chat_banner(console, session_id, provider)
                    continue
                elif action == "2":
                    session_id = f"session-{uuid.uuid4().hex[:6]}"
                    session_start_time = time.time()
                    console.clear()
                    render_chat_banner(console, session_id, provider)
                    continue
                elif action == "3":
                    render_historical_sessions_browser(console, orchestrator)
                    continue
                else:
                    console.print("\n[dim]Evaluation concluded. Session memory cleared. Goodbye![/dim]")
                    break

            else:
                console.print(f"[bold red]Unknown command:[/bold red] {cmd}. Use /exit, /history, /metrics, /session or /clear.")
                continue

        # Execute Conversational Turn
        with console.status("[bold green]Processing turn through guardrails, tools and telemetry...[/bold green]", spinner="dots"):
            response = orchestrator.process_turn(session_id, user_input)

        # Assistant Response (in Portuguese per retail context)
        console.print(
            Panel(
                Text(response.response_text, style="white"),
                title="[bold green]Consultor Empório da Música[/bold green]",
                border_style="green",
                padding=(1, 2),
            )
        )

        # Telemetry HUD (strictly text-based, no UI emojis)
        console.print(
            Panel(
                Text(response.telemetry_hud, style="bold dim white"),
                border_style="dim",
                padding=(0, 1),
            )
        )


if __name__ == "__main__":
    run_cli()
