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
#
# UPDATED 2026-07-10 (senior-tester, TASK-029) — the 3 cases above are now
# data-driven from eval/golden_set_deepeval_faq.yaml via
# eval/deepeval_dataset.py::load_dataset(), loaded into a real
# deepeval.dataset.EvaluationDataset, instead of one hardcoded
# LLMTestCase/GEval call per test function. Behavior is unchanged: still a
# real run_conversation() call per case, still the real RetrievalCapture
# spy (faq_retrieval fixture), still the same 3 questions/metrics/
# thresholds/GEval criteria text — see the YAML file's header for exactly
# what "unchanged" means here.
###############################################################################

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from eval.deepeval_dataset import build_metrics, load_dataset
from eval.deepeval_gemini import build_judge

_dataset = load_dataset("golden_set_deepeval_faq.yaml")


@pytest.mark.eval
@pytest.mark.llm
@pytest.mark.parametrize("golden", _dataset.goldens, ids=[g.name for g in _dataset.goldens])
async def test_faq_cases(golden, faq_retrieval):
    """Run one FAQ Agent case (question + metrics from golden.additional_metadata).

    See eval/golden_set_deepeval_faq.yaml for the 3 cases this parametrizes
    over: 2 grounded-Q&A cases (AnswerRelevancy + Faithfulness) and 1
    not-fabricated-fallback case (a GEval check), all against the real
    orchestrator via run_conversation().
    """
    from tests.eval.conftest import run_conversation

    case = golden.additional_metadata
    question = case["input"]
    actual_output = await run_conversation(question)

    fallback = case.get("not_found_fallback", "(no context retrieved)")
    test_case = LLMTestCase(
        input=question,
        actual_output=actual_output,
        retrieval_context=faq_retrieval.contexts() or [fallback],
    )
    judge = build_judge()
    assert_test(test_case, build_metrics(case, judge))
