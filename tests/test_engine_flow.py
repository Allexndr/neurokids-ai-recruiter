import pytest
from unittest.mock import AsyncMock, MagicMock

from app.bot.engine import BotEngine
from app.bot.states import State
from app.config import Settings
from app.storage.db import Session


@pytest.fixture
def engine():
    settings = Settings(
        telegram_bot_token="x",
        together_api_key="",
        fallback_attempts_max=2,
    )
    tg = MagicMock()
    tg.send_message = AsyncMock()
    return BotEngine(settings, None, tg)


@pytest.mark.asyncio
async def test_old_age_not_rejected(engine):
    session = Session(
        chat_id="1",
        state=State.COLLECT_NAME_AGE.value,
        lang="ru",
        profile={"ui_mode": "telegram", "lang_locked": True},
    )
    reply = await engine.handle(session, "Данияр")
    assert session.state == State.COLLECT_STUDENT.value
    assert session.profile.get("name") == "Данияр"
    assert "Атаман" not in reply.text
    assert reply.reply_markup is not None


@pytest.mark.asyncio
async def test_step_by_step_tz_flow(engine):
    session = Session(
        chat_id="2",
        state=State.COLLECT_NAME_AGE.value,
        lang="ru",
        profile={"ui_mode": "telegram", "lang_locked": True},
    )
    await engine.handle(session, "Айым")
    assert session.profile.get("name") == "Айым"
    assert session.state == State.COLLECT_STUDENT.value
    await engine.handle(session, "job:yes", is_callback=True)
    assert session.profile.get("job_search_active") is True
    assert session.state == State.COLLECT_EXPERIENCE.value
    reply = await engine.handle(session, "3 года в продажах, CRM, хочу в HR")
    assert session.state == State.WELCOME_QUALIFIED.value
    assert "Neurokids" in reply.text
    assert reply.reply_markup is not None


@pytest.mark.asyncio
async def test_not_looking_closes(engine):
    session = Session(
        chat_id="3",
        state=State.COLLECT_STUDENT.value,
        lang="ru",
        profile={"ui_mode": "telegram", "lang_locked": True, "name": "Test"},
    )
    reply = await engine.handle(session, "job:no", is_callback=True)
    assert session.state == State.CLOSED.value
    assert session.profile.get("job_search_active") is False
    assert reply.reply_markup is not None


@pytest.mark.asyncio
async def test_menu_text_shows_buttons_not_commands(engine):
    session = Session(
        chat_id="4",
        state=State.WELCOME_QUALIFIED.value,
        lang="ru",
        profile={"ui_mode": "telegram", "lang_locked": True, "name": "Айым"},
    )
    reply = await engine.handle(session, "привет")
    assert "Neurokids" in reply.text
    assert reply.reply_markup is not None
    assert "act:schedule" in str(reply.reply_markup)


@pytest.mark.asyncio
async def test_faq_topic_callback(engine):
    session = Session(
        chat_id="5",
        state=State.WELCOME_QUALIFIED.value,
        lang="ru",
        profile={"ui_mode": "telegram", "lang_locked": True, "name": "Айым"},
    )
    reply = await engine.handle(session, "faq:salary", is_callback=True)
    assert "собеседован" in reply.text.lower() or "hr" in reply.text.lower()
    assert "faq:schedule" in str(reply.reply_markup)
