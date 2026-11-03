"""Audit Store: Dual-layer persistence for conversation history and execution telemetry.

Decouples customer conversation turns from low-level operational telemetry
such as tool invocations, guardrail checks, token counts, and latency profiling.
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Dict, List, Optional


class AuditStore:
    """Manages dual-layer SQLite persistence for conversations and telemetry."""

    def __init__(self, db_path: str = "emporio_records.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create tables per SPEC.md Section 6."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Conversational History (Customer-facing thread)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT CHECK(role IN ('user', 'assistant', 'system')) NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            # 2. Execution Audit & Telemetry Log (Low-level execution metrics)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS execution_audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    event_type TEXT NOT NULL, -- 'TOOL_INVOCATION', 'GUARDRAIL_INTERCEPT', 'AGENT_RESPONSE', 'ERROR'
                    component_name TEXT NOT NULL, -- e.g., 'lookup_catalog', 'accessory_guardrail'
                    input_payload TEXT,
                    output_payload TEXT,
                    latency_ms REAL NOT NULL,
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    status TEXT NOT NULL, -- 'SUCCESS', 'BLOCKED', 'FAILED'
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            # 3. Customer Session Summary & Analytics CRM
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS customer_sessions (
                    session_id TEXT PRIMARY KEY,
                    customer_id INTEGER,
                    phone TEXT,
                    customer_name TEXT,
                    affinity_tags TEXT,
                    sentiment_score TEXT,
                    interaction_category TEXT,
                    alerts_detected TEXT,
                    total_duration_sec INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            # Helpful indices for fast querying
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_conv_session ON conversation_history(session_id);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_session ON execution_audit_logs(session_id);"
            )
            conn.commit()

    def save_message(self, session_id: str, role: str, content: str) -> int:
        """Persist a single message turn in conversation history.

        Args:
            session_id: Session identifier.
            role: 'user', 'assistant', or 'system'.
            content: Message body.

        Returns:
            Inserted row ID.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO conversation_history (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content),
            )
            conn.commit()
            return cursor.lastrowid

    def get_conversation_history(
        self, session_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Retrieve historical message turns for sliding-window context.

        Args:
            session_id: Session identifier.
            limit: Maximum turns to fetch.

        Returns:
            List of message dictionaries in chronological order.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT role, content, created_at 
                FROM conversation_history 
                WHERE session_id = ? 
                ORDER BY id ASC LIMIT ?
                """,
                (session_id, limit),
            )
            rows = cursor.fetchall()
            return [{"role": r["role"], "content": r["content"]} for r in rows]

    def list_all_sessions(self) -> List[Dict[str, Any]]:
        """List all distinct historical sessions with turn counts and timestamps."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 
                    session_id, 
                    COUNT(*) as turn_count, 
                    MIN(created_at) as started_at, 
                    MAX(created_at) as last_activity
                FROM conversation_history
                GROUP BY session_id
                ORDER BY last_activity DESC
                """
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_full_session_transcript(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve all chronological turns for a given session with metadata."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT role, content, created_at 
                FROM conversation_history 
                WHERE session_id = ? 
                ORDER BY id ASC
                """,
                (session_id,),
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def log_audit_event(
        self,
        session_id: str,
        event_type: str,
        component_name: str,
        input_payload: Any = None,
        output_payload: Any = None,
        latency_ms: float = 0.0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        status: str = "SUCCESS",
    ) -> int:
        """Record an execution telemetry audit event.

        Args:
            session_id: Session identifier.
            event_type: 'TOOL_INVOCATION', 'GUARDRAIL_INTERCEPT', 'AGENT_RESPONSE', 'ERROR'.
            component_name: Name of tool, guardrail, or model.
            input_payload: Raw or structured input.
            output_payload: Raw or structured output.
            latency_ms: Execution duration in milliseconds.
            prompt_tokens: Input tokens consumed.
            completion_tokens: Output tokens generated.
            status: 'SUCCESS', 'BLOCKED', or 'FAILED'.

        Returns:
            Inserted row ID.
        """
        in_str = (
            json.dumps(input_payload, ensure_ascii=False)
            if isinstance(input_payload, (dict, list))
            else str(input_payload) if input_payload is not None else None
        )
        out_str = (
            json.dumps(output_payload, ensure_ascii=False)
            if isinstance(output_payload, (dict, list))
            else str(output_payload) if output_payload is not None else None
        )

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO execution_audit_logs (
                    session_id, event_type, component_name, input_payload,
                    output_payload, latency_ms, prompt_tokens, completion_tokens, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    event_type,
                    component_name,
                    in_str,
                    out_str,
                    round(latency_ms, 2),
                    prompt_tokens,
                    completion_tokens,
                    status,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_audit_logs(
        self, session_id: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Retrieve audit telemetry records."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if session_id:
                cursor.execute(
                    """
                    SELECT * FROM execution_audit_logs 
                    WHERE session_id = ? 
                    ORDER BY id DESC LIMIT ?
                    """,
                    (session_id, limit),
                )
            else:
                cursor.execute(
                    "SELECT * FROM execution_audit_logs ORDER BY id DESC LIMIT ?",
                    (limit,),
                )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_session_metrics(self, session_id: str) -> Dict[str, Any]:
        """Aggregate telemetry performance metrics for a specific session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 
                    COUNT(*) AS total_events,
                    SUM(latency_ms) AS total_latency_ms,
                    AVG(latency_ms) AS avg_latency_ms,
                    SUM(prompt_tokens) AS total_prompt_tokens,
                    SUM(completion_tokens) AS total_completion_tokens,
                    SUM(CASE WHEN event_type = 'TOOL_INVOCATION' THEN 1 ELSE 0 END) AS tools_called,
                    SUM(CASE WHEN event_type = 'GUARDRAIL_INTERCEPT' THEN 1 ELSE 0 END) AS guardrails_triggered
                FROM execution_audit_logs
                WHERE session_id = ?
                """,
                (session_id,),
            )
            row = cursor.fetchone()
            return {
                "total_events": row["total_events"] or 0,
                "total_latency_ms": round(row["total_latency_ms"] or 0.0, 2),
                "avg_latency_ms": round(row["avg_latency_ms"] or 0.0, 2),
                "total_tokens": (row["total_prompt_tokens"] or 0)
                + (row["total_completion_tokens"] or 0),
                "prompt_tokens": row["total_prompt_tokens"] or 0,
                "completion_tokens": row["total_completion_tokens"] or 0,
                "tools_called": row["tools_called"] or 0,
                "guardrails_triggered": row["guardrails_triggered"] or 0,
            }

    def save_customer_session(
        self,
        session_id: str,
        customer_id: Optional[int] = None,
        phone: Optional[str] = None,
        customer_name: Optional[str] = None,
        affinity_tags: Optional[List[str]] = None,
        sentiment_score: str = "Neutro",
        interaction_category: str = "Consulta Catálogo",
        alerts_detected: Optional[List[Dict[str, Any]]] = None,
        total_duration_sec: int = 0,
    ) -> None:
        """Upsert customer session analytics and CRM profile."""
        tags_json = json.dumps(affinity_tags or [], ensure_ascii=False)
        alerts_json = json.dumps(alerts_detected or [], ensure_ascii=False)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO customer_sessions (
                    session_id, customer_id, phone, customer_name,
                    affinity_tags, sentiment_score, interaction_category,
                    alerts_detected, total_duration_sec, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(session_id) DO UPDATE SET
                    customer_id = COALESCE(excluded.customer_id, customer_sessions.customer_id),
                    phone = COALESCE(excluded.phone, customer_sessions.phone),
                    customer_name = COALESCE(excluded.customer_name, customer_sessions.customer_name),
                    affinity_tags = excluded.affinity_tags,
                    sentiment_score = excluded.sentiment_score,
                    interaction_category = excluded.interaction_category,
                    alerts_detected = excluded.alerts_detected,
                    total_duration_sec = excluded.total_duration_sec,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    session_id,
                    customer_id,
                    phone,
                    customer_name,
                    tags_json,
                    sentiment_score,
                    interaction_category,
                    alerts_json,
                    total_duration_sec,
                ),
            )
            conn.commit()

    def get_customer_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve customer session CRM profile."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM customer_sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            try:
                res["affinity_tags"] = json.loads(res.get("affinity_tags") or "[]")
            except Exception:
                res["affinity_tags"] = []
            try:
                res["alerts_detected"] = json.loads(res.get("alerts_detected") or "[]")
            except Exception:
                res["alerts_detected"] = []
            return res

    @staticmethod
    def format_telemetry_hud(
        latency_ms: float,
        prompt_tokens: int,
        completion_tokens: int,
        tool_invoked: Optional[str] = None,
        guardrails_summary: str = "Scope Passed | Factual Grounding: 100% Verified",
    ) -> str:
        """Render Observability HUD string per SPEC.md Section 7."""
        tool_display = tool_invoked or "None (Direct/Intercepted)"
        total_tokens = prompt_tokens + completion_tokens
        line1 = f"[RESPONSE TIME] {latency_ms:.0f}ms  |  [TOKENS] {total_tokens} (Prompt: {prompt_tokens} / Completion: {completion_tokens})"
        line2 = f"[TOOL INVOKED] {tool_display}"
        line3 = f"[GUARDRAILS] {guardrails_summary}"

        width = 82
        border_top = "┌─ [TELEMETRY & AUDIT HUD] " + ("─" * (width - 27)) + "┐"
        border_bottom = "└" + ("─" * (width - 2)) + "┘"

        pad1 = " " * max(width - 4 - len(line1), 1)
        pad2 = " " * max(width - 4 - len(line2), 1)
        pad3 = " " * max(width - 4 - len(line3), 1)

        return (
            f"{border_top}\n"
            f"│ {line1}{pad1}│\n"
            f"│ {line2}{pad2}│\n"
            f"│ {line3}{pad3}│\n"
            f"{border_bottom}"
        )
