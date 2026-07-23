# Copyright 2026 DANG NT (dangnt.vn@gmail.com)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Description: Booking Agent — books/reschedules/cancels appointments via
#              dal/booking_repository (ARCH-001 §5.1, §5.3). No SQL and no
#              conflict-handling logic here beyond interpreting tool results
#              — that all lives in dal/booking_repository.py (ADR-0009). Uses a
#              dynamic ADK instruction provider (a callable, not a static
#              string, same pattern as symptom/agent.py) to inject today's date
#              as the anchor the LLM resolves relative dates against (BUG-009).
#              ADR-0027 (2026-07-22): _render_specialty_code_table() builds the
#              {specialty_code_table} block (display name at settings.lang_suffix
#              -> snake_case code) so the LLM can look up a specialty code
#              instead of guessing one when the patient names a specialty
#              directly, without a doctor_id handoff from the Symptom Agent.
###############################################################################

from datetime import UTC, datetime

from google.adk.agents import Agent
from google.adk.agents.readonly_context import ReadonlyContext
from google.genai import types

from common.config import settings
from common.resilience import build_adk_model
from dal.specialties import SPECIALTIES, specialty_display_name

from .prompt import BOOKING_INSTRUCTION_TEMPLATE, REPLY_LANGUAGE_NAME
from .tools import (
    cancel_booking,
    check_available_slots,
    create_booking,
    find_doctor_by_name,
    find_earliest_available_slot,
    list_doctors_by_specialty,
    update_booking,
)

# Weekday labels keyed by datetime.weekday() (Mon=0), one tuple per LANG_SUFFIX so the
# injected reference date always matches this process's fixed reply language (CEO decision
# 2026-07-22, common.config.REPLY_LANGUAGE_NAME_BY_LANG_SUFFIX / prompt.py's REPLY_LANGUAGE_NAME).
# Previously this was a single Vietnamese-only tuple — on the jp/en servers that leaked a
# literal Vietnamese weekday label (e.g. "Thứ Tư") into the NGÀY THAM CHIẾU line of an
# otherwise jp/en reply, exactly the kind of mixed-language leak this task's language-fix rule
# is meant to prevent, just resurfacing in the date anchor instead of the model's own wording
# (code-reviewer finding, review 1/3). Hard-coded rather than strftime("%A")/babel so the
# injected anchor never depends on the host locale (a Windows/Linux runner with a non-vi/ja/en
# locale would emit yet another language) and so each tuple stays in lockstep with
# REPLY_LANGUAGE_NAME_BY_LANG_SUFFIX's own 3 keys.
_WEEKDAY_NAMES_BY_LANG_SUFFIX = {
    "vn": ("Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"),
    "jp": ("月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"),
    "en": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
}


def _render_specialty_code_table() -> str:
    """Build the "display name -> code" lookup block (ADR-0027 §1).

    Mirror image of symptom/agent.py::_render_specialty_display_table (that
    one goes TRIAGE vn label -> display name; this one goes display name ->
    code) — kept as its own helper here rather than shared, matching the
    existing one-helper-per-agent layout each prompt already uses.

    One line per specialty, in SPECIALTIES order: the display name at this
    server's settings.lang_suffix, an arrow, then the snake_case code — so the
    LLM can look up whatever language it's replying in on the left, and copy
    the code on the right verbatim into list_doctors_by_specialty, never
    inventing/translating one itself.
    """
    return "\n".join(
        f"{specialty_display_name(code, settings.lang_suffix)} → {code}" for code in SPECIALTIES
    )


def _build_instruction(ctx: ReadonlyContext) -> str:
    """ADK instruction provider — injects today's date/weekday as the anchor the
    LLM resolves relative Vietnamese dates against (BUG-009).

    Uses datetime.now(UTC) to stay on the same clock the rest of the booking
    domain interprets dates against: slot_time is TIMESTAMPTZ and
    check_available_slots builds clinic-hour slots in UTC
    (dal/booking_repository.py), so the anchor day must share that clock rather
    than introduce a separate local-time "today".
    """
    today = datetime.now(UTC).date()
    return BOOKING_INSTRUCTION_TEMPLATE.format(
        today_iso=today.isoformat(),
        today_weekday=_WEEKDAY_NAMES_BY_LANG_SUFFIX[settings.lang_suffix][today.weekday()],
        # Resolved once at prompt.py's import time (LANG_SUFFIX is fixed for this
        # process's whole lifetime) — not recomputed per request, see that module's
        # docstring (CEO decision 2026-07-22, supersedes BUG-039's per-message
        # auto-detect instruction).
        reply_language=REPLY_LANGUAGE_NAME,
        # ADR-0027: display-name -> code table so the LLM can look up the
        # specialty code instead of guessing/translating one when the patient
        # names a specialty directly (no doctor_id handoff from Symptom Agent).
        specialty_code_table=_render_specialty_code_table(),
    )


def build_booking_agent() -> Agent:
    """Build the Booking Agent with booking + doctor-lookup tools and a date-anchored prompt."""
    return Agent(
        name="booking_agent",
        model=build_adk_model(settings.booking_llm_model),
        generate_content_config=types.GenerateContentConfig(
            temperature=settings.booking_llm_temperature,
            max_output_tokens=settings.booking_llm_max_tokens,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
        instruction=_build_instruction,
        tools=[
            find_doctor_by_name,
            list_doctors_by_specialty,
            check_available_slots,
            find_earliest_available_slot,
            create_booking,
            update_booking,
            cancel_booking,
        ],
    )


booking_agent = build_booking_agent()
