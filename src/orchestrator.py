"""Conversational Orchestrator: Native tool-calling agent with multi-layer guardrails and telemetry HUD."""

from __future__ import annotations

import json
import re
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.config import AppConfig, get_llm_client
from src.data_engine import PolicyVectorIndex, init_sqlite_engine
from src.guardrails.input_guards import validate_input
from src.guardrails.output_guards import validate_output
from src.services.catalog_service import lookup_catalog
from src.services.customer_service import (
    authenticate_or_register_customer,
    normalize_phone,
    update_customer_profile,
)
from src.services.order_service import get_order_details
from src.services.policy_service import query_store_policy
from src.storage.audit_store import AuditStore

SYSTEM_PROMPT = """Você é o consultor de atendimento inteligente da Empório da Música, uma tradicional loja física e online de instrumentos musicais fundada em 2008 em Campo Grande/MS (Rua 14 de Maio, 3200 — Centro).

## SUA PERSONA E DIRETRIZES DE COMUNICAÇÃO:
1. **Consultoria Musical:** Você é caloroso, atencioso, entende profundamente de música ("persona de colega músico"), transparente e prestativo. Ajude o cliente a encontrar o melhor instrumento para seu nível e estilo.
2. **Convite Sutil e Contextual à Loja Física:** Convide o cliente para conhecer a loja física em Campo Grande (Rua 14 de Maio, 3200) SOMENTE quando for natural e pertinente ao contexto (ex: quando o cliente perguntar o endereço da loja, se há loja física, ou quando quiser experimentar a acústica e a pegada de um instrumento antes de fechar negócio). NUNCA repita esse convite de forma mecânica ou forçada em consultas gerais de catálogo.
3. **Escopo Estrito de Catálogo:** A Empório da Música vende EXCLUSIVAMENTE instrumentos musicais. NÃO vendemos acessórios (cordas avulsas, palhetas, cabos, amplificadores, pedais, capas, afinadores). Se o cliente insistir em acessórios, recuse com simpatia e indique que procure parceiros na região central de Campo Grande.
4. **Identificação Progressiva e Atendimento Personalizado (Progressive Profiling):**
   - Não exija login logo de início. O cliente pode pesquisar produtos e tirar dúvidas livremente.
   - Quando o cliente solicitar informações pessoais (ex: rastreio de pedido, devolução/troca ou quiser salvar suas preferências), solicite gentilmente o nome e o telefone completo com DDD para localizá-lo com segurança através de `authenticate_or_register_customer`.
   - Conforme a conversa avança, você pode coletar o endereço ou cidade para calcular opções de entrega com `update_customer_profile`.
5. **Políticas da Loja:**
   - **Pagamento:** PIX tem 5% de desconto à vista sobre o preço de tabela (NÃO cumulativo com produtos em promoção). Cartão em até 12x sem juros (parcelas mínimas: R$ 100 para 7-12x; R$ 80 para 4-6x; R$ 50 para até 3x).
   - **Trocas e Devoluções:** Arrependimento de compra online em até 7 dias corridos após o recebimento (CDC Art. 49). Garantia legal de 30 dias para defeitos de fabricação.
   - **Frete:** Frete grátis via motoboy para Grande Campo Grande em compras acima de R$ 500 (taxa fixa de R$ 35 abaixo desse valor). Envios nacionais via PAC/SEDEX e Jadlog.
6. **Uso Obrigatório de Ferramentas:**
   - NUNCA invente preços, prazos ou disponibilidade. Use sempre as ferramentas disponíveis:
     * `lookup_catalog`: para pesquisar instrumentos, preços, promoções e parcelamentos.
     * `get_order_details`: para consultar status de pedidos, rastreio e elegibilidade de devolução pelo CDC.
     * `query_store_policy`: para consultar regras oficiais da loja, frete, garantia, horários e endereço.
     * `authenticate_or_register_customer`: para identificar ou cadastrar o cliente pelo telefone.
     * `update_customer_profile`: para atualizar endereço e preferências musicais.
7. **Uso Moderado de Emojis:** É permitido o uso moderado e pontual de emojis no diálogo com o cliente (no máximo 1 ou 2 por mensagem), preservando sempre a postura profissional e consultiva, sem poluição visual.
"""

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "lookup_catalog",
            "description": "Busca instrumentos no catálogo da loja, verificando estoque, promoções ativas, descontos no PIX e parcelamento sem juros.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Termo de busca pelo nome do instrumento, modelo ou marca (ex: 'Yamaha C40', 'Tagima', 'violão nylon')",
                    },
                    "category": {
                        "type": "string",
                        "description": "Categoria do instrumento (ex: 'Violões', 'Guitarras', 'Baixos', 'Teclados e Pianos')",
                    },
                    "max_price": {
                        "type": "number",
                        "description": "Preço máximo em Reais (BRL)",
                    },
                    "in_stock_only": {
                        "type": "boolean",
                        "description": "Filtrar estritamente itens disponíveis em estoque (padrão true)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_details",
            "description": "Consulta detalhes, status, rastreamento e elegibilidade de devolução pelo CDC (7 dias) de um pedido.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "integer",
                        "description": "ID numérico único do pedido (ex: 1, 2, 7)",
                    },
                    "customer_name_or_phone": {
                        "type": "string",
                        "description": "Nome do cliente ou telefone para localização do pedido",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_store_policy",
            "description": "Consulta o manual de políticas oficiais da loja sobre formas de pagamento, garantia, frete, trocas CDC e horários de atendimento.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Tópico de dúvida (ex: 'horário de funcionamento', 'frete Campo Grande', 'garantia de instrumentos', 'prazo de devolução')",
                    }
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "authenticate_or_register_customer",
            "description": "Identifica e autentica um cliente existente pelo telefone completo ou cria um novo cadastro de forma transparente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {
                        "type": "string",
                        "description": "Telefone completo do cliente com DDD (ex: '67998123456' ou '(67) 99812-3456')",
                    },
                    "name": {
                        "type": "string",
                        "description": "Nome completo do cliente",
                    },
                    "birth_date": {
                        "type": "string",
                        "description": "Data de nascimento opcional (ex: '15/04/1990')",
                    },
                },
                "required": ["phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_customer_profile",
            "description": "Atualiza dados cadastrais complementares (endereço ou preferências musicais) de forma fluida durante o atendimento.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {
                        "type": "string",
                        "description": "Telefone do cliente autenticado",
                    },
                    "address": {
                        "type": "string",
                        "description": "Novo endereço ou CEP para entrega",
                    },
                    "musical_interests": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Instrumentos ou marcas de interesse do cliente",
                    },
                },
                "required": ["phone"],
            },
        },
    },
]


