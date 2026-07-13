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
###############################################################################

from datetime import UTC, datetime

from google.adk.agents import Agent
from google.adk.agents.readonly_context import ReadonlyContext
from google.genai import types

from common.config import settings
from common.resilience import build_adk_model

from .prompt import BOOKING_INSTRUCTION_TEMPLATE
from .tools import (
    cancel_booking,
    check_available_slots,
    create_booking,
    find_doctor_by_name,
    update_booking,
)

# Vietnamese weekday labels keyed by datetime.weekday() (Mon=0). Hard-coded
# rather than strftime("%A") so the injected anchor never depends on the host
# locale (a Windows/Linux runner with a non-vi locale would emit English names).
_VN_WEEKDAYS = ("Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật")


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
        today_weekday=_VN_WEEKDAYS[today.weekday()],
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
            check_available_slots,
            create_booking,
            update_booking,
            cancel_booking,
        ],
    )


booking_agent = build_booking_agent()
