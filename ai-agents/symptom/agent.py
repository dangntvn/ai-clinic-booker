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
###############################################################################

from google.adk.agents import Agent
from google.adk.agents.readonly_context import ReadonlyContext

from common.config import settings

from .prompt import SYMPTOM_INSTRUCTION_TEMPLATE, TRIAGE_TABLE
from .tools import search_knowledge_base


def _render_doctors_context(doctors: list) -> str:
    """Render the active doctors list into a compact block for the prompt.

    One line per doctor with doctor_id front and center — that id is the
    bridge into check_available_slots/create_booking (ARCH-001 §6.3).
    """
    if not doctors:
        return "(chưa có bác sĩ nào trong hệ thống)"

    lines = []
    for d in doctors:
        bio = f" — {d.bio}" if d.bio else ""
        work_days = ",".join(d.work_days) if d.work_days else "?"
        lines.append(
            f"doctor_id={d.id} | {d.full_name} ({d.title or ''}) | {d.specialty} | "
            f"làm việc: {work_days}{bio}"
        )
    return "\n".join(lines)


async def _build_instruction(ctx: ReadonlyContext) -> str:
    """ADK instruction provider — queries doctors fresh on every invocation."""
    from common.database import AsyncSessionFactory
    from data.doctor_repository import DoctorRepository

    async with AsyncSessionFactory() as session:
        repo = DoctorRepository(session)
        doctors = await repo.list_active()

    return SYMPTOM_INSTRUCTION_TEMPLATE.format(
        triage_table=TRIAGE_TABLE,
        doctors_context=_render_doctors_context(doctors),
    )


def build_symptom_agent() -> Agent:
    """Build the Symptom Agent with a dynamic, DB-backed instruction."""
    return Agent(
        name="symptom_agent",
        model=settings.gemini_llm_model,
        instruction=_build_instruction,
        tools=[search_knowledge_base],
    )


symptom_agent = build_symptom_agent()
