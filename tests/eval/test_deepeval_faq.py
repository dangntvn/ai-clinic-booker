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
# Description: FAQ Agent DeepEval tests — LLM-as-judge, real orchestrator run
#              (no mocked actual_output), grounded in the 22 real
#              phongkham5sao.vn knowledge_base rows seeded by TASK-025/026
#              (ids 1-22, see eval/seed_result_2026-07-08.json). Two core
#              metrics only (TASK-027 DoD):
#                - AnswerRelevancyMetric: does the reply actually answer the
#                  question asked (catches off-topic replies).
#                - FaithfulnessMetric: does the reply only state facts present
#                  in the real retrieved context (catches hallucination) —
#                  the highest real risk for a RAG-backed FAQ agent.
#              A third case checks the not-found fallback (ADR-0008) using a
#              question TASK-026 confirmed has zero real content (BHYT) —
#              this must NOT be silently fabricated.
###############################################################################

import pytest
from deepeval import assert_test
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

from eval.deepeval_gemini import build_judge

THRESHOLD = 0.7


@pytest.mark.eval
@pytest.mark.llm
async def test_faq_pricing_question_grounded(faq_retrieval):
    """Real pricing fact from eval/fixtures/knowledge_base/policy/bang-gia-xet-nghiem.md (id=20)."""
    from tests.eval.conftest import run_conversation

    question = "Xét nghiệm nhóm máu ở phòng khám giá bao nhiêu?"
    actual_output = await run_conversation(question)

    test_case = LLMTestCase(
        input=question,
        actual_output=actual_output,
        retrieval_context=faq_retrieval.contexts() or ["(no context retrieved)"],
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
async def test_faq_clinic_info_question_grounded(faq_retrieval):
    """Real clinic info from eval/fixtures/knowledge_base/clinic_info/gioi-thieu.md (id=1)."""
    from tests.eval.conftest import run_conversation

    question = "Phòng khám Đa khoa 5 Sao ở địa chỉ nào và mở cửa giờ nào?"
    actual_output = await run_conversation(question)

    test_case = LLMTestCase(
        input=question,
        actual_output=actual_output,
        retrieval_context=faq_retrieval.contexts() or ["(no context retrieved)"],
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
async def test_faq_out_of_scope_question_not_fabricated(faq_retrieval):
    """TASK-026 confirmed (real retrieval test + WebSearch) phongkham5sao.vn has

    no BHYT/insurance policy page — the real knowledge_base has nothing to
    ground this in. The agent must not invent a policy answer.
    """
    from tests.eval.conftest import run_conversation

    question = "Phòng khám có nhận thanh toán bằng bảo hiểm y tế (BHYT) không?"
    actual_output = await run_conversation(question)

    test_case = LLMTestCase(
        input=question,
        actual_output=actual_output,
        retrieval_context=faq_retrieval.contexts() or ["(no real content covers BHYT policy)"],
    )
    judge = build_judge()
    not_fabricated = GEval(
        name="NoFabricatedPolicy",
        criteria=(
            "The knowledge_base has no real content about BHYT/insurance policy. "
            "'actual_output' passes only if it admits it doesn't have this "
            "information / suggests contacting the clinic directly, and does "
            "NOT assert a specific BHYT acceptance policy (yes or no) as fact."
        ),
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=THRESHOLD,
        model=judge,
    )
    assert_test(test_case, [not_fabricated])
