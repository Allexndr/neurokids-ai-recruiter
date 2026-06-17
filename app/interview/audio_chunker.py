"""Split long Telegram voice/audio into Whisper-safe chunks."""

from __future__ import annotations

import io
import logging
import math

logger = logging.getLogger(__name__)

WHISPER_MAX_BYTES = 24 * 1024 * 1024


def estimate_total_chunks(duration_sec: int, chunk_sec: int) -> int:
    duration_sec = max(1, duration_sec)
    chunk_sec = max(60, chunk_sec)
    return max(1, math.ceil(duration_sec / chunk_sec))


def extract_chunk_bytes(
    audio_bytes: bytes,
    chunk_index: int,
    chunk_sec: int,
    fmt: str = "ogg",
) -> bytes:
    """Return bytes for chunk_index (0-based). Falls back to full file if ffmpeg unavailable."""
    try:
        from pydub import AudioSegment

        try:
            import imageio_ffmpeg

            AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass

        audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format=fmt)
        start_ms = chunk_index * chunk_sec * 1000
        end_ms = min(len(audio), start_ms + chunk_sec * 1000)
        if start_ms >= len(audio):
            return b""
        segment = audio[start_ms:end_ms]
        out = io.BytesIO()
        export_fmt = "mp3" if fmt not in ("ogg", "opus", "webm") else "ogg"
        segment.export(out, format=export_fmt)
        data = out.getvalue()
        if len(data) > WHISPER_MAX_BYTES:
            half = chunk_sec // 2
            if half >= 60:
                return extract_chunk_bytes(audio_bytes, chunk_index * 2, half, fmt)
        return data
    except Exception as e:
        logger.warning("Chunk extract failed (chunk %s): %s", chunk_index, e)
        if chunk_index == 0:
            return audio_bytes[:WHISPER_MAX_BYTES]
        return b""
