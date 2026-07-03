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
#              — that all lives in dal/booking_repository.py (ADR-0009).
###############################################################################

from google.adk.agents import Agent
from google.genai import types

from common.config import settings

from .prompt import BOOKING_INSTRUCTION
from .tools import cancel_booking, check_available_slots, create_booking, update_booking


def build_booking_agent() -> Agent:
    """Build the Booking Agent with its four booking tools."""
    return Agent(
        name="booking_agent",
        model=settings.booking_llm_model,
        generate_content_config=types.GenerateContentConfig(
            temperature=settings.booking_llm_temperature,
            max_output_tokens=settings.booking_llm_max_tokens,
        ),
        instruction=BOOKING_INSTRUCTION,
        tools=[check_available_slots, create_booking, update_booking, cancel_booking],
    )


booking_agent = build_booking_agent()
