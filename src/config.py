"""Configuration module: Multi-provider LLM settings, dynamic runtime keys, and session persistence."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

SESSION_CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".evaluator_session.json")


class AppConfig:
    """Central dynamic configuration for Empório da Música AI Agent."""

    # Active provider: 'offline', 'groq', 'openai', 'gemini', 'deepseek', 'ollama'
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "groq").lower().strip()

    # Groq Settings
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    GROQ_TEMPERATURE: float = float(os.getenv("GROQ_TEMPERATURE", "0.1"))

    # OpenAI Settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "0.1"))

    # Google Gemini Settings
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    GEMINI_TEMPERATURE: float = float(os.getenv("GEMINI_TEMPERATURE", "0.1"))

    # DeepSeek Settings
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    DEEPSEEK_TEMPERATURE: float = float(os.getenv("DEEPSEEK_TEMPERATURE", "0.1"))

    # Ollama Settings
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

    # Storage & Audit
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "emporio_records.db")
    DATA_DIR: str = os.getenv("DATA_DIR", "data")
    STORE_POLICIES_JSON: str = os.getenv("STORE_POLICIES_JSON", "data/store_policies.json")
    POLICY_PDF_PATH: str = os.getenv("POLICY_PDF_PATH", "data/políticas_da_loja.pdf")

    @classmethod
    def get_api_key(cls, provider: Optional[str] = None) -> str:
        """Get the active API key dynamically from environment or class settings."""
        prov = (provider or cls.LLM_PROVIDER).lower().strip()
        if prov == "groq":
            return os.getenv("GROQ_API_KEY", cls.GROQ_API_KEY).strip()
        elif prov == "openai":
            return os.getenv("OPENAI_API_KEY", cls.OPENAI_API_KEY).strip()
        elif prov == "gemini":
            return os.getenv("GEMINI_API_KEY", cls.GEMINI_API_KEY).strip()
        elif prov == "deepseek":
            return os.getenv("DEEPSEEK_API_KEY", cls.DEEPSEEK_API_KEY).strip()
        elif prov == "ollama":
            return "ollama"
        return ""

    @classmethod
    def get_model(cls, provider: Optional[str] = None) -> str:
        """Get the active model name for the given provider."""
        prov = (provider or cls.LLM_PROVIDER).lower().strip()
        if prov == "groq":
            return os.getenv("GROQ_MODEL", cls.GROQ_MODEL)
        elif prov == "openai":
            return os.getenv("OPENAI_MODEL", cls.OPENAI_MODEL)
        elif prov == "gemini":
            return os.getenv("GEMINI_MODEL", cls.GEMINI_MODEL)
        elif prov == "deepseek":
            return os.getenv("DEEPSEEK_MODEL", cls.DEEPSEEK_MODEL)
        elif prov == "ollama":
            return os.getenv("OLLAMA_MODEL", cls.OLLAMA_MODEL)
        return "deterministic-offline"

    @classmethod
    def set_active_provider(
        cls,
        provider: str,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        persist: bool = True,
    ) -> None:
        """Dynamically set the active provider and its API key."""
        cls.LLM_PROVIDER = provider.lower().strip()
        os.environ["LLM_PROVIDER"] = cls.LLM_PROVIDER

        if api_key:
            if cls.LLM_PROVIDER == "groq":
                cls.GROQ_API_KEY = api_key
                os.environ["GROQ_API_KEY"] = api_key
            elif cls.LLM_PROVIDER == "openai":
                cls.OPENAI_API_KEY = api_key
                os.environ["OPENAI_API_KEY"] = api_key
            elif cls.LLM_PROVIDER == "gemini":
                cls.GEMINI_API_KEY = api_key
                os.environ["GEMINI_API_KEY"] = api_key
            elif cls.LLM_PROVIDER == "deepseek":
                cls.DEEPSEEK_API_KEY = api_key
                os.environ["DEEPSEEK_API_KEY"] = api_key

        if model:
            if cls.LLM_PROVIDER == "groq":
                cls.GROQ_MODEL = model
                os.environ["GROQ_MODEL"] = model
            elif cls.LLM_PROVIDER == "openai":
                cls.OPENAI_MODEL = model
                os.environ["OPENAI_MODEL"] = model
            elif cls.LLM_PROVIDER == "gemini":
                cls.GEMINI_MODEL = model
                os.environ["GEMINI_MODEL"] = model
            elif cls.LLM_PROVIDER == "deepseek":
                cls.DEEPSEEK_MODEL = model
                os.environ["DEEPSEEK_MODEL"] = model
            elif cls.LLM_PROVIDER == "ollama":
                cls.OLLAMA_MODEL = model
                os.environ["OLLAMA_MODEL"] = model

        if persist:
            cls.save_session_config()

    @classmethod
    def save_session_config(cls) -> None:
        """Save current evaluator engine settings to ephemeral session file."""
        data = {
            "provider": cls.LLM_PROVIDER,
            "groq_api_key": cls.GROQ_API_KEY or os.getenv("GROQ_API_KEY", ""),
            "openai_api_key": cls.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", ""),
            "gemini_api_key": cls.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", ""),
            "deepseek_api_key": cls.DEEPSEEK_API_KEY or os.getenv("DEEPSEEK_API_KEY", ""),
            "groq_model": cls.GROQ_MODEL,
            "openai_model": cls.OPENAI_MODEL,
            "gemini_model": cls.GEMINI_MODEL,
            "deepseek_model": cls.DEEPSEEK_MODEL,
        }
        try:
            with open(SESSION_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    @classmethod
    def load_session_config(cls) -> Dict[str, Any]:
        """Load session configuration into memory and environment."""
        if not os.path.exists(SESSION_CONFIG_FILE):
            return {}
        try:
            with open(SESSION_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("provider"):
                cls.LLM_PROVIDER = data["provider"]
                os.environ["LLM_PROVIDER"] = data["provider"]
            if data.get("groq_api_key"):
                cls.GROQ_API_KEY = data["groq_api_key"]
                os.environ["GROQ_API_KEY"] = data["groq_api_key"]
            if data.get("openai_api_key"):
                cls.OPENAI_API_KEY = data["openai_api_key"]
                os.environ["OPENAI_API_KEY"] = data["openai_api_key"]
            if data.get("gemini_api_key"):
                cls.GEMINI_API_KEY = data["gemini_api_key"]
                os.environ["GEMINI_API_KEY"] = data["gemini_api_key"]
            if data.get("deepseek_api_key"):
                cls.DEEPSEEK_API_KEY = data["deepseek_api_key"]
                os.environ["DEEPSEEK_API_KEY"] = data["deepseek_api_key"]
            return data
        except Exception:
            return {}

    @classmethod
    def clear_session_config(cls) -> None:
        """Purge ephemeral session configuration file and memory."""
        cls.GROQ_API_KEY = ""
        cls.OPENAI_API_KEY = ""
        cls.GEMINI_API_KEY = ""
        cls.DEEPSEEK_API_KEY = ""
        os.environ.pop("GROQ_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("DEEPSEEK_API_KEY", None)
        if os.path.exists(SESSION_CONFIG_FILE):
            try:
                os.remove(SESSION_CONFIG_FILE)
            except Exception:
                pass


# Pre-load session config if present
AppConfig.load_session_config()


def get_llm_client(
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Any:
    """Factory returning the configured LLM client instance for any provider."""
    prov = (provider or AppConfig.LLM_PROVIDER).lower().strip()
    key = api_key or AppConfig.get_api_key(prov)

    if prov == "offline":
        return None

    if prov == "groq":
        if not key or key.startswith("gsk_your"):
            return None
        from groq import Groq

        return Groq(api_key=key)

    elif prov == "openai":
        if not key or key.startswith("sk-your"):
            return None
        from openai import OpenAI

        return OpenAI(api_key=key)

    elif prov == "gemini":
        if not key or key.startswith("AIzaSy_your"):
            return None
        from openai import OpenAI

        # Google Gemini supports the OpenAI-compatible v1beta endpoint natively
        return OpenAI(
            api_key=key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )

    elif prov == "deepseek":
        if not key or key.startswith("sk-your"):
            return None
        from openai import OpenAI

        return OpenAI(
            api_key=key,
            base_url="https://api.deepseek.com",
        )

    elif prov == "ollama":
        from openai import OpenAI

        return OpenAI(
            base_url=f"{AppConfig.OLLAMA_BASE_URL}/v1",
            api_key="ollama",
        )

    return None
