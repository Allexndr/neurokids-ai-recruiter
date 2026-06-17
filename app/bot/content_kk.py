"""Қазақша — AI HR-ассистент."""

INTRO_VACANCY = (
    "Мен <b>Neurokids HR</b> — іріктеу және собеседованиеге жазуға көмектесемін.\n"
    "Жауаптарды HR-менеджерге жіберемін."
)

ASK_NAME = (
    "📋 <b>1-қадам — есіміңіз?</b>\n\n"
    "Есімді бір хабарламада жазыңыз.\n\n"
    "💡 Мысал: <b>Айым</b> немесе <b>Александр</b>"
)

ASK_JOB_SEARCH = (
    "📋 <b>2-қадам — жұмыс іздеу актуалды ма?</b>\n\n"
    "Қазір белсенді іздеп жүрсіз бе?"
)

ASK_EXPERIENCE = (
    "📋 <b>3-қадам — тәжірибе мен дағдылар</b>\n\n"
    "Тәжірибеңізді, дағдыларыңызды қысқаша жазыңыз.\n"
    "Немесе PDF/DOCX резюмені жіберіңіз.\n\n"
    "💡 Мысал: «3 жыл сатуда, CRM, HR-ға кіргім келеді»"
)

NOT_LOOKING = (
    "Түсінікті, рахмет 🙏\n"
    "Іздеу актуалды болғанда — «Қайта бастау» 👇"
)

USE_BUTTONS = "Төмендегі батырманы таңдаңыз 👇"
FAQ_PICK_TOPIC = "Сұрақ тақырыбын таңдаңыз 👇"
ASK_RESUME_UPLOAD = (
    "📄 <b>Резюме жіберу</b>\n\n"
    "PDF немесе DOCX файлын бір хабарламада тіркеңіз.\n"
    "AI белсенді вакансияға сәйкестікті есептейді."
)

ERR_GARBAGE = "Мұндай жауап қабылданбайды. Мысалды қараңыз 👆"
ERR_NO_NAME = "Есіміңізді жазыңыз."
ERR_BAD_NAME = "Есім дұрыс емес сияқты."
ERR_YES_NO = "<b>Иә</b> немесе <b>Жоқ</b> батырмасын басыңыз."
ERR_EXPERIENCE_SHORT = "Тәжірибе туралы сәл толығырақ жазыңыз."

CONFIRM_STEP = "Қабылданды ✅"
GREETING = INTRO_VACANCY
ASK_NAME_AGE = ASK_NAME
ASK_STUDENT = ASK_JOB_SEARCH


def welcome_qualified(name: str) -> str:
    n = name or "дос"
    return (
        f"Рахмет, {n}! Анкета қабылданды ✅\n\n"
        "<b>Neurokids HR</b> — не істейміз?\n"
        "• 📅 Собеседованиеге жазылу\n"
        "• ❓ Сұрақ қою\n"
        "• 📄 Резюме жіберу\n\n"
        "Таңдаңыз 👇"
    )


FAQ_INTERNSHIP = "Тағылым — HR-мен собеседованиеда."
FAQ_EXPERIENCE = "Тәжірибе маңызды, бірақ шешім — интервью бойынша."
FAQ_SCHEDULE = "График — HR-мен собеседованиеда."
FAQ_JOB = "Neurokids HR — іріктеу, жазылу, кері байланыс."
FAQ_PRODUCT = "Вакансия деталдары — собеседованиеда."
FAQ_SALARY = "Жалақы — HR-мен интервьюде."
FAQ_SALARY_DETAIL = FAQ_SALARY
FAQ_PERCENT = FAQ_SALARY
FAQ_COMPANY = "Neurokids — рекрутингті автоматтандыратын AI HR-ассистент."

ASK_INTERVIEW_TIME = "Собеседование уақытын таңдаңыз 👇"
RESCHEDULE_OFFER = "Басқа уақытты таңдаңыз 👇"
EARLY_ARRIVAL = "Жақсы! Қанша уақытта боласыз?"
EARLY_OK = "Қабылданды, күтеміз ✅"


def confirm_visit(name: str, when_label: str) -> str:
    return (
        f"{name or 'Дос'}, сіз {when_label} жазылдыңыз 📅\n\n"
        "24 сағат және 1 сағат бұрын еске саламын.\n"
        "Жоспар өзгерсе — «Уақыт өзгерту» 👇"
    )


REMINDER_24H = "🔔 Еске салу: ертең собеседование. Растаңыз 👇"
REMINDER_1H = "🔔 1 сағаттан кейін собеседование. Растаңыз 👇"
REMINDER_2H = "🔔 2 сағаттан кейін кездесу. Келесіз бе? 👇"
HANDOFF = "HR-менеджерге қосамын — сәл күтіңіз 🙏"
FALLBACK_VOICE = "🎙 Дауыстық жіберіңіз — транскрипция мен HR карточкасын дайындаймын."
DB_TOUCH = "Іздеу актуалды ма? Жazылу немесе сұрақ?"

REJECT_AGE = REJECT_CITY = REJECT_LANGUAGE = REJECT_SCHEDULE = REJECT_ONLINE = ""
STUDENT_SCHEDULE_OK = ASK_CITY = ASK_SCHEDULE = ASK_STUDENT_SCHEDULE = ASK_LANGUAGE = ""
