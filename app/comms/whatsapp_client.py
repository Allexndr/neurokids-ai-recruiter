"""WhatsApp Cloud API client."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class WhatsAppClient:
    def __init__(self, token: str, phone_number_id: str):
        self.token = token
        self.phone_number_id = phone_number_id
        self.base = f"https://graph.facebook.com/v21.0/{phone_number_id}"

    async def send_text(self, to: str, text: str) -> bool:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text[:4096]},
        }
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(f"{self.base}/messages", json=payload, headers=headers)
                r.raise_for_status()
                return True
        except Exception as e:
            logger.exception("WA send error: %s", e)
            return False

    def extract_message(self, body: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
        """Returns (from_phone, text, message_id)."""
        try:
            entry = body.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})
            messages = value.get("messages", [])
            if not messages:
                return None, None, None
            msg = messages[0]
            from_id = msg.get("from")
            mid = msg.get("id")
            if msg.get("type") == "text":
                return from_id, msg.get("text", {}).get("body", ""), mid
            return from_id, "", mid
        except (IndexError, KeyError, TypeError):
            return None, None, None
