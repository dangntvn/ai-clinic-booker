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
# Description: Single source of truth for every evaluation metric formula
#              (Hit Rate@k, MRR, intent-routing accuracy, faithfulness) —
#              ARCH-001 §8 metric rule: only this file may define a formula;
#              tests/eval/test_retrieval_metrics.py only checks these
#              formulas against synthetic input, never asserts real
#              thresholds itself (that's tests/eval/test_eval_gate.py).
###############################################################################


def hit_rate_at_k(retrieved_ids: list[int], relevant_ids: list[int], k: int) -> float:
    """Fraction of queries (here: 1 query at a time) with a relevant id in the top-k.

    Args:
        retrieved_ids: Ids returned by the search, best match first.
        relevant_ids: Ids considered a correct answer for this query.
        k: How many of the top results to consider.

    Returns:
        1.0 if any of the top-k retrieved_ids is in relevant_ids, else 0.0.
    """
    return 1.0 if set(retrieved_ids[:k]) & set(relevant_ids) else 0.0


def mean_hit_rate_at_k(cases: list[dict], k: int) -> float:
    """Average hit_rate_at_k across a batch of golden-set cases.

    Args:
        cases: Each dict has "retrieved_ids" and "relevant_ids" (both list[int]).
        k: Cutoff passed to hit_rate_at_k.
    """
    if not cases:
        return 0.0
    scores = [hit_rate_at_k(c["retrieved_ids"], c["relevant_ids"], k) for c in cases]
    return sum(scores) / len(scores)


def reciprocal_rank(retrieved_ids: list[int], relevant_ids: list[int]) -> float:
    """1/rank of the first relevant id in retrieved_ids (0.0 if none found)."""
    relevant = set(relevant_ids)
    for rank, item_id in enumerate(retrieved_ids, start=1):
        if item_id in relevant:
            return 1.0 / rank
    return 0.0


def mrr(cases: list[dict]) -> float:
    """Mean Reciprocal Rank across a batch of golden-set cases.

    Args:
        cases: Each dict has "retrieved_ids" and "relevant_ids" (both list[int]).
    """
    if not cases:
        return 0.0
    scores = [reciprocal_rank(c["retrieved_ids"], c["relevant_ids"]) for c in cases]
    return sum(scores) / len(scores)


def intent_routing_accuracy(cases: list[dict]) -> float:
    """Fraction of golden-set cases where the actual intent matched expected.

    Args:
        cases: Each dict has "expected_intent" and "actual_intent" (both str).
    """
    if not cases:
        return 0.0
    correct = sum(1 for c in cases if c["expected_intent"] == c["actual_intent"])
    return correct / len(cases)


def faithfulness_score(answer: str, context: str, judge_verdict: bool) -> float:
    """Score one LLM-judge faithfulness verdict as 1.0/0.0.

    The actual judging (does `answer` only state facts present in `context`)
    is an LLM call made by the caller (tests/eval/test_faithfulness.py,
    @pytest.mark.llm) — this function just standardizes the verdict into the
    same [0, 1] scale as the other metrics so runner.py can average them.

    Args:
        answer: The agent's answer text (unused by the formula itself, kept
                 for signature symmetry/logging by callers).
        context: The retrieved context the answer should be grounded in
                 (unused by the formula itself, same reason).
        judge_verdict: True if the LLM judge ruled the answer faithful to context.
    """
    return 1.0 if judge_verdict else 0.0


def mean_faithfulness(verdicts: list[bool]) -> float:
    """Average faithfulness_score across a batch of LLM-judge verdicts."""
    if not verdicts:
        return 0.0
    return sum(1.0 if v else 0.0 for v in verdicts) / len(verdicts)


def booking_concurrency_pass_rate(cases: list[dict]) -> float:
    """Fraction of concurrency golden-set cases where actual_successes matched expected.

    Args:
        cases: Each dict has "expected_successes" and "actual_successes" (both int).
    """
    if not cases:
        return 0.0
    correct = sum(1 for c in cases if c["expected_successes"] == c["actual_successes"])
    return correct / len(cases)
