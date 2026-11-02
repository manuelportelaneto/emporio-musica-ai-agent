"""Input Guardrails: Accessory inquiry interception, PII sanitization, and prompt injection defense."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

ACCESSORY_REFUSAL_MESSAGE = (
    "Na Empório da Música somos especialistas exclusivos em instrumentos musicais! "
    "Não comercializamos acessórios como cordas, palhetas, cabos, amplificadores ou capas. "
    "Se você estiver em Campo Grande, podemos indicar lojas parceiras na região central (Rua 14 de Maio). "
    "Posso te ajudar com a escolha de algum instrumento do nosso catálogo hoje?"
)

# Accessory keywords
ACCESSORY_KEYWORDS = [
    r"\bcordas?\b",
    r"\bencordoamentos?\b",
    r"\bpalhetas?\b",
    r"\bcabos?\b",
    r"\bpedais\b",
    r"\bpedal\b",
    r"\bpedaleiras?\b",
    r"\bamplificador(es)?\b",
    r"\bamps?\b",
    r"\bcaixas?\s+de\s+som\b",
    r"\bcases?\b",
    r"\bbags?\b",
    r"\bcapas?\b",
    r"\bafinador(es)?\b",
    r"\bcorreias?\b",
    r"\bsuportes?\b",
    r"\bcapotrastes?\b",
    r"\bbaquetas?\b",
    r"\bpeles?\s+de\s+bateria\b",
    r"\bboquilhas?\b",
]

# Patterns where "cordas" is just an instrument spec (e.g., "violão de cordas de nylon")
INSTRUMENT_SPEC_EXCEPTIONS = [
    r"viol[aã]o.*cordas",
    r"cordas.*(nylon|a[çc]o).*viol[aã]o",
    r"baixo.*(\d+)\s*cordas",
    r"guitarra.*(\d+)\s*cordas",
    r"cordas orquestrais",  # Category name in catalog
    r"instrumentos? de cordas?",
]

# Regex for Brazilian CPF: XXX.XXX.XXX-XX or 11 consecutive digits
CPF_REGEX = re.compile(r"\b(\d{3}\.\d{3}\.\d{3}-\d{2}|\d{11})\b")

# Regex for Credit Card numbers: 13 to 19 digits with optional spaces/dashes
CREDIT_CARD_REGEX = re.compile(r"\b(?:\d[ -]*?){13,19}\b")

# Prompt injection patterns
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"esque[çc]a\s+(todas\s+as\s+)?instru[çc][õo]es\s+anteriores",
    r"voc[êe]\s+agora\s+[ée]\s+(dan|jailbreak|outro)",
    r"system\s*prompt",
    r"reveal\s+(your\s+)?system\s+instructions",
    r"mostre\s+(as\s+)?suas\s+instru[çc][õo]es",
    r"modo\s+desenvolvedor",
]


@dataclass
class InputGuardResult:
    """Outcome of input guardrails evaluation."""

    passed: bool
    sanitized_text: str
    intercept_response: Optional[str] = None
    reason: Optional[str] = None
    pii_detected: bool = False
    blocked_category: Optional[str] = None


def mask_pii(text: str) -> Tuple[str, bool]:
    """Detect and mask Brazilian CPFs and credit card numbers.

    Returns:
        Tuple of (sanitized_text, pii_detected).
    """
    pii_found = False
    sanitized = text

    # Mask credit cards first (since they are longer sequences)
    def mask_cc(match: re.Match) -> str:
        nonlocal pii_found
        raw_digits = re.sub(r"\D", "", match.group(0))
        if 13 <= len(raw_digits) <= 19:
            pii_found = True
            return "[CARTÃO PROTEGIDO]"
        return match.group(0)

    sanitized = CREDIT_CARD_REGEX.sub(mask_cc, sanitized)

    # Mask CPF
    def mask_cpf(match: re.Match) -> str:
        nonlocal pii_found
        raw = match.group(0)
        digits = re.sub(r"\D", "", raw)
        if len(digits) == 11:
            pii_found = True
            return "[CPF PROTEGIDO]"
        return raw

    sanitized = CPF_REGEX.sub(mask_cpf, sanitized)

    return sanitized, pii_found


def check_accessory_inquiry(text: str) -> bool:
    """Determine whether the message is asking for accessories."""
    lowered = text.lower()

    # Check for instrument spec exceptions
    for exc in INSTRUMENT_SPEC_EXCEPTIONS:
        if re.search(exc, lowered):
            # If the user specifically asks "você vende cordas" or "tem palheta para violão", it's still an accessory
            if re.search(r"\b(vende|tem|comprar|pre[çc]o|quanto custa|valor|estoque)\b.*(palheta|corda|cabo|amplificador|afinador|pedal)", lowered):
                # Check if asking specifically for accessory purchase
                if not re.search(r"\b(viol[aã]o|guitarra|baixo|teclado|bateria)\b.*(novo|usado|pre[çc]o|indica[çc][aã]o|modelo)", lowered):
                    return True
            return False

    # Check for direct accessory inquiries
    for pattern in ACCESSORY_KEYWORDS:
        if re.search(pattern, lowered):
            # Check context: inquiry about buying/having
            inquiry_verbs = [
                r"\b(vende|vendem|tem|t[êe]m|comprar|pre[çc]o|quanto custa|valor|estoque|dispon[íi]vel)\b",
                r"\b(quero|preciso|busco|procuro|gostaria de)\b",
            ]
            for verb in inquiry_verbs:
                if re.search(verb, lowered):
                    return True

            # If isolated accessory noun or short message (e.g. "palhetas fender", "jogos de cordas")
            tokens = lowered.split()
            if len(tokens) <= 4:
                return True

    return False


def check_prompt_injection(text: str) -> bool:
    """Detect common prompt injection attacks."""
    lowered = text.lower()
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, lowered):
            return True
    return False


def validate_input(user_input: str) -> InputGuardResult:
    """Apply Layer 1 defense: PII masking, injection detection, and accessory interceptor.

    Args:
        user_input: Raw text string from the customer.

    Returns:
        InputGuardResult indicating whether processing may proceed.
    """
    if not user_input or not user_input.strip():
        return InputGuardResult(
            passed=False,
            sanitized_text="",
            intercept_response="Olá! Como posso ajudar você a encontrar o instrumento ideal hoje?",
            reason="EMPTY_INPUT",
        )

    # 1. PII Sanitization
    sanitized, pii_detected = mask_pii(user_input)

    # 2. Prompt Injection Defense
    if check_prompt_injection(sanitized):
        return InputGuardResult(
            passed=False,
            sanitized_text=sanitized,
            intercept_response=(
                "Como assistente da Empório da Música, estou aqui exclusivamente para te atender "
                "sobre nosso catálogo de instrumentos musicais, pedidos e políticas da loja. "
                "Como posso te ajudar com sua música hoje?"
            ),
            reason="PROMPT_INJECTION_ATTEMPT",
            pii_detected=pii_detected,
            blocked_category="SECURITY",
        )

    # 3. Deterministic Accessory Denial Interceptor
    if check_accessory_inquiry(sanitized):
        return InputGuardResult(
            passed=False,
            sanitized_text=sanitized,
            intercept_response=ACCESSORY_REFUSAL_MESSAGE,
            reason="ACCESSORY_OUT_OF_SCOPE",
            pii_detected=pii_detected,
            blocked_category="ACCESSORY_INTERCEPT",
        )

    return InputGuardResult(
        passed=True,
        sanitized_text=sanitized,
        intercept_response=None,
        reason=None,
        pii_detected=pii_detected,
    )
