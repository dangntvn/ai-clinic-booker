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
# Description: Symptom Agent — suggests specialty/doctor per BIZ-001; the
#              full doctors table is rendered into context on every
#              invocation via an ADK instruction provider (a callable
#              instruction, not a static string) so it's always current —
#              never searched via Qdrant (ADR-0020).
#              ADR-0026 (2026-07-22): _render_doctors_context renders each
#              doctor's specialty as its display name (tra dal/specialties.py
#              at settings.lang_suffix), never the raw snake_case code — this
#              is the most common surface a specialty label reaches the
#              patient through. _build_instruction also builds the
#              specialty_display_table block (TRIAGE Vietnamese label ->
#              display name at this server's lang_suffix) so the LLM can
#              copy the right label instead of translating one itself.
###############################################################################

from google.adk.agents import Agent
from google.adk.agents.readonly_context import ReadonlyContext
from google.genai import types

from common.config import settings
from common.resilience import build_adk_model
from dal.specialties import SPECIALTY_DISPLAY_NAMES, specialty_display_name

from .prompt import REPLY_LANGUAGE_NAME, SYMPTOM_INSTRUCTION_TEMPLATE, TRIAGE_TABLE
from .tools import search_knowledge_base


def _render_doctors_context(doctors: list) -> str:
    """Render the active doctors list into a compact block for the prompt.

    One line per doctor with doctor_id front and center — that id is the
    bridge into check_available_slots/create_booking (ARCH-001 §6.3). The
    specialty label is the display name for this server's settings.lang_suffix
    (ADR-0026), not the raw snake_case code stored in the DB — the LLM reads
    this block straight into its answer, so the label must already be in the
    right language, never left for the LLM to translate.
    """
    if not doctors:
        return "(chưa có bác sĩ nào trong hệ thống)"

    lines = []
    for d in doctors:
        bio = f" — {d.bio}" if d.bio else ""
        work_days = ",".join(d.work_days) if d.work_days else "?"
        specialty_label = specialty_display_name(d.specialty, settings.lang_suffix)
        lines.append(
            f"doctor_id={d.id} | {d.full_name} ({d.title or ''}) | {specialty_label} | "
            f"làm việc: {work_days}{bio}"
        )
    return "\n".join(lines)


def _render_specialty_display_table() -> str:
    """Build the "TRIAGE Vietnamese label -> display name" block (ADR-0026).

    One line per specialty, in SPECIALTIES order: the canonical Vietnamese
    label used inside TRIAGE_TABLE, an arrow, then the display name at this
    server's settings.lang_suffix. On the vn server the two columns are
    identical (no-op) — that's expected, not a bug.
    """
    lines = [
        f"{names['vn']} → {names[settings.lang_suffix]}"
        for names in SPECIALTY_DISPLAY_NAMES.values()
    ]
    return "\n".join(lines)


async def _build_instruction(ctx: ReadonlyContext) -> str:
    """ADK instruction provider — queries doctors fresh on every invocation."""
    from common.database import AsyncSessionFactory
    from dal.doctor_repository import DoctorRepository

    async with AsyncSessionFactory() as session:
        repo = DoctorRepository(session)
        doctors = await repo.list_active()

    return SYMPTOM_INSTRUCTION_TEMPLATE.format(
        triage_table=TRIAGE_TABLE,
        specialty_display_table=_render_specialty_display_table(),
        doctors_context=_render_doctors_context(doctors),
        # Resolved once at prompt.py's import time (LANG_SUFFIX is fixed for this
        # process's whole lifetime) — not recomputed per request, see that module's
        # docstring (CEO decision 2026-07-22, supersedes BUG-039's per-message
        # auto-detect instruction).
        reply_language=REPLY_LANGUAGE_NAME,
    )


def build_symptom_agent() -> Agent:
    """Build the Symptom Agent with a dynamic, DB-backed instruction."""
    return Agent(
        name="symptom_agent",
        model=build_adk_model(settings.symptom_llm_model),
        generate_content_config=types.GenerateContentConfig(
            temperature=settings.symptom_llm_temperature,
            max_output_tokens=settings.symptom_llm_max_tokens,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
        instruction=_build_instruction,
        tools=[search_knowledge_base],
    )


symptom_agent = build_symptom_agent()
