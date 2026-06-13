from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiosqlite

from app.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    chat_id TEXT PRIMARY KEY,
    state TEXT NOT NULL DEFAULT 'choose_view',
    lang TEXT NOT NULL DEFAULT 'ru',
    profile_json TEXT NOT NULL DEFAULT '{}',
    clarify_attempts INTEGER NOT NULL DEFAULT 0,
    contact_name TEXT,
    interview_at INTEGER,
    interview_label TEXT,
    reminder_24_sent INTEGER NOT NULL DEFAULT 0,
    reminder_2_sent INTEGER NOT NULL DEFAULT 0,
    reminder_1_sent INTEGER NOT NULL DEFAULT 0,
    interview_confirmed INTEGER,
    candidate_id INTEGER,
    vacancy_id INTEGER,
    calendar_event_id TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL,
    candidate_id INTEGER,
    channel TEXT NOT NULL DEFAULT 'telegram',
    direction TEXT NOT NULL,
    body TEXT,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS stats (
    key TEXT PRIMARY KEY,
    value INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS vacancies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    criteria_json TEXT NOT NULL DEFAULT '{}',
    hh_vacancy_id TEXT,
    hh_search_query TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL DEFAULT 'telegram',
    external_id TEXT,
    chat_id TEXT,
    name TEXT,
    contact TEXT,
    resume_text TEXT,
    profile_json TEXT NOT NULL DEFAULT '{}',
    match_score INTEGER,
    match_summary TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    vacancy_id INTEGER,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS interviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL,
    scheduled_at INTEGER NOT NULL,
    calendar_event_id TEXT,
    reminder_24_sent INTEGER NOT NULL DEFAULT 0,
    reminder_1_sent INTEGER NOT NULL DEFAULT 0,
    confirmed INTEGER,
    status TEXT NOT NULL DEFAULT 'scheduled',
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS interview_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interview_id INTEGER,
    candidate_id INTEGER NOT NULL,
    transcript TEXT,
    summary TEXT,
    profile_json TEXT NOT NULL DEFAULT '{}',
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_interview ON sessions(interview_at);
CREATE INDEX IF NOT EXISTS idx_candidates_vacancy ON candidates(vacancy_id);
CREATE INDEX IF NOT EXISTS idx_candidates_score ON candidates(match_score);
CREATE INDEX IF NOT EXISTS idx_messages_candidate ON messages(candidate_id);
"""


@dataclass
class Session:
    chat_id: str
    state: str
    lang: str = "ru"
    profile: dict[str, Any] = field(default_factory=dict)
    clarify_attempts: int = 0
    contact_name: str | None = None
    interview_at: int | None = None
    interview_label: str | None = None
    reminder_24_sent: bool = False
    reminder_2_sent: bool = False
    reminder_1_sent: bool = False
    interview_confirmed: bool | None = None
    candidate_id: int | None = None
    vacancy_id: int | None = None
    calendar_event_id: str | None = None
    status: str = "new"
    updated_at: int = 0


@dataclass
class Vacancy:
    id: int
    title: str
    criteria: dict[str, Any] = field(default_factory=dict)
    hh_vacancy_id: str | None = None
    hh_search_query: str | None = None
    active: bool = True
    created_at: int = 0


@dataclass
class Candidate:
    id: int
    source: str = "telegram"
    external_id: str | None = None
    chat_id: str | None = None
    name: str | None = None
    contact: str | None = None
    resume_text: str | None = None
    profile: dict[str, Any] = field(default_factory=dict)
    match_score: int | None = None
    match_summary: str | None = None
    status: str = "new"
    vacancy_id: int | None = None
    created_at: int = 0
    updated_at: int = 0


class Store:
    def __init__(self, path: str):
        self.path = path
        self._ready = False

    async def init(self) -> None:
        if self._ready:
            return
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as conn:
            await conn.executescript(SCHEMA)
            await self._migrate(conn)
            await conn.commit()
        self._ready = True

    async def _migrate(self, conn: aiosqlite.Connection) -> None:
        cur = await conn.execute("PRAGMA table_info(sessions)")
        cols = {row[1] for row in await cur.fetchall()}
        migrations = [
            ("reminder_1_sent", "INTEGER NOT NULL DEFAULT 0"),
            ("interview_confirmed", "INTEGER"),
            ("candidate_id", "INTEGER"),
            ("vacancy_id", "INTEGER"),
            ("calendar_event_id", "TEXT"),
        ]
        for col, typedef in migrations:
            if col not in cols:
                await conn.execute(f"ALTER TABLE sessions ADD COLUMN {col} {typedef}")

    async def get_session(self, chat_id: str) -> Session:
        await self.init()
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute("SELECT * FROM sessions WHERE chat_id = ?", (chat_id,))
            row = await cur.fetchone()
        if not row:
            return Session(chat_id=chat_id, state="choose_view", updated_at=int(time.time()))
        return self._row_to_session(row)

    def _row_to_session(self, row: aiosqlite.Row) -> Session:
        keys = row.keys()
        return Session(
            chat_id=row["chat_id"],
            state=row["state"],
            lang=row["lang"] or "ru",
            profile=json.loads(row["profile_json"] or "{}"),
            clarify_attempts=row["clarify_attempts"] or 0,
            contact_name=row["contact_name"],
            interview_at=row["interview_at"],
            interview_label=row["interview_label"],
            reminder_24_sent=bool(row["reminder_24_sent"]),
            reminder_2_sent=bool(row["reminder_2_sent"]),
            reminder_1_sent=bool(row["reminder_1_sent"]) if "reminder_1_sent" in keys else False,
            interview_confirmed=bool(row["interview_confirmed"]) if row["interview_confirmed"] is not None else None,
            candidate_id=row["candidate_id"] if "candidate_id" in keys else None,
            vacancy_id=row["vacancy_id"] if "vacancy_id" in keys else None,
            calendar_event_id=row["calendar_event_id"] if "calendar_event_id" in keys else None,
            status=row["status"] or "new",
            updated_at=row["updated_at"] or 0,
        )

    async def save_session(self, s: Session) -> None:
        await self.init()
        s.updated_at = int(time.time())
        async with aiosqlite.connect(self.path) as conn:
            await conn.execute(
                """
                INSERT INTO sessions (
                    chat_id, state, lang, profile_json, clarify_attempts, contact_name,
                    interview_at, interview_label, reminder_24_sent, reminder_2_sent,
                    reminder_1_sent, interview_confirmed, candidate_id, vacancy_id,
                    calendar_event_id, status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    state=excluded.state, lang=excluded.lang, profile_json=excluded.profile_json,
                    clarify_attempts=excluded.clarify_attempts, contact_name=excluded.contact_name,
                    interview_at=excluded.interview_at, interview_label=excluded.interview_label,
                    reminder_24_sent=excluded.reminder_24_sent, reminder_2_sent=excluded.reminder_2_sent,
                    reminder_1_sent=excluded.reminder_1_sent, interview_confirmed=excluded.interview_confirmed,
                    candidate_id=excluded.candidate_id, vacancy_id=excluded.vacancy_id,
                    calendar_event_id=excluded.calendar_event_id,
                    status=excluded.status, updated_at=excluded.updated_at
                """,
                (
                    s.chat_id, s.state, s.lang, json.dumps(s.profile, ensure_ascii=False),
                    s.clarify_attempts, s.contact_name, s.interview_at, s.interview_label,
                    int(s.reminder_24_sent), int(s.reminder_2_sent), int(s.reminder_1_sent),
                    int(s.interview_confirmed) if s.interview_confirmed is not None else None,
                    s.candidate_id, s.vacancy_id, s.calendar_event_id, s.status, s.updated_at,
                ),
            )
            await conn.commit()

    async def reset_session(self, chat_id: str) -> Session:
        s = Session(chat_id=chat_id, state="choose_view", updated_at=int(time.time()))
        await self.save_session(s)
        return s

    async def log_message(
        self, chat_id: str, direction: str, body: str, candidate_id: int | None = None, channel: str = "telegram"
    ) -> None:
        await self.init()
        async with aiosqlite.connect(self.path) as conn:
            await conn.execute(
                "INSERT INTO messages (chat_id, candidate_id, channel, direction, body, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (chat_id, candidate_id, channel, direction, body[:2000], int(time.time())),
            )
            await conn.commit()

    async def bump_stat(self, key: str, n: int = 1) -> None:
        await self.init()
        async with aiosqlite.connect(self.path) as conn:
            await conn.execute(
                "INSERT INTO stats (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = value + excluded.value",
                (key, n),
            )
            await conn.commit()

    async def get_stats(self) -> dict[str, int]:
        await self.init()
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute("SELECT key, value FROM stats")
            rows = await cur.fetchall()
        return {r["key"]: r["value"] for r in rows}

    async def due_reminders(self, now_ts: int) -> list[Session]:
        await self.init()
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                """
                SELECT * FROM sessions
                WHERE interview_at IS NOT NULL
                  AND status NOT IN ('rejected', 'no_show')
                """
            )
            rows = await cur.fetchall()
        out: list[Session] = []
        for row in rows:
            s = self._row_to_session(row)
            if s.interview_at:
                out.append(s)
        _ = now_ts
        return out

    # --- Vacancies ---

    async def create_vacancy(self, title: str, criteria: dict[str, Any], hh_search_query: str = "") -> int:
        await self.init()
        now = int(time.time())
        async with aiosqlite.connect(self.path) as conn:
            cur = await conn.execute(
                "INSERT INTO vacancies (title, criteria_json, hh_search_query, created_at) VALUES (?, ?, ?, ?)",
                (title, json.dumps(criteria, ensure_ascii=False), hh_search_query, now),
            )
            await conn.commit()
            return cur.lastrowid or 0

    async def get_vacancy(self, vacancy_id: int) -> Vacancy | None:
        await self.init()
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute("SELECT * FROM vacancies WHERE id = ?", (vacancy_id,))
            row = await cur.fetchone()
        if not row:
            return None
        return Vacancy(
            id=row["id"], title=row["title"],
            criteria=json.loads(row["criteria_json"] or "{}"),
            hh_vacancy_id=row["hh_vacancy_id"], hh_search_query=row["hh_search_query"],
            active=bool(row["active"]), created_at=row["created_at"],
        )

    async def list_vacancies(self, active_only: bool = True) -> list[Vacancy]:
        await self.init()
        q = "SELECT * FROM vacancies" + (" WHERE active = 1" if active_only else "") + " ORDER BY id DESC"
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(q)
            rows = await cur.fetchall()
        return [
            Vacancy(
                id=r["id"], title=r["title"], criteria=json.loads(r["criteria_json"] or "{}"),
                hh_vacancy_id=r["hh_vacancy_id"], hh_search_query=r["hh_search_query"],
                active=bool(r["active"]), created_at=r["created_at"],
            )
            for r in rows
        ]

    async def get_active_vacancy(self) -> Vacancy | None:
        vacs = await self.list_vacancies(active_only=True)
        return vacs[0] if vacs else None

    # --- Candidates ---

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
    ) -> int:
        await self.init()
        now = int(time.time())
        async with aiosqlite.connect(self.path) as conn:
            if chat_id:
                cur = await conn.execute("SELECT id FROM candidates WHERE chat_id = ?", (chat_id,))
                existing = await cur.fetchone()
                if existing:
                    cid = existing[0]
                    await conn.execute(
                        """UPDATE candidates SET name=COALESCE(?,name), resume_text=COALESCE(?,resume_text),
                           match_score=COALESCE(?,match_score), match_summary=COALESCE(?,match_summary),
                           profile_json=?, vacancy_id=COALESCE(?,vacancy_id), status=?, updated_at=? WHERE id=?""",
                        (name, resume_text, match_score, match_summary,
                         json.dumps(profile or {}, ensure_ascii=False), vacancy_id, status, now, cid),
                    )
                    await conn.commit()
                    return cid

            cur = await conn.execute(
                """INSERT INTO candidates (source, external_id, chat_id, name, resume_text, profile_json,
                   match_score, match_summary, status, vacancy_id, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (source, external_id, chat_id, name, resume_text,
                 json.dumps(profile or {}, ensure_ascii=False), match_score, match_summary,
                 status, vacancy_id, now, now),
            )
            await conn.commit()
            return cur.lastrowid or 0

    async def get_candidate(self, candidate_id: int) -> Candidate | None:
        await self.init()
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,))
            row = await cur.fetchone()
        if not row:
            return None
        return self._row_to_candidate(row)

    def _row_to_candidate(self, row: aiosqlite.Row) -> Candidate:
        return Candidate(
            id=row["id"], source=row["source"], external_id=row["external_id"],
            chat_id=row["chat_id"], name=row["name"], contact=row["contact"],
            resume_text=row["resume_text"], profile=json.loads(row["profile_json"] or "{}"),
            match_score=row["match_score"], match_summary=row["match_summary"],
            status=row["status"], vacancy_id=row["vacancy_id"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    async def list_candidates(
        self, vacancy_id: int | None = None, limit: int = 20, order_by_score: bool = True
    ) -> list[Candidate]:
        await self.init()
        q = "SELECT * FROM candidates WHERE 1=1"
        params: list[Any] = []
        if vacancy_id:
            q += " AND vacancy_id = ?"
            params.append(vacancy_id)
        q += " ORDER BY match_score IS NULL, match_score DESC, id DESC" if order_by_score else " ORDER BY id DESC"
        q += " LIMIT ?"
        params.append(limit)
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(q, params)
            rows = await cur.fetchall()
        return [self._row_to_candidate(r) for r in rows]

    async def search_candidates(self, query: str, limit: int = 10) -> list[Candidate]:
        await self.init()
        like = f"%{query}%"
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                """SELECT * FROM candidates
                   WHERE name LIKE ? OR resume_text LIKE ? OR match_summary LIKE ?
                   ORDER BY match_score IS NULL, match_score DESC LIMIT ?""",
                (like, like, like, limit),
            )
            rows = await cur.fetchall()
        return [self._row_to_candidate(r) for r in rows]

    # --- Interviews & analysis ---

    async def create_interview(self, candidate_id: int, scheduled_at: int, calendar_event_id: str | None = None) -> int:
        await self.init()
        now = int(time.time())
        async with aiosqlite.connect(self.path) as conn:
            cur = await conn.execute(
                "INSERT INTO interviews (candidate_id, scheduled_at, calendar_event_id, created_at) VALUES (?, ?, ?, ?)",
                (candidate_id, scheduled_at, calendar_event_id, now),
            )
            await conn.commit()
            return cur.lastrowid or 0

    async def save_interview_analysis(
        self, candidate_id: int, transcript: str, summary: str, profile: dict[str, Any], interview_id: int | None = None
    ) -> int:
        await self.init()
        now = int(time.time())
        async with aiosqlite.connect(self.path) as conn:
            cur = await conn.execute(
                """INSERT INTO interview_analysis (interview_id, candidate_id, transcript, summary, profile_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (interview_id, candidate_id, transcript, summary, json.dumps(profile, ensure_ascii=False), now),
            )
            await conn.commit()
            return cur.lastrowid or 0

    async def get_candidate_messages(self, candidate_id: int, limit: int = 30) -> list[dict[str, Any]]:
        await self.init()
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                "SELECT direction, body, created_at, channel FROM messages WHERE candidate_id = ? ORDER BY id DESC LIMIT ?",
                (candidate_id, limit),
            )
            rows = await cur.fetchall()
        return [dict(r) for r in rows]


_settings = get_settings()
store = Store(_settings.database_path)