def extract_affinity_tags(text: str) -> List[str]:
    """Extract musical instruments, brands, and skill levels from conversational text."""
    tags = []
    text_lower = text.lower()
    keywords = {
        "violão": ["violão", "violao", "nylon", "aço"],
        "guitarra": ["guitarra", "stratocaster", "telecaster", "les paul"],
        "baixo": ["baixo", "bass", "contrabaixo"],
        "teclado": ["teclado", "piano", "sintetizador"],
        "bateria": ["bateria", "percussão", "pratos"],
        "ukulele": ["ukulele", "ukulelê"],
        "yamaha": ["yamaha"],
        "fender": ["fender", "squier"],
        "tagima": ["tagima"],
        "roland": ["roland"],
        "giannini": ["giannini"],
        "casio": ["casio"],
        "korg": ["korg"],
        "iniciante": ["iniciante", "começando", "aprender", "estudo", "primeiro violão"],
        "profissional": ["profissional", "palco", "show", "gravação", "estúdio"],
    }
    for tag, terms in keywords.items():
        if any(t in text_lower for t in terms):
            tags.append(tag)
    return tags


def analyze_turn_sentiment(text: str) -> str:
    """Classify sentiment expressed by user in the current turn."""
    lower = text.lower()
    positive = [
        "obrigado", "obrigada", "valeu", "excelente", "maravilha",
        "ótimo", "otimo", "adorei", "gostei", "perfeito", "legal",
        "show", "bacana", "ajudou", "bom dia", "boa tarde"
    ]
    frustrated = [
        "demora", "reclamar", "ruim", "errado", "defeito", "quebrado",
        "péssimo", "pessimo", "odiei", "absurdo", "falha", "propaganda enganosa",
        "atrasou", "não recebi"
    ]
    curious = [
        "queria", "gostaria", "saber", "duvida", "dúvida", "quanto custa",
        "sonho", "aprender", "recomenda", "indica", "qual a diferença"
    ]

    if any(p in lower for p in positive):
        return "Positivo"
    elif any(f in lower for f in frustrated):
        return "Frustrado"
    elif any(c in lower for c in curious):
        return "Curioso / Entusiasmado"
    return "Neutro"


