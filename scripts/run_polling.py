#!/usr/bin/env python3
"""Local polling mode when webhook is not available."""

from __future__ import annotations

import asyncio
import logging
import os
import sys

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ai.router import LLMRouter
from app.bot.engine import BotEngine
from app.bot.handlers import handle_telegram_update
from app.config import get_settings
from app.storage import store
from app.telegram_api import TelegramClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def poll():
    settings = get_settings()
    if not settings.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN required")
        return
    await store.init()
    tg = TelegramClient(settings.telegram_bot_token)
    llm = LLMRouter(settings) if settings.is_llm_configured else None
    engine = BotEngine(settings, llm, tg)
    offset = 0
    base = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
    async with httpx.AsyncClient(timeout=35.0) as client:
        await client.post(f"{base}/deleteWebhook")
        logger.info("Polling started...")
        while True:
            r = await client.get(f"{base}/getUpdates", params={"offset": offset, "timeout": 30})
            data = r.json()
            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                try:
                    await handle_telegram_update(upd, settings, tg, engine, llm)
                except Exception:
                    logger.exception("Update error")


if __name__ == "__main__":
    asyncio.run(poll())
