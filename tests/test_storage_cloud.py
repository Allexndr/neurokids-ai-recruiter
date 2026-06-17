import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.storage.blob import BlobStore
from app.storage.factory import create_store


def test_blob_store_unavailable_without_token():
    b = BlobStore("")
    assert b.available is False


@pytest.mark.asyncio
async def test_blob_put_returns_none_without_token():
    b = BlobStore("")
    assert await b.put("x", b"data") is None


@pytest.mark.asyncio
async def test_factory_uses_sqlite_by_default(monkeypatch):
    monkeypatch.delenv("MONGODB_URI", raising=False)
    from app.config import get_settings

    get_settings.cache_clear()
    with patch.dict("os.environ", {}, clear=False):
        monkeypatch.setenv("MONGODB_URI", "")
        get_settings.cache_clear()
        from app.config import get_settings as gs

        gs.cache_clear()
        store = create_store()
    assert type(store).__name__ == "Store"


@pytest.mark.asyncio
async def test_factory_uses_mongo_when_uri_set(monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017/test")
    get_settings.cache_clear()
    store = create_store()
    assert type(store).__name__ == "MongoStore"


@pytest.mark.asyncio
async def test_blob_put_voice_path():
    b = BlobStore("test-token", prefix="neurokids-hr-bot")
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value={"url": "https://blob.example/voice.bin"})

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.storage.blob.httpx.AsyncClient", return_value=mock_client):
        url = await b.put_voice_audio(42, b"audio-bytes", "audio/ogg")

    assert url == "https://blob.example/voice.bin"
    call_headers = mock_client.put.await_args.kwargs["headers"]
    assert call_headers["x-pathname"] == "neurokids-hr-bot/voice/job_42.bin"
