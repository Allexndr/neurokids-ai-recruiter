from __future__ import annotations

import json
import re
from typing import Any

from app.ai.prompts import EXTRACT_SYSTEM, INTENT_SYSTEM, STEP_INTERPRET_SYSTEM
from app.bot.semantic import SemanticResult, StepContext, interpret_answer
from app.bot.screening import regex_parse_profile

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.together_client import TogetherClient


def _extract_json(raw: str) -> dict[str, Any]:
    raw = (raw or "").strip()
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


def merge_profile(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in extra.items():
        if v is None:
            continue
        if k not in out or out[k] in (None, ""):
            out[k] = v
    return out


def parse_profile_local(text: str) -> dict[str, Any]:
    return regex_parse_profile(text)


def profile_complete(profile: dict[str, Any]) -> bool:
    return bool(profile.get("name")) and profile.get("age") is not None


async def parse_profile_with_ai(
    text: str,
    together: TogetherClient | None,
) -> dict[str, Any]:
    local = parse_profile_local(text)
    if profile_complete(local) and local.get("is_student") is not None:
        return local
    if not together:
        return local
    messages = [
        {"role": "system", "content": EXTRACT_SYSTEM},
        {"role": "user", "content": text},
    ]
    raw, _ = await together.chat(messages, temperature=0.1, max_tokens=180)
    if not raw:
        return local
    return merge_profile(local, _extract_json(raw))


async def classify_intent(text: str, together: TogetherClient | None) -> str:
    t = (text or "").lower()
    if any(x in t for x in ("собес", "кездес", "запис", "жазыл", "приду", "келем")):
        return "schedule"
    if any(x in t for x in ("келе алмай", "перенос", "бүгін келе", "раньше", "ертерек")):
        return "reschedule"
    if any(x in t for x in ("подтверж", "раста", "келем", "буду")):
        return "confirm"
    if not together:
        return "faq"
    messages = [
        {"role": "system", "content": INTENT_SYSTEM},
        {"role": "user", "content": text},
    ]
    raw, _ = await together.chat(messages, temperature=0.0, max_tokens=20)
    if not raw:
        return "other"
    word = raw.strip().split()[0].lower()
    for w in ("schedule", "faq", "reschedule", "confirm", "cancel_visit", "other"):
        if w in word:
            return w
    return "other"


async def interpret_step_answer(
    text: str,
    ctx: StepContext,
    together: "TogetherClient | None",
    *,
    is_student: bool | None = None,
    question_hint: str = "",
) -> SemanticResult:
    local = interpret_answer(text, ctx, is_student=is_student)
    if local.ok:
        return local
    if not together:
        return local

    prompt = (
        f"{STEP_INTERPRET_SYSTEM}\n\n"
        f"context={ctx.value}\n"
        f"question={question_hint}\n"
        f"is_student={is_student}\n"
    )
    raw, _ = await together.chat(
        [{"role": "system", "content": prompt}, {"role": "user", "content": text}],
        temperature=0.1,
        max_tokens=80,
    )
    if not raw:
        return local
    data = _extract_json(raw)
    ans = data.get("answer")
    if ans is None:
        return SemanticResult(False, error_key="yes_no_unclear")
    if ans == "student_branch":
        return SemanticResult(True, value="student_branch")
    if ans == "almaty":
        return SemanticResult(True, value="almaty")
    if ans == "other":
        return SemanticResult(True, value="other")
    if isinstance(ans, bool):
        return SemanticResult(True, value=ans)
    s = str(ans).lower()
    if s in ("true", "yes", "да", "иә", "1"):
        return SemanticResult(True, value=True)
    if s in ("false", "no", "нет", "жоқ", "2"):
        return SemanticResult(True, value=False)
    return SemanticResult(False, error_key="yes_no_unclear")