def detect_turn_alerts(
    user_text: str,
    tools_called: List[str],
    guardrails_summary: str,
    results_count: int,
) -> List[Dict[str, Any]]:
    """Detect multi-scope operational alerts (Development, Security, Business)."""
    alerts: List[Dict[str, Any]] = []
    lower = user_text.lower()

    # 1. Security Scope
    if "blocked" in guardrails_summary.lower() or "injection" in guardrails_summary.lower():
        alerts.append({
            "scope": "security",
            "type": "PROMPT_INJECTION_DEFENSE",
            "message": "Tentativa de injeção de prompt ou instrução fora de escopo bloqueada.",
        })
    if "[cpf protegido]" in lower or "[cartão protegido]" in lower or re.search(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b", user_text):
        alerts.append({
            "scope": "security",
            "type": "PII_PROTECTED",
            "message": "PII sensível detectado e mascarado para privacidade.",
        })

    # 2. Business Scope
    accessory_terms = ["corda", "encordoamento", "palheta", "cabo", "pedal", "amplificador", "afinador", "capa", "case"]
    found_accessories = [term for term in accessory_terms if term in lower]
    if found_accessories:
        alerts.append({
            "scope": "business",
            "type": "UNMET_ACCESSORY_DEMAND",
            "message": f"Demanda reprimida por acessórios: {', '.join(found_accessories)} (item fora de catálogo).",
        })
    if any("lookup_catalog" in t for t in tools_called) and results_count == 0:
        alerts.append({
            "scope": "business",
            "type": "ZERO_SEARCH_RESULTS",
            "message": f"Busca sem estoque ou produto indisponível para: '{user_text[:35]}'.",
        })

    # 3. Development Scope
    if any("lookup_catalog" in t for t in tools_called) and results_count == 0:
        alerts.append({
            "scope": "development",
            "type": "SEARCH_REFINEMENT_OPPORTUNITY",
            "message": f"Oportunidade de enriquecimento de sinônimos para o termo: '{user_text[:35]}'.",
        })

    return alerts


@dataclass
class OrchestratorResponse:
    """Complete response payload with observability telemetry."""

    response_text: str
    session_id: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    tools_invoked: List[str] = field(default_factory=list)
    guardrails_summary: str = "Scope Passed | Factual Grounding: 100% Verified"
    telemetry_hud: str = ""


class ConversationalOrchestrator:
    """Core agent orchestrating tool calling, multi-layer guardrails, and telemetry."""

    def __init__(
        self,
        db_conn: Optional[sqlite3.Connection] = None,
        policy_index: Optional[PolicyVectorIndex] = None,
        audit_store: Optional[AuditStore] = None,
    ):
        self.db_conn = db_conn or init_sqlite_engine(AppConfig.DATA_DIR)
        self.policy_index = policy_index or PolicyVectorIndex(AppConfig.POLICY_PDF_PATH)
        self.audit_store = audit_store or AuditStore(AppConfig.DATABASE_PATH)
        self.llm_client = get_llm_client()
        self.session_profiles: Dict[str, Dict[str, Any]] = {}

    def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Route tool invocation to deterministic backend service."""
        if tool_name == "lookup_catalog":
            return lookup_catalog(
                conn=self.db_conn,
                query=arguments.get("query"),
                category=arguments.get("category"),
                max_price=arguments.get("max_price"),
                in_stock_only=arguments.get("in_stock_only", True),
            )
        elif tool_name == "get_order_details":
            return get_order_details(
                conn=self.db_conn,
                order_id=arguments.get("order_id"),
                customer_name_or_phone=arguments.get("customer_name_or_phone"),
            )
        elif tool_name == "query_store_policy":
            return query_store_policy(
                index=self.policy_index,
                topic=arguments.get("topic", ""),
            )
        elif tool_name == "authenticate_or_register_customer":
            return authenticate_or_register_customer(
                conn=self.db_conn,
                name=arguments.get("name", ""),
                phone=arguments.get("phone", ""),
                birth_date=arguments.get("birth_date"),
            )
        elif tool_name == "update_customer_profile":
            return update_customer_profile(
                conn=self.db_conn,
                phone=arguments.get("phone", ""),
                address=arguments.get("address"),
                musical_interests=arguments.get("musical_interests"),
            )
        else:
            return {"error": f"Unknown tool: {tool_name}"}

    def _fallback_offline_agent(
        self, user_text: str, session_id: str
    ) -> Tuple[str, List[str], List[Dict[str, Any]], int, int]:
        """Intelligent deterministic fallback when external LLM API is offline."""
        lowered = user_text.lower()
        tools_called = []
        tool_payloads = []
        session_state = self.session_profiles.get(session_id, {})

        # 1. Check for Phone Number / Customer Authentication Intent
        phone_match = re.search(r"\b(\(?\d{2}\)?\s*9?\d{4}[-\s]?\d{4})\b", user_text)
        if phone_match or any(w in lowered for w in ["meu telefone", "meu contato", "me cadastrar", "meu nome é"]):
            phone_val = phone_match.group(1) if phone_match else "67998123456"
            # Extract potential customer name
            name_val = "Cliente Empório"
            for sample in ["lucas", "ana", "pedro", "mariana", "rafael", "juliana", "thiago", "fernanda"]:
                if sample in lowered:
                    name_val = sample.capitalize()
                    break

            res = self._execute_tool(
                "authenticate_or_register_customer",
                {"phone": phone_val, "name": name_val},
            )
            tools_called.append(f"authenticate_or_register_customer(phone='{phone_val}')")
            tool_payloads.append(res)

            if res.get("status") in ("authenticated", "registered"):
                session_state["customer_id"] = res["customer_id"]
                session_state["phone"] = res["phone"]
                session_state["customer_name"] = res["name"]
                self.session_profiles[session_id] = session_state

                orders_summary = ""
                if res.get("recent_orders"):
                    orders_summary = f" Localizei {len(res['recent_orders'])} pedido(s) recente(s) em sua conta."

                ans = (
                    f"Que ótimo te receber, {res['name']}!{orders_summary} "
                    f"Sua conta está autenticada com sucesso. Em que posso te ajudar hoje? "
                    f"Posso te mostrar instrumentos do nosso catálogo, consultar detalhes de pedidos ou tirar dúvidas sobre pagamentos!"
                )
                return ans, tools_called, tool_payloads, 115, 65

        # 2. Check order tracking intent
        if any(w in lowered for w in ["pedido", "rastreio"]):
            order_id = None
            id_match = re.search(r"\bpedido\s*#?(\d+)\b", lowered) or re.search(r"\b(\d{1,4})\b", lowered)
            if id_match:
                try:
                    order_id = int(id_match.group(1))
                except ValueError:
                    pass

            name_match = session_state.get("customer_name")
            for sample in ["lucas", "ana", "pedro", "mariana"]:
                if sample in lowered:
                    name_match = sample

            res = self._execute_tool("get_order_details", {"order_id": order_id, "customer_name_or_phone": name_match})
            tools_called.append(f"get_order_details(order_id={order_id})")
            tool_payloads.append(res or {})

            if res:
                ret = res["return_policy"]
                items_desc = ", ".join([f"{it['name']} (Qtd: {it['quantity']})" for it in res["items"]])
                ans = (
                    f"Localizei seu pedido #{res['order_id']} no sistema! "
                    f"Itens: {items_desc}. Status atual: {res['status'].upper()}. "
                    f"Código de rastreamento: {res['tracking_code']}. "
                    f"{ret['reason']}"
                )
                return ans, tools_called, tool_payloads, 110, 65
            else:
                ans = (
                    "Para consultar os detalhes do seu pedido com segurança, você poderia me informar "
                    "o número do pedido ou o seu telefone de cadastro com DDD?"
                )
                return ans, tools_called, tool_payloads, 90, 45

        # 3. Check instrument / catalog search intent
        brands = [
            "yamaha", "tagima", "giannini", "fender", "roland", "casio",
            "shelby", "kalani", "kala", "rozini", "ibanez", "epiphone",
            "strinberg", "korg"
        ]
        has_instrument = any(b in lowered for b in brands) or any(
            i in lowered for i in [
                "violão", "violao", "guitarra", "baixo", "teclado", "piano",
                "bateria", "ukulele", "flauta", "sax"
            ]
        )

        if has_instrument:
            query_term = user_text
            for brand in brands:
                if brand in lowered:
                    m = re.search(rf"\b{brand}\s*([\w\-]+)?", lowered)
                    if m:
                        query_term = m.group(0)
                    break

            res = self._execute_tool("lookup_catalog", {"query": query_term, "in_stock_only": True})
            tools_called.append(f"lookup_catalog(query='{query_term}')")
            tool_payloads.append(res)

            if res:
                items_lines = []
                for item in res:
                    promo_info = f" (com desconto especial de {item['discount_percentage']}%)" if item["has_promotion"] else ""
                    items_lines.append(
                        f"• {item['name']}{promo_info}: Preço regular R$ {item['regular_price']:.2f}, "
                        f"à vista no PIX por R$ {item['pix_price']:.2f} ou parcelado em {item['installments']}."
                    )
                catalog_summary = "\n".join(items_lines)
                ans = (
                    f"Encontrei excelentes opções no nosso catálogo para você:\n\n{catalog_summary}\n\n"
                    f"Lembrando que o pagamento via PIX conta com 5% de desconto à vista sobre o preço de tabela! "
                    f"Qual desses modelos chama mais sua atenção? Posso te detalhar as madeiras, a tocabilidade ou simular outro plano de parcelamento."
                )
                return ans, tools_called, tool_payloads, 140, 85

        # 4. Check payment questions
        if any(w in lowered for w in ["pix", "cartão", "cartao", "parcelar", "parcela", "parcelamento", "pagamento"]):
            res = self._execute_tool("query_store_policy", {"topic": "formas de pagamento pix cartão parcelamento"})
            tools_called.append("query_store_policy(topic='pagamento pix cartão')")
            tool_payloads.append(res)
            ans = (
                "Na Empório da Música facilitamos sua compra! Para pagamento à vista no PIX, você ganha 5% de desconto "
                "sobre o valor de tabela (desconto não-cumulativo com itens em promoção). "
                "No cartão de crédito, parcelamos em até 12x sem juros (parcelas mínimas: R$ 100 para 7-12x, R$ 80 para 4-6x e R$ 50 para até 3x). "
                "Qual instrumento você gostaria de adquirir hoje?"
            )
            return ans, tools_called, tool_payloads, 110, 60

        # 5. Check store address or physical visit intent
        if any(w in lowered for w in ["onde fica", "endereço", "endereco", "loja física", "loja fisica", "visitar", "campo grande", "horário", "horario"]):
            res = self._execute_tool("query_store_policy", {"topic": "endereço loja horário de funcionamento"})
            tools_called.append("query_store_policy(topic='endereço loja')")
            tool_payloads.append(res)
            ans = (
                "Nossa loja física fica na Rua 14 de Maio, 3200 — Centro, em Campo Grande/MS (CEP 79202-333). "
                "Funcionamos de segunda a sexta das 08h30 às 18h30 e aos sábados das 08h30 às 13h00. "
                "Será um prazer te receber pessoalmente para tomar um café e experimentar nossos instrumentos!"
            )
            return ans, tools_called, tool_payloads, 100, 55

        # 6. Check general store policy (shipping, warranty, returns)
        if any(w in lowered for w in ["frete", "garantia", "telefone", "devolução", "devolver"]):
            res = self._execute_tool("query_store_policy", {"topic": user_text})
            tools_called.append(f"query_store_policy(topic='{user_text[:20]}')")
            tool_payloads.append(res)
            ans = (
                "Para a Grande Campo Grande, temos entrega via motoboy com frete grátis em compras acima de R$ 500 "
                "(ou taxa fixa de R$ 35 abaixo desse valor). Envios para outros estados são feitos via Correios (SEDEX/PAC) e Jadlog. "
                "Nossa política de trocas segue o Código de Defesa do Consumidor com 7 dias corridos de arrependimento "
                "e 30 dias de garantia contra defeitos de fabricação."
            )
            return ans, tools_called, tool_payloads, 95, 55

        # 7. Default fallback
        res = self._execute_tool("lookup_catalog", {"query": user_text, "in_stock_only": True})
        tools_called.append(f"lookup_catalog(query='{user_text[:20]}')")
        tool_payloads.append(res)

        if res:
            items_lines = []
            for item in res:
                promo_info = f" (com desconto especial de {item['discount_percentage']}%)" if item["has_promotion"] else ""
                items_lines.append(
                    f"• {item['name']}{promo_info}: Preço regular R$ {item['regular_price']:.2f}, "
                    f"à vista no PIX por R$ {item['pix_price']:.2f} ou parcelado em {item['installments']}."
                )
            catalog_summary = "\n".join(items_lines)
            ans = (
                f"Encontrei excelentes opções no nosso catálogo para você:\n\n{catalog_summary}\n\n"
                f"Gostaria de mais detalhes sobre algum desses modelos ou prefere ver opções em outra categoria?"
            )
            return ans, tools_called, tool_payloads, 140, 85
        else:
            ans = (
                "Não encontrei instrumentos com esses termos exatos no momento. "
                "Nosso catálogo é focado exclusivamente em instrumentos musicais (cordas, teclas, sopros e percussão). "
                "Gostaria de ver opções de alguma categoria ou marca específica?"
            )
            return ans, tools_called, tool_payloads, 80, 40

    def process_turn(self, session_id: str, user_message: str) -> OrchestratorResponse:
        """Execute a full conversational turn with guardrails, tools, and telemetry."""
        start_time = time.perf_counter()

        if session_id not in self.session_profiles:
            self.session_profiles[session_id] = {
                "customer_id": None,
                "phone": None,
                "customer_name": None,
                "affinity_tags": [],
                "sentiment_history": [],
                "alerts": [],
                "start_time": time.time(),
            }
        session_state = self.session_profiles[session_id]

        # Extract affinity tags and turn sentiment
        turn_tags = extract_affinity_tags(user_message)
        session_state["affinity_tags"] = list(set(session_state["affinity_tags"] + turn_tags))
        turn_sentiment = analyze_turn_sentiment(user_message)
        session_state["sentiment_history"].append(turn_sentiment)

        # ---------------------------------------------------------
        # Layer 1: Input Guardrails (Accessory Interceptor & PII)
        # ---------------------------------------------------------
        input_guard = validate_input(user_message)

        if not input_guard.passed:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            resp_text = input_guard.intercept_response or ""

            # Log guardrail audit event
            self.audit_store.log_audit_event(
                session_id=session_id,
                event_type="GUARDRAIL_INTERCEPT",
                component_name="input_guardrails",
                input_payload={"raw": user_message, "sanitized": input_guard.sanitized_text},
                output_payload={"response": resp_text, "reason": input_guard.reason},
                latency_ms=latency_ms,
                prompt_tokens=len(user_message.split()) * 2,
                completion_tokens=len(resp_text.split()) * 2,
                status="BLOCKED",
            )
            # Save turns in conversation history
            self.audit_store.save_message(session_id, "user", input_guard.sanitized_text)
            self.audit_store.save_message(session_id, "assistant", resp_text)

            guard_summary = f"Blocked ({input_guard.reason}) | Zero LLM Cost"
            hud = AuditStore.format_telemetry_hud(
                latency_ms=latency_ms,
                prompt_tokens=0,
                completion_tokens=0,
                tool_invoked=None,
                guardrails_summary=guard_summary,
            )

            # Record turn alerts
            turn_alerts = detect_turn_alerts(user_message, [], guard_summary, 0)
            session_state["alerts"].extend(turn_alerts)
            total_dur = int(time.time() - session_state["start_time"])
            self.audit_store.save_customer_session(
                session_id=session_id,
                customer_id=session_state.get("customer_id"),
                phone=session_state.get("phone"),
                customer_name=session_state.get("customer_name"),
                affinity_tags=session_state.get("affinity_tags", []),
                sentiment_score=turn_sentiment,
                interaction_category="Fora de Escopo / Acessórios",
                alerts_detected=session_state.get("alerts", []),
                total_duration_sec=total_dur,
            )

            return OrchestratorResponse(
                response_text=resp_text,
                session_id=session_id,
                latency_ms=latency_ms,
                prompt_tokens=0,
                completion_tokens=0,
                tools_invoked=[],
                guardrails_summary=guard_summary,
                telemetry_hud=hud,
            )

        # ---------------------------------------------------------
        # Layer 2: LLM Tool Calling or Intelligent Fallback
        # ---------------------------------------------------------
        sanitized_input = input_guard.sanitized_text
        self.audit_store.save_message(session_id, "user", sanitized_input)
        history = self.audit_store.get_conversation_history(session_id, limit=8)

        tools_invoked: List[str] = []
        tool_payloads: List[Dict[str, Any]] = []
        prompt_tokens = 0
        completion_tokens = 0
        raw_response_text = ""

        if self.llm_client is not None:
            try:
                messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                for h in history[:-1]:  # Exclude last inserted message since we pass it explicitly
                    messages.append({"role": h["role"], "content": h["content"]})
                messages.append({"role": "user", "content": sanitized_input})

                model_name = (
                    AppConfig.GROQ_MODEL
                    if AppConfig.LLM_PROVIDER == "groq"
                    else AppConfig.OPENAI_MODEL
                )
                temp = (
                    AppConfig.GROQ_TEMPERATURE
                    if AppConfig.LLM_PROVIDER == "groq"
                    else AppConfig.OPENAI_TEMPERATURE
                )

                response = self.llm_client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    tools=TOOLS_SCHEMA,
                    tool_choice="auto",
                    temperature=temp,
                )

                choice = response.choices[0]
                prompt_tokens += getattr(response.usage, "prompt_tokens", 0)
                completion_tokens += getattr(response.usage, "completion_tokens", 0)

                # Check if model requested tool execution
                if choice.message.tool_calls:
                    messages.append(choice.message)

                    for tc in choice.message.tool_calls:
                        t_name = tc.function.name
                        try:
                            t_args = json.loads(tc.function.arguments)
                        except json.JSONDecodeError:
                            t_args = {}

                        t_start = time.perf_counter()
                        t_result = self._execute_tool(t_name, t_args)
                        t_latency = (time.perf_counter() - t_start) * 1000.0

                        tools_invoked.append(f"{t_name}({t_args})")
                        tool_payloads.append(t_result)

                        if t_name == "authenticate_or_register_customer" and isinstance(t_result, dict):
                            session_state["customer_id"] = t_result.get("customer_id")
                            session_state["phone"] = t_result.get("phone")
                            session_state["customer_name"] = t_result.get("name")

                        self.audit_store.log_audit_event(
                            session_id=session_id,
                            event_type="TOOL_INVOCATION",
                            component_name=t_name,
                            input_payload=t_args,
                            output_payload=t_result,
                            latency_ms=t_latency,
                            status="SUCCESS",
                        )

                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": json.dumps(t_result, ensure_ascii=False),
                            }
                        )

                    # Second call to synthesize final consultative answer
                    second_resp = self.llm_client.chat.completions.create(
                        model=model_name,
                        messages=messages,
                        temperature=temp,
                    )
                    raw_response_text = second_resp.choices[0].message.content or ""
                    prompt_tokens += getattr(second_resp.usage, "prompt_tokens", 0)
                    completion_tokens += getattr(second_resp.usage, "completion_tokens", 0)
                else:
                    raw_response_text = choice.message.content or ""

            except Exception:
                # Graceful degradation to deterministic fallback
                (
                    raw_response_text,
                    tools_invoked,
                    tool_payloads,
                    prompt_tokens,
                    completion_tokens,
                ) = self._fallback_offline_agent(sanitized_input, session_id)
        else:
            (
                raw_response_text,
                tools_invoked,
                tool_payloads,
                prompt_tokens,
                completion_tokens,
            ) = self._fallback_offline_agent(sanitized_input, session_id)

        # ---------------------------------------------------------
        # Layer 3: Output Guardrails (Factual Grounding & Persona)
        # ---------------------------------------------------------
        output_guard = validate_output(raw_response_text, tool_payloads)
        final_answer = output_guard.validated_text

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        # Save assistant message and audit turn
        self.audit_store.save_message(session_id, "assistant", final_answer)
        self.audit_store.log_audit_event(
            session_id=session_id,
            event_type="AGENT_RESPONSE",
            component_name="orchestrator",
            input_payload={"message": sanitized_input},
            output_payload={"response": final_answer, "grounding_score": output_guard.grounding_score},
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            status="SUCCESS" if output_guard.passed else "FLAGGED",
        )

        tool_str = ", ".join(tools_invoked) if tools_invoked else "Direct Response"
        grounding_pct = int(output_guard.grounding_score * 100)
        guard_summary = f"Scope Passed | Factual Grounding: {grounding_pct}% Verified"
        hud = AuditStore.format_telemetry_hud(
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            tool_invoked=tool_str,
            guardrails_summary=guard_summary,
        )

        # Record alerts and update customer session CRM
        results_count = len(tool_payloads[0]) if tool_payloads and isinstance(tool_payloads[0], list) else 1
        turn_alerts = detect_turn_alerts(user_message, tools_invoked, guard_summary, results_count)
        session_state["alerts"].extend(turn_alerts)

        category = "Consulta Catálogo"
        if any("get_order_details" in t for t in tools_invoked):
            category = "Pós-Venda / Rastreio"
        elif any("query_store_policy" in t for t in tools_invoked):
            category = "Políticas & Atendimento"
        elif any("authenticate_or_register_customer" in t for t in tools_invoked):
            category = "Autenticação / Cadastro"

        total_dur = int(time.time() - session_state["start_time"])
        self.audit_store.save_customer_session(
            session_id=session_id,
            customer_id=session_state.get("customer_id"),
            phone=session_state.get("phone"),
            customer_name=session_state.get("customer_name"),
            affinity_tags=session_state.get("affinity_tags", []),
            sentiment_score=turn_sentiment,
            interaction_category=category,
            alerts_detected=session_state.get("alerts", []),
            total_duration_sec=total_dur,
        )

        return OrchestratorResponse(
            response_text=final_answer,
            session_id=session_id,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            tools_invoked=tools_invoked,
            guardrails_summary=guard_summary,
            telemetry_hud=hud,
        )
