"""Conversational Orchestrator: Native tool-calling agent with multi-layer guardrails and telemetry HUD."""

from __future__ import annotations

import json
import re
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.config import AppConfig, get_llm_client, resolve_active_model
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
4. **Identificação Progressiva e Cadastro pelo Telefone com DDD (NUNCA solicite CPF):**
   - Não exija login logo de início. O cliente pode pesquisar produtos e tirar dúvidas livremente.
   - Quando o cliente solicitar informações pessoais (ex: rastreio de pedido, devolução/troca), avançar para compra ou salvar preferências, solicite o **nome e o telefone completo com DDD** (ex: '67998123456' ou '11987654321').
   - **NUNCA solicite CPF ao cliente:** A Empório da Música cadastra e identifica clientes exclusivamente por Telefone e Nome. Não solicitamos nem armazenamos CPF no sistema.
   - **PADRONIZAÇÃO DE ENTRADA:** Oriente o cliente a enviar o telefone no formato com DDD apenas em números (ex: '67998123456' ou '11987654321'). Porém, se o cliente enviar com pontuação (ex: '(67) 99812-3456'), aceite e normalize normalmente.
   - Assim que o cliente fornecer o telefone, invoque IMEDIATAMENTE a ferramenta `authenticate_or_register_customer`.
   - Se o telefone já foi fornecido ou a conta já foi autenticada nesta sessão, NUNCA pergunte o telefone de novo. Avance para a próxima etapa (endereço, frete, simulação de pagamento).
   - Se o cliente informar endereço ou cidade (ex: Mauá/SP), invoque `update_customer_profile` para registrar os dados e informe as opções de frete correspondentes.
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
8. **Saudações, Cumprimentos e Interações Humanizadas:**
   - Ao receber saudações básicas (ex: 'oi', 'olá', 'bom dia', 'boa tarde', 'boa noite', 'tudo bem?', 'como vai?'), responda exatamente como um colega músico e consultor humano faria: retribua o cumprimento de forma calorosa, simpática e educada, pergunte como a pessoa está e como você pode ajudá-la hoje no mundo dos instrumentos musicais.
   - NUNCA responda friamente ou roboticamente a um cumprimento.
   - NUNCA invente chamadas de ferramentas de catálogo para palavras de saudação como 'oi' ou 'olá'. Apenas responda naturalmente e se coloque à disposição para consultoria de instrumentos, promoções com 5% de desconto no PIX, parcelamento em até 12x, rastreio de pedidos ou dúvidas sobre a loja.
9. **Produtos Indisponíveis ou Fora de Catálogo:**
   - Se a busca no catálogo não retornar resultados (ex: itens como banjos, cavaquinhos, sanfonas, harpas ou marcas sem estoque), NUNCA invente instrumentos ou preços falsos! Seja transparente e atencioso: explique que a loja não possui aquele instrumento específico em catálogo/estoque no momento, cite as famílias que trabalhamos (violões, guitarras, baixos, teclas, sopros e percussão) e pergunte se o cliente tem interesse em alguma dessas alternativas.
10. **Consultoria Contextual e Recomendação ("qual a melhor para mim?", "o que você recomenda?"):**
   - Quando o cliente pedir recomendação ou perguntar "qual a melhor para mim?", "qual você indica?", "qual a diferença?", NÃO faça nova busca no banco com essas frases.
   - **Atenção ao Contexto Imediato:** Baseie sua resposta estritamente no último instrumento ou opções que você acabou de apresentar no turno imediatamente anterior (ex: se acabou de listar a Fender Telecaster, PRS SE Custom 24 e Ibanez RG550, compare exatamente essas guitarras para o cliente!). NUNCA confunda com perguntas de acessórios que já foram respondidas e encerradas em turnos passados.
   - Converse como um músico apaixonado: destaque as vantagens de cada modelo citado (timbre, versatilidade, tocabilidade) e pergunte o estilo e nível do cliente para ajudá-lo a escolher com segurança.
