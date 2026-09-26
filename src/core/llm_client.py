"""
llm_client.py — Modular LLM client wrapper.

Provides a single `LLMClient` class that abstracts over four back-ends:
  - OpenAI  (gpt-4o, gpt-4o-mini, etc.)
  - Anthropic (claude-3-* family)
  - Ollama  (local models via HTTP)
  - Groq   (OpenAI-compatible; openai/gpt-oss-20b, openai/gpt-oss-120b, qwen/qwen3.8-27b, etc.)

Usage:
    from src.core.llm_client import LLMClient, LLMResponse
    client = LLMClient(provider="groq", model="openai/gpt-oss-20b", api_key="gsk_…")
    response = client.chat(system_prompt="You are …", user_message="Analyse …")
    print(response.content)

All back-ends return an `LLMResponse` dataclass with `.content` (str) and
`.usage` (token counts dict).  Errors surface as `LLMClientError`.
"""

import json
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

from src.core.config import (
    PROVIDER_ANTHROPIC,
    PROVIDER_GROQ,
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI,
    settings,
)

# ---------------------------------------------------------------------------
# Response and error types
# ---------------------------------------------------------------------------

@dataclass
class LLMResponse:
    content: str
    usage: dict = field(default_factory=dict)
    provider: str = ""
    model: str = ""


class LLMClientError(Exception):
    """Raised when the LLM back-end returns an error or is misconfigured."""


# ---------------------------------------------------------------------------
# LLMClient
# ---------------------------------------------------------------------------

