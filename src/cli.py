"""Interactive CLI: Rich terminal interface with professional Telemetry HUD and session management."""

from __future__ import annotations

import os
import sys
import uuid
from typing import Optional

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.config import AppConfig
from src.orchestrator import ConversationalOrchestrator


def render_banner(console: Console, session_id: str) -> None:
    """Render executive top header banner without emojis in UI elements."""
    banner_text = Text()
    banner_text.append("EMPORIO DA MUSICA — CONVERSATIONAL RETAIL ASSISTANT\n", style="bold cyan")
    banner_text.append("Campo Grande / MS (Rua 14 de Maio, 3200) | Artefact Technical Case\n", style="dim white")
    banner_text.append(f"Active Session: {session_id} | Provider: {AppConfig.LLM_PROVIDER.upper()} | Model: {AppConfig.GROQ_MODEL}", style="italic green")

    console.print(
        Panel(
            banner_text,
            border_style="cyan",
            title="[SYSTEM ONLINE]",
            subtitle="Commands: /session <id> | /history | /metrics | /clear | /exit",
            title_align="center",
            subtitle_align="center",
        )
    )


def run_cli() -> None:
    """Start interactive session loop."""
    console = Console()
    orchestrator = ConversationalOrchestrator()

    # Default session with random suffix for complete isolation
    session_id = f"session-{uuid.uuid4().hex[:6]}"
    render_banner(console, session_id)

    while True:
        try:
            user_input = console.input(f"\n[bold cyan]Cliente ({session_id}) > [/bold cyan]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Encerrando sessao... Ate logo![/dim]")
            break

        if not user_input:
            continue

        # Handle slash commands
        if user_input.startswith("/"):
            cmd_parts = user_input.split(maxsplit=1)
            cmd = cmd_parts[0].lower()
            arg = cmd_parts[1].strip() if len(cmd_parts) > 1 else ""

            if cmd in ("/exit", "/quit"):
                console.print("[dim]Atendimento finalizado. Obrigado por visitar a Emporio da Musica![/dim]")
                break

            elif cmd == "/clear":
                console.clear()
                render_banner(console, session_id)
                continue

            elif cmd == "/session":
                if arg:
                    session_id = arg
                    console.print(f"[bold green][SESSION UPDATED][/bold green] Sessao alterada para: [bold white]{session_id}[/bold white]")
                else:
                    new_id = f"session-{uuid.uuid4().hex[:6]}"
                    session_id = new_id
                    console.print(f"[bold green][NEW SESSION][/bold green] Nova sessao iniciada: [bold white]{session_id}[/bold white]")
                continue

            elif cmd == "/history":
                history = orchestrator.audit_store.get_conversation_history(session_id, limit=20)
                if not history:
                    console.print(f"[dim]Nenhum historico gravado para a sessao '{session_id}'.[/dim]")
                else:
                    table = Table(title=f"Historico de Conversa — Sessao: {session_id}", border_style="dim")
                    table.add_column("Role", style="bold cyan", width=12)
                    table.add_column("Mensagem", style="white")
                    for h in history:
                        table.add_row(h["role"].capitalize(), h["content"])
                    console.print(table)
                continue

            elif cmd == "/metrics":
                metrics = orchestrator.audit_store.get_session_metrics(session_id)
                table = Table(title=f"Telemetria Acumulada — Sessao: {session_id}", border_style="cyan")
                table.add_column("Metrica", style="bold white")
                table.add_column("Valor", style="green")
                table.add_row("Total de Eventos Auditados", str(metrics["total_events"]))
                table.add_row("Latencia Total Acumulada", f"{metrics['total_latency_ms']} ms")
                table.add_row("Latencia Media por Turno", f"{metrics['avg_latency_ms']} ms")
                table.add_row("Tokens Totais Consumidos", str(metrics["total_tokens"]))
                table.add_row("Prompt Tokens", str(metrics["prompt_tokens"]))
                table.add_row("Completion Tokens", str(metrics["completion_tokens"]))
                table.add_row("Ferramentas Executadas", str(metrics["tools_called"]))
                table.add_row("Guardrails Disparados", str(metrics["guardrails_triggered"]))
                console.print(table)
                continue

            else:
                console.print(f"[bold red]Comando desconhecido:[/bold red] {cmd}. Utilize /session, /history, /metrics ou /exit.")
                continue

        # Execute conversation turn
        with console.status("[bold green]Processando consulta com guardrails e ferramentas...[/bold green]", spinner="dots"):
            response = orchestrator.process_turn(session_id, user_input)

        # Render Assistant Response Panel
        console.print(
            Panel(
                Text(response.response_text, style="white"),
                title="[bold green]Consultor Emporio da Musica[/bold green]",
                border_style="green",
                padding=(1, 2),
            )
        )

        # Render Telemetry HUD without emojis
        console.print(
            Panel(
                Text(response.telemetry_hud, style="bold dim white"),
                border_style="dim",
                padding=(0, 1),
            )
        )


if __name__ == "__main__":
    run_cli()