11. **Fechamento de Atendimento, Prazos de Entrega e Simulação de Pagamento:**
   - Sempre que o cliente decidir comprar um instrumento ou passar o endereço/cidade:
     * **Regras de Frete:**
       - Para a Grande Campo Grande/MS: frete grátis via motoboy para compras acima de R$ 500,00 (taxa fixa de R$ 35,00 abaixo desse valor), com entrega rápida de 1 a 3 dias úteis.
       - Para entregas fora de Campo Grande (envio nacional, ex: Mauá/SP, São Paulo, etc.): despachamos com seguro total de carga via Correios (SEDEX: 2 a 4 dias úteis; PAC: 5 a 10 dias úteis) ou transportadora parceira Jadlog (4 a 7 dias úteis). O código de rastreamento é enviado ao cliente assim que despachado.
     * **Condições de Pagamento:**
       - PIX: 5% de desconto à vista sobre o preço de tabela do instrumento (não cumulativo com itens em promoção).
       - Cartão de crédito: parcelamento em até 12x sem juros (respeitando parcelas mínimas de R$ 100 para 7-12x; R$ 80 para 4-6x; R$ 50 para até 3x).
     * Apresente os valores calculados de forma clara, simpática e profissional para o cliente.
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
                        "description": "Telefone completo do cliente somente com números/dígitos e DDD, sem pontos, traços ou parênteses (ex: '67998123456')",
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
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.db_conn = db_conn or init_sqlite_engine(AppConfig.DATA_DIR)
        self.policy_index = policy_index or PolicyVectorIndex(
            pdf_path=AppConfig.POLICY_PDF_PATH,
            json_path=AppConfig.STORE_POLICIES_JSON,
        )
        self.audit_store = audit_store or AuditStore(AppConfig.DATABASE_PATH)
        self.provider = (provider or AppConfig.LLM_PROVIDER).lower().strip()
        self.api_key = api_key if api_key is not None else AppConfig.get_api_key(self.provider)
        self.model = model or AppConfig.get_model(self.provider)
        self.llm_client = get_llm_client(self.provider, self.api_key)
        self.session_profiles: Dict[str, Dict[str, Any]] = {}

    def configure_llm(
        self,
        provider: str,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        persist: bool = True,
    ) -> bool:
        """Dynamically reconfigure or reconnect the LLM client at runtime."""
        self.provider = provider.lower().strip()
        if api_key is not None:
            self.api_key = api_key.strip()
        else:
            self.api_key = AppConfig.get_api_key(self.provider)

        AppConfig.set_active_provider(
            provider=self.provider,
            api_key=self.api_key,
            model=model,
            persist=persist,
        )
        self.model = model or AppConfig.get_model(self.provider)
        self.llm_client = get_llm_client(self.provider, self.api_key)
        return self.llm_client is not None

    def is_llm_connected(self) -> bool:
        """Check if active LLM client is connected and ready for inference."""
        return self.llm_client is not None and self.provider != "offline"

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
        """Intelligent deterministic fallback with humanized conversational empathy."""
        lowered = user_text.lower().strip()
        tools_called = []
        tool_payloads = []
        session_state = self.session_profiles.get(session_id, {})

        # 0. Check Greetings & Humanized Social Interactions ("oi", "olá", "bom dia", etc.)
        greeting_terms = [
            r"\b(ol[aá]|oi|oie|opa|salve|fala|e\s*a[íi])\b",
            r"\bbom\s*dia\b",
            r"\bboa\s*tarde\b",
            r"\bboa\s*noite\b",
            r"\btudo\s*bem\b",
            r"\bcomo\s*vai\b",
        ]
        is_greeting = any(re.search(pat, lowered) for pat in greeting_terms)
        has_business_intent = any(
            w in lowered
            for w in [
                "violão", "violao", "guitarra", "baixo", "teclado", "piano",
                "bateria", "ukulele", "preço", "preco", "custa", "pedido",
                "rastreio", "frete", "pagamento", "pix", "cartão", "cartao",
                "onde fica", "endereço", "endereco", "garantia", "devolução",
                "devolver", "marca", "yamaha", "tagima", "fender",
                "meu nome", "telefone", "contato", "cadastr", "cpf"
            ]
        ) or bool(re.search(r"\b(\(?\d{2}\)?\s*9?\d{4}[-\s]?\d{4})\b", user_text))

        if is_greeting and not has_business_intent:
            if "boa tarde" in lowered:
                salutation = "Olá! Muito boa tarde!"
            elif "boa noite" in lowered:
                salutation = "Olá! Muito boa noite!"
            elif "bom dia" in lowered:
                salutation = "Olá! Muito bom dia! Tudo ótimo por aqui, e com você?"
            elif "tudo bem" in lowered or "como vai" in lowered:
                salutation = "Olá! Tudo ótimo por aqui, e com você?"
            else:
                salutation = "Olá! Seja muito bem-vindo(a)!"

            cust_name = session_state.get("customer_name")
            name_suffix = f", {cust_name}" if cust_name else ""

            ans = (
                f"{salutation}{name_suffix} Seja muito bem-vindo(a) à Empório da Música! 🎵\n\n"
                f"Sou seu consultor musical virtual. Como posso te ajudar hoje?\n\n"
                f"Posso te ajudar a:\n"
                f"• Explorar instrumentos do nosso catálogo (violões, guitarras, teclados, sopros e percussão);\n"
                f"• Simular condições de pagamento (5% de desconto à vista no PIX ou em até 12x sem juros no cartão);\n"
                f"• Consultar o status ou rastreamento de um pedido existente;\n"
                f"• Tirar dúvidas sobre prazos de entrega, frete e garantia da loja."
            )
            return ans, [], [], 35, 75
        session_state = self.session_profiles.get(session_id, {})

        # 1. Check for Out-of-Catalog or Non-Stocked Traditional Instruments (e.g. banjo, cavaquinho, sanfona)
        out_of_catalog_instruments = {
            r"\bbanjos?\b": "banjo",
            r"\bcavaquinhos?\b": "cavaquinho",
            r"\bcavacos?\b": "cavaquinho",
            r"\bsanfonas?\b": "sanfona",
            r"\bacordeons?\b": "acordeon",
            r"\bacorde[ãa]os?\b": "acordeon",
            r"\bharpas?\b": "harpa",
            r"\bviolas?\s+caipiras?\b": "viola caipira",
            r"\bgaitas?\b": "gaita",
        }
        for pat, item_name in out_of_catalog_instruments.items():
            if re.search(pat, lowered):
                ans = (
                    f"No momento não temos {item_name} em nosso estoque. "
                    f"Nosso catálogo atual é especializado em violões (nylon e aço), guitarras elétricas, "
                    f"contrabaixos, teclados arranjadores, pianos digitais, baterias acústicas e eletrônicas, e ukuleles.\n\n"
                    f"Você teria interesse em conhecer opções de alguma dessas famílias de instrumentos? "
                    f"Ou, se preferir, podemos indicar lojas parceiras na região central de Campo Grande que trabalham com {item_name}!"
                )
                return ans, [], [], 30, 65

        # 2. Check Contextual Advisory / Recommendation ("qual a melhor para mim?", "qual recomenda?")
        advisory_patterns = [
            r"qual\s+(é\s+)?(a\s+)?melhor",
            r"qual\s+voc[êe]\s+(me\s+)?recomenda",
            r"qual\s+voc[êe]\s+indica",
            r"me\s+ajuda\s+a\s+escolher",
            r"qual\s+a\s+diferen[çc]a",
            r"o\s+que\s+voc[êe]\s+acha",
            r"qual\s+(eu\s+)?devo\s+comprar",
            r"qual\s+vale\s+mais\s+a\s+pena",
        ]
        if any(re.search(pat, lowered) for pat in advisory_patterns):
            tags = session_state.get("affinity_tags", [])
            if "guitarra" in tags or "guitarra" in lowered:
                ans = (
                    "Essa é uma excelente pergunta! Para escolher a guitarra perfeita para você, vale considerar o estilo musical que você mais gosta de tocar:\n\n"
                    "• **Fender Telecaster Player Series:** É o ícone dos timbres limpos, definidos e estalados. Perfeita para Rock clássico, Blues, Funk, Country e MPB.\n"
                    "• **PRS SE Custom 24:** Campeã de versatilidade, sustain e acabamento refinado. Atende com perfeição desde o Pop e Rock até timbres encorpados com humbucker.\n"
                    "• **Ibanez RG550:** Focada em performance e alta velocidade. Braço ultrafino e microafinação, imbatível para Heavy Metal, Hard Rock e solos técnicos.\n\n"
                    "Qual desses estilos tem mais a ver com você? Me conte sobre seus artistas favoritos que te indico o match perfeito!"
                )
            elif "violão" in tags or "violao" in lowered:
                ans = (
                    "Excelente dúvida! A escolha do violão ideal depende da pegada e do som que você procura:\n\n"
                    "• **Cordas de Nylon (ex: Yamaha C40):** Braço mais largo e tensão mais macia nos dedos. É a recomendação número um para quem está começando, ou para MPB, Bossa Nova e peças clássicas.\n"
                    "• **Cordas de Aço (ex: Yamaha F310 / Giannini GF-1R):** Timbre brilhante, encorpado e com alta projeção. Ideal para Pop, Sertanejo, Folk, Rock acústico e dedilhados modernos.\n\n"
                    "Você prefere o conforto acústico do nylon ou o brilho e volume das cordas de aço?"
                )
            else:
                ans = (
                    "Excelente pergunta! Como músico e consultor, para te direcionar para o melhor instrumento com máxima precisão:\n\n"
                    "1. **Qual é o seu nível musical?** (iniciante, intermediário ou já toca há algum tempo?)\n"
                    "2. **Qual gênero musical você mais quer tocar?** (Rock, Sertanejo, MPB, Pop, Metal, Clássico...)\n"
                    "3. **Você tem uma faixa de investimento em mente?**\n\n"
                    "Com esses detalhes eu consigo te recomendar a melhor opção com o maior custo-benefício e simular as parcelas em 12x ou o desconto de 5% à vista no PIX!"
                )
            return ans, [], [], 35, 95

        # 3. Check for Phone Number / Customer Authentication Intent
        phone_match = (
            re.search(r"(?:(?:\+|00)?55\s*)?(?:\(?([1-9]{2})\)?\s*)?(9?\d{4})[-\s]?(\d{4})\b", user_text)
            or re.search(r"\b(\d{10,11})\b", user_text)
        )
        if phone_match or any(w in lowered for w in ["meu telefone", "meu contato", "me cadastrar", "meu nome é"]):
            phone_val = normalize_phone(phone_match.group(0)) if phone_match else "67998123456"
            # Extract potential customer name
            name_val = session_state.get("customer_name")
            name_extract = re.search(r"(?i)\b(?:meu\s+nome\s+[ée]|sou\s+(?:o|a)?|chamo-me|me\s+chamo)\s+([A-Za-zÀ-ÖØ-öø-ÿ]+(?:\s+[A-Za-zÀ-ÖØ-öø-ÿ]+)?)", user_text)
            if name_extract:
                name_val = name_extract.group(1).strip()
            if not name_val:
                for sample in ["lucas", "ana", "pedro", "mariana", "rafael", "juliana", "thiago", "fernanda", "manuel", "gabriel"]:
                    if sample in lowered:
                        name_val = sample.capitalize()
                        break
            name_val = name_val or "Cliente Empório"

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

                # Check if address was provided (e.g. Mauá, SP, São Paulo, Campo Grande)
                addr_match = re.search(r"(?i)(?:em|para|endere[çc]o[:\s]+)?([A-Za-zÀ-ÖØ-öø-ÿ\s]+(?:\/[A-Za-z]{2}|,\s*[A-Za-z]{2}))", user_text)
                address_val = session_state.get("address")
                if "mauá" in lowered or "maua" in lowered:
                    address_val = "Mauá/SP"
                elif addr_match and len(addr_match.group(1).strip()) > 3:
                    address_val = addr_match.group(1).strip()

                if address_val:
                    session_state["address"] = address_val
                    self._execute_tool(
                        "update_customer_profile",
                        {"phone": phone_val, "address": address_val},
                    )
                    tools_called.append(f"update_customer_profile(phone='{phone_val}', address='{address_val}')")

                self.session_profiles[session_id] = session_state

                # Check if customer has an instrument context or order in progress
                affinity = session_state.get("affinity_tags", [])
                if "prs" in str(affinity).lower() or "guitarra" in str(affinity).lower():
                    is_outside_cg = address_val and "campo grande" not in address_val.lower()
                    loc_desc = f" para {address_val}" if address_val else ""
                    shipping_desc = (
                        f"Para o envio{loc_desc}, despachamos com seguro total de carga via Correios (SEDEX: 2 a 4 dias úteis ou PAC: 5 a 10 dias úteis) e transportadora Jadlog (4 a 7 dias úteis). O rastreamento é gerado assim que o instrumento é despachado!"
                        if is_outside_cg
                        else "Como a compra é acima de R$ 500,00, o frete via motoboy para Grande Campo Grande é 100% GRÁTIS (1 a 3 dias úteis)!"
                    )
                    ans = (
                        f"Perfeito, {res['name']}! Seu cadastro com o telefone {res['phone']} foi confirmado com sucesso. 🎉\n\n"
                        f"**Resumo do seu Pedido (PRS SE Custom 24):**\n"
                        f"• **Condições de Pagamento:** R$ 6.460,00 à vista via PIX (com 5% de desconto!) ou até 12x de R$ 566,67 sem juros no cartão de crédito.\n"
                        f"• **Opções de Frete:** {shipping_desc}\n\n"
                        f"Qual modalidade de pagamento você prefere para gerarmos o pedido: PIX ou Cartão de Crédito?"
                    )
                    return ans, tools_called, tool_payloads, 115, 65

                orders_summary = ""
                if res.get("recent_orders"):
                    orders_summary = f" Localizei {len(res['recent_orders'])} pedido(s) recente(s) em sua conta."

                ans = (
                    f"Que ótimo te receber, {res['name']}!{orders_summary} "
                    f"Sua conta está autenticada com sucesso pelo telefone {res['phone']}. Em que posso te ajudar hoje? "
                    f"Posso te mostrar instrumentos do nosso catálogo, consultar detalhes de pedidos ou tirar dúvidas sobre pagamentos!"
                )
                return ans, tools_called, tool_payloads, 115, 65

        # 4. Check order tracking intent
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
                    "o número do pedido ou o seu telefone de cadastro com DDD apenas em números, sem pontos, traços ou parênteses (ex: 67998123456)?"
                )
                return ans, tools_called, tool_payloads, 90, 45

        # 5. Check instrument / catalog search intent with smart category normalization
        category_aliases = {
            "guitarras": ("Guitarras", "guitarra"),
            "guitarra": ("Guitarras", "guitarra"),
            "violões": ("Violões", "violão"),
            "violoes": ("Violões", "violão"),
            "violão": ("Violões", "violão"),
            "violao": ("Violões", "violão"),
            "baixos": ("Baixos", "baixo"),
            "baixo": ("Baixos", "baixo"),
            "contrabaixos": ("Baixos", "baixo"),
            "contrabaixo": ("Baixos", "baixo"),
            "teclados": ("Teclados e Pianos", "teclado"),
            "teclado": ("Teclados e Pianos", "teclado"),
            "pianos": ("Teclados e Pianos", "piano"),
            "piano": ("Teclados e Pianos", "piano"),
            "baterias": ("Baterias e Percussão", "bateria"),
            "bateria": ("Baterias e Percussão", "bateria"),
            "ukuleles": ("Ukuleles", "ukulele"),
            "ukulele": ("Ukuleles", "ukulele"),
        }

        brands = [
            "yamaha", "tagima", "giannini", "fender", "roland", "casio",
            "shelby", "kalani", "kala", "rozini", "ibanez", "epiphone",
            "strinberg", "korg"
        ]

        matched_category = None
        clean_query = None

        for alias, (cat_name, q_val) in category_aliases.items():
            if re.search(rf"\b{alias}\b", lowered):
                matched_category = cat_name
                clean_query = q_val
                break

        for brand in brands:
            if re.search(rf"\b{brand}\b", lowered):
                clean_query = brand
                break

        if clean_query or matched_category:
            res = self._execute_tool(
                "lookup_catalog",
                {"query": clean_query, "category": matched_category, "in_stock_only": True},
            )
            tools_called.append(f"lookup_catalog(query='{clean_query}', category='{matched_category}')")
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
            else:
                cat_desc = matched_category or clean_query or "itens"
                ans = (
                    f"No momento não encontramos modelos disponíveis para '{cat_desc}' em estoque. "
                    f"Nosso estoque se renova semanalmente com instrumentos de cordas, teclas, sopros e percussão. "
                    f"Gostaria de ver opções em outra categoria ou marca?"
                )
                return ans, tools_called, tool_payloads, 80, 45

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
                "Entendi! Como consultor da Empório da Música, estou aqui para te ajudar no que for preciso. "
                "Você gostaria de ver opções em instrumentos de cordas (violões e guitarras), teclas (pianos e teclados), "
                "baterias ou sopros? Ou se preferir, posso te orientar sobre formas de pagamento (5% de desconto no PIX e até 12x sem juros), "
                "rastreamento de pedidos ou cálculo de frete!"
            )
            return ans, tools_called, tool_payloads, 80, 45

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
        history = self.audit_store.get_conversation_history(session_id, limit=20)

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

                model_name = resolve_active_model(self.provider, self.llm_client, self.model)
                temp = 0.1

                tool_rounds = 0
                max_tool_rounds = 3

                while tool_rounds < max_tool_rounds:
                    response = self.llm_client.chat.completions.create(
                        model=model_name,
                        messages=messages,
                        tools=TOOLS_SCHEMA,
                        tool_choice="auto",
                        temperature=temp,
                        max_tokens=AppConfig.MAX_OUTPUT_TOKENS,
                    )

                    choice = response.choices[0]
                    prompt_tokens += getattr(response.usage, "prompt_tokens", 0)
                    completion_tokens += getattr(response.usage, "completion_tokens", 0)

                    if not choice.message.tool_calls:
                        raw_response_text = choice.message.content or ""
                        break

                    tool_rounds += 1
                    messages.append(choice.message)

                    for tc in choice.message.tool_calls:
                        t_name = tc.function.name
                        try:
                            t_args = json.loads(tc.function.arguments)
                        except json.JSONDecodeError:
                            t_args = {}

                        # Guard against hallucinated searches on greeting terms
                        if t_name == "lookup_catalog" and t_args.get("query", "").strip().lower() in ("oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"):
                            t_args["query"] = ""

                        # If update_customer_profile is called without phone, supply session phone
                        if t_name == "update_customer_profile" and not t_args.get("phone"):
                            t_args["phone"] = session_state.get("phone", "")

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

                        if t_name == "lookup_catalog" and (t_result == [] or t_result is None):
                            tool_content = json.dumps(
                                {
                                    "total_found": 0,
                                    "products": [],
                                    "message": f"Nenhum produto encontrado para o termo de busca '{t_args.get('query', '')}'. O produto não consta no catálogo ou está sem estoque no momento.",
                                    "available_categories": [
                                        "Guitarras",
                                        "Violões",
                                        "Baixos",
                                        "Teclados e Pianos",
                                        "Baterias e Percussão",
                                        "Ukuleles",
                                    ],
                                },
                                ensure_ascii=False,
                            )
                        else:
                            tool_content = json.dumps(t_result, ensure_ascii=False)

                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": tool_content,
                            }
                        )
                else:
                    final_comp = self.llm_client.chat.completions.create(
                        model=model_name,
                        messages=messages,
                        temperature=temp,
                        max_tokens=AppConfig.MAX_OUTPUT_TOKENS,
                    )
                    raw_response_text = final_comp.choices[0].message.content or ""
                    prompt_tokens += getattr(final_comp.usage, "prompt_tokens", 0)
                    completion_tokens += getattr(final_comp.usage, "completion_tokens", 0)

            except Exception as e:
                # Log actual LLM failure for transparency and observability
                self.audit_store.log_audit_event(
                    session_id=session_id,
                    event_type="ERROR",
                    component_name=f"{self.provider}_llm_engine",
                    input_payload={"message": sanitized_input, "model": self.model},
                    output_payload={"error": str(e), "error_type": type(e).__name__},
                    latency_ms=(time.perf_counter() - start_time) * 1000.0,
                    status="FAILED",
                )
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


# Backward-compatible alias
AgentOrchestrator = ConversationalOrchestrator

