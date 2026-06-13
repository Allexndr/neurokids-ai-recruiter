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
async def test_reject_old_candidate(engine):
    session = Session(
        chat_id="1",
        state=State.COLLECT_NAME_AGE.value,
        lang="kk",
        profile={"ui_mode": "telegram", "lang_locked": True},
    )
    reply = await engine.handle(session, "Данияр, 32, жоқ, жоқ")
    assert session.state == State.REJECTED.value
    assert "30" in reply.text


@pytest.mark.asyncio
async def test_step_by_step_profile(engine):
    session = Session(
        chat_id="2",
        state=State.COLLECT_NAME_AGE.value,
        lang="ru",
        profile={"ui_mode": "whatsapp", "lang_locked": True},
    )
    await engine.handle(session, "Айым, 25")
    assert session.profile.get("age") == 25
    assert session.state == State.COLLECT_STUDENT.value
    await engine.handle(session, "2")
    assert session.profile.get("is_student") is False
    await engine.handle(session, "2")
    assert session.profile.get("has_experience") is False
    assert session.state == State.COLLECT_CITY.value


@pytest.mark.asyncio
async def test_language_svobodno_qualifies(engine):
    session = Session(
        chat_id="3",
        state=State.COLLECT_LANGUAGE.value,
        lang="ru",
        profile={
            "ui_mode": "telegram",
            "lang_locked": True,
            "name": "Айым",
            "age": 25,
            "is_student": False,
            "has_experience": False,
            "city": "almaty",
            "schedule_ok": True,
        },
    )
    reply = await engine.handle(session, "свободно")
    assert session.profile.get("language_ok") is True
    assert session.state != State.REJECTED.value
    assert "не подходите" not in reply.text.lower()
