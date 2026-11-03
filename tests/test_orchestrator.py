"""Unit tests for the Conversational Orchestrator."""

from __future__ import annotations

import os
import tempfile
import pytest

from src.data_engine import PolicyVectorIndex, init_sqlite_engine
from src.guardrails.input_guards import ACCESSORY_REFUSAL_MESSAGE
from src.orchestrator import ConversationalOrchestrator
from src.storage.audit_store import AuditStore


@pytest.fixture(scope="session")
def shared_engine():
    return init_sqlite_engine("data")


@pytest.fixture(scope="session")
def shared_policy_index():
    return PolicyVectorIndex("data/políticas_da_loja.pdf")


@pytest.fixture
def orchestrator(shared_engine, shared_policy_index):
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_db = f.name
    store = AuditStore(db_path=temp_db)

    orch = ConversationalOrchestrator(
        db_conn=shared_engine,
        policy_index=shared_policy_index,
        audit_store=store,
        provider="offline",
    )
    yield orch

    if os.path.exists(temp_db):
        os.remove(temp_db)


class TestOrchestrator:
    def test_accessory_interception(self, orchestrator):
        session = "session-test-acc"
        resp = orchestrator.process_turn(session, "Vocês vendem encordoamento de violão?")

        assert resp.response_text == ACCESSORY_REFUSAL_MESSAGE
        assert len(resp.tools_invoked) == 0
        assert "Blocked" in resp.guardrails_summary
        assert "Zero LLM Cost" in resp.guardrails_summary
        assert resp.latency_ms > 0

    def test_catalog_search_flow(self, orchestrator):
        session = "session-test-cat"
        resp = orchestrator.process_turn(session, "Gostaria de ver o violão Yamaha C40")

        assert "Yamaha C40" in resp.response_text
        assert "PIX" in resp.response_text
        assert any("lookup_catalog" in t for t in resp.tools_invoked)
        assert "TELEMETRY & AUDIT HUD" in resp.telemetry_hud

    def test_customer_authentication_flow(self, orchestrator):
        session = "session-test-auth"
        resp = orchestrator.process_turn(session, "Olá, meu nome é Lucas Mendes e meu telefone é (67) 99812-3456")

        assert "Lucas" in resp.response_text
        assert any("authenticate_or_register_customer" in t for t in resp.tools_invoked)
        sess = orchestrator.audit_store.get_customer_session(session)
        assert sess is not None
        assert "Lucas" in sess["customer_name"]
        assert sess["customer_id"] == 1

    def test_raw_phone_digits_authentication_not_blocked_as_cpf(self, orchestrator):
        session = "session-test-raw-phone"
        # User provides 11 consecutive numeric digits as requested by the store
        resp = orchestrator.process_turn(session, "67998123456")

        assert "[CPF PROTEGIDO]" not in resp.response_text
        assert any("authenticate_or_register_customer" in t for t in resp.tools_invoked)
        assert "Lucas" in resp.response_text or "autenticada" in resp.response_text

    def test_order_tracking_flow(self, orchestrator):
        session = "session-test-ord"
        resp = orchestrator.process_turn(session, "Qual o status do pedido #1?")

        assert "1" in resp.response_text
        assert "DELIVERED" in resp.response_text or "BRAB1234567BR" in resp.response_text
        assert any("get_order_details" in t for t in resp.tools_invoked)
        assert "TELEMETRY & AUDIT HUD" in resp.telemetry_hud

    def test_policy_inquiry_flow(self, orchestrator):
        session = "session-test-pol"
        resp = orchestrator.process_turn(session, "Qual o endereço da loja e horário de funcionamento?")

        assert "14 de Maio" in resp.response_text or "Campo Grande" in resp.response_text
        assert any("query_store_policy" in t for t in resp.tools_invoked)

    def test_pii_sanitization_in_storage(self, orchestrator):
        session = "session-test-pii"
        resp = orchestrator.process_turn(
            session, "Meu CPF é 123.456.789-00, tem violão Tagima disponível?"
        )

        history = orchestrator.audit_store.get_conversation_history(session)
        assert len(history) == 2
        user_msg = history[0]["content"]
        assert "123.456.789-00" not in user_msg
        assert "[CPF PROTEGIDO]" in user_msg

    def test_humanized_greeting_flow(self, orchestrator):
        session = "session-test-greeting"
        resp = orchestrator.process_turn(session, "Bom dia! Tudo bem com você?")

        assert "bom dia" in resp.response_text.lower()
        assert "Empório da Música" in resp.response_text or "instrumentos" in resp.response_text.lower()
        assert len(resp.tools_invoked) == 0  # No catalog query triggered for greeting
        assert "Não encontrei instrumentos" not in resp.response_text

    def test_runtime_llm_reconfiguration(self, orchestrator):
        # Configure Groq provider
        orchestrator.configure_llm(provider="groq", api_key="gsk_dummy_test_key_123", persist=False)
        assert orchestrator.provider == "groq"
        assert orchestrator.api_key == "gsk_dummy_test_key_123"

        # Switch to offline mode
        orchestrator.configure_llm(provider="offline", persist=False)
        assert orchestrator.provider == "offline"
        assert orchestrator.llm_client is None
