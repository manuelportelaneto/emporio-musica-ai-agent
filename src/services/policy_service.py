"""Policy Service: RAG search across store manual policies."""

from __future__ import annotations

from typing import Any, Dict, List

from src.data_engine import PolicyVectorIndex


def query_store_policy(
    index: PolicyVectorIndex,
    topic: str,
    top_k: int = 2,
) -> Dict[str, Any]:
    """Retrieve official store policy excerpts for a specific query topic.

    Args:
        index: Initialized PolicyVectorIndex.
        topic: User query or policy topic (e.g., 'frete', 'garantia', 'endereço', 'horário').
        top_k: Number of relevant chunks to retrieve.

    Returns:
        Dictionary containing extracted policy passages and contact summary.
    """
    matches = index.search(query=topic, top_k=top_k)

    if not matches:
        return {
            "topic": topic,
            "found": False,
            "excerpts": [],
            "fallback_contact": (
                "Para mais detalhes, entre em contato diretamente com nossa equipe em Campo Grande: "
                "Rua 14 de Maio, 3200 — Centro, Fone: (67) 3341-4444 ou contato@emporiodamusica.com.br."
            ),
        }

    return {
        "topic": topic,
        "found": True,
        "results_count": len(matches),
        "excerpts": [
            {
                "page": m["page"],
                "relevance_score": m["score"],
                "content": m["content"],
            }
            for m in matches
        ],
        "store_info": {
            "name": "Empório da Música",
            "address": "Rua 14 de Maio, 3200 — Centro, Campo Grande / MS (CEP 79202-333)",
            "phone": "(67) 3341-4444",
            "email": "contato@emporiodamusica.com.br",
        },
    }
