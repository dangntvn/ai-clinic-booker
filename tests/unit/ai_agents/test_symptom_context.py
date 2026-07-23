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
# Description: Unit tests for the Symptom Agent's doctor-context rendering
#              (ai_agents/symptom/agent.py::_render_doctors_context). This is
#              the data half of BUG-017's "don't fabricate a doctor for a
#              specialty that has none": the rendered block feeds the LLM only
#              real (doctor -> their own specialty) pairs, so a specialty with
#              zero doctors simply produces no line for it — the LLM is never
#              handed a doctor it could attribute to an empty specialty. Pure,
#              offline: the roster is simulated directly (the empty-specialty
#              state can no longer be reproduced against the seeded DB after
#              BUG-017 gave every specialty >= 2 doctors).
#              ADR-0026 (2026-07-22): `_doctor()` fixtures now pass the
#              snake_case specialty CODE (matching the real DB column), and
#              assertions check for the rendered DISPLAY NAME at whatever
#              settings.lang_suffix this test process is running under (not
#              hardcoded "en" — LANG_SUFFIX is env-driven, ADR-0023/0024), not
#              the raw code — that's the behavior _render_doctors_context now
#              has (tra dal/specialties.py, never the code verbatim).
###############################################################################

from types import SimpleNamespace

from ai_agents.symptom.agent import _render_doctors_context
from common.config import settings
from dal.specialties import specialty_display_name


def _display(code: str) -> str:
    return specialty_display_name(code, settings.lang_suffix)


def _doctor(doctor_id, full_name, specialty):
    return SimpleNamespace(
        id=doctor_id,
        full_name=full_name,
        title="Bác sĩ",
        specialty=specialty,
        work_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        bio=None,
    )


def test_empty_roster_renders_explicit_no_doctor_marker():
    assert _render_doctors_context([]) == "(chưa có bác sĩ nào trong hệ thống)"


def test_uncovered_specialty_produces_no_doctor_line():
    """A roster with no cardiology doctor must not surface any doctor tied to
    'cardiology' — the block only ever pairs a doctor with their OWN
    specialty, so the LLM has nothing to fabricate a cardiologist from."""
    roster = [
        _doctor(3, "Phạm Thị Lan Hương", "general_internal_medicine"),
        _doctor(8, "Đào Thanh Thủy", "dermatology"),
    ]
    rendered = _render_doctors_context(roster)
    lines = rendered.splitlines()

    # Each doctor renders on exactly one line, paired with their OWN specialty
    # display name at this process's settings.lang_suffix.
    huong = next(ln for ln in lines if "Phạm Thị Lan Hương" in ln)
    thuy = next(ln for ln in lines if "Đào Thanh Thủy" in ln)
    assert _display("general_internal_medicine") in huong
    assert _display("dermatology") in thuy
    # The uncovered specialty's display name appears nowhere in the block.
    assert _display("cardiology") not in rendered


def test_each_doctor_rendered_only_under_their_own_specialty():
    """Sanity: no cross-attribution — a dermatology doctor never renders under
    any other specialty's display name."""
    roster = [_doctor(8, "Đào Thanh Thủy", "dermatology")]
    rendered = _render_doctors_context(roster)

    assert rendered.count("Đào Thanh Thủy") == 1
    assert _display("dermatology") in rendered
    for other_code in ("cardiology", "gastroenterology", "pulmonology", "endocrinology"):
        assert _display(other_code) not in rendered
