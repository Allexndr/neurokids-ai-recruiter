from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_database_path() -> str:
    if os.environ.get("VERCEL") == "1":
        return "/tmp/hr_recruiter.sqlite3"
    return "data/bot.sqlite3"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    webhook_base_url: str = ""
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = "changeme"
    telegram_hr_chat_id: str = ""
    hr_pin: str = ""

    ai_provider: str = "together"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    openrouter_api_key: str = ""
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    together_api_key: str = ""
    together_model: str = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
    openai_api_key: str = ""

    hh_client_id: str = ""
    hh_client_secret: str = ""
    hh_access_token: str = ""

    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = "changeme"

    google_calendar_id: str = ""
    google_service_account_json: str = ""

    bot_timezone: str = "Europe/Moscow"
    cron_secret: str = ""
    admin_token: str = ""

    database_path: str = Field(default_factory=_default_database_path)
    database_url: str = ""
    mongodb_uri: str = Field(default="", validation_alias="MONGODB_URI")
    mongodb_db_name: str = "hr_recruiter_bot"
    blob_read_write_token: str = ""
    blob_prefix: str = "botforbus-blob"

    fallback_attempts_max: int = 2

    voice_chunk_seconds: int = 300
    max_voice_duration_sec: int = 2400
    max_voice_bytes: int = 20 * 1024 * 1024

    @property
    def telegram_webhook_url(self) -> str:
        return f"{self.webhook_base_url.rstrip('/')}/webhook/telegram"

    @property
    def whatsapp_webhook_url(self) -> str:
        return f"{self.webhook_base_url.rstrip('/')}/webhook/whatsapp"

    @property
    def is_telegram_configured(self) -> bool:
        return bool(self.telegram_bot_token)

    @property
    def is_llm_configured(self) -> bool:
        return bool(self.groq_api_key or self.openrouter_api_key or self.together_api_key)

    @property
    def is_together_configured(self) -> bool:
        return bool(self.together_api_key)

    @property
    def is_stt_configured(self) -> bool:
        return bool(self.together_api_key or self.groq_api_key or self.openai_api_key)

    @property
    def is_hr_notify_configured(self) -> bool:
        return bool(self.telegram_hr_chat_id and self.telegram_bot_token)

    @property
    def is_whatsapp_configured(self) -> bool:
        return bool(self.whatsapp_token and self.whatsapp_phone_number_id)

    @property
    def is_hh_configured(self) -> bool:
        return bool(self.hh_access_token)

    @property
    def is_google_calendar_configured(self) -> bool:
        return bool(self.google_calendar_id and self.google_service_account_json)

    @property
    def is_mongodb_configured(self) -> bool:
        return bool(self.mongodb_uri)

    @property
    def is_blob_configured(self) -> bool:
        return bool(self.blob_read_write_token)

    @property
    def hr_chat_ids(self) -> set[str]:
        return {s.strip() for s in self.telegram_hr_chat_id.split(",") if s.strip()}

    def is_hr_chat(self, chat_id: str) -> bool:
        ids = self.hr_chat_ids
        return bool(ids) and str(chat_id) in ids


@lru_cache
def get_settings() -> Settings:
    return Settings()
