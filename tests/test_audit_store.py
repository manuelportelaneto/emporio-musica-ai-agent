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

    def test_conversation_history_sliding_window_limit(self, temp_audit_store):
        session = "test-session-window"
        for i in range(10):
            temp_audit_store.save_message(session, "user", f"user-{i}")
            temp_audit_store.save_message(session, "assistant", f"bot-{i}")

        # Total 20 messages. Limit 4 should return the last 4 in chronological order: user-8, bot-8, user-9, bot-9
        recent = temp_audit_store.get_conversation_history(session, limit=4)
        assert len(recent) == 4
        assert recent[0]["content"] == "user-8"
        assert recent[1]["content"] == "bot-8"
        assert recent[2]["content"] == "user-9"
        assert recent[3]["content"] == "bot-9"

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
        assert "[RESPONSE TIME]" in hud

    def test_customer_session_crm(self, temp_audit_store):
        session = "session-crm-test"
        temp_audit_store.save_customer_session(
            session_id=session,
            customer_id=1,
            phone="67998123456",
            customer_name="Lucas Mendes",
            address="Rua 14 de Maio, 3200",
            cart_items=[{"name": "Yamaha C40", "pix_price": 569.91}],
            affinity_tags=["violão", "yamaha"],
            sentiment_score="Positivo",
            interaction_category="Consulta Catálogo",
            alerts_detected=[{"scope": "business", "message": "Cliente buscou afinador"}],
            total_duration_sec=45,
        )

        sess = temp_audit_store.get_customer_session(session)
        assert sess is not None
        assert sess["customer_name"] == "Lucas Mendes"
        assert sess["address"] == "Rua 14 de Maio, 3200"
        assert len(sess["cart_items"]) == 1
        assert sess["cart_items"][0]["name"] == "Yamaha C40"
        assert sess["sentiment_score"] == "Positivo"
        assert "violão" in sess["affinity_tags"]
        assert len(sess["alerts_detected"]) == 1

    def test_list_all_sessions_and_full_transcript(self, temp_audit_store):
        temp_audit_store.save_message("session-alpha", "user", "Olá!")
        temp_audit_store.save_message("session-alpha", "assistant", "Olá! Como posso ajudar?")
        temp_audit_store.save_message("session-beta", "user", "Qual o valor do violão?")

        all_sess = temp_audit_store.list_all_sessions()
        assert len(all_sess) >= 2
        alpha_info = next((s for s in all_sess if s["session_id"] == "session-alpha"), None)
        assert alpha_info is not None
        assert alpha_info["turn_count"] == 2

        transcript = temp_audit_store.get_full_session_transcript("session-alpha")
        assert len(transcript) == 2
        assert transcript[0]["role"] == "user"
        assert transcript[0]["content"] == "Olá!"
        assert transcript[1]["role"] == "assistant"

    def test_clear_session_and_get_session_audit_logs(self, temp_audit_store):
        session = "session-to-clear"
        temp_audit_store.save_message(session, "user", "Test clear")
        temp_audit_store.log_audit_event(
            session_id=session,
            event_type="TOOL_INVOCATION",
            component_name="catalog_service",
            latency_ms=10.0,
        )
        
        logs = temp_audit_store.get_session_audit_logs(session)
        assert len(logs) == 1
        assert logs[0]["event_type"] == "TOOL_INVOCATION"
        
        temp_audit_store.clear_session(session)
        assert len(temp_audit_store.get_conversation_history(session)) == 0
        assert len(temp_audit_store.get_session_audit_logs(session)) == 0

    def test_get_session_metrics_includes_turns_and_tool_invocations(self, temp_audit_store):
        session = "session-kpi-metrics"
        temp_audit_store.save_message(session, "user", "Turn 1")
        temp_audit_store.save_message(session, "assistant", "Bot 1")
        temp_audit_store.save_message(session, "user", "Turn 2")
        temp_audit_store.save_message(session, "assistant", "Bot 2")

        temp_audit_store.log_audit_event(
            session_id=session,
            event_type="TOOL_INVOCATION",
            component_name="lookup_catalog",
            latency_ms=12.5,
        )
        temp_audit_store.log_audit_event(
            session_id=session,
            event_type="AGENT_RESPONSE",
            component_name="orchestrator",
            latency_ms=500.0,
            prompt_tokens=100,
            completion_tokens=50,
        )

        metrics = temp_audit_store.get_session_metrics(session)
        assert metrics["total_turns"] == 2
        assert metrics["tool_invocations"]["lookup_catalog"] == 1
        assert metrics["total_tokens"] == 150
        assert metrics["avg_latency_ms"] > 0

    def test_clear_all_sessions(self, temp_audit_store):
        temp_audit_store.save_message("s1", "user", "Hello s1")
        temp_audit_store.save_message("s2", "user", "Hello s2")
        temp_audit_store.log_audit_event("s1", "AGENT_RESPONSE", "orchestrator", latency_ms=10.0)
        
        assert len(temp_audit_store.list_all_sessions()) >= 2
        temp_audit_store.clear_all_sessions()
        assert len(temp_audit_store.list_all_sessions()) == 0
        assert len(temp_audit_store.get_conversation_history("s1")) == 0
        assert len(temp_audit_store.get_audit_logs()) == 0

