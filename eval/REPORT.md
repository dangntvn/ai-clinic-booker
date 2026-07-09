# Eval Report

**Run**: 2026-07-08, `pytest -m eval` (real Gemini `gemini-2.5-flash` + `gemini-embedding-001`, real Postgres, real Qdrant — no mocks). Full classification of every failure is in [`EVAL_FINDINGS.md`](./EVAL_FINDINGS.md).

## 1. Classic quality gate (`test_eval_gate.py` → `eval/runner.py::run_eval()`)

| Metric | Score | Threshold | Result | Classification |
|---|---|---|---|---|
| `retrieval_hit_rate@5` | 0.091 | 0.7 | **FAIL** | Thiếu data (expected — see EVAL_FINDINGS #1) |
| `retrieval_mrr` | 0.023 | 0.5 | **FAIL** | Thiếu data (expected — see EVAL_FINDINGS #1) |
| `intent_routing_accuracy` | 0.917 (12/12 = 1.0 on a clean rerun) | 0.8 | FAIL in this run, PASS on rerun | Threshold/flakiness, likely a transient Gemini 503 (see EVAL_FINDINGS #2) |
| `booking_concurrency_pass_rate` | 0.800 | 1.0 | **FAIL** | 2 real bugs found — BUG-006, BUG-007 (see EVAL_FINDINGS #3) |

## 2. DeepEval LLM-judge suite (`test_deepeval_{faq,symptom,booking}.py`, TASK-027, 9 cases)

Run in the same session as above:

| Test | Result | Classification |
|---|---|---|
| `test_faq_pricing_question_grounded` | FAIL (this run) → PASS on isolated retry | LLM-judge nondeterminism (see EVAL_FINDINGS #4) |
| `test_faq_clinic_info_question_grounded` | PASS | — |
| `test_faq_out_of_scope_question_not_fabricated` | PASS | — |
| `test_symptom_medical_guide_question_grounded` | FAIL (this run) → PASS on isolated retry | LLM-judge nondeterminism (see EVAL_FINDINGS #4) |
| `test_symptom_routes_to_real_doctor_for_covered_specialty` | FAIL (this run) → PASS on isolated retry | LLM-judge nondeterminism (see EVAL_FINDINGS #4) |
| `test_symptom_does_not_invent_doctor_for_uncovered_specialty` | PASS | — |
| `test_booking_proposes_only_real_available_slot` | PASS | — |
| `test_booking_confirms_before_create_then_creates_real_booking` | **FAIL (reproducible, 2/2)** | Real issue — data pollution from its own earlier run + BUG-006 (see EVAL_FINDINGS #5) |
| `test_booking_non_work_day_no_fabricated_slots` | PASS | — |

## Summary

- **5 real product bugs found this run**: BUG-006 (critical), BUG-007 (high), plus BUG-001/002 (carried over from TASK-026, still open), BUG-005 (carried over, still open).
- **1 eval-methodology bug found**: BUG-008 — booking golden set / DeepEval booking test pollute real DB state, making repeat runs unreliable.
- **1 confirmed data gap** (not a bug): `golden_set_rag.yaml`'s Hit-Rate/MRR metric is structurally unable to pass with the current 22-row real content — 10 of its 11 queries have no real answer in the system (TASK-026 finding, unchanged).
- **LLM-judge nondeterminism**: 3 of 9 DeepEval cases flipped from FAIL to PASS on an isolated retry with no code change — expected variance for an LLM-as-judge setup, not itself a bug, but worth keeping in mind when reading any single run's numbers.

See [`eval/EVAL_FINDINGS.md`](./EVAL_FINDINGS.md) for the full per-case detail and
[`../../../../01-docs/99-project-management/backlog/bugs/`](../../../../01-docs/99-project-management/backlog/bugs/README.md)
for the filed, fixable bug reports.
