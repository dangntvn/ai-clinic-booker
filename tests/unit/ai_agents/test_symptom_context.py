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
###############################################################################

from types import SimpleNamespace

from ai_agents.symptom.agent import _render_doctors_context


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
    """A roster with no Tim mạch doctor must not surface any doctor tied to
    'Tim mạch' — the block only ever pairs a doctor with their OWN specialty,
    so the LLM has nothing to fabricate a cardiologist from."""
    roster = [
        _doctor(3, "Phạm Thị Lan Hương", "Nội tổng quát"),
        _doctor(8, "Đào Thanh Thủy", "Da liễu"),
    ]
    rendered = _render_doctors_context(roster)
    lines = rendered.splitlines()

    # Each doctor renders on exactly one line, paired with their OWN specialty.
    huong = next(ln for ln in lines if "Phạm Thị Lan Hương" in ln)
    thuy = next(ln for ln in lines if "Đào Thanh Thủy" in ln)
    assert "Nội tổng quát" in huong
    assert "Da liễu" in thuy
    # The uncovered specialty appears nowhere in the block.
    assert "Tim mạch" not in rendered


def test_each_doctor_rendered_only_under_their_own_specialty():
    """Sanity: no cross-attribution — a Da liễu doctor never renders under any
    other specialty label."""
    roster = [_doctor(8, "Đào Thanh Thủy", "Da liễu")]
    rendered = _render_doctors_context(roster)

    assert rendered.count("Đào Thanh Thủy") == 1
    assert "Da liễu" in rendered
    for other in ("Tim mạch", "Tiêu hóa", "Hô hấp", "Nội tiết"):
        assert other not in rendered
