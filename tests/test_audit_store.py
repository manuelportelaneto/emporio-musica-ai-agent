"""Unit tests for dual-layer persistence and telemetry tracking."""

from __future__ import annotations

import os
import tempfile
import pytest

from src.storage.audit_store import AuditStore


@pytest.fixture
def temp_audit_store():
    """Temporary isolated SQLite store for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_path = f.name

    store = AuditStore(db_path=temp_path)
    yield store

    if os.path.exists(temp_path):
        os.remove(temp_path)


class TestAuditStore:
    def test_conversation_history_persistence(self, temp_audit_store):
        session = "test-session-123"
        temp_audit_store.save_message(session, "user", "Olá, procuro violão Yamaha C40")
        temp_audit_store.save_message(session, "assistant", "Temos o Yamaha C40 por R$ 599,90!")

        history = temp_audit_store.get_conversation_history(session)
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert "Yamaha C40" in history[0]["content"]
        assert history[1]["role"] == "assistant"
        assert "599,90" in history[1]["content"]

    def test_audit_event_logging(self, temp_audit_store):
        session = "test-session-audit"
        event_id = temp_audit_store.log_audit_event(
            session_id=session,
            event_type="TOOL_INVOCATION",
            component_name="lookup_catalog",
            input_payload={"query": "Yamaha C40"},
            output_payload=[{"name": "Yamaha C40", "price": 599.9}],
            latency_ms=15.4,
            prompt_tokens=45,
            completion_tokens=22,
            status="SUCCESS",
        )
        assert event_id > 0

        logs = temp_audit_store.get_audit_logs(session_id=session)
        assert len(logs) == 1
        log = logs[0]
        assert log["event_type"] == "TOOL_INVOCATION"
        assert log["component_name"] == "lookup_catalog"
        assert log["latency_ms"] == 15.4
        assert log["prompt_tokens"] == 45
        assert log["completion_tokens"] == 22
        assert "Yamaha C40" in log["input_payload"]

    def test_session_metrics_aggregation(self, temp_audit_store):
        session = "test-session-metrics"
        temp_audit_store.log_audit_event(
            session_id=session,
            event_type="TOOL_INVOCATION",
            component_name="lookup_catalog",
            latency_ms=100.0,
            prompt_tokens=50,
            completion_tokens=25,
        )
        temp_audit_store.log_audit_event(
            session_id=session,
            event_type="GUARDRAIL_INTERCEPT",
            component_name="accessory_interceptor",
            latency_ms=5.0,
            prompt_tokens=0,
            completion_tokens=0,
            status="BLOCKED",
        )

        metrics = temp_audit_store.get_session_metrics(session)
        assert metrics["total_events"] == 2
        assert metrics["total_latency_ms"] == 105.0
        assert metrics["total_tokens"] == 75
        assert metrics["tools_called"] == 1
        assert metrics["guardrails_triggered"] == 1

    def test_format_telemetry_hud(self):
        hud = AuditStore.format_telemetry_hud(
            latency_ms=412.0,
            prompt_tokens=128,
            completion_tokens=56,
            tool_invoked='lookup_catalog(query="Yamaha C40", in_stock_only=True)',
            guardrails_summary="Scope Passed | Factual Grounding: 100% Verified",
        )
        assert "TELEMETRY & AUDIT HUD" in hud
        assert "412ms" in hud
        assert "[TOKENS] 184" in hud
        assert "lookup_catalog" in hud
        assert "100% Verified" in hud
