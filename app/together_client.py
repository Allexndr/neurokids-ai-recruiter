"""Together AI — OpenAI-compatible chat API."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

TOGETHER_API_BASE = "https://api.together.xyz/v1"


class TogetherClient:
    def __init__(
        self,
        api_key: str,
        model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
    ):
        self.api_key = api_key
        self.model = model
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.25,
        max_tokens: int = 280,
    ) -> tuple[str | None, str | None]:
        url = f"{TOGETHER_API_BASE}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(url, json=payload, headers=self.headers)
                r.raise_for_status()
                data = r.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content")
                return content.strip() if content else None, None
        except httpx.HTTPStatusError as e:
            err = f"HTTP {e.response.status_code}: {e.response.text[:300]}"
            logger.error("Together chat error: %s", err)
            return None, err
        except Exception as e:
            logger.exception("Together chat exception")
            return None, str(e)
