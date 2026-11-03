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

# Valid Brazilian Area Codes (DDDs)
VALID_BRAZILIAN_DDDS = {
    "11", "12", "13", "14", "15", "16", "17", "18", "19",
    "21", "22", "24", "27", "28",
    "31", "32", "33", "34", "35", "37", "38",
    "41", "42", "43", "44", "45", "46", "47", "48", "49",
    "51", "53", "54", "55",
    "61", "62", "63", "64", "65", "66", "67", "68", "69",
    "71", "73", "74", "75", "77", "79",
    "81", "82", "83", "84", "85", "86", "87", "88", "89",
    "91", "92", "93", "94", "95", "96", "97", "98", "99",
}


def is_brazilian_phone(text: str) -> bool:
    """Verify if numeric sequence represents a valid Brazilian mobile or landline."""
    clean = re.sub(r"\D", "", str(text))
    # 11 digits: DDD + 9 + 8 digits (mobile)
    if len(clean) == 11 and clean[:2] in VALID_BRAZILIAN_DDDS and clean[2] == "9":
        return True
    # 10 digits: DDD + 8 digits (landline)
    if len(clean) == 10 and clean[:2] in VALID_BRAZILIAN_DDDS and clean[2] in "2345":
        return True
    return False


def is_valid_cpf_checksum(cpf: str) -> bool:
    """Verify Brazilian CPF modulo-11 checksum."""
    digits = re.sub(r"\D", "", str(cpf))
    if len(digits) != 11 or digits == digits[0] * 11:
        return False
    s1 = sum(int(digits[i]) * (10 - i) for i in range(9))
    d1 = 11 - (s1 % 11)
    d1 = 0 if d1 >= 10 else d1
    if int(digits[9]) != d1:
        return False
    s2 = sum(int(digits[i]) * (11 - i) for i in range(10))
    d2 = 11 - (s2 % 11)
    d2 = 0 if d2 >= 10 else d2
    return int(digits[10]) == d2


# Regex for Brazilian Formatted CPF: XXX.XXX.XXX-XX
FORMATTED_CPF_REGEX = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")

# Regex for Explicit CPF declaration (e.g., "CPF: 12345678900", "meu CPF é 12345678900")
EXPLICIT_CPF_REGEX = re.compile(r"(?i)\b(?:cpf|documento)\b[:\s=]*(\d{3}\.?\d{3}\.?\d{3}-?\d{2}|\d{11})\b")

# Regex for Standalone 11-digit numbers
RAW_11_DIGIT_REGEX = re.compile(r"\b\d{11}\b")

# Regex for Credit Card numbers: 13 to 19 digits with optional spaces/dashes
CREDIT_CARD_REGEX = re.compile(r"\b(?:\d[ -]*?){13,19}\b")

# Prompt injection patterns
PROMPT_INJECTION_PATTERNS = [
    r"(?:ignore|esque[çc]a|desconsidere)\s+(?:todas\s+as\s+)?(?:suas\s+)?instru[çc][õo]es(?:\s+anteriores)?",
    r"ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions",
    r"voc[êe]\s+agora\s+[ée]\s+(?:dan|jailbreak|outro|um\s+assistente\s+geral)",
    r"(?:system\s*prompt|prompt\s+do\s+sistema)",
    r"(?:reveal|print|show)\s+(?:your\s+)?system\s+instructions",
    r"(?:revele|mostre|print)\s+(?:as\s+)?(?:suas\s+)?instru[çc][õo]es",
    r"modo\s+(?:desenvolvedor|developer|dan|livre)",
    r"(?:escreva|fa[çc]a|crie)\s+um\s+script\s+(?:em\s+python|de\s+scraping|para\s+scraping)",
    r"\bscraping\b",
    r"\bjailbreak\b",
]

# Non-musical product categories and unrelated retail items
OUT_OF_SCOPE_PRODUCTS = [
    r"\bcelular(es)?\b",
    r"\bsmartphones?\b",
    r"\beletr[ôo]nicos?\b",
    r"\binform[áa]tica\b",
    r"\bcomputador(es)?\b",
    r"\bnotebooks?\b",
    r"\btelevis[õo]es\b",
    r"\btvs?\b",
    r"\broupas?\b",
    r"\bcal[çc]ados?\b",
    r"\beletrodom[ée]sticos?\b",
    r"\brem[ée]dios?\b",
    r"\bfarm[áa]cia\b",
    r"\bcomida\b",
    r"\blanches?\b",
    r"\bpizza\b",
]

