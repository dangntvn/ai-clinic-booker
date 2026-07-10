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
#
# UPDATED 2026-07-10 (senior-tester, TASK-015 batch 3/4) — added the
# span-level retrieval family (chunk_hits/hit_rate_at_k_from_hits/
# mrr_from_hits/precision_from_hits/first_hit_rank) and keyword_match(),
# ported from H:\thanhnt-projects\AI-Rag-Health's eval/metrics.py to close
# the gap between this project's golden sets (which now carry answer_span/
# answer_keywords, see golden_set_rag.yaml) and its metrics. The existing
# doc-id-level hit_rate_at_k(retrieved_ids, relevant_ids, k) already owned
# that name with a different signature, so the new span-level one is named
# hit_rate_at_k_from_hits(hits, k) instead of colliding with it — the
# reference file has no such collision (it only has the span-level family).
#
# faithfulness_score() is REPLACED, not renamed: the old signature
# `faithfulness_score(answer, context, judge_verdict: bool) -> float` was a
# thin bool->float shim around a judge verdict decided entirely by the
# caller — grep confirms it had zero call sites anywhere in the codebase
# (only its own docstring referenced the never-implemented
# tests/eval/test_faithfulness.py scaffold), so there was no consumer whose
# signature needed preserving. It's replaced with a real LLM-judge
# implementation (prompts a judge model and parses a 0.0-1.0 score),
# mirroring rag-health's faithfulness_score(answer, context_chunks,
# judge_llm) exactly, except this project's LLM access is async
# (common/gemini_client.py's generate() is a coroutine) so the judge is
# injected as an async callable rather than an object with a sync
# `.invoke()`. mean_faithfulness(verdicts: list[bool]) is kept as-is (still
# tested by test_retrieval_metrics.py, still a legitimate aggregator for any
# future binary-verdict judge use) but is independent of the new
# faithfulness_score — it never called it even before this change.
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


def _normalize(s: str) -> str:
    """Collapse all whitespace so span matching is robust to markdown/newline reflow.

    Args:
        s: Input string (may be None).

    Returns:
        String with all whitespace runs collapsed to a single space.
    """
    return " ".join((s or "").split())


def chunk_hits(retrieved_texts: list[str], answer_span: str) -> list[bool]:
    """Compute per-rank ground truth for span-level retrieval evaluation.

    A retrieved chunk is considered a hit when its whitespace-normalised text
    contains the whitespace-normalised ``answer_span`` as a substring.

    Args:
        retrieved_texts: Ordered list of chunk texts (most relevant first).
        answer_span:     Verbatim answer span from the golden set.

    Returns:
        A boolean list of the same length as ``retrieved_texts``.
    """
    span = _normalize(answer_span)
    return [bool(span) and span in _normalize(t) for t in retrieved_texts]


def hit_rate_at_k_from_hits(hits: list[bool], k: int) -> float:
    """Compute Span Hit Rate@K: 1.0 if the answer span appears in any of the top-K chunks.

    Named ``_from_hits`` (rather than reusing ``hit_rate_at_k``) because that
    name is already taken by the doc-id-level formula above, which has a
    different signature (``retrieved_ids``/``relevant_ids`` instead of a
    pre-computed boolean hit list).

    Args:
        hits: Per-rank boolean hit list from ``chunk_hits``.
        k:    Cutoff rank.

    Returns:
        1.0 if there is at least one hit in the top-K, 0.0 otherwise.
    """
    return 1.0 if any(hits[:k]) else 0.0


def mrr_from_hits(hits: list[bool]) -> float:
    """Compute MRR from a boolean hit list (span-level).

    Returns the reciprocal rank of the first chunk that contains the answer span.

    Args:
        hits: Per-rank boolean hit list from ``chunk_hits``.

    Returns:
        Float in (0.0, 1.0], or 0.0 if no hit was found.
    """
    for rank, hit in enumerate(hits, start=1):
        if hit:
            return 1.0 / rank
    return 0.0


def first_hit_rank(hits: list[bool]) -> int | None:
    """Return the 1-based rank of the first chunk that contains the answer span.

    Args:
        hits: Per-rank boolean hit list from ``chunk_hits``.

    Returns:
        Integer rank of the first hit, or ``None`` if the span was not retrieved.
    """
    for rank, hit in enumerate(hits, start=1):
        if hit:
            return rank
    return None


def precision_from_hits(hits: list[bool], k: int) -> float:
    """Compute Context Precision@K: fraction of top-K chunks that contain the span.

    Measures signal-to-noise in the retrieved context — a high value means the
    retrieved chunks are densely relevant rather than mixed with irrelevant material.

    Args:
        hits: Per-rank boolean hit list from ``chunk_hits``.
        k:    Cutoff rank.

    Returns:
        Float in [0.0, 1.0]. Returns 0.0 when ``hits[:k]`` is empty.
    """
    top_k = hits[:k]
    if not top_k:
        return 0.0
    return sum(1 for h in top_k if h) / len(top_k)


def keyword_match(answer: str, keywords: list[str]) -> float:
    """Compute the fraction of expected keywords present in the generated answer.

    Performs case-insensitive substring matching — a keyword is considered
    present if it appears anywhere in the lowercased answer text.

    Args:
        answer:   The LLM-generated answer string.
        keywords: List of expected keywords from the golden set.

    Returns:
        Float in [0.0, 1.0]. Returns 0.0 when ``keywords`` is empty.
    """
    if not keywords:
        return 0.0
    text = (answer or "").lower()
    return sum(1 for kw in keywords if kw.lower() in text) / len(keywords)


async def faithfulness_score(answer: str, context_chunks: list[str], judge_generate) -> float:
    """Rate how faithfully the generated answer is supported by the retrieved context.

    Prompts a judge LLM to score the answer on a 0.0-1.0 scale where 1.0 means
    every claim in the answer is directly supported by the provided context.
    Falls back to 0.0 on any parsing error.

    Args:
        answer:         The LLM-generated answer to evaluate.
        context_chunks: List of retrieved chunk texts used as the grounding context.
        judge_generate: An async callable with the same signature as
                        ``common/gemini_client.py::generate(system_prompt,
                        user_message, ...) -> str`` — injected rather than
                        imported here so this stays a plain formula module
                        callers can unit-test with a fake judge (no real
                        Gemini call needed to test the parsing logic).

    Returns:
        Float in [0.0, 1.0] representing the faithfulness score.
    """
    system_prompt = "You are an impartial evaluator judging RAG answer faithfulness."
    prompt = (
        "Rate how faithfully the answer is supported by the context on a scale of 0.0 to 1.0.\n"
        "1.0 = every claim in the answer is directly supported by the context.\n"
        "0.0 = the answer contains claims not supported by the context.\n\n"
        f"Context:\n{chr(10).join(context_chunks)}\n\n"
        f"Answer: {answer}\n\n"
        "Respond with ONLY a float between 0.0 and 1.0."
    )
    response_text = await judge_generate(system_prompt, prompt, disable_thinking=True)
    try:
        return float(response_text.strip())
    except ValueError:
        return 0.0


def mean_faithfulness(verdicts: list[bool]) -> float:
    """Average a batch of binary LLM-judge verdicts into a [0, 1] score.

    Independent of ``faithfulness_score`` above (a continuous 0.0-1.0 judge
    score) — this is for the separate case of a judge that only returns a
    yes/no verdict per case, kept for tests/eval/test_retrieval_metrics.py
    and any future binary-verdict judge.
    """
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