class LLMClient:
    """
    Thin, provider-agnostic wrapper around LLM chat APIs.

    Args:
        provider:  One of "openai", "anthropic", "ollama".
        model:     Model identifier (e.g. "gpt-4o-mini").
        api_key:   API key (overrides env-var-derived settings if provided).
        base_url:  Override the API base URL (useful for Ollama or proxies).
        timeout:   HTTP timeout in seconds (default 120).
    """

    def __init__(
        self,
        provider: str = "",
        model: str = "",
        api_key: str = "",
        base_url: str = "",
        timeout: int = 120,
    ) -> None:
        self.provider = provider or settings.default_provider
        self.model = model or settings.resolved_model()
        self.timeout = timeout

        # Resolve API key from argument or settings
        if api_key:
            self._api_key = api_key
        elif self.provider == PROVIDER_OPENAI:
            self._api_key = settings.openai_api_key
        elif self.provider == PROVIDER_ANTHROPIC:
            self._api_key = settings.anthropic_api_key
        elif self.provider == PROVIDER_GROQ:
            self._api_key = settings.groq_api_key
        else:
            self._api_key = ""  # Ollama does not need a key

        # Resolve base URL
        if base_url:
            self._base_url = base_url.rstrip("/")
        elif self.provider == PROVIDER_OLLAMA:
            self._base_url = settings.ollama_base_url.rstrip("/")
        elif self.provider == PROVIDER_OPENAI:
            self._base_url = "https://api.openai.com/v1"
        elif self.provider == PROVIDER_GROQ:
            self._base_url = "https://api.groq.com/openai/v1"
        elif self.provider == PROVIDER_ANTHROPIC:
            self._base_url = "https://api.anthropic.com"
        else:
            self._base_url = ""

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def chat(
        self,
        user_message: str,
        system_prompt: str = "",
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """
        Send a chat completion request and return an LLMResponse.

        Args:
            user_message:   The user-turn message.
            system_prompt:  Optional system instruction.
            temperature:    Sampling temperature (0–2).
            max_tokens:     Maximum tokens to generate.

        Returns:
            LLMResponse

        Raises:
            LLMClientError on API errors or network failures.
        """
        if self.provider in (PROVIDER_OPENAI, PROVIDER_GROQ):
            return self._chat_openai(user_message, system_prompt, temperature, max_tokens)
        elif self.provider == PROVIDER_ANTHROPIC:
            return self._chat_anthropic(user_message, system_prompt, temperature, max_tokens)
        elif self.provider == PROVIDER_OLLAMA:
            return self._chat_ollama(user_message, system_prompt, temperature, max_tokens)
        else:
            raise LLMClientError(f"Unknown provider: {self.provider!r}")

    # ------------------------------------------------------------------
    # OpenAI / Groq back-end  (with 429 retry + Retry-After back-off)
    # ------------------------------------------------------------------

    _MAX_RETRIES = 4
    _RETRY_BASE_DELAY = 5.0  # seconds; doubled each attempt up to Retry-After header

    def _chat_openai(
        self,
        user_message: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        provider_label = "Groq" if self.provider == PROVIDER_GROQ else "OpenAI"
        if not self._api_key:
            raise LLMClientError(f"{provider_label} API key is not configured.")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        last_exc: Exception = RuntimeError("unreachable")
        for attempt in range(self._MAX_RETRIES):
            try:
                response = httpx.post(
                    f"{self._base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
            except httpx.RequestError as exc:
                raise LLMClientError(f"Network error calling {provider_label}: {exc}") from exc

            if response.status_code == 429:
                # Respect Retry-After header; fall back to exponential back-off
                retry_after = response.headers.get("retry-after") or response.headers.get("x-ratelimit-reset-tokens")
                try:
                    wait = float(retry_after)
                except (TypeError, ValueError):
                    wait = self._RETRY_BASE_DELAY * (2 ** attempt)
                wait = min(wait, 60.0)  # cap at 60 s
                last_exc = LLMClientError(
                    f"{provider_label} rate limit (429): waiting {wait:.1f}s before retry "
                    f"(attempt {attempt + 1}/{self._MAX_RETRIES})…"
                )
                time.sleep(wait)
                continue

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise LLMClientError(
                    f"{provider_label} API error {exc.response.status_code}: {exc.response.text}"
                ) from exc

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            return LLMResponse(content=content, usage=usage, provider=self.provider, model=self.model)

        raise last_exc

    # ------------------------------------------------------------------
    # Anthropic back-end
    # ------------------------------------------------------------------

    def _chat_anthropic(
        self,
        user_message: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        if not self._api_key:
            raise LLMClientError("Anthropic API key is not configured.")

        payload: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": user_message}],
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            response = httpx.post(
                f"{self._base_url}/v1/messages",
                json=payload,
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMClientError(
                f"Anthropic API error {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise LLMClientError(f"Network error calling Anthropic: {exc}") from exc

        data = response.json()
        content = data["content"][0]["text"]
        usage = data.get("usage", {})
        return LLMResponse(content=content, usage=usage, provider=self.provider, model=self.model)

    # ------------------------------------------------------------------
    # Ollama back-end
    # ------------------------------------------------------------------

    def _chat_ollama(
        self,
        user_message: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        """Uses the Ollama /api/chat endpoint (available since Ollama 0.1.14)."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        try:
            response = httpx.post(
                f"{self._base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMClientError(
                f"Ollama API error {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise LLMClientError(f"Network error calling Ollama: {exc}") from exc

        data = response.json()
        content = data["message"]["content"]
        usage = {
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "completion_tokens": data.get("eval_count", 0),
        }
        return LLMResponse(content=content, usage=usage, provider=self.provider, model=self.model)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def is_configured(self) -> bool:
        """Return True if the client has the minimum required configuration."""
        if self.provider in (PROVIDER_OPENAI, PROVIDER_GROQ, PROVIDER_ANTHROPIC):
            return bool(self._api_key)
        if self.provider == PROVIDER_OLLAMA:
            return bool(self._base_url)
        return False

    def __repr__(self) -> str:
        return f"LLMClient(provider={self.provider!r}, model={self.model!r})"


# ---------------------------------------------------------------------------
# JSON extraction helper (used by the analyzer)
# ---------------------------------------------------------------------------

def extract_json_from_response(text: str) -> Optional[dict]:
    """
    Extract the first valid JSON object from an LLM response string.

    LLMs sometimes wrap JSON in markdown code fences; this handles that.
    Returns the parsed dict, or None if no valid JSON is found.
    """
    # Strip markdown code fences
    cleaned = text.strip()
    for fence in ("```json", "```"):
        if cleaned.startswith(fence):
            cleaned = cleaned[len(fence):]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            break

    # Try to parse directly
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try to find a JSON object inside the text using brace matching
    start = cleaned.find("{")
    if start == -1:
        return None

    depth = 0
    for i, ch in enumerate(cleaned[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(cleaned[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None
