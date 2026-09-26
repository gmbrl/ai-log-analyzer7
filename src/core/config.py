"""
config.py — Central configuration, constants, and environment loading.
All configurable knobs for the AI Log Analyzer live here.
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# LLM provider constants
# ---------------------------------------------------------------------------
PROVIDER_OPENAI = "openai"
PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_OLLAMA = "ollama"
PROVIDER_GROQ = "groq"

SUPPORTED_PROVIDERS = [PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_OLLAMA, PROVIDER_GROQ]

# Default model per provider
DEFAULT_MODELS = {
    PROVIDER_OPENAI: "gpt-4o-mini",
    PROVIDER_ANTHROPIC: "claude-3-haiku-20240307",
    PROVIDER_OLLAMA: "llama3",
    PROVIDER_GROQ: "openai/gpt-oss-20b",
}

# Models that have been decommissioned — will be silently replaced by the provider default
DECOMMISSIONED_MODELS = {
    "llama3-8b-8192",
    "llama3-70b-8192",
    "mixtral-8x7b-32768",
    "gemma-7b-it",
    "gemma2-9b-it",
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
}

# ---------------------------------------------------------------------------
# Log level ordering (used for severity filtering)
# ---------------------------------------------------------------------------
LOG_LEVEL_ORDER = {
    "TRACE": 0,
    "DEBUG": 1,
    "INFO": 2,
    "NOTICE": 3,
    "WARNING": 4,
    "WARN": 4,
    "ERROR": 5,
    "CRITICAL": 6,
    "FATAL": 6,
    "EMERGENCY": 7,
}

# All canonical log levels recognised by the parser
ALL_LOG_LEVELS = ["TRACE", "DEBUG", "INFO", "NOTICE", "WARNING", "WARN", "ERROR", "CRITICAL", "FATAL", "EMERGENCY"]

# ---------------------------------------------------------------------------
# Chunking parameters
# ---------------------------------------------------------------------------
# Maximum number of log lines to send to the LLM in a single chunk
MAX_LINES_PER_CHUNK = 300
# Maximum characters per chunk (safety net independent of line count)
MAX_CHARS_PER_CHUNK = 12_000

# ---------------------------------------------------------------------------
# Groq-specific chunk limits
# Groq free tier: 8,000 TPM.  The system prompt + schema is ~600 tokens,
# leaving only ~2,400 tokens for log text per request at 3,000 token chunks.
# We cap Groq chunks to 2,000 chars (~500 tokens) to stay safely under limit.
# ---------------------------------------------------------------------------
GROQ_MAX_CHARS_PER_CHUNK = 2_000
GROQ_MAX_LINES_PER_CHUNK = 60

# ---------------------------------------------------------------------------
# File upload limits
# ---------------------------------------------------------------------------
SUPPORTED_EXTENSIONS = [".log", ".txt", ".json", ".csv"]
MAX_FILE_SIZE_MB = 50

# ---------------------------------------------------------------------------
# PII redaction placeholder tokens
# ---------------------------------------------------------------------------
PII_PLACEHOLDERS = {
    "email": "[EMAIL]",
    "ipv4": "[IPv4]",
    "ipv6": "[IPv6]",
    "bearer_token": "[BEARER_TOKEN]",
    "api_key": "[API_KEY]",
    "password": "[PASSWORD]",
    "credit_card": "[CREDIT_CARD]",
    "ssn": "[SSN]",
    "jwt": "[JWT]",
}

# ---------------------------------------------------------------------------
# App-level settings loaded from environment
# ---------------------------------------------------------------------------
@dataclass
class AppSettings:
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    ollama_base_url: str = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    default_provider: str = field(default_factory=lambda: os.getenv("DEFAULT_LLM_PROVIDER", PROVIDER_GROQ))
    default_model: str = field(default_factory=lambda: os.getenv("DEFAULT_LLM_MODEL", ""))

    def resolved_model(self) -> str:
        """Return the configured model, falling back to the provider default.

        If the configured model has been decommissioned, the provider default
        is returned instead so stale .env values don't break the app.
        """
        model = self.default_model or DEFAULT_MODELS.get(self.default_provider, "gpt-4o-mini")
        if model in DECOMMISSIONED_MODELS:
            return DEFAULT_MODELS.get(self.default_provider, "gpt-4o-mini")
        return model


# Singleton settings instance used throughout the app
settings = AppSettings()
