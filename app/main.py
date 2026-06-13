"""Recruiter Support Bot — FastAPI + Telegram + WhatsApp webhooks."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app.ai.router import LLMRouter
from app.bot.engine import BotEngine
from app.bot.handlers import handle_telegram_update
from app.bot.scheduling import available_slots
from app.calendar.google_calendar import GoogleCalendarClient
from app.comms.whatsapp_client import WhatsAppClient
from app.config import get_settings
from app.storage.db import store
from app.telegram_api import TelegramClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

tg_client: TelegramClient | None = None
wa_client: WhatsAppClient | None = None
llm_router: LLMRouter | None = None
gcal_client: GoogleCalendarClient | None = None
engine: BotEngine | None = None
_ready = False


async def ensure_ready() -> None:
    global tg_client, wa_client, llm_router, gcal_client, engine, _ready
    if _ready:
        return
    settings = get_settings()
    await store.init()
    if settings.is_llm_configured:
        llm_router = LLMRouter(settings)
    if settings.is_telegram_configured:
        tg_client = TelegramClient(settings.telegram_bot_token)
    if settings.is_whatsapp_configured:
        wa_client = WhatsAppClient(settings.whatsapp_token, settings.whatsapp_phone_number_id)
    if settings.is_google_calendar_configured:
        gcal_client = GoogleCalendarClient(
            settings.google_calendar_id,
            settings.google_service_account_json,
            settings.bot_timezone,
        )
    if tg_client:
        engine = BotEngine(settings, llm_router, tg_client, gcal_client)
    _ready = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_ready()
    settings = get_settings()
    if tg_client and settings.webhook_base_url:
        r = await tg_client.set_webhook(
            settings.telegram_webhook_url,
            settings.telegram_webhook_secret,
        )
        logger.info("Telegram webhook: %s", r)
    yield


app = FastAPI(title="Recruiter Support Bot", lifespan=lifespan)


@app.get("/health")
async def health():
    settings = get_settings()
    return {
        "ok": True,
        "telegram": settings.is_telegram_configured,
        "whatsapp": settings.is_whatsapp_configured,
        "llm": settings.is_llm_configured,
        "together": settings.is_together_configured,
        "hh": settings.is_hh_configured,
        "calendar": settings.is_google_calendar_configured,
        "hr_notify": settings.is_hr_notify_configured,
    }


@app.get("/setup")
@app.post("/setup")
async def setup():
    await ensure_ready()
    settings = get_settings()
    if not tg_client or not settings.webhook_base_url:
        raise HTTPException(400, "TELEGRAM_BOT_TOKEN and WEBHOOK_BASE_URL required")
    result = await tg_client.set_webhook(
        settings.telegram_webhook_url,
        settings.telegram_webhook_secret,
    )
    return {"webhook": settings.telegram_webhook_url, "result": result}


@app.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(default=""),
):
    await ensure_ready()
    settings = get_settings()
    if settings.telegram_webhook_secret and x_telegram_bot_api_secret_token:
        if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
            raise HTTPException(403, "Invalid secret")

    if not engine or not tg_client:
        raise HTTPException(503, "Bot not configured")

    body = await request.json()
    try:
        await handle_telegram_update(body, settings, tg_client, engine, llm_router)
    except Exception:
        logger.exception("Handler error")
    return {"ok": True}


@app.get("/webhook/whatsapp")
async def whatsapp_verify(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
):
    settings = get_settings()
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(403, "Forbidden")


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    await ensure_ready()
    settings = get_settings()
    if not wa_client or not engine:
        return {"ok": True}

    body = await request.json()
    phone, text, _ = wa_client.extract_message(body)
    if not phone or not text:
        return {"ok": True}

    chat_id = f"wa:{phone}"
    session = await store.get_session(chat_id)
    session.profile.setdefault("ui_mode", "whatsapp")
    session.profile["lang_locked"] = True
    if session.state == "choose_view":
        session.state = "collect_name_age"
    await store.log_message(chat_id, "in", text, channel="whatsapp")

    reply = await engine.handle(session, text, is_callback=False)
    await store.save_session(session)
    await wa_client.send_text(phone, reply.text)
    await store.log_message(chat_id, "out", reply.text, channel="whatsapp")
    return {"ok": True}


@app.get("/api/cron/reminders")
@app.post("/api/cron/reminders")
async def cron_reminders(
    request: Request,
    authorization: str = Header(default=""),
):
    await ensure_ready()
    settings = get_settings()
    secret = settings.cron_secret or settings.admin_token
    if secret:
        auth = authorization.replace("Bearer ", "").strip()
        q = request.query_params.get("secret", "")
        if auth != secret and q != secret:
            raise HTTPException(403, "Forbidden")

    if not engine:
        return {"sent": 0}
    n = await engine.process_reminders()
    return {"sent": n}


@app.get("/admin/stats")
async def admin_stats(authorization: str = Header(default="")):
    settings = get_settings()
    if settings.admin_token:
        if authorization.replace("Bearer ", "").strip() != settings.admin_token:
            raise HTTPException(403, "Forbidden")
    await store.init()
    return JSONResponse(await store.get_stats())


@app.get("/admin/candidates")
async def admin_candidates(
    authorization: str = Header(default=""),
    vacancy_id: int | None = None,
    limit: int = 50,
):
    settings = get_settings()
    if settings.admin_token:
        if authorization.replace("Bearer ", "").strip() != settings.admin_token:
            raise HTTPException(403, "Forbidden")
    await store.init()
    cands = await store.list_candidates(vacancy_id=vacancy_id, limit=limit)
    return [
        {
            "id": c.id,
            "name": c.name,
            "source": c.source,
            "match_score": c.match_score,
            "status": c.status,
            "vacancy_id": c.vacancy_id,
        }
        for c in cands
    ]


@app.get("/admin/slots")
async def admin_slots(authorization: str = Header(default="")):
    settings = get_settings()
    if settings.admin_token:
        if authorization.replace("Bearer ", "").strip() != settings.admin_token:
            raise HTTPException(403, "Forbidden")
    slots = available_slots(tz_name=settings.bot_timezone)
    if gcal_client and gcal_client.available:
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(settings.bot_timezone)
        now = datetime.now(tz)
        busy = gcal_client.get_busy_slots(now, now + timedelta(days=7))
        slots = gcal_client.filter_available_slots(slots, busy)
    return [{"id": s.slot_id, "label_ru": s.label_ru, "starts_at": s.starts_at.isoformat()} for s in slots]
