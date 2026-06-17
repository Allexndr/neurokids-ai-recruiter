from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from app.bot import content_kk as KK
from app.bot import content_ru as RU
from app.bot.extractors import classify_intent, interpret_step_answer
from app.bot.semantic import StepContext
from app.bot.profile_validate import (
    ValidationResult,
    parse_experience_text,
    parse_job_search_answer,
    parse_name,
)
from app.bot.channel_ui import (
    is_whatsapp_ui,
    parse_lang_choice,
    slot_index_choice,
    wa_main_menu_text,
    wa_reminder_text,
    wa_slots_text,
)
from app.bot.faq import answer_faq, faq_by_topic
from app.bot import content_boot as BOOT
from app.bot.keyboards import (
    confirm_keyboard,
    faq_keyboard,
    faq_topics_keyboard,
    handoff_keyboard,
    language_keyboard,
    main_menu_keyboard,
    reminder_keyboard,
    resume_prompt_keyboard,
    slots_keyboard,
    step_nav_keyboard,
    yes_no_keyboard,
)
from app.bot.scheduling import bookable_slots, format_slot_label, slot_by_id
from app.bot.screening import (
    RejectReason,
    detect_city,
    screen_language_answer,
    screen_profile,
    screen_schedule_answer,
    student_schedule_compatible,
    wants_online,
)
from app.bot.states import State
from app.config import Settings
from app.hr_notify import notify_hr
from app.bot.outbound import update_panel
from app.storage import Session, store
from app.telegram_api import TelegramClient, detect_message_lang

logger = logging.getLogger(__name__)

CB_SCHEDULE = "act:schedule"
CB_FAQ = "act:faq"
CB_MENU = "act:menu"
CB_LANG_KK = "lang:kk"
CB_LANG_RU = "lang:ru"

TEXT_INPUT_STATES = frozenset(
    {
        State.COLLECT_NAME_AGE.value,
        State.COLLECT_EXPERIENCE.value,
    }
)


@dataclass
class EngineReply:
    text: str
    reply_markup: dict | None = None
    notify_hr: str | None = None
    stat: str | None = None


def _c(lang: str):
    return KK if lang == "kk" else RU


def _markup(session: Session, keyboard: dict | None) -> dict | None:
    if is_whatsapp_ui(session):
        return None
    return keyboard


def _begin_step(session: Session) -> None:
    session.clarify_attempts = 0


def _normalize_legacy_session(session: Session) -> None:
    if session.state == "choose_view":
        session.state = State.CHOOSE_LANG.value
        session.profile["ui_mode"] = "telegram"


def _is_text_input_state(state: str) -> bool:
    return state in TEXT_INPUT_STATES


