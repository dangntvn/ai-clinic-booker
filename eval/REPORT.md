# Eval Report

**Run**: 2026-07-09, real `pytest -m eval` executed end-to-end by senior-tester on the host
`.venv` against the live dockerised stack (`ai-clinic-booker-{postgres,qdrant}-1`) + real Gemini
(`gemini-2.5-flash` + `gemini-embedding-001`) — no mocks. This supersedes the 2026-07-08 run: the
real product bugs that run found (BUG-006/007/008, plus BUG-001/002/005) have since been fixed and
verified, and the stale RAG golden set was rewritten (17 grounded queries). Full per-case
classification is in [`EVAL_FINDINGS.md`](./EVAL_FINDINGS.md).

> Note: `runner.py::run_eval()` overwrites this file with a minimal 4-line dump each time it runs;
> the curated narrative below is the human-maintained version — re-apply it after any raw gate run.

Environment reproduction is documented in
[`.claude/memory/2026-07-09-eval-run-host-environment.md`](../../../../.claude/memory/2026-07-09-eval-run-host-environment.md).
Pre-run reset: `python scripts/seed_eval_fixtures.py` (wiped + reseeded to 11 doctors ids 3-13,
22 knowledge rows ids 1-22) so the numbers below start from identical real data.

## 1. Classic quality gate (`test_eval_gate.py` → `eval/runner.py::run_eval()`) — all PASS

Single clean run, `test_eval_gate` PASSED (exit 0):

| Metric | Score | Threshold | Result | Notes |
|---|---|---|---|---|
| `retrieval_hit_rate@5` (17 RAG cases) | 1.000 | 0.7 | **PASS** | Rewritten grounded golden set (EVAL_FINDINGS #1) |
| `retrieval_mrr` (17 RAG cases) | 0.971 | 0.9 | **PASS** | 16/17 hit rank #1; id 1 at rank #2 (expected, EVAL_FINDINGS #1) |
| `intent_routing_accuracy` (12 intent cases) | 1.000 | 0.8 | **PASS** | 12/12, no 503 this run (EVAL_FINDINGS #2) |
| `booking_concurrency_pass_rate` (10 booking cases) | 1.000 | 1.0 | **PASS** | BUG-006/007/008 fixed; runner self-cleans (EVAL_FINDINGS #3) |

**No threshold was changed at any point** — every number above is measured against the thresholds
already in `runner.py` (0.7 / 0.9 / 0.8 / 1.0).

## 2. DeepEval LLM-judge suite (`test_deepeval_{faq,symptom,booking}.py`, 9 cases)

Run right after the gate, same session:

| Test | Full-run result | Classification |
|---|---|---|
| `test_faq_pricing_question_grounded` | FAIL (AnswerRelevancy 0.5) → PASS on isolated re-run | LLM-judge nondeterminism (EVAL_FINDINGS #4) |
| `test_faq_clinic_info_question_grounded` | PASS | — |
| `test_faq_out_of_scope_question_not_fabricated` | FAIL (GEval 0.0) → PASS on isolated re-run | LLM-judge **false negative** — agent output verified correct & stable 4/4 (EVAL_FINDINGS #4) |
| `test_symptom_medical_guide_question_grounded` | PASS | — |
| `test_symptom_routes_to_real_doctor_for_covered_specialty` | PASS | — |
| `test_symptom_does_not_invent_doctor_for_uncovered_specialty` | PASS | — |
| `test_booking_proposes_only_real_available_slot` | PASS | Exercises `check_available_slots` — confirms BUG-006 fix |
| `test_booking_confirms_before_create_then_creates_real_booking` | PASS | Was reproducible-FAIL 2026-07-08; BUG-006/008 fix restored it |
| `test_booking_non_work_day_no_fabricated_slots` | PASS | Confirms BUG-007 fix |

**7/9 passed on the first full run; the 2 that failed both flipped to PASS when re-run in isolation
with no code change** — the LLM-judge nondeterminism signature. Note the *set* of flaky cases
shifted vs. 2026-07-08 (then: pricing + 2 symptom cases; now: pricing + out-of-scope), which is
itself evidence that any single DeepEval case can flip — the flakiness is judge-side, not tied to a
specific agent behaviour.

## Summary

- **All 4 classic gate metrics PASS**, all 9 DeepEval cases pass once judge nondeterminism is
  accounted for. This is the first fully-green real run and is the baseline this project should
  track going forward.
- **No new product bug found.** The single suspicious case (`test_faq_out_of_scope_...`, GEval 0.0)
  was investigated directly: the agent's real reply, stable across 4 runs, correctly says it has no
  BHYT information and does **not** assert a policy — the judge's failure reason quoted a sentence
  ("Phòng khám không nhận... BHYT") that never appears in the agent output, i.e. the judge
  hallucinated. Faithful agent behaviour, judge-side false negative.
- **Retry-fix (senior-dev, `common/resilience.py::build_adk_model`) status**: 4 clean intent runs
  this session (48 conversations) with zero crashes and zero 503s. Because no 503 actually occurred,
  these live runs prove **stability** but do not themselves exercise the retry path — the
  "503-once-then-success → retried" behaviour is proven by the unit test
  `tests/unit/ai_agents/test_adk_model_retry.py`, not by this run (EVAL_FINDINGS #2).
- **Reproducibility caveat**: `test_booking_confirms_before_create_...` creates a real confirmed
  booking that persists. Always run `scripts/seed_eval_fixtures.py` before an eval run (as was done
  here); the classic `run_booking_eval()` is self-cleaning but the DeepEval booking case is not.

See [`eval/EVAL_FINDINGS.md`](./EVAL_FINDINGS.md) for full per-case detail.
