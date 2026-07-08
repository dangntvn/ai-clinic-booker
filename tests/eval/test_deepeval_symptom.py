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
# Description: Symptom Agent DeepEval tests — real orchestrator run, grounded
#              in real seeded data: (1) the 2 real medical_guide rows (ids
#              14-15) for open-guidance questions, (2) the live `doctors`
#              table (11 real doctors, ids 3-13, TASK-025/026) for specialty
#              routing — the triage table itself is static code (ADR-0018),
#              not something to re-verify here; what TASK-026 flagged as
#              actually risky with real data is (a) hallucinated grounding
#              and (b) inventing a doctor for a specialty that has none.
###############################################################################

import pytest
from deepeval import assert_test
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

from eval.deepeval_gemini import build_judge

THRESHOLD = 0.7


@pytest.mark.eval
@pytest.mark.llm
async def test_symptom_medical_guide_question_grounded(symptom_retrieval):
    """Real content from eval/fixtures/knowledge_base/medical_guide/cao-huyet-ap.md (id=14)."""
    from tests.eval.conftest import run_conversation

    question = "Huyết áp bao nhiêu thì được coi là cao?"
    actual_output = await run_conversation(question)

    test_case = LLMTestCase(
        input=question,
        actual_output=actual_output,
        retrieval_context=symptom_retrieval.contexts() or ["(no context retrieved)"],
    )
    judge = build_judge()
    assert_test(
        test_case,
        [
            AnswerRelevancyMetric(threshold=THRESHOLD, model=judge),
            FaithfulnessMetric(threshold=THRESHOLD, model=judge),
        ],
    )


@pytest.mark.eval
@pytest.mark.llm
async def test_symptom_routes_to_real_doctor_for_covered_specialty():
    """Da liễu is one of the 9/14 specialties with a real seeded doctor.

    Real doctor: Đào Thanh Thủy, doctor_id=8 (eval/seed_result_2026-07-08.json).
    Symptoms below match the Da liễu row of the triage table
    (ai-agents/symptom/prompt.py TRIAGE_TABLE) verbatim ("nổi mẩn/mề đay/ngứa",
    "nấm da/hắc lào/lang ben").
    """
    from tests.eval.conftest import run_conversation

    question = "Tôi bị nổi mẩn đỏ ngứa ở chân và nghi bị nấm da, nên khám khoa nào?"
    actual_output = await run_conversation(question)

    test_case = LLMTestCase(input=question, actual_output=actual_output)
    judge = build_judge()
    routes_correctly = GEval(
        name="RoutesToRealDaLieuDoctor",
        criteria=(
            "'actual_output' should recommend the 'Da liễu' (dermatology) "
            "department for these skin symptoms, per the clinic's triage "
            "rules. If it names a specific doctor or doctor_id, it must be "
            "'Đào Thanh Thủy' (doctor_id=8) — the only real Da liễu doctor "
            "in the system — not any other name."
        ),
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=THRESHOLD,
        model=judge,
    )
    assert_test(test_case, [routes_correctly])


@pytest.mark.eval
@pytest.mark.llm
async def test_symptom_does_not_invent_doctor_for_uncovered_specialty():
    """Tim mạch (cardiology) is one of the 5/14 specialties with ZERO real

    doctors from phongkham5sao.vn (TASK-024/026 finding). The agent must not
    fabricate a cardiologist that doesn't exist in the seeded `doctors` table.
    """
    from tests.eval.conftest import run_conversation

    question = "Tôi hay hồi hộp, tim đập nhanh và tức ngực khi gắng sức, nên khám khoa nào?"
    actual_output = await run_conversation(question)

    test_case = LLMTestCase(input=question, actual_output=actual_output)
    judge = build_judge()
    no_fake_doctor = GEval(
        name="NoFabricatedCardiologist",
        criteria=(
            "The clinic's real doctor list has NO doctor with specialty "
            "'Tim mạch' (cardiology) — this is a known, confirmed gap. "
            "'actual_output' passes only if it does NOT name a specific "
            "doctor or doctor_id for Tim mạch (naming the specialty itself, "
            "or saying no cardiologist is currently available, is fine and "
            "should pass)."
        ),
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=THRESHOLD,
        model=judge,
    )
    assert_test(test_case, [no_fake_doctor])
