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
# Description: Tests eval/metrics.py formulas with synthetic input only —
#              no real quality-threshold assertion here (ARCH-001 §8 metric
#              rule; the real gate is tests/eval/test_eval_gate.py).
#
# UPDATED 2026-07-10 (senior-tester, TASK-015 batch 3/4) — added coverage for
# the span-level retrieval family + keyword_match + the new async
# faithfulness_score, all still synthetic-input-only (faithfulness_score's
# "judge" is a fake async callable here, never a real Gemini call).
###############################################################################

import pytest

from eval.metrics import (
    booking_concurrency_pass_rate,
    chunk_hits,
    faithfulness_score,
    first_hit_rank,
    hit_rate_at_k,
    hit_rate_at_k_from_hits,
    intent_routing_accuracy,
    keyword_match,
    mean_faithfulness,
    mean_hit_rate_at_k,
    mrr,
    mrr_from_hits,
    precision_from_hits,
    reciprocal_rank,
)


def test_hit_rate_at_k_hit():
    assert hit_rate_at_k(retrieved_ids=[3, 1, 2], relevant_ids=[1], k=3) == 1.0


def test_hit_rate_at_k_miss_outside_k():
    assert hit_rate_at_k(retrieved_ids=[3, 1, 2], relevant_ids=[1], k=1) == 0.0


def test_hit_rate_at_k_no_relevant():
    assert hit_rate_at_k(retrieved_ids=[3, 1, 2], relevant_ids=[99], k=3) == 0.0


def test_mean_hit_rate_at_k():
    cases = [
        {"retrieved_ids": [1, 2], "relevant_ids": [1]},
        {"retrieved_ids": [5, 6], "relevant_ids": [1]},
    ]
    assert mean_hit_rate_at_k(cases, k=2) == 0.5


def test_mean_hit_rate_at_k_empty():
    assert mean_hit_rate_at_k([], k=5) == 0.0


def test_reciprocal_rank_first_position():
    assert reciprocal_rank([1, 2, 3], [1]) == 1.0


def test_reciprocal_rank_third_position():
    assert reciprocal_rank([2, 3, 1], [1]) == 1.0 / 3


def test_reciprocal_rank_not_found():
    assert reciprocal_rank([2, 3, 4], [1]) == 0.0


def test_mrr():
    cases = [
        {"retrieved_ids": [1, 2], "relevant_ids": [1]},  # rank 1 -> 1.0
        {"retrieved_ids": [2, 1], "relevant_ids": [1]},  # rank 2 -> 0.5
    ]
    assert mrr(cases) == 0.75


def test_intent_routing_accuracy():
    cases = [
        {"expected_intent": "faq_agent", "actual_intent": "faq_agent"},
        {"expected_intent": "booking_agent", "actual_intent": "symptom_agent"},
    ]
    assert intent_routing_accuracy(cases) == 0.5


def test_mean_faithfulness():
    assert mean_faithfulness([True, True, False, True]) == 0.75


def test_booking_concurrency_pass_rate():
    cases = [
        {"expected_successes": 1, "actual_successes": 1},
        {"expected_successes": 1, "actual_successes": 2},
    ]
    assert booking_concurrency_pass_rate(cases) == 0.5


# --- span-level retrieval family (TASK-015 batch 3/4) ---


def test_chunk_hits_matches_normalized_substring():
    texts = ["Giờ hoạt động: Thứ 2 - Chủ nhật,\n07h30 - 17h00", "không liên quan"]
    assert chunk_hits(texts, "07h30 - 17h00") == [True, False]


def test_chunk_hits_empty_span_never_hits():
    assert chunk_hits(["bất kỳ nội dung nào"], "") == [False]


def test_hit_rate_at_k_from_hits_hit_within_k():
    assert hit_rate_at_k_from_hits([False, True, False], k=2) == 1.0


def test_hit_rate_at_k_from_hits_hit_outside_k():
    assert hit_rate_at_k_from_hits([False, False, True], k=2) == 0.0


def test_mrr_from_hits_first_position():
    assert mrr_from_hits([True, False]) == 1.0


def test_mrr_from_hits_third_position():
    assert mrr_from_hits([False, False, True]) == 1.0 / 3


def test_mrr_from_hits_no_hit():
    assert mrr_from_hits([False, False]) == 0.0


def test_first_hit_rank_found():
    assert first_hit_rank([False, True, False]) == 2


def test_first_hit_rank_not_found():
    assert first_hit_rank([False, False]) is None


def test_precision_from_hits():
    assert precision_from_hits([True, False, True, False], k=4) == 0.5


def test_precision_from_hits_empty():
    assert precision_from_hits([], k=5) == 0.0


# --- keyword_match (TASK-015 batch 3/4) ---


def test_keyword_match_all_present():
    assert keyword_match("Giá 150.000 VNĐ cho xét nghiệm", ["150.000", "VNĐ"]) == 1.0


def test_keyword_match_partial_is_case_insensitive():
    assert keyword_match("Giá 150.000 vnđ", ["150.000", "VNĐ", "xét nghiệm"]) == 2 / 3


def test_keyword_match_empty_keywords():
    assert keyword_match("bất kỳ câu trả lời nào", []) == 0.0


# --- faithfulness_score (TASK-015 batch 3/4) — fake async judge, no real Gemini call ---


@pytest.mark.asyncio
async def test_faithfulness_score_parses_judge_response():
    async def fake_judge(system_prompt: str, user_message: str, **kwargs) -> str:
        return "0.85"

    score = await faithfulness_score("some answer", ["some context"], fake_judge)
    assert score == 0.85


@pytest.mark.asyncio
async def test_faithfulness_score_falls_back_to_zero_on_unparsable_response():
    async def fake_judge(system_prompt: str, user_message: str, **kwargs) -> str:
        return "not a float"

    score = await faithfulness_score("some answer", ["some context"], fake_judge)
    assert score == 0.0