class BotEngine:
    def __init__(self, settings: Settings, together, tg: TelegramClient, gcal=None):
        self.settings = settings
        self.together = together
        self.tg = tg
        self.gcal = gcal

    def _bookable_slots(self):
        return bookable_slots(tz_name=self.settings.bot_timezone, gcal=self.gcal)

    def _slots_kb(self, lang: str):
        return slots_keyboard(lang, self.settings.bot_timezone, slots=self._bookable_slots())

    async def handle(
        self,
        session: Session,
        text: str,
        is_callback: bool = False,
    ) -> EngineReply:
        t = (text or "").strip()
        _normalize_legacy_session(session)
        if session.state == State.CHOOSE_LANG.value and not session.profile.get("lang_locked"):
            lang = session.lang or "kk"
        else:
            lang = session.lang or detect_message_lang(text) or "kk"
            session.lang = lang

        if t in ("/start", "/reset"):
            session.state = State.CHOOSE_LANG.value
            session.profile = {"ui_mode": "telegram"}
            session.clarify_attempts = 0
            session.status = "new"
            session.lang = "kk"
            await store.save_session(session)
            return self._start_reply(stat="started")

        if t == "/human":
            session.state = State.HANDOFF_HR.value
            session.status = "handoff"
            await store.save_session(session)
            return EngineReply(
                _c(lang).HANDOFF,
                reply_markup=_markup(session, handoff_keyboard(lang)),
                notify_hr="handoff",
                stat="handoff",
            )

        if is_callback:
            return await self._handle_callback(session, t, lang)

        state = session.state

        if state in (State.REJECTED.value, State.CLOSED.value, State.HANDOFF_HR.value):
            return await self._prompt_for_state(session, lang, hint=True)

        if not _is_text_input_state(state):
            if state in (
                State.WELCOME_QUALIFIED.value,
                State.QA.value,
                State.SCHEDULE_INTERVIEW.value,
                State.CONFIRM.value,
            ):
                return await self._prompt_for_state(session, lang, hint=True)
            if state == State.CHOOSE_LANG.value:
                lchoice = parse_lang_choice(t)
                if lchoice:
                    return await self._apply_lang_choice(session, lchoice)
                return await self._prompt_for_state(session, lang, hint=bool(t))
            if state == State.COLLECT_STUDENT.value:
                return await self._prompt_for_state(session, lang, hint=bool(t))
            if t and not t.startswith("/"):
                return await self._prompt_for_state(session, lang, hint=True)

        if state == State.COLLECT_NAME_AGE.value:
            if not t or t.startswith("/"):
                return self._ask_name_age(session, lang)
            return await self._collect_name_age(session, t, lang)

        if state == State.COLLECT_EXPERIENCE.value:
            return await self._collect_experience(session, t, lang)

        if state == State.COLLECT_PROFILE.value:
            session.state = State.COLLECT_NAME_AGE.value
            await store.save_session(session)
            return self._ask_name_age(session, lang)

        if state == State.COLLECT_CITY.value:
            return await self._collect_city(session, t, lang)

        if state == State.COLLECT_SCHEDULE.value:
            return await self._collect_schedule(session, t, lang)

        if state == State.STUDENT_SCHEDULE.value:
            return await self._student_schedule(session, t, lang)

        if state == State.COLLECT_LANGUAGE.value:
            return await self._collect_language(session, t, lang)

        if state in (
            State.WELCOME_QUALIFIED.value,
            State.QA.value,
            State.SCHEDULE_INTERVIEW.value,
            State.CONFIRM.value,
        ):
            return await self._prompt_for_state(session, lang, hint=True)

        session.profile.setdefault("ui_mode", "telegram")
        if not session.profile.get("lang_locked"):
            return self._start_reply()
        return EngineReply(_c(lang).GREETING)

    def _start_reply(self, stat: str | None = None) -> EngineReply:
        return EngineReply(
            BOOT.WELCOME_START,
            reply_markup=language_keyboard(),
            stat=stat,
        )

    def _choose_lang_reply(self, session: Session) -> EngineReply:
        kb = None if is_whatsapp_ui(session) else language_keyboard()
        return EngineReply(BOOT.WELCOME_START, reply_markup=kb)

    async def _apply_lang_choice(self, session: Session, lang: str) -> EngineReply:
        session.lang = lang
        session.profile["lang_locked"] = True
        session.profile["ui_mode"] = "telegram"
        session.state = State.COLLECT_NAME_AGE.value
        session.clarify_attempts = 0
        await store.save_session(session)
        await store.bump_stat(f"lang_{lang}")
        kb = step_nav_keyboard(lang, back="act:change_lang")
        return EngineReply(
            f"{_c(lang).INTRO_VACANCY}\n\n{_c(lang).ASK_NAME}",
            reply_markup=_markup(session, kb),
        )

    async def _prompt_for_state(self, session: Session, lang: str, *, hint: bool = False) -> EngineReply:
        c = _c(lang)
        prefix = f"{c.USE_BUTTONS}\n\n" if hint else ""
        state = session.state

        if state == State.CHOOSE_LANG.value:
            return EngineReply(prefix + BOOT.WELCOME_START, reply_markup=_markup(session, language_keyboard()))

        if state == State.COLLECT_STUDENT.value:
            return EngineReply(
                prefix + c.ASK_JOB_SEARCH,
                reply_markup=_markup(session, yes_no_keyboard(lang, "job")),
            )

        if state == State.COLLECT_EXPERIENCE.value:
            return EngineReply(
                prefix + c.ASK_EXPERIENCE,
                reply_markup=_markup(session, step_nav_keyboard(lang, back="act:back_job")),
            )

        if state in (State.WELCOME_QUALIFIED.value, State.QA.value):
            session.state = State.WELCOME_QUALIFIED.value
            await store.save_session(session)
            return EngineReply(
                prefix + c.welcome_qualified(session.profile.get("name", "")),
                reply_markup=_markup(session, main_menu_keyboard(lang)),
            )

        if state == State.SCHEDULE_INTERVIEW.value:
            return EngineReply(
                prefix + c.ASK_INTERVIEW_TIME,
                reply_markup=_markup(session, self._slots_kb(lang)),
            )

        if state == State.CONFIRM.value:
            name = session.profile.get("name", "")
            label = session.interview_label or "—"
            return EngineReply(
                prefix + c.confirm_visit(name, label),
                reply_markup=_markup(session, confirm_keyboard(lang)),
            )

        if state == State.CLOSED.value:
            return EngineReply(
                prefix + c.NOT_LOOKING,
                reply_markup=_markup(session, handoff_keyboard(lang)),
            )

        if state in (State.REJECTED.value, State.HANDOFF_HR.value):
            text = c.HANDOFF if state == State.HANDOFF_HR.value else c.DB_TOUCH
            return EngineReply(prefix + text, reply_markup=_markup(session, handoff_keyboard(lang)))

        if session.profile.get("awaiting_resume"):
            return EngineReply(
                prefix + c.ASK_RESUME_UPLOAD,
                reply_markup=_markup(session, resume_prompt_keyboard(lang)),
            )

        if not session.profile.get("lang_locked"):
            return self._start_reply()
        return EngineReply(prefix + c.GREETING, reply_markup=_markup(session, main_menu_keyboard(lang)))

    def _err(self, lang: str, key: str) -> str:
        c = _c(lang)
        return {
            "garbage": c.ERR_GARBAGE,
            "no_age": c.ERR_NO_AGE,
            "no_name": c.ERR_NO_NAME,
            "bad_name": c.ERR_BAD_NAME,
            "age_young": c.ERR_AGE_YOUNG,
            "age_invalid": c.ERR_AGE_INVALID,
            "yes_no_unclear": c.ERR_YES_NO,
            "experience_short": c.ERR_EXPERIENCE_SHORT,
        }.get(key, c.ERR_GARBAGE)

    def _ask_name_age(self, session: Session, lang: str) -> EngineReply:
        return EngineReply(
            _c(lang).ASK_NAME,
            reply_markup=_markup(session, step_nav_keyboard(lang, back="act:change_lang")),
        )

    async def _retry_invalid(
        self, session: Session, lang: str, step_prompt: str, err_key: str, keyboard: dict | None = None
    ) -> EngineReply:
        session.clarify_attempts += 1
        if session.clarify_attempts >= self.settings.fallback_attempts_max:
            session.state = State.HANDOFF_HR.value
            await store.save_session(session)
            return EngineReply(
                _c(lang).HANDOFF,
                reply_markup=_markup(session, handoff_keyboard(lang)),
                notify_hr="handoff",
                stat="handoff",
            )
        await store.save_session(session)
        return EngineReply(
            f"{self._err(lang, err_key)}\n\n{step_prompt}",
            reply_markup=_markup(session, keyboard),
        )

    async def _collect_name_age(self, session: Session, text: str, lang: str) -> EngineReply:
        result = parse_name(text)
        if not result.ok:
            return await self._retry_invalid(session, lang, _c(lang).ASK_NAME, result.error_key or "garbage")

        session.profile["name"] = result.data["name"]
        _begin_step(session)
        session.state = State.COLLECT_STUDENT.value
        await store.save_session(session)
        kb = yes_no_keyboard(lang, "job")
        body = f"{_c(lang).CONFIRM_STEP}\n\n{_c(lang).ASK_JOB_SEARCH}"
        return EngineReply(body, reply_markup=_markup(session, kb))

    async def _collect_student(self, session: Session, text: str, lang: str) -> EngineReply:
        result = parse_job_search_answer(text)
        if not result.ok:
            return await self._retry_invalid(
                session,
                lang,
                _c(lang).ASK_JOB_SEARCH,
                result.error_key or "yes_no_unclear",
                yes_no_keyboard(lang, "job"),
            )
        active = result.data["job_search_active"]
        session.profile["job_search_active"] = active
        if not active:
            session.state = State.CLOSED.value
            session.status = "not_looking"
            await store.save_session(session)
            return EngineReply(
                _c(lang).NOT_LOOKING,
                reply_markup=_markup(session, handoff_keyboard(lang)),
                stat="not_looking",
            )
        _begin_step(session)
        session.state = State.COLLECT_EXPERIENCE.value
        await store.save_session(session)
        return EngineReply(
            f"{_c(lang).CONFIRM_STEP}\n\n{_c(lang).ASK_EXPERIENCE}",
            reply_markup=_markup(session, step_nav_keyboard(lang, back="act:back_job")),
        )

    async def _collect_experience(self, session: Session, text: str, lang: str) -> EngineReply:
        result = parse_experience_text(text)
        if not result.ok:
            return await self._retry_invalid(
                session,
                lang,
                _c(lang).ASK_EXPERIENCE,
                result.error_key or "garbage",
                step_nav_keyboard(lang, back="act:back_job"),
            )
        session.profile["experience_summary"] = result.data["experience_summary"]
        _begin_step(session)
        return await self._qualify(session, lang)

    async def _after_profile_collected(self, session: Session, lang: str) -> EngineReply:
        return await self._qualify(session, lang)

    async def _handle_callback(self, session: Session, data: str, lang: str) -> EngineReply:
        if data.startswith("job:") or data.startswith("stu:"):
            val = data.endswith(":yes")
            fake = "1" if val else "2"
            if session.state == State.COLLECT_STUDENT.value:
                return await self._collect_student(session, fake, lang)
        if data.startswith("exp:"):
            val = data.endswith(":yes")
            fake = "да" if val else "нет"
            if session.state == State.COLLECT_EXPERIENCE.value:
                return await self._collect_experience(session, fake, lang)

        if data.startswith("sch:"):
            fake = "1" if data.endswith(":yes") else "2"
            if session.state == State.COLLECT_SCHEDULE.value:
                return await self._collect_schedule(session, fake, lang)

        if data.startswith("lng:"):
            fake = "1" if data.endswith(":yes") else "2"
            if session.state == State.COLLECT_LANGUAGE.value:
                return await self._collect_language(session, fake, lang)

        if data.startswith("view:"):
            session.state = State.CHOOSE_LANG.value
            session.profile = {"ui_mode": "telegram"}
            session.clarify_attempts = 0
            session.status = "new"
            session.lang = "kk"
            await store.save_session(session)
            return self._start_reply(stat="restarted")

        if data == CB_LANG_KK:
            return await self._apply_lang_choice(session, "kk")
        if data == CB_LANG_RU:
            return await self._apply_lang_choice(session, "ru")

        if data.startswith("faq:"):
            topic = data[4:]
            ans = faq_by_topic(topic, lang) or _c(lang).FAQ_JOB
            session.state = State.QA.value
            session.profile.pop("awaiting_resume", None)
            await store.save_session(session)
            return EngineReply(ans, reply_markup=_markup(session, faq_topics_keyboard(lang)))

        if data == "act:resume":
            session.profile["awaiting_resume"] = True
            if session.profile.get("lang_locked"):
                session.state = State.WELCOME_QUALIFIED.value
            await store.save_session(session)
            return EngineReply(
                _c(lang).ASK_RESUME_UPLOAD,
                reply_markup=_markup(session, resume_prompt_keyboard(lang)),
            )

        if data == "act:change_lang":
            session.profile.pop("lang_locked", None)
            session.state = State.CHOOSE_LANG.value
            session.clarify_attempts = 0
            await store.save_session(session)
            return self._start_reply()

        if data == "act:back_name":
            session.state = State.COLLECT_NAME_AGE.value
            session.profile.pop("name", None)
            session.clarify_attempts = 0
            await store.save_session(session)
            return self._ask_name_age(session, lang)

        if data == "act:back_job":
            session.state = State.COLLECT_STUDENT.value
            session.profile.pop("job_search_active", None)
            session.clarify_attempts = 0
            await store.save_session(session)
            return await self._prompt_for_state(session, lang)

        if is_whatsapp_ui(session) and data.startswith(("act:", "slot:", "rem:")):
            if data == CB_SCHEDULE:
                session.state = State.SCHEDULE_INTERVIEW.value
                await store.save_session(session)
                return EngineReply(wa_slots_text(lang, self.settings.bot_timezone))
            if data == CB_FAQ:
                session.state = State.QA.value
                await store.save_session(session)
                return EngineReply(_c(lang).FAQ_JOB)
            return EngineReply(wa_main_menu_text(lang))

        if data == CB_SCHEDULE:
            session.state = State.SCHEDULE_INTERVIEW.value
            await store.save_session(session)
            return EngineReply(
                _c(lang).ASK_INTERVIEW_TIME,
                reply_markup=_markup(session, self._slots_kb(lang)),
            )

        if data == CB_FAQ:
            session.state = State.QA.value
            session.profile.pop("awaiting_resume", None)
            await store.save_session(session)
            return EngineReply(
                _c(lang).FAQ_PICK_TOPIC,
                reply_markup=_markup(session, faq_topics_keyboard(lang)),
            )

        if data == CB_MENU:
            session.profile.pop("awaiting_resume", None)
            session.state = State.WELCOME_QUALIFIED.value
            await store.save_session(session)
            text = _c(lang).welcome_qualified(session.profile.get("name", ""))
            if is_whatsapp_ui(session):
                text += f"\n\n{wa_main_menu_text(lang)}"
            return EngineReply(
                text,
                reply_markup=_markup(session, main_menu_keyboard(lang)),
            )

        if data.startswith("slot:"):
            sid = data[5:]
            slot = slot_by_id(sid, tz_name=self.settings.bot_timezone, gcal=self.gcal)
            if not slot:
                return EngineReply(
                    _c(lang).ASK_INTERVIEW_TIME,
                    reply_markup=_markup(session, self._slots_kb(lang)),
                )
            session.interview_at = int(slot.starts_at.timestamp())
            session.interview_label = format_slot_label(slot, lang)
            session.state = State.CONFIRM.value
            session.status = "scheduled"
            calendar_event_id = None
            if self.gcal and self.gcal.available:
                name = session.profile.get("name", "Кандидат")
                calendar_event_id = self.gcal.create_event(
                    f"Собеседование: {name}",
                    slot.starts_at,
                    description=f"Telegram chat: {session.chat_id}",
                )
            session.calendar_event_id = calendar_event_id
            if session.candidate_id:
                await store.create_interview(
                    session.candidate_id,
                    session.interview_at,
                    calendar_event_id,
                )
            await store.save_session(session)
            name = session.profile.get("name", "")
            return EngineReply(
                _c(lang).confirm_visit(name, session.interview_label),
                reply_markup=_markup(session, confirm_keyboard(lang)),
                notify_hr="scheduled",
                stat="scheduled",
            )

        if data == "rem:yes":
            session.interview_confirmed = True
            session.status = "confirmed"
            await store.save_session(session)
            body = "✅ Күтеміз!" if lang == "kk" else "✅ Отлично, ждём вас на собеседовании!"
            return EngineReply(
                body,
                reply_markup=_markup(session, confirm_keyboard(lang)),
                notify_hr="confirmed",
            )

        if data == "rem:no":
            session.status = "no_show"
            await store.save_session(session)
            body = _c(lang).RESCHEDULE_OFFER
            if is_whatsapp_ui(session):
                body += f"\n\n{wa_slots_text(lang, self.settings.bot_timezone)}"
            return EngineReply(
                body,
                reply_markup=_markup(session, self._slots_kb(lang)),
                notify_hr="no_show",
                stat="no_show",
            )

        if data == "act:human" or data == "act:restart":
            if data == "act:restart":
                session.state = State.CHOOSE_LANG.value
                session.profile = {"ui_mode": "telegram"}
                session.clarify_attempts = 0
                session.status = "new"
                session.lang = "kk"
                await store.save_session(session)
                return self._start_reply(stat="restarted")
            session.state = State.HANDOFF_HR.value
            session.status = "handoff"
            await store.save_session(session)
            return EngineReply(
                _c(lang).HANDOFF,
                reply_markup=_markup(session, handoff_keyboard(lang)),
                notify_hr="handoff",
                stat="handoff",
            )

        return EngineReply(
            _c(lang).HANDOFF,
            reply_markup=_markup(session, handoff_keyboard(lang)),
        )

    async def _collect_city(self, session: Session, text: str, lang: str) -> EngineReply:
        sem = await interpret_step_answer(
            text,
            StepContext.CITY,
            self.together,
            question_hint=_c(lang).ASK_CITY,
        )
        if sem.ok:
            if sem.value == "almaty":
                session.profile["city"] = "almaty"
            elif sem.value == "other":
                session.profile["city"] = "other"
            elif sem.value == "online":
                session.profile["wants_online"] = True
        else:
            city = detect_city(text)
            if city:
                session.profile["city"] = city
            elif wants_online(text):
                session.profile["wants_online"] = True

        reject = screen_profile(session.profile, lang)
        if reject:
            return await self._reject(session, reject)

        if not session.profile.get("city") and not session.profile.get("wants_online"):
            return await self._retry_invalid(
                session, lang, _c(lang).ASK_CITY, sem.error_key or "garbage", None
            )

        _begin_step(session)
        return await self._after_city(session, lang)

    async def _after_city(self, session: Session, lang: str) -> EngineReply:
        _begin_step(session)
        session.state = State.COLLECT_SCHEDULE.value
        await store.save_session(session)
        return EngineReply(
            f"{_c(lang).CONFIRM_STEP}\n\n{_c(lang).ASK_SCHEDULE}",
            reply_markup=_markup(session, yes_no_keyboard(lang, "sch")),
        )

    async def _collect_schedule(self, session: Session, text: str, lang: str) -> EngineReply:
        is_student = session.profile.get("is_student")
        sem = await interpret_step_answer(
            text,
            StepContext.SCHEDULE,
            self.together,
            is_student=is_student,
            question_hint=_c(lang).ASK_SCHEDULE,
        )
        if sem.ok:
            if sem.value == "student_branch":
                _begin_step(session)
                session.state = State.STUDENT_SCHEDULE.value
                await store.save_session(session)
                return EngineReply(_c(lang).ASK_STUDENT_SCHEDULE)
            if sem.value is False:
                return await self._reject(
                    session, RejectReason("schedule", _c(lang).REJECT_SCHEDULE)
                )
            if sem.value is True:
                _begin_step(session)
                return await self._ask_language(session, lang)

        result = screen_schedule_answer(text, lang, is_student)
        if isinstance(result, RejectReason):
            return await self._reject(session, result)
        if result == "student_branch":
            _begin_step(session)
            session.state = State.STUDENT_SCHEDULE.value
            await store.save_session(session)
            return EngineReply(_c(lang).ASK_STUDENT_SCHEDULE)
        if result == "ok":
            _begin_step(session)
            return await self._ask_language(session, lang)

        return await self._retry_invalid(
            session,
            lang,
            _c(lang).ASK_SCHEDULE,
            sem.error_key or "yes_no_unclear",
            yes_no_keyboard(lang, "sch"),
        )

    async def _student_schedule(self, session: Session, text: str, lang: str) -> EngineReply:
        sem = await interpret_step_answer(
            text,
            StepContext.STUDENT_SCHEDULE,
            self.together,
            is_student=True,
            question_hint=_c(lang).ASK_STUDENT_SCHEDULE,
        )
        if sem.ok and sem.value:
            session.profile["schedule_ok"] = True
            _begin_step(session)
            return await self._ask_language(session, lang)
        if student_schedule_compatible(text):
            session.profile["schedule_ok"] = True
            _begin_step(session)
            return await self._ask_language(session, lang)
        return await self._retry_invalid(
            session, lang, _c(lang).ASK_STUDENT_SCHEDULE, sem.error_key or "garbage", None
        )

    async def _ask_language(self, session: Session, lang: str) -> EngineReply:
        if session.profile.get("language_ok") is True:
            return await self._qualify(session, lang)
        _begin_step(session)
        session.state = State.COLLECT_LANGUAGE.value
        await store.save_session(session)
        return EngineReply(
            f"{_c(lang).CONFIRM_STEP}\n\n{_c(lang).ASK_LANGUAGE}",
            reply_markup=_markup(session, yes_no_keyboard(lang, "lng")),
        )

    async def _collect_language(self, session: Session, text: str, lang: str) -> EngineReply:
        sem = await interpret_step_answer(
            text,
            StepContext.LANGUAGE,
            self.together,
            question_hint=_c(lang).ASK_LANGUAGE,
        )
        if sem.ok:
            if sem.value is False:
                return await self._reject(
                    session, RejectReason("language", _c(lang).REJECT_LANGUAGE)
                )
            if sem.value is True:
                session.profile["language_ok"] = True
                return await self._qualify(session, lang)

        result = screen_language_answer(text, lang)
        if isinstance(result, RejectReason):
            return await self._reject(session, result)
        if result is True:
            session.profile["language_ok"] = True
            return await self._qualify(session, lang)

        return await self._retry_invalid(
            session,
            lang,
            _c(lang).ASK_LANGUAGE,
            sem.error_key or "yes_no_unclear",
            yes_no_keyboard(lang, "lng"),
        )

    async def _qualify(self, session: Session, lang: str) -> EngineReply:
        session.state = State.WELCOME_QUALIFIED.value
        session.status = "qualified"
        vacancy = await store.get_active_vacancy()
        if vacancy:
            session.vacancy_id = vacancy.id
        cid = await store.upsert_candidate(
            source="telegram",
            chat_id=session.chat_id,
            name=session.profile.get("name"),
            vacancy_id=session.vacancy_id,
            profile=session.profile,
            resume_text=session.profile.get("experience_summary"),
            status="qualified",
        )
        session.candidate_id = cid
        await store.save_session(session)
        name = session.profile.get("name", "")
        text = _c(lang).welcome_qualified(name)
        if is_whatsapp_ui(session):
            text += f"\n\n{wa_main_menu_text(lang)}"
        return EngineReply(
            text,
            reply_markup=_markup(session, main_menu_keyboard(lang)),
            notify_hr="qualified",
            stat="qualified",
        )

    async def _reject(self, session: Session, reason: RejectReason) -> EngineReply:
        session.state = State.REJECTED.value
        session.status = "rejected"
        lang = session.lang or "ru"
        await store.save_session(session)
        await store.bump_stat(f"reject_{reason.code}")
        return EngineReply(
            reason.message,
            reply_markup=_markup(session, handoff_keyboard(lang)),
            notify_hr="rejected",
            stat="rejected",
        )

    async def _post_qualify(self, session: Session, text: str, lang: str) -> EngineReply:
        if is_whatsapp_ui(session):
            wa = await self._whatsapp_post_qualify(session, text, lang)
            if wa:
                return wa

        intent = await classify_intent(text, self.together)

        if intent == "schedule" or text.lower() in ("собеседование", "жазылу", "записаться"):
            session.state = State.SCHEDULE_INTERVIEW.value
            await store.save_session(session)
            body = _c(lang).ASK_INTERVIEW_TIME
            if is_whatsapp_ui(session):
                body += f"\n\n{wa_slots_text(lang, self.settings.bot_timezone)}"
            return EngineReply(
                body,
                reply_markup=_markup(session, self._slots_kb(lang)),
            )

        if intent == "reschedule":
            body = _c(lang).RESCHEDULE_OFFER
            if is_whatsapp_ui(session):
                body += f"\n\n{wa_slots_text(lang, self.settings.bot_timezone)}"
            return EngineReply(
                body,
                reply_markup=_markup(session, self._slots_kb(lang)),
            )

        if "ертерек" in text.lower() or "раньше" in text.lower() or "маңда" in text.lower():
            return EngineReply(
                _c(lang).EARLY_ARRIVAL,
                reply_markup=_markup(session, confirm_keyboard(lang)),
            )

        if any(x in text.lower() for x in ("мин", "сағ", "час", "15", "10")):
            if session.state != State.CONFIRM.value:
                pass
            return EngineReply(
                _c(lang).EARLY_OK,
                reply_markup=_markup(session, confirm_keyboard(lang)),
            )

        ans = await answer_faq(text, lang, self.together)
        if ans:
            session.state = State.QA.value
            await store.save_session(session)
            extra = f"\n\n{wa_main_menu_text(lang)}" if is_whatsapp_ui(session) else ""
            return EngineReply(
                ans + extra,
                reply_markup=_markup(session, main_menu_keyboard(lang)),
            )

        session.clarify_attempts += 1
        if session.clarify_attempts >= self.settings.fallback_attempts_max:
            session.state = State.HANDOFF_HR.value
            await store.save_session(session)
            return EngineReply(
                _c(lang).HANDOFF,
                reply_markup=_markup(session, handoff_keyboard(lang)),
                notify_hr="handoff",
            )
        tail = f"\n\n{wa_main_menu_text(lang)}" if is_whatsapp_ui(session) else ""
        return EngineReply(
            _c(lang).FAQ_JOB + tail,
            reply_markup=_markup(session, main_menu_keyboard(lang)),
        )

    async def _whatsapp_post_qualify(self, session: Session, text: str, lang: str) -> EngineReply | None:
        t = text.strip().lower()
        if session.state == State.SCHEDULE_INTERVIEW.value:
            slot = slot_index_choice(text, lang, self.settings.bot_timezone)
            if t in ("0", "назад", "артқа"):
                session.state = State.WELCOME_QUALIFIED.value
                await store.save_session(session)
                return EngineReply(
                    _c(lang).welcome_qualified(session.profile.get("name", ""))
                    + f"\n\n{wa_main_menu_text(lang)}",
                )
            if slot:
                session.interview_at = int(slot.starts_at.timestamp())
                session.interview_label = format_slot_label(slot, lang)
                session.state = State.CONFIRM.value
                session.status = "scheduled"
                await store.save_session(session)
                return EngineReply(
                    _c(lang).confirm_visit(session.profile.get("name", ""), session.interview_label),
                    notify_hr="scheduled",
                    stat="scheduled",
                )
            return EngineReply(wa_slots_text(lang, self.settings.bot_timezone))

        if t in ("1",) or "жазыл" in t or "запис" in t or "собес" in t:
            session.state = State.SCHEDULE_INTERVIEW.value
            await store.save_session(session)
            return EngineReply(
                _c(lang).ASK_INTERVIEW_TIME + "\n\n" + wa_slots_text(lang, self.settings.bot_timezone),
            )
        if t in ("2",) or "сұрақ" in t or "вопрос" in t:
            session.state = State.QA.value
            await store.save_session(session)
            return EngineReply(_c(lang).FAQ_JOB + f"\n\n{wa_main_menu_text(lang)}")
        return None

    async def process_reminders(self) -> int:
        now = int(time.time())
        sent = 0
        sessions = await store.due_reminders(now)
        for s in sessions:
            if not s.interview_at:
                continue
            delta = s.interview_at - now
            lang = s.lang or "kk"
            c = _c(lang)
            if 82800 <= delta <= 90000 and not s.reminder_24_sent:
                body = c.REMINDER_24H
                kb = reminder_keyboard(lang)
                if is_whatsapp_ui(s):
                    body += f"\n\n{wa_reminder_text(lang)}"
                    await self.tg.send_message(s.chat_id, body)
                else:
                    await update_panel(self.tg, s, s.chat_id, body, kb)
                    await store.save_session(s)
                s.reminder_24_sent = True
                await store.save_session(s)
                await notify_hr(
                    self.settings,
                    self.tg,
                    s,
                    "reminder_24",
                    extra=f"Кандидат: {s.profile.get('name', '—')}\nВизит: {s.interview_label or '—'}",
                )
                sent += 1
            elif 3300 <= delta <= 4200 and not s.reminder_1_sent:
                body = c.REMINDER_1H if hasattr(c, "REMINDER_1H") else c.REMINDER_2H
                kb = reminder_keyboard(lang)
                if is_whatsapp_ui(s):
                    body += f"\n\n{wa_reminder_text(lang)}"
                    await self.tg.send_message(s.chat_id, body)
                else:
                    await update_panel(self.tg, s, s.chat_id, body, kb)
                    await store.save_session(s)
                s.reminder_1_sent = True
                await store.save_session(s)
                await notify_hr(
                    self.settings,
                    self.tg,
                    s,
                    "reminder_1",
                    extra=f"Кандидат: {s.profile.get('name', '—')}\nВизит: {s.interview_label or '—'}",
                )
                sent += 1
            elif 6600 <= delta <= 7800 and not s.reminder_2_sent:
                body = c.REMINDER_2H
                kb = reminder_keyboard(lang)
                if is_whatsapp_ui(s):
                    body += f"\n\n{wa_reminder_text(lang)}"
                    await self.tg.send_message(s.chat_id, body)
                else:
                    await update_panel(self.tg, s, s.chat_id, body, kb)
                    await store.save_session(s)
                s.reminder_2_sent = True
                await store.save_session(s)
                sent += 1
        return sent
