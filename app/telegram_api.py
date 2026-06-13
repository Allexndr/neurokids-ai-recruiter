"""Telegram Bot API client."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def sanitize_for_telegram(text: str) -> str:
    """Escape MarkdownV2-sensitive chars minimally for legacy Markdown mode."""
    if not text:
        return text
    for ch in ("_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"):
        text = text.replace(ch, f"\\{ch}")
    return text


class TelegramClient:
    def __init__(self, token: str):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"

    async def _post(self, method: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        url = f"{self.base_url}/{method}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(url, json=payload)
                r.raise_for_status()
                return r.json()
        except Exception:
            logger.exception("Telegram API error: %s", method)
            return None

    async def send_chat_action(self, chat_id: str | int, action: str = "typing") -> None:
        await self._post("sendChatAction", {"chat_id": chat_id, "action": action})

    async def send_message(
        self,
        chat_id: str | int,
        text: str,
        parse_mode: str | None = "HTML",
        reply_markup: dict | None = None,
    ) -> dict[str, Any] | None:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = reply_markup
        result = await self._post("sendMessage", payload)
        if result is None and parse_mode:
            payload.pop("parse_mode", None)
            result = await self._post("sendMessage", payload)
        return result

    async def edit_message(
        self,
        chat_id: str | int,
        message_id: int,
        text: str,
        parse_mode: str | None = "HTML",
        reply_markup: dict | None = None,
    ) -> bool:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        result = await self._post("editMessageText", payload)
        if result is None and parse_mode:
            payload.pop("parse_mode", None)
            result = await self._post("editMessageText", payload)
        return bool(result and result.get("ok"))

    def extract_panel_message_id(self, body: dict[str, Any]) -> int | None:
        if "callback_query" in body:
            msg = body["callback_query"].get("message") or {}
            mid = msg.get("message_id")
            return int(mid) if mid is not None else None
        return None

    async def answer_callback_query(self, callback_query_id: str, text: str | None = None) -> None:
        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        await self._post("answerCallbackQuery", payload)

    async def set_webhook(self, url: str, secret_token: str = "") -> dict[str, Any] | None:
        payload: dict[str, Any] = {
            "url": url,
            "allowed_updates": ["message", "callback_query"],
            "drop_pending_updates": True,
        }
        if secret_token:
            payload["secret_token"] = secret_token
        return await self._post("setWebhook", payload)

    async def get_file(self, file_id: str) -> dict[str, Any] | None:
        return await self._post("getFile", {"file_id": file_id})

    async def download_file(self, file_path: str) -> bytes:
        url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.get(url)
                r.raise_for_status()
                return r.content
        except Exception:
            logger.exception("Telegram file download failed")
            return b""


def extract_update_info(body: dict[str, Any]) -> tuple[str | None, str | None, str | None, str | None]:
    if "callback_query" in body:
        cq = body["callback_query"]
        msg = cq.get("message", {})
        chat = msg.get("chat", {})
        chat_id = str(chat.get("id", ""))
        text = cq.get("data", "")
        user = cq.get("from", {})
        name = (user.get("first_name") or "").strip()
        if user.get("last_name"):
            name += " " + user.get("last_name", "")
        return chat_id, text, name.strip() or None, cq.get("id")

    msg = body.get("message", {})
    if not msg:
        return None, None, None, None
    chat = msg.get("chat", {})
    chat_id = str(chat.get("id", ""))
    text = msg.get("text", "") or ""
    user = msg.get("from", {})
    name = (user.get("first_name") or "").strip()
    if user.get("last_name"):
        name += " " + user.get("last_name", "")
    return chat_id, text, name.strip() or None, None


_KK_CHARS = re.compile(r"[әіңғүұқөһӘІҢҒҮҰҚӨҺ]")


def detect_message_lang(text: str) -> str:
    if _KK_CHARS.search(text):
        return "kk"
    t = text.lower()
    kk_hints = ("жоқ", "иә", "қалай", "жұмыс", "сәлем", "керек", "қанша", "график")
    if any(h in t for h in kk_hints):
        return "kk"
    return "ru"
