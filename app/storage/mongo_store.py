"""MongoDB Atlas — постоянное хранилище для Vercel (вместо /tmp SQLite)."""

from __future__ import annotations

import json
import time
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from pymongo import ReturnDocument

from app.storage.db import Candidate, Session, Vacancy, VoiceJob


class MongoStore:
    def __init__(self, uri: str, db_name: str = "hr_recruiter_bot"):
        self.uri = uri
        self.db_name = db_name
        self._client: AsyncIOMotorClient | None = None
        self._db: AsyncIOMotorDatabase | None = None
        self._ready = False

    @property
    def db(self) -> AsyncIOMotorDatabase:
        assert self._db is not None
        return self._db

    async def init(self) -> None:
        if self._ready:
            return
        self._client = AsyncIOMotorClient(self.uri, serverSelectionTimeoutMS=8000)
        self._db = self._client[self.db_name]
        await self._client.admin.command("ping")
        await self._ensure_indexes()
        self._ready = True

    async def _ensure_indexes(self) -> None:
        await self.db.sessions.create_index("chat_id", unique=True)
        await self.db.candidates.create_index("chat_id")
        await self.db.candidates.create_index([("match_score", -1)])
        await self.db.voice_jobs.create_index([("status", 1), ("updated_at", 1)])
        await self.db.messages.create_index([("candidate_id", 1), ("created_at", -1)])

    async def _next_id(self, name: str) -> int:
        doc = await self.db.counters.find_one_and_update(
            {"_id": name},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return int(doc["seq"])

    # --- sessions ---

    async def get_session(self, chat_id: str) -> Session:
        await self.init()
        row = await self.db.sessions.find_one({"chat_id": chat_id})
        if not row:
            return Session(chat_id=chat_id, state="choose_lang", updated_at=int(time.time()))
        return self._doc_to_session(row)

    def _doc_to_session(self, row: dict[str, Any]) -> Session:
        profile = row.get("profile")
        if isinstance(profile, str):
            profile = json.loads(profile or "{}")
        return Session(
            chat_id=row["chat_id"],
            state=row.get("state", "choose_lang"),
            lang=row.get("lang") or "ru",
            profile=profile or {},
            clarify_attempts=row.get("clarify_attempts") or 0,
            contact_name=row.get("contact_name"),
            interview_at=row.get("interview_at"),
            interview_label=row.get("interview_label"),
            reminder_24_sent=bool(row.get("reminder_24_sent")),
            reminder_2_sent=bool(row.get("reminder_2_sent")),
            reminder_1_sent=bool(row.get("reminder_1_sent")),
            interview_confirmed=row.get("interview_confirmed"),
            candidate_id=row.get("candidate_id"),
            vacancy_id=row.get("vacancy_id"),
            calendar_event_id=row.get("calendar_event_id"),
            status=row.get("status") or "new",
            updated_at=row.get("updated_at") or 0,
        )

    async def save_session(self, s: Session) -> None:
        await self.init()
        s.updated_at = int(time.time())
        doc = {
            "chat_id": s.chat_id,
            "state": s.state,
            "lang": s.lang,
            "profile": s.profile,
            "clarify_attempts": s.clarify_attempts,
            "contact_name": s.contact_name,
            "interview_at": s.interview_at,
            "interview_label": s.interview_label,
            "reminder_24_sent": int(s.reminder_24_sent),
            "reminder_2_sent": int(s.reminder_2_sent),
            "reminder_1_sent": int(s.reminder_1_sent),
            "interview_confirmed": int(s.interview_confirmed) if s.interview_confirmed is not None else None,
            "candidate_id": s.candidate_id,
            "vacancy_id": s.vacancy_id,
            "calendar_event_id": s.calendar_event_id,
            "status": s.status,
            "updated_at": s.updated_at,
        }
        await self.db.sessions.update_one({"chat_id": s.chat_id}, {"$set": doc}, upsert=True)

    async def reset_session(self, chat_id: str) -> Session:
        s = Session(chat_id=chat_id, state="choose_lang", updated_at=int(time.time()))
        await self.save_session(s)
        return s

    async def log_message(
        self, chat_id: str, direction: str, body: str, candidate_id: int | None = None, channel: str = "telegram"
    ) -> None:
        await self.init()
        await self.db.messages.insert_one(
            {
                "id": await self._next_id("messages"),
                "chat_id": chat_id,
                "candidate_id": candidate_id,
                "channel": channel,
                "direction": direction,
                "body": body[:2000],
                "created_at": int(time.time()),
            }
        )

    async def bump_stat(self, key: str, n: int = 1) -> None:
        await self.init()
        await self.db.stats.update_one({"key": key}, {"$inc": {"value": n}}, upsert=True)

    async def get_stats(self) -> dict[str, int]:
        await self.init()
        out: dict[str, int] = {}
        async for row in self.db.stats.find({}):
            out[row["key"]] = int(row.get("value", 0))
        return out

    async def due_reminders(self, now_ts: int) -> list[Session]:
        await self.init()
        cursor = self.db.sessions.find(
            {"interview_at": {"$ne": None}, "status": {"$nin": ["rejected", "no_show"]}}
        )
        out: list[Session] = []
        async for row in cursor:
            s = self._doc_to_session(row)
            if s.interview_at:
                out.append(s)
        _ = now_ts
        return out

    # --- vacancies ---

    async def create_vacancy(self, title: str, criteria: dict[str, Any], hh_search_query: str = "") -> int:
        await self.init()
        vid = await self._next_id("vacancies")
        await self.db.vacancies.insert_one(
            {
                "id": vid,
                "title": title,
                "criteria": criteria,
                "hh_vacancy_id": None,
                "hh_search_query": hh_search_query,
                "active": True,
                "created_at": int(time.time()),
            }
        )
        return vid

    def _doc_to_vacancy(self, row: dict[str, Any]) -> Vacancy:
        criteria = row.get("criteria")
        if isinstance(criteria, str):
            criteria = json.loads(criteria or "{}")
        return Vacancy(
            id=row["id"],
            title=row["title"],
            criteria=criteria or {},
            hh_vacancy_id=row.get("hh_vacancy_id"),
            hh_search_query=row.get("hh_search_query"),
            active=bool(row.get("active", True)),
            created_at=row.get("created_at", 0),
        )

    async def get_vacancy(self, vacancy_id: int) -> Vacancy | None:
        await self.init()
        row = await self.db.vacancies.find_one({"id": vacancy_id})
        return self._doc_to_vacancy(row) if row else None

    async def list_vacancies(self, active_only: bool = True) -> list[Vacancy]:
        await self.init()
        q: dict[str, Any] = {"active": True} if active_only else {}
        cursor = self.db.vacancies.find(q).sort("id", -1)
        return [self._doc_to_vacancy(r) async for r in cursor]

    async def get_active_vacancy(self) -> Vacancy | None:
        vacs = await self.list_vacancies(active_only=True)
        return vacs[0] if vacs else None

    # --- candidates ---

    async def upsert_candidate(
        self,
        source: str,
        name: str | None = None,
        chat_id: str | None = None,
        resume_text: str | None = None,
        vacancy_id: int | None = None,
        match_score: int | None = None,
        match_summary: str | None = None,
        profile: dict[str, Any] | None = None,
        external_id: str | None = None,
        status: str = "new",
        resume_blob_url: str | None = None,
    ) -> int:
        await self.init()
        now = int(time.time())
        prof = profile or {}
        if resume_blob_url:
            prof = {**prof, "resume_blob_url": resume_blob_url}

        if chat_id:
            existing = await self.db.candidates.find_one({"chat_id": chat_id})
            if existing:
                cid = existing["id"]
                upd: dict[str, Any] = {"profile": prof, "status": status, "updated_at": now}
                if name is not None:
                    upd["name"] = name
                if resume_text is not None:
                    upd["resume_text"] = resume_text
                if match_score is not None:
                    upd["match_score"] = match_score
                if match_summary is not None:
                    upd["match_summary"] = match_summary
                if vacancy_id is not None:
                    upd["vacancy_id"] = vacancy_id
                await self.db.candidates.update_one({"id": cid}, {"$set": upd})
                return cid

        cid = await self._next_id("candidates")
        await self.db.candidates.insert_one(
            {
                "id": cid,
                "source": source,
                "external_id": external_id,
                "chat_id": chat_id,
                "name": name,
                "contact": None,
                "resume_text": resume_text,
                "profile": prof,
                "match_score": match_score,
                "match_summary": match_summary,
                "status": status,
                "vacancy_id": vacancy_id,
                "created_at": now,
                "updated_at": now,
            }
        )
        return cid

    def _doc_to_candidate(self, row: dict[str, Any]) -> Candidate:
        profile = row.get("profile")
        if isinstance(profile, str):
            profile = json.loads(profile or "{}")
        return Candidate(
            id=row["id"],
            source=row.get("source", "telegram"),
            external_id=row.get("external_id"),
            chat_id=row.get("chat_id"),
            name=row.get("name"),
            contact=row.get("contact"),
            resume_text=row.get("resume_text"),
            profile=profile or {},
            match_score=row.get("match_score"),
            match_summary=row.get("match_summary"),
            status=row.get("status", "new"),
            vacancy_id=row.get("vacancy_id"),
            created_at=row.get("created_at", 0),
            updated_at=row.get("updated_at", 0),
        )

    async def get_candidate(self, candidate_id: int) -> Candidate | None:
        await self.init()
        row = await self.db.candidates.find_one({"id": candidate_id})
        return self._doc_to_candidate(row) if row else None

    async def list_candidates(
        self, vacancy_id: int | None = None, limit: int = 20, order_by_score: bool = True
    ) -> list[Candidate]:
        await self.init()
        q: dict[str, Any] = {}
        if vacancy_id:
            q["vacancy_id"] = vacancy_id
        sort = [("match_score", -1), ("id", -1)] if order_by_score else [("id", -1)]
        cursor = self.db.candidates.find(q).sort(sort).limit(limit)
        return [self._doc_to_candidate(r) async for r in cursor]

    async def search_candidates(self, query: str, limit: int = 10) -> list[Candidate]:
        await self.init()
        import re

        rx = re.compile(re.escape(query), re.IGNORECASE)
        cursor = (
            self.db.candidates.find(
                {"$or": [{"name": rx}, {"resume_text": rx}, {"match_summary": rx}]}
            )
            .sort([("match_score", -1)])
            .limit(limit)
        )
        return [self._doc_to_candidate(r) async for r in cursor]

    async def find_candidate_by_external(self, source: str, external_id: str) -> Candidate | None:
        await self.init()
        row = await self.db.candidates.find_one({"source": source, "external_id": external_id})
        return self._doc_to_candidate(row) if row else None

    async def add_hr_comment(self, candidate_id: int, text: str) -> bool:
        await self.init()
        c = await self.get_candidate(candidate_id)
        if not c:
            return False
        now = int(time.time())
        profile = dict(c.profile or {})
        comments = list(profile.get("hr_comments") or [])
        comments.append({"text": text.strip(), "at": now})
        profile["hr_comments"] = comments[-50:]
        await self.db.candidates.update_one(
            {"id": candidate_id},
            {"$set": {"profile": profile, "updated_at": now}},
        )
        return True

    async def set_vacancy_hh_id(self, vacancy_id: int, hh_vacancy_id: str) -> bool:
        await self.init()
        r = await self.db.vacancies.update_one(
            {"id": vacancy_id},
            {"$set": {"hh_vacancy_id": hh_vacancy_id.strip()}},
        )
        return r.modified_count > 0

    async def get_latest_interview_analysis(self, candidate_id: int) -> dict | None:
        await self.init()
        row = await self.db.interview_analysis.find_one(
            {"candidate_id": candidate_id},
            sort=[("id", -1)],
        )
        if not row:
            return None
        profile = row.get("profile")
        if isinstance(profile, str):
            profile = json.loads(profile or "{}")
        return {
            "transcript": row.get("transcript"),
            "summary": row.get("summary"),
            "profile": profile or {},
            "created_at": row.get("created_at"),
        }

    # --- interviews ---

    async def create_interview(self, candidate_id: int, scheduled_at: int, calendar_event_id: str | None = None) -> int:
        await self.init()
        iid = await self._next_id("interviews")
        await self.db.interviews.insert_one(
            {
                "id": iid,
                "candidate_id": candidate_id,
                "scheduled_at": scheduled_at,
                "calendar_event_id": calendar_event_id,
                "created_at": int(time.time()),
            }
        )
        return iid

    async def save_interview_analysis(
        self, candidate_id: int, transcript: str, summary: str, profile: dict[str, Any], interview_id: int | None = None
    ) -> int:
        await self.init()
        aid = await self._next_id("interview_analysis")
        await self.db.interview_analysis.insert_one(
            {
                "id": aid,
                "interview_id": interview_id,
                "candidate_id": candidate_id,
                "transcript": transcript,
                "summary": summary,
                "profile": profile,
                "created_at": int(time.time()),
            }
        )
        return aid

    async def get_candidate_messages(self, candidate_id: int, limit: int = 30) -> list[dict[str, Any]]:
        await self.init()
        cursor = (
            self.db.messages.find({"candidate_id": candidate_id})
            .sort("created_at", -1)
            .limit(limit)
        )
        return [
            {
                "direction": r["direction"],
                "body": r["body"],
                "created_at": r["created_at"],
                "channel": r.get("channel", "telegram"),
            }
            async for r in cursor
        ]

    # --- voice jobs ---

    def _doc_to_voice_job(self, row: dict[str, Any]) -> VoiceJob:
        parts = row.get("parts")
        if isinstance(parts, str):
            parts = json.loads(parts or "[]")
        return VoiceJob(
            id=row["id"],
            chat_id=row["chat_id"],
            file_id=row["file_id"],
            duration_sec=row.get("duration_sec", 0),
            file_size=row.get("file_size", 0),
            mime_hint=row.get("mime_hint") or "ogg",
            candidate_id=row.get("candidate_id"),
            contact_name=row.get("contact_name"),
            status=row.get("status", "pending"),
            chunk_index=row.get("chunk_index", 0),
            total_chunks=row.get("total_chunks", 1),
            parts=parts or [],
            error=row.get("error"),
            audio_blob_url=row.get("audio_blob_url"),
            created_at=row.get("created_at", 0),
            updated_at=row.get("updated_at", 0),
        )

    async def create_voice_job(
        self,
        chat_id: str,
        file_id: str,
        duration_sec: int,
        file_size: int,
        total_chunks: int,
        candidate_id: int | None = None,
        contact_name: str | None = None,
        mime_hint: str = "ogg",
    ) -> int:
        await self.init()
        now = int(time.time())
        jid = await self._next_id("voice_jobs")
        await self.db.voice_jobs.insert_one(
            {
                "id": jid,
                "chat_id": chat_id,
                "file_id": file_id,
                "duration_sec": duration_sec,
                "file_size": file_size,
                "mime_hint": mime_hint,
                "candidate_id": candidate_id,
                "contact_name": contact_name,
                "status": "pending",
                "chunk_index": 0,
                "total_chunks": total_chunks,
                "parts": [],
                "error": None,
                "audio_blob_url": None,
                "created_at": now,
                "updated_at": now,
            }
        )
        return jid

    async def get_voice_job(self, job_id: int) -> VoiceJob | None:
        await self.init()
        row = await self.db.voice_jobs.find_one({"id": job_id})
        return self._doc_to_voice_job(row) if row else None

    async def set_voice_job_blob(self, job_id: int, blob_url: str) -> None:
        await self.init()
        await self.db.voice_jobs.update_one(
            {"id": job_id},
            {"$set": {"audio_blob_url": blob_url, "updated_at": int(time.time())}},
        )

    async def mark_voice_job_processing(self, job_id: int) -> None:
        await self.init()
        await self.db.voice_jobs.update_one(
            {"id": job_id, "status": {"$in": ["pending", "processing"]}},
            {"$set": {"status": "processing", "updated_at": int(time.time())}},
        )

    async def append_voice_chunk(self, job_id: int, text: str) -> VoiceJob | None:
        await self.init()
        job = await self.get_voice_job(job_id)
        if not job:
            return None
        parts = list(job.parts)
        parts.append(text)
        await self.db.voice_jobs.update_one(
            {"id": job_id},
            {
                "$set": {
                    "chunk_index": job.chunk_index + 1,
                    "parts": parts,
                    "status": "processing",
                    "updated_at": int(time.time()),
                }
            },
        )
        return await self.get_voice_job(job_id)

    async def complete_voice_job(self, job_id: int) -> None:
        await self.init()
        await self.db.voice_jobs.update_one(
            {"id": job_id},
            {"$set": {"status": "done", "updated_at": int(time.time())}},
        )

    async def fail_voice_job(self, job_id: int, error: str) -> None:
        await self.init()
        await self.db.voice_jobs.update_one(
            {"id": job_id},
            {"$set": {"status": "failed", "error": error[:500], "updated_at": int(time.time())}},
        )

    async def list_stale_voice_jobs(self, limit: int = 5, stale_sec: int = 90) -> list[VoiceJob]:
        await self.init()
        cutoff = int(time.time()) - stale_sec
        cursor = (
            self.db.voice_jobs.find(
                {"status": {"$in": ["pending", "processing"]}, "updated_at": {"$lt": cutoff}}
            )
            .sort("updated_at", 1)
            .limit(limit)
        )
        return [self._doc_to_voice_job(r) async for r in cursor]
