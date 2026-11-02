"""Output Guardrails: Factual grounding verification and persona/tone modulation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class OutputGuardResult:
    """Outcome of output guardrails evaluation."""

    passed: bool
    validated_text: str
    modifications_made: bool = False
    warnings: List[str] = field(default_factory=list)
    grounding_score: float = 1.0


def extract_prices_from_text(text: str) -> List[float]:
    """Extract BRL currency amounts from generated response."""
    # Matches R$ 1.234,56 or R$ 599,90 or R$ 599.90
    matches = re.findall(r"R\$\s*([\d\.\,]+)", text)
    prices = []
    for m in matches:
        raw = m.strip().rstrip(".,;:!?")
        if "," in raw and "." in raw:
            cleaned = raw.replace(".", "").replace(",", ".")
        elif "," in raw:
            cleaned = raw.replace(",", ".")
        else:
            cleaned = raw
        try:
            val = float(cleaned)
            prices.append(val)
        except ValueError:
            continue
    return prices


def verify_factual_grounding(
    text: str,
    tool_outputs: List[Dict[str, Any]],
) -> Tuple[bool, List[str], float]:
    """Verify that cited prices and order statuses match executed tool payloads.

    Args:
        text: Agent's generated answer text.
        tool_outputs: List of raw payloads returned by executed tools.

    Returns:
        Tuple of (is_grounded, warnings, grounding_score).
    """
    warnings: List[str] = []
    if not tool_outputs:
        return True, warnings, 1.0

    valid_prices: set[float] = set()
    for payload in tool_outputs:
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict):
                    for k in ("regular_price", "promo_price", "pix_price", "installment_value", "total_amount"):
                        val = item.get(k)
                        if val is not None:
                            try:
                                valid_prices.add(round(float(val), 2))
                            except (ValueError, TypeError):
                                pass
        elif isinstance(payload, dict):
            for k in ("regular_price", "promo_price", "pix_price", "installment_value", "total_amount"):
                val = payload.get(k)
                if val is not None:
                    try:
                        valid_prices.add(round(float(val), 2))
                    except (ValueError, TypeError):
                        pass

    generated_prices = extract_prices_from_text(text)
    if not generated_prices or not valid_prices:
        return True, warnings, 1.0

    unverified_count = 0
    for p in generated_prices:
        # Allow small floating point rounding differences (e.g. within R$ 1.00)
        is_close = any(abs(p - vp) <= 0.05 for vp in valid_prices)
        if not is_close:
            unverified_count += 1
            warnings.append(f"Price R$ {p:.2f} not found in tool execution payload.")

    grounding_score = 1.0 - (unverified_count / max(len(generated_prices), 1))
    is_grounded = unverified_count == 0 or grounding_score >= 0.75
    return is_grounded, warnings, round(grounding_score, 2)


def check_tone_and_persona(text: str) -> Tuple[str, bool]:
    """Modulate tone to ensure warm consultative persona without aggressive sales tactics."""
    modified = text
    modifications_made = False

    # Check and soften aggressive sales urgencies
    aggressive_patterns = [
        (r"compre\s+agora\s+antes\s+que\s+acabe", "se quiser, posso reservar ou te convidar para testar na loja"),
        (r"últimas\s+unidades,\s+corra", "temos poucas unidades disponíveis"),
        (r"você\s+vai\s+perder\s+essa\s+chance", "vale muito a pena conferir de perto"),
    ]

    for pat, rep in aggressive_patterns:
        if re.search(pat, modified, flags=re.IGNORECASE):
            modified = re.sub(pat, rep, modified, flags=re.IGNORECASE)
            modifications_made = True

    return modified, modifications_made


def validate_output(
    response_text: str,
    tool_outputs: Optional[List[Dict[str, Any]]] = None,
) -> OutputGuardResult:
    """Validate Layer 3 defense: factual verification and tone moderation.

    Args:
        response_text: Raw LLM response string.
        tool_outputs: List of outputs from executed tools.

    Returns:
        OutputGuardResult.
    """
    if not response_text:
        return OutputGuardResult(passed=False, validated_text="", warnings=["Empty response"])

    # 1. Tone Modulation
    modulated_text, tone_mod = check_tone_and_persona(response_text)

    # 2. Factual Grounding Verification
    is_grounded, warnings, score = verify_factual_grounding(
        modulated_text, tool_outputs or []
    )

    return OutputGuardResult(
        passed=is_grounded,
        validated_text=modulated_text,
        modifications_made=tone_mod,
        warnings=warnings,
        grounding_score=score,
    )
