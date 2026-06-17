from __future__ import annotations

from app.storage.db import Candidate, Vacancy


def hr_main_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "👥 Кандидаты", "callback_data": "hr:cands"},
                {"text": "🏆 Рейтинг AI", "callback_data": "hr:rank"},
            ],
            [
                {"text": "📋 Вакансии", "callback_data": "hr:vac"},
                {"text": "📈 Статистика", "callback_data": "hr:stats"},
            ],
            [
                {"text": "🔄 HH sync", "callback_data": "hr:sync"},
                {"text": "🔍 Поиск", "callback_data": "hr:search"},
            ],
            [{"text": "⚖️ Сравнить", "callback_data": "hr:cmp"}],
            [
                {"text": "📄 Импорт PDF", "callback_data": "hr:imp:resume"},
                {"text": "📊 Импорт CSV", "callback_data": "hr:imp:csv"},
            ],
            [{"text": "❓ Команды /", "callback_data": "hr:help"}],
        ]
    }


def hr_back_menu_row() -> list[dict]:
    return [{"text": "↩️ Меню HR", "callback_data": "hr:menu"}]


def hr_nav_keyboard() -> dict:
    return {"inline_keyboard": [hr_back_menu_row()]}


def hr_candidates_keyboard(candidates: list[Candidate]) -> dict:
    rows: list[list[dict]] = []
    for c in candidates[:12]:
        score = c.match_score if c.match_score is not None else "—"
        name = (c.name or "—")[:18]
        rows.append([{"text": f"#{c.id} {name} · {score}", "callback_data": f"hr:cand:{c.id}"}])
    rows.append(hr_back_menu_row())
    return {"inline_keyboard": rows}


def hr_candidate_keyboard(candidate_id: int) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "📤 Написать", "callback_data": f"hr:out:{candidate_id}"},
                {"text": "💬 Коммент", "callback_data": f"hr:comm:{candidate_id}"},
            ],
            [{"text": "↩️ К списку", "callback_data": "hr:cands"}],
            hr_back_menu_row(),
        ]
    }


def hr_vacancies_keyboard(vacancies: list[Vacancy]) -> dict:
    rows: list[list[dict]] = []
    for v in vacancies[:10]:
        mark = "✅" if v.active else "⏸"
        title = v.title[:24]
        rows.append([{"text": f"{mark} #{v.id} {title}", "callback_data": f"hr:cands:{v.id}"}])
    rows.append(hr_back_menu_row())
    return {"inline_keyboard": rows}
