"""Выбор бэкенда: MongoDB Atlas на Vercel, SQLite локально/в тестах."""

from __future__ import annotations

import os

from app.config import get_settings


def create_store():
    settings = get_settings()
    mongo_uri = settings.mongodb_uri or os.environ.get("MONGODB_URI", "")
    if mongo_uri:
        from app.storage.mongo_store import MongoStore

        return MongoStore(mongo_uri, db_name=settings.mongodb_db_name)
    from app.storage.db import Store

    return Store(settings.database_path)
