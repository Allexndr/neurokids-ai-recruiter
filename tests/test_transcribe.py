import pytest
from unittest.mock import AsyncMock, patch

from app.config import Settings
from app.interview.transcribe import transcribe_audio


@pytest.mark.asyncio
async def test_transcribe_uses_together_when_configured():
    settings = Settings(
        together_api_key="tgp_test",
        groq_api_key="gsk_test",
    )
    with patch(
        "app.interview.transcribe._transcribe_together",
        new_callable=AsyncMock,
        return_value="привет",
    ) as together:
        text = await transcribe_audio(settings, b"audio", "chunk.ogg")
    assert text == "привет"
    together.assert_awaited_once()


@pytest.mark.asyncio
async def test_stt_configured_with_together_only():
    settings = Settings(together_api_key="tgp_test")
    assert settings.is_stt_configured is True


@pytest.mark.asyncio
async def test_transcribe_falls_back_to_groq():
    settings = Settings(together_api_key="tgp_test", groq_api_key="gsk_test")
    with (
        patch(
            "app.interview.transcribe._transcribe_together",
            new_callable=AsyncMock,
            return_value="",
        ),
        patch(
            "app.interview.transcribe._transcribe_groq",
            new_callable=AsyncMock,
            return_value="из groq",
        ) as groq,
    ):
        text = await transcribe_audio(settings, b"audio", "chunk.ogg")
    assert text == "из groq"
    groq.assert_awaited_once()
