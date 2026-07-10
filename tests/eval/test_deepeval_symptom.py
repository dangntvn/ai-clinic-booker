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
#
# UPDATED 2026-07-10 (senior-tester, TASK-029) — the 3 cases above are now
# data-driven from eval/golden_set_deepeval_symptom.yaml via
# eval/deepeval_dataset.py::load_dataset(), loaded into a real
# deepeval.dataset.EvaluationDataset, instead of one hardcoded
# LLMTestCase/GEval call per test function. Behavior is unchanged: still a
# real run_conversation() call per case, still the same 3 questions/
# metrics/thresholds/GEval criteria text. The `symptom_retrieval` fixture
# (RetrievalCapture spy) is now requested for all 3 parametrized cases
# rather than only the medical_guide one — the 2 routing cases (whose
# YAML entry has `context_kind: none`) simply never read
# `symptom_retrieval.contexts()`, so the spy is installed-but-unused for
# them, an intentional, harmless side effect of collapsing 3 test functions
# into 1 parametrized one (documented here, not hidden).
###############################################################################

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from eval.deepeval_dataset import build_metrics, load_dataset
from eval.deepeval_gemini import build_judge

_dataset = load_dataset("golden_set_deepeval_symptom.yaml")


@pytest.mark.eval
@pytest.mark.llm
@pytest.mark.parametrize("golden", _dataset.goldens, ids=[g.name for g in _dataset.goldens])
async def test_symptom_cases(golden, symptom_retrieval):
    """Run one Symptom Agent case (question + metrics from golden.additional_metadata).

    See eval/golden_set_deepeval_symptom.yaml for the 3 cases this
    parametrizes over: 1 grounded medical_guide Q&A case (AnswerRelevancy +
    Faithfulness) and 2 specialty-routing cases (GEval checks, no
    retrieval_context attached — matches the pre-refactor behavior), all
    against the real orchestrator via run_conversation().
    """
    from tests.eval.conftest import run_conversation

    case = golden.additional_metadata
    question = case["input"]
    actual_output = await run_conversation(question)

    if case.get("context_kind") == "retrieval":
        fallback = case.get("not_found_fallback", "(no context retrieved)")
        test_case = LLMTestCase(
            input=question,
            actual_output=actual_output,
            retrieval_context=symptom_retrieval.contexts() or [fallback],
        )
    else:
        test_case = LLMTestCase(input=question, actual_output=actual_output)

    judge = build_judge()
    assert_test(test_case, build_metrics(case, judge))
