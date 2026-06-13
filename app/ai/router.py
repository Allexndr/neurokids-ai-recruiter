"""Multi-provider LLM router: Together (primary) → Groq → OpenRouter."""

from __future__ import annotations

import logging

import httpx

from app.config import Settings
from app.together_client import TogetherClient

logger = logging.getLogger(__name__)

GROQ_BASE = "https://api.groq.com/openai/v1"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"


class LLMRouter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._together: TogetherClient | None = None
        if settings.together_api_key:
            self._together = TogetherClient(settings.together_api_key, settings.together_model)

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.25,
        max_tokens: int = 800,
    ) -> tuple[str | None, str | None]:
        provider = (self.settings.ai_provider or "together").lower()

        if provider == "together" and self._together:
            text, err = await self._together.chat(messages, temperature, max_tokens)
            if text:
                return text, None
            logger.warning("Together failed: %s", err)

        if provider in ("together", "groq") and self.settings.groq_api_key:
            text, err = await self._openai_compatible(
                GROQ_BASE,
                self.settings.groq_api_key,
                self.settings.groq_model,
                messages,
                temperature,
                max_tokens,
            )
            if text:
                return text, None
            logger.warning("Groq failed: %s", err)

        if self._together and provider != "together":
            text, err = await self._together.chat(messages, temperature, max_tokens)
            if text:
                return text, None

        if self.settings.openrouter_api_key:
            text, err = await self._openai_compatible(
                OPENROUTER_BASE,
                self.settings.openrouter_api_key,
                self.settings.openrouter_model,
                messages,
                temperature,
                max_tokens,
                extra_headers={"HTTP-Referer": "https://recruter-support-bot", "X-Title": "HR Bot"},
            )
            if text:
                return text, None
            logger.warning("OpenRouter failed: %s", err)

        if self._together:
            return await self._together.chat(messages, temperature, max_tokens)

        return None, "No LLM provider configured"

    async def _openai_compatible(
        self,
        base: str,
        api_key: str,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[str | None, str | None]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(f"{base}/chat/completions", json=payload, headers=headers)
                r.raise_for_status()
                data = r.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content")
                return (content.strip() if content else None), None
        except httpx.HTTPStatusError as e:
            return None, f"HTTP {e.response.status_code}: {e.response.text[:300]}"
        except Exception as e:
            logger.exception("LLM request failed")
            return None, str(e)
