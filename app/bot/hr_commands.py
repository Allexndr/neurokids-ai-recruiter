"""HR Telegram commands for recruiters."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.ai.prompts_hr import COMPARE_SYSTEM
from app.sourcing.hh_client import HHClient
from app.sourcing.resume_parser import extract_text_from_bytes
from app.sourcing.scorer import parse_csv_candidates, score_resume
from app.storage.db import store

if TYPE_CHECKING:
    from app.ai.router import LLMRouter
    from app.config import Settings


async def handle_hr_command(
    text: str,
    chat_id: str,
    settings: Settings,
    llm: LLMRouter | None,
    document_bytes: bytes | None = None,
    document_name: str = "",
) -> str | None:
    t = (text or "").strip()
    low = t.lower()

    if low.startswith("/help") or low == "/hr":
        return _help_text()

    if low.startswith("/vacancy"):
        return await _vacancy_command(t)

    if low.startswith("/candidates"):
        return await _candidates_command(t)

    if low.startswith("/candidate "):
        return await _candidate_detail(t)

    if low.startswith("/rank"):
        return await _rank_command(t, llm)

    if low.startswith("/search "):
        return await _search_command(t)

    if low.startswith("/compare "):
        return await _compare_command(t, llm)

    if low.startswith("/import_csv") and document_bytes:
        return await _import_csv(document_bytes, llm)

    if low.startswith("/import_resume") and document_bytes:
        return await _import_resume(document_bytes, document_name, llm)

    if low.startswith("/hh_search "):
        return await _hh_search(t, settings, llm)

    if low.startswith("/hh_responses "):
        return await _hh_responses(t, settings, llm)

    if low.startswith("/stats"):
        stats = await store.get_stats()
        lines = ["<b>Статистика воронки</b>"] + [f"{k}: {v}" for k, v in sorted(stats.items())]
        return "\n".join(lines) if stats else "Статистика пуста."

    return None


def _help_text() -> str:
    return (
        "<b>HR-команды recruter_support_bot</b>\n\n"
        "/vacancy create Название | навык1, навык2 — создать вакансию\n"
        "/vacancy list — список вакансий\n"
        "/candidates [id_вакансии] — топ кандидатов\n"
        "/candidate 5 — карточка кандидата\n"
        "/rank [id_вакансии] — рейтинг по AI\n"
        "/search запрос — поиск в базе\n"
        "/compare 1 2 — сравнить кандидатов\n"
        "/import_resume — прикрепите PDF/DOCX к сообщению\n"
        "/import_csv — прикрепите CSV (name, phone, resume)\n"
        "/hh_search запрос — поиск резюме HH (платный доступ)\n"
        "/hh_responses id_вакансии_hh — отклики на вакансию\n"
        "/stats — воронка"
    )


async def _vacancy_command(text: str) -> str:
    parts = text.split(maxsplit=2)
    if len(parts) < 2:
        return "Использование: /vacancy create Название | навыки или /vacancy list"

    sub = parts[1].lower()
    if sub == "list":
        vacs = await store.list_vacancies(active_only=False)
        if not vacs:
            return "Вакансий нет. Создайте: /vacancy create Менеджер | продажи, CRM"
        lines = ["<b>Вакансии</b>"]
        for v in vacs:
            lines.append(f"#{v.id} {v.title} {'✅' if v.active else '⏸'}")
        return "\n".join(lines)

    if sub == "create" and len(parts) >= 3:
        raw = parts[2]
        if "|" in raw:
            title, skills_raw = raw.split("|", 1)
            skills = [s.strip() for s in skills_raw.split(",") if s.strip()]
        else:
            title, skills = raw, []
        criteria = {"skills": skills, "min_experience_years": 0}
        vid = await store.create_vacancy(title.strip(), criteria)
        return f"✅ Вакансия #{vid} создана: <b>{title.strip()}</b>\nНавыки: {', '.join(skills) or '—'}"

    return "Использование: /vacancy create Название | навык1, навык2"


async def _candidates_command(text: str) -> str:
    parts = text.split()
    vacancy_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
    cands = await store.list_candidates(vacancy_id=vacancy_id, limit=15)
    if not cands:
        return "Кандидатов пока нет."
    lines = ["<b>Кандидаты</b> (по score)"]
    for c in cands:
        score = c.match_score if c.match_score is not None else "—"
        lines.append(f"#{c.id} {c.name or '—'} — score {score} [{c.source}]")
    return "\n".join(lines)


async def _candidate_detail(text: str) -> str:
    parts = text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        return "Использование: /candidate 5"
    c = await store.get_candidate(int(parts[1]))
    if not c:
        return "Кандидат не найден."
    lines = [
        f"<b>#{c.id} {c.name or '—'}</b>",
        f"Источник: {c.source} | Статус: {c.status}",
        f"Score: {c.match_score or '—'}",
    ]
    if c.match_summary:
        lines.append(f"Выжимка: {c.match_summary}")
    if c.resume_text:
        lines.append(f"\nРезюме:\n{c.resume_text[:1500]}")
    msgs = await store.get_candidate_messages(c.id, limit=5)
    if msgs:
        lines.append("\n<b>Последние сообщения:</b>")
        for m in reversed(msgs):
            lines.append(f"{m['direction']}: {m['body'][:200]}")
    return "\n".join(lines)


async def _rank_command(text: str, llm: LLMRouter | None) -> str:
    if not llm:
        return "LLM не настроен (GROQ_API_KEY / OPENROUTER / TOGETHER)."
    parts = text.split()
    vacancy_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
    vacancy = await store.get_vacancy(vacancy_id) if vacancy_id else await store.get_active_vacancy()
    if not vacancy:
        return "Создайте вакансию: /vacancy create ..."

    cands = await store.list_candidates(vacancy_id=vacancy.id, limit=50, order_by_score=False)
    if not cands:
        return "Нет кандидатов для оценки."

    lines = [f"<b>Рейтинг: {vacancy.title}</b>"]
    scored: list[tuple[int, int, str]] = []
    for c in cands:
        if not c.resume_text:
            continue
        result = await score_resume(llm, vacancy.title, vacancy.criteria, c.resume_text)
        score = result.get("score", 0)
        summary = result.get("summary", "")
        await store.upsert_candidate(
            source=c.source, chat_id=c.chat_id, name=c.name,
            resume_text=c.resume_text, vacancy_id=vacancy.id,
            match_score=score, match_summary=summary, profile=c.profile,
        )
        scored.append((c.id, score, c.name or "—"))

    scored.sort(key=lambda x: x[1], reverse=True)
    for cid, score, name in scored[:15]:
        lines.append(f"#{cid} {name} — <b>{score}</b>/100")
    return "\n".join(lines) if len(lines) > 1 else "Нет резюме для скоринга."


async def _search_command(text: str) -> str:
    q = text.split(maxsplit=1)[1] if " " in text else ""
    if not q:
        return "Использование: /search python менеджер"
    cands = await store.search_candidates(q)
    if not cands:
        return "Ничего не найдено."
    lines = [f"<b>Поиск: {q}</b>"]
    for c in cands:
        lines.append(f"#{c.id} {c.name or '—'} score={c.match_score or '—'}")
    return "\n".join(lines)


async def _compare_command(text: str, llm: LLMRouter | None) -> str:
    if not llm:
        return "LLM не настроен."
    parts = text.split()
    if len(parts) < 3 or not parts[1].isdigit() or not parts[2].isdigit():
        return "Использование: /compare 1 2"
    c1 = await store.get_candidate(int(parts[1]))
    c2 = await store.get_candidate(int(parts[2]))
    if not c1 or not c2:
        return "Кандидат не найден."
    user = f"Candidate 1 (id={c1.id}): {c1.resume_text or c1.match_summary}\n\nCandidate 2 (id={c2.id}): {c2.resume_text or c2.match_summary}"
    content, _ = await llm.chat(
        [{"role": "system", "content": COMPARE_SYSTEM}, {"role": "user", "content": user}],
        max_tokens=600,
    )
    return content or "Не удалось сравнить."


async def _import_csv(data: bytes, llm: LLMRouter | None) -> str:
    rows = parse_csv_candidates(data)
    if not rows:
        return "CSV пуст или неверный формат."
    vacancy = await store.get_active_vacancy()
    count = 0
    for row in rows:
        name = row.get("name") or row.get("имя") or row.get("fio") or ""
        resume = row.get("resume") or row.get("резюме") or row.get("text") or ""
        phone = row.get("phone") or row.get("телефон") or ""
        score, summary = None, None
        if llm and vacancy and resume:
            result = await score_resume(llm, vacancy.title, vacancy.criteria, resume)
            score = result.get("score")
            summary = result.get("summary")
        await store.upsert_candidate(
            source="crm", name=name or None, contact=phone or None,
            resume_text=resume or None, vacancy_id=vacancy.id if vacancy else None,
            match_score=score, match_summary=summary,
        )
        count += 1
    return f"✅ Импортировано {count} кандидатов из CSV."


async def _import_resume(data: bytes, filename: str, llm: LLMRouter | None) -> str:
    text = extract_text_from_bytes(data, filename)
    if not text:
        return "Не удалось извлечь текст из файла."
    vacancy = await store.get_active_vacancy()
    score, summary = None, None
    if llm and vacancy:
        result = await score_resume(llm, vacancy.title, vacancy.criteria, text)
        score = result.get("score")
        summary = result.get("summary")
    cid = await store.upsert_candidate(
        source="file", resume_text=text, vacancy_id=vacancy.id if vacancy else None,
        match_score=score, match_summary=summary,
    )
    return f"✅ Резюме #{cid} добавлено. Score: {score or '—'}\n{summary or ''}"


async def _hh_search(text: str, settings: Settings, llm: LLMRouter | None) -> str:
    if not settings.is_hh_configured:
        return "HH не настроен: HH_ACCESS_TOKEN в .env"
    q = text.split(maxsplit=1)[1] if " " in text else ""
    if not q:
        return "Использование: /hh_search python разработчик"
    client = HHClient(settings.hh_access_token)
    items = await client.search_resumes(q)
    if not items:
        return "Нет результатов (нужен платный доступ работодателя к базе резюме HH)."
    vacancy = await store.get_active_vacancy()
    lines = [f"<b>HH: {q}</b> ({len(items)} найдено)"]
    for item in items[:10]:
        rid = item.get("id", "")
        title = item.get("title", "—")
        resume = await client.get_resume(rid)
        rtext = client.resume_to_text(resume) if resume else title
        score, summary = None, None
        if llm and vacancy:
            result = await score_resume(llm, vacancy.title, vacancy.criteria, rtext)
            score = result.get("score")
            summary = result.get("summary")
        cid = await store.upsert_candidate(
            source="hh", external_id=rid, name=title, resume_text=rtext,
            vacancy_id=vacancy.id if vacancy else None, match_score=score, match_summary=summary,
        )
        lines.append(f"#{cid} {title} — score {score or '—'}")
    return "\n".join(lines)


async def _hh_responses(text: str, settings: Settings, llm: LLMRouter | None) -> str:
    if not settings.is_hh_configured:
        return "HH не настроен."
    parts = text.split()
    if len(parts) < 2:
        return "Использование: /hh_responses VACANCY_ID"
    client = HHClient(settings.hh_access_token)
    items = await client.list_negotiations(parts[1])
    if not items:
        return "Нет откликов или неверный ID вакансии."
    vacancy = await store.get_active_vacancy()
    lines = [f"<b>Отклики HH: {len(items)}</b>"]
    for item in items[:15]:
        resume = item.get("resume", {})
        rid = resume.get("id", "")
        title = resume.get("title", "—")
        full = await client.get_resume(rid) if rid else None
        rtext = client.resume_to_text(full) if full else title
        score, summary = None, None
        if llm and vacancy:
            result = await score_resume(llm, vacancy.title, vacancy.criteria, rtext)
            score = result.get("score")
            summary = result.get("summary")
        cid = await store.upsert_candidate(
            source="hh", external_id=rid, name=title, resume_text=rtext,
            vacancy_id=vacancy.id if vacancy else None, match_score=score, match_summary=summary,
        )
        lines.append(f"#{cid} {title} — {score or '—'}")
    return "\n".join(lines)