OUT_OF_SCOPE_PRODUCT_REFUSAL_MESSAGE = (
    "Na Empório da Música somos especialistas e atendemos exclusivamente o universo dos instrumentos musicais "
    "(como violões, guitarras, contrabaixos, teclados, pianos, baterias, sopros e percussão). "
    "Não comercializamos celulares, eletrônicos de uso geral, produtos de informática ou outros itens fora do segmento musical.\n\n"
    "Posso te ajudar a encontrar algum instrumento musical do nosso catálogo hoje? 🎵"
)


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
    """Detect and mask Brazilian CPFs and credit card numbers while strictly preserving valid phone numbers.

    Returns:
        Tuple of (sanitized_text, pii_detected).
    """
    pii_found = False
    sanitized = text

    # 1. Mask credit cards first (since they are longer digit sequences)
    def mask_cc(match: re.Match) -> str:
        nonlocal pii_found
        raw_digits = re.sub(r"\D", "", match.group(0))
        if 13 <= len(raw_digits) <= 19:
            pii_found = True
            return "[CARTÃO PROTEGIDO]"
        return match.group(0)

    sanitized = CREDIT_CARD_REGEX.sub(mask_cc, sanitized)

    # 2. Mask explicitly formatted CPFs (XXX.XXX.XXX-XX)
    def mask_formatted_cpf(match: re.Match) -> str:
        nonlocal pii_found
        pii_found = True
        return "[CPF PROTEGIDO]"

    sanitized = FORMATTED_CPF_REGEX.sub(mask_formatted_cpf, sanitized)

    # 3. Mask explicit CPF declarations (e.g. "CPF: 12345678900", "meu CPF é 12345678900")
    def mask_explicit_cpf(match: re.Match) -> str:
        nonlocal pii_found
        pii_found = True
        return "[CPF PROTEGIDO]"

    sanitized = EXPLICIT_CPF_REGEX.sub(mask_explicit_cpf, sanitized)

    # 4. Handle standalone unformatted 11-digit numbers:
    # Disambiguate between Brazilian Phone Number and raw CPF
    def mask_raw_11(match: re.Match) -> str:
        nonlocal pii_found
        raw_val = match.group(0)
        digits = re.sub(r"\D", "", raw_val)

        # If it represents a valid Brazilian mobile or landline, preserve it as a business phone!
        if is_brazilian_phone(digits):
            return raw_val

        # If it's a valid CPF checksum and not a phone, mask it
        if is_valid_cpf_checksum(digits):
            pii_found = True
            return "[CPF PROTEGIDO]"

        return raw_val

    sanitized = RAW_11_DIGIT_REGEX.sub(mask_raw_11, sanitized)

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


def check_out_of_scope_product(text: str) -> bool:
    """Detect inquiries about non-musical product categories."""
    lowered = text.lower()
    for pattern in OUT_OF_SCOPE_PRODUCTS:
        if re.search(pattern, lowered):
            return True
    return False


def build_accessory_refusal(text: str) -> str:
    """Build a natural, contextual refusal message mentioning the asked accessory."""
    lowered = text.lower()
    mapping = {
        "baqueta": "baquetas",
        "baquetas": "baquetas",
        "corda": "cordas",
        "cordas": "cordas e encordoamentos",
        "encordoamento": "encordoamentos",
        "palheta": "palhetas",
        "palhetas": "palhetas",
        "cabo": "cabos e conectores",
        "cabos": "cabos",
        "pedal": "pedais de efeito",
        "pedais": "pedais de efeito",
        "pedaleira": "pedaleiras",
        "pedaleiras": "pedaleiras",
        "amplificador": "amplificadores",
        "amplificadores": "amplificadores",
        "afinador": "afinadores",
        "afinadores": "afinadores",
        "capa": "capas e bags",
        "capas": "capas e bags",
        "bag": "bags e cases",
        "case": "cases",
        "correia": "correias",
        "suporte": "suportes",
        "boquilha": "boquilhas",
        "pele": "peles de bateria",
    }
    found = []
    for k, v in mapping.items():
        if re.search(rf"\b{k}\b", lowered):
            if v not in found:
                found.append(v)
    if found:
        accessory_str = ", ".join(found)
        return (
            f"Na Empório da Música somos especialistas exclusivos em instrumentos musicais completos! "
            f"Não comercializamos acessórios ou peças avulsas como {accessory_str}. "
            f"Se você estiver em Campo Grande, podemos indicar lojas parceiras na região central (Rua 14 de Maio). "
            f"Posso te ajudar com a escolha de algum instrumento do nosso catálogo hoje? 🎵"
        )
    return ACCESSORY_REFUSAL_MESSAGE


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
                "Como consultor virtual da Empório da Música, meu atendimento é dedicado exclusivamente "
                "ao nosso catálogo de instrumentos musicais, pedidos, trocas e políticas da loja. "
                "Não posso seguir comandos externos, executar scripts ou desviar das diretrizes de atendimento da loja. "
                "Como posso te ajudar a encontrar o instrumento ideal para você hoje? 🎵"
            ),
            reason="PROMPT_INJECTION_ATTEMPT",
            pii_detected=pii_detected,
            blocked_category="SECURITY",
        )

    # 3. Deterministic Out-of-Scope Products Interceptor
    if check_out_of_scope_product(sanitized):
        return InputGuardResult(
            passed=False,
            sanitized_text=sanitized,
            intercept_response=OUT_OF_SCOPE_PRODUCT_REFUSAL_MESSAGE,
            reason="PRODUCT_OUT_OF_SCOPE",
            pii_detected=pii_detected,
            blocked_category="COMMERCIAL_SCOPE",
        )

    # 4. Deterministic Accessory Denial Interceptor
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
