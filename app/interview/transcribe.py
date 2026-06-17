"""Speech-to-text: Together Whisper → Groq → OpenAI."""

from __future__ import annotations

import logging

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

TOGETHER_AUDIO = "https://api.together.ai/v1/audio/transcriptions"
GROQ_AUDIO = "https://api.groq.com/openai/v1/audio/transcriptions"
OPENAI_AUDIO = "https://api.openai.com/v1/audio/transcriptions"


async def transcribe_audio(settings: Settings, audio_bytes: bytes, filename: str = "audio.ogg") -> str:
    if settings.together_api_key:
        text = await _transcribe_together(settings.together_api_key, audio_bytes, filename)
        if text:
            return text

    if settings.groq_api_key:
        text = await _transcribe_groq(settings.groq_api_key, audio_bytes, filename)
        if text:
            return text

    if settings.openai_api_key:
        text = await _transcribe_openai(settings.openai_api_key, audio_bytes, filename)
        if text:
            return text

    return ""


async def _transcribe_together(api_key: str, data: bytes, filename: str) -> str:
    headers = {"Authorization": f"Bearer {api_key}"}
    files = {"file": (filename, data, "audio/ogg")}
    form = {"model": "openai/whisper-large-v3", "language": "ru", "response_format": "json"}
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            r = await client.post(TOGETHER_AUDIO, headers=headers, files=files, data=form)
            r.raise_for_status()
            payload = r.json()
            if isinstance(payload, dict):
                return (payload.get("text") or "").strip()
            return ""
    except Exception as e:
        logger.warning("Together Whisper failed: %s", e)
        return ""


async def _transcribe_groq(api_key: str, data: bytes, filename: str) -> str:
    headers = {"Authorization": f"Bearer {api_key}"}
    files = {"file": (filename, data, "audio/ogg")}
    form = {"model": "whisper-large-v3", "language": "ru"}
    try:
        async with httpx.AsyncClient(timeout=55.0) as client:
            r = await client.post(GROQ_AUDIO, headers=headers, files=files, data=form)
            r.raise_for_status()
            return r.json().get("text", "").strip()
    except Exception as e:
        logger.warning("Groq Whisper failed: %s", e)
        return ""


async def _transcribe_openai(api_key: str, data: bytes, filename: str) -> str:
    headers = {"Authorization": f"Bearer {api_key}"}
    files = {"file": (filename, data, "audio/ogg")}
    form = {"model": "whisper-1", "language": "ru"}
    try:
        async with httpx.AsyncClient(timeout=55.0) as client:
            r = await client.post(OPENAI_AUDIO, headers=headers, files=files, data=form)
            r.raise_for_status()
            return r.json().get("text", "").strip()
    except Exception as e:
        logger.warning("OpenAI Whisper failed: %s", e)
        return ""
