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
###############################################################################

from eval.metrics import (
    booking_concurrency_pass_rate,
    hit_rate_at_k,
    intent_routing_accuracy,
    mean_faithfulness,
    mean_hit_rate_at_k,
    mrr,
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
