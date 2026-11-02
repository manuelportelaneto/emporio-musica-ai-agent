"""Configuration module: Multi-provider LLM settings and environment loader."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

# Load .env if present
load_dotenv()


class AppConfig:
    """Central configuration for Empório da Música AI Agent."""

    # Active provider: 'groq', 'openai', 'ollama', or 'mock'
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "groq").lower().strip()

    # Groq Settings
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    GROQ_TEMPERATURE: float = float(os.getenv("GROQ_TEMPERATURE", "0.1"))

    # OpenAI Settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "0.1"))

    # Ollama Settings
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

    # Storage & Audit
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "emporio_records.db")
    DATA_DIR: str = os.getenv("DATA_DIR", "data")
    POLICY_PDF_PATH: str = os.getenv("POLICY_PDF_PATH", "data/políticas_da_loja.pdf")


def get_llm_client() -> Any:
    """Factory returning the configured LLM client instance."""
    provider = AppConfig.LLM_PROVIDER

    if provider == "groq":
        api_key = AppConfig.GROQ_API_KEY
        if not api_key or api_key.startswith("gsk_your"):
            # If not configured, raise informative error or allow mock
            return None
        from groq import Groq

        return Groq(api_key=api_key)

    elif provider == "openai":
        api_key = AppConfig.OPENAI_API_KEY
        if not api_key or api_key.startswith("sk-your"):
            return None
        from openai import OpenAI

        return OpenAI(api_key=api_key)

    elif provider == "ollama":
        from openai import OpenAI

        return OpenAI(
            base_url=f"{AppConfig.OLLAMA_BASE_URL}/v1",
            api_key="ollama",
        )

    return None
