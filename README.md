# Recruiter Support Bot (Neurokids HR)

AI HR-ассистент в Telegram: скрининг кандидатов, AI-оценка резюме, запись на интервью, напоминания, анализ интервью, HR-команды.

## Модули

1. **Поиск и отбор** — загрузка PDF/DOCX, CSV, HH.ru API, AI-скоринг `/rank`
2. **Коммуникация** — Telegram + WhatsApp Cloud API
3. **Интервью** — слоты + Google Calendar
4. **Напоминания** — за 24 ч и 1 ч с подтверждением
5. **Анализ интервью** — Groq/OpenAI Whisper + LLM-карточка
6. **База кандидатов** — SQLite/Postgres, рейтинг, поиск

## Быстрый старт

```bash
cd hr-recruter-bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Заполните TELEGRAM_BOT_TOKEN, GROQ_API_KEY, TELEGRAM_HR_CHAT_ID
uvicorn app.main:app --reload --port 8000
```

Локальный webhook: ngrok → `WEBHOOK_BASE_URL` → `curl http://localhost:8000/setup`

Polling (без webhook):

```bash
python scripts/run_polling.py
```

## Переменные окружения

См. [.env.example](.env.example)

| Переменная | Назначение |
|------------|------------|
| `TELEGRAM_BOT_TOKEN` | Токен @recruter_support_bot |
| `TELEGRAM_HR_CHAT_ID` | Chat ID HR для уведомлений и команд |
| `GROQ_API_KEY` | Бесплатный LLM + Whisper |
| `OPENROUTER_API_KEY` | Fallback LLM |
| `HH_ACCESS_TOKEN` | HH.ru API (отклики бесплатно, поиск — платно) |
| `WHATSAPP_*` | Meta Cloud API |
| `GOOGLE_*` | Google Calendar |

## HR-команды в Telegram

Отправляйте из чата `TELEGRAM_HR_CHAT_ID`:

- `/vacancy create Менеджер \| продажи, CRM`
- `/candidates` — топ кандидатов
- `/rank` — AI-рейтинг
- `/import_resume` + файл PDF
- `/hh_responses VACANCY_ID`

## Cron напоминаний

```bash
curl "https://YOUR_URL/api/cron/reminders?secret=CRON_SECRET"
```

Каждые 15 мин (cron-job.org).

## Тесты

```bash
pytest -q
```

## Деплой Vercel

```bash
chmod +x scripts/deploy-vercel.sh
./scripts/deploy-vercel.sh
```

**Важно:** отзовите токен бота в @BotFather, если он был опубликован. Храните секреты только в `.env`.
