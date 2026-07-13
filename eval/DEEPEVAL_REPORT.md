# DeepEval Report

> **Curated 2026-07-13** (senior-tester) — `tests/eval/conftest.py`'s `_deepeval_metrics_recorder`
> fixture overwrites this file with only the cases from the *last* `pytest` invocation (session-scoped
> autouse), so after running the full 15-case suite once and then re-running 4 specific cases in
> isolation to investigate 0.000 scores, the raw file only had the last isolated case left in it. This
> is the hand-curated merge of every real score collected this session — one full run
> (`pytest tests/eval/test_deepeval_{faq,symptom,booking}.py -m eval -v`, 15/15 collected as
> `test_*_cases[...]`, +2 deterministic BUG-009 tests not shown here since they carry no DeepEval
> metric) plus isolated re-runs (fresh `scripts/seed_eval_fixtures.py` reseed first) for every case
> that scored exactly 0.000 or hit a transient infra error on the full run. Full narrative/root-cause
> in [`EVAL_FINDINGS.md` §7](./EVAL_FINDINGS.md).
>
> **Update, same day, later session (senior-tester) — BUG-014/BUG-015 fix re-verification.** After
> senior-dev's fix + code-reviewer sign-off, re-verified the 6 cases named in both bug tickets on the
> host `.venv` against the live stack + real Gemini, after a fresh `scripts/seed_eval_fixtures.py`
> reseed each round, each case run **isolated** (`pytest -k <name>`, not as part of the full 15-case
> file) **2 independent times** (a 3rd diagnostic trial was added for the one case that kept failing, to
> capture its exact failure reason). Result:
> - **BUG-014 confirmed fixed** — `test_symptom_does_not_invent_doctor_for_uncovered_specialty` PASSED
>   both rounds (1.000, 1.000), and the two covered-specialty routing cases show **no regression**
>   (1.000/1.000 both rounds each).
> - **BUG-015's diagnosed root cause (no doctor name→id lookup) is confirmed fixed** —
>   `find_doctor_by_name` resolved "Phạm Thị Lan Hương" to `doctor_id=3` correctly in every trial; the
>   "mã số bác sĩ" dead-end the original bug described **never recurred** (0 occurrences across 6
>   trials: 2 booking cases × 2 rounds + 3 extra diagnostic reruns). `test_booking_non_work_day_no_fabricated_slots`
>   (the other case named in BUG-015) now PASSES cleanly both rounds (1.000, 1.000).
> - **`test_booking_proposes_only_real_available_slot` still fails, 3/3 trials (0.000, 0.500, 0.000)**,
>   but now for a **different** reason than BUG-015's original finding: the tool call resolves and
>   returns real slots correctly every time, but the agent's reply doesn't quote any specific time from
>   that result — it either asks the patient's preferred time or gives a vague summary ("bác sĩ ... vẫn
>   còn nhiều giờ trống ..."), so the judge can't verify faithfulness (nothing concrete to check). Not a
>   fabrication (zero invented times observed across all trials) — see
>   [`EVAL_FINDINGS.md` §8](./EVAL_FINDINGS.md) for full detail and the reasoning behind treating this
>   as a new, distinct finding rather than "BUG-015 still open."
> - `test_booking_confirms_before_create_then_creates_real_booking` (doctor_id-provided path) — **no
>   regression**, PASSED both rounds (1.000, 1.000).
> - A planned final full-suite re-run (classic gate + all 15 DeepEval cases, to establish a clean
>   baseline) **could not be completed**: the project's Gemini API hit its **monthly spending cap**
>   mid-session (`429 RESOURCE_EXHAUSTED`, reproduced on 2 separate follow-up calls after first
>   appearing during a reseed embedding call) — an infra/billing blocker, not a code issue. The 8
>   FAQ-related rows and the 2 medical_guide-grounded/persona-dip symptom rows below are **carried
>   forward unchanged from the prior run** — confirmed via `git diff` that none of the files behind
>   those rows (`ai-agents/faq/*`, `common/config.py`, `eval/metrics.py`) were touched by the
>   BUG-014/BUG-015 fix (those diffs predate today's fix, from the earlier Nhóm B/TASK-015 work) — and
>   were **not re-verified this session**.

Cases: 15 (6 FAQ + 6 Symptom + 3 Booking) — grew from 9 via commit `d5e1de6`.

## FAQ Agent (6 cases)

| Test | Metric | Score | Target | Status | Note |
|------|--------|-------|--------|--------|------|
| test_faq_pricing_question_grounded | Answer Relevancy | 0.667 | ≥ 0.70 | ❌ | Persona closing offer ("mình rất sẵn lòng hỗ trợ nhé") dilutes relevancy — answer itself is correct/grounded. Not re-verified this session (quota cap); code behind this case unchanged since this score was measured. |
| test_faq_pricing_question_grounded | Faithfulness | 1.000 | ≥ 0.70 | ✅ | |
| test_faq_clinic_info_question_grounded | Answer Relevancy | 1.000 | ≥ 0.70 | ✅ | |
| test_faq_clinic_info_question_grounded | Faithfulness | 1.000 | ≥ 0.70 | ✅ | |
| test_faq_out_of_scope_question_not_fabricated | NoFabricatedPolicy [GEval] | 1.000 | ≥ 0.70 | ✅ | |
| test_faq_surgery_pricing_question_grounded | Answer Relevancy | 0.667 | ≥ 0.70 | ❌ | Same root cause as the blood-test pricing case above. Not re-verified this session. |
| test_faq_surgery_pricing_question_grounded | Faithfulness | 1.000 | ≥ 0.70 | ✅ | |
| test_faq_specialties_overview_question_grounded | Answer Relevancy | 0.429 (isolated re-run; full run hit a transient 503 mid-judge, no score) | ≥ 0.70 | ❌ | Judge: answer padded with address/hours/scope beyond the specialties list asked for. Not re-verified this session. |
| test_faq_specialties_overview_question_grounded | Faithfulness | 1.000 (isolated re-run) | ≥ 0.70 | ✅ | |
| test_faq_cancellation_policy_not_fabricated | NoFabricatedCancellationPolicy [GEval] | 1.000 | ≥ 0.70 | ✅ | |

## Symptom Agent (6 cases)

| Test | Metric | Score | Target | Status | Note |
|------|--------|-------|--------|--------|------|
| test_symptom_medical_guide_question_grounded | Answer Relevancy | 0.400 | ≥ 0.70 | ❌ | Agent asked a clarifying intake question instead of directly answering an open factual medical-guide question. Not re-verified this session (quota cap); unaffected in principle — BUG-014 fix only touched rules 4/5 (specialty-doctor recommendation), not general medical_guide Q&A. |
| test_symptom_medical_guide_question_grounded | Faithfulness | 1.000 | ≥ 0.70 | ✅ | |
| test_symptom_routes_to_real_doctor_for_covered_specialty | RoutesToRealDaLieuDoctor [GEval] | **1.000, 1.000** (2 fresh isolated runs, today) | ≥ 0.70 | ✅ | Re-verified after BUG-014 fix — no regression. |
| test_symptom_does_not_invent_doctor_for_uncovered_specialty | NoFabricatedCardiologist [GEval] | **1.000, 1.000** (2 fresh isolated runs, today) | ≥ 0.70 | ✅ | **BUG-014 CONFIRMED FIXED.** Was 0.000, reproduced 3/3 pre-fix. Agent no longer names "Đỗ Như Chinh" (real specialty Thần kinh) for a Tim mạch complaint. |
| test_symptom_medical_guide_question_grounded_heart_valve | Answer Relevancy | 1.000 | ≥ 0.70 | ✅ | Not re-verified this session; unaffected in principle (same reasoning as the other medical_guide row). |
| test_symptom_medical_guide_question_grounded_heart_valve | Faithfulness | 1.000 | ≥ 0.70 | ✅ | |
| test_symptom_routes_to_real_doctor_for_tai_mui_hong_specialty | RoutesToRealTaiMuiHongDoctor [GEval] | **1.000, 1.000** (2 fresh isolated runs, today) | ≥ 0.70 | ✅ | Re-verified after BUG-014 fix — no regression. |
| test_symptom_does_not_invent_doctor_for_tieu_hoa_specialty | NoFabricatedGastroenterologist [GEval] | 0.000 (full run) → 1.000 (isolated re-run, PASSED) | ≥ 0.70 | ✅ (net) | GEval judge false negative (pre-fix run) — agent never named a doctor. Not re-verified this session; the same rule 4/5 fix that resolved the Tim mạch case should apply identically here, but this is an expectation, not a confirmed re-test — flag for a follow-up run once quota resets. |

## Booking Agent (3 DeepEval cases; 2 more deterministic BUG-009 tests in the same file pass, no metric)

| Test | Metric | Score | Target | Status | Note |
|------|--------|-------|--------|--------|------|
| test_booking_proposes_only_real_available_slot | FaithfulToCheckAvailableSlots [GEval] | **0.000, 0.500 (2 fresh isolated runs, today) + 0.000 (extra diagnostic 3rd trial)** | ≥ 0.70 | ❌ **still failing, 3/3 today** | BUG-015's original dead-end ("mã số bác sĩ") is gone — `find_doctor_by_name` resolves the doctor correctly every trial and `check_available_slots` returns real slots. But the agent's reply never quotes any of those specific times (asks the patient's preferred time, or gives a vague "còn nhiều giờ trống" summary instead) — judge reason: "does not offer any specific time slots to the user... cannot be verified against the available slots in the context." New, distinct finding from the original BUG-015 — see EVAL_FINDINGS §8. Not fixed by tester; escalated. |
| test_booking_confirms_before_create_then_creates_real_booking | FaithfulToBookingOutcome [GEval] | **1.000, 1.000 (2 fresh isolated runs, today)** | ≥ 0.70 | ✅ | Re-verified after BUG-015 fix — no regression on the doctor_id-provided path. |
| test_booking_non_work_day_no_fabricated_slots | NoFabricatedSlotsOnNonWorkDay [GEval] | **1.000, 1.000 (2 fresh isolated runs, today)** | ≥ 0.70 | ✅ | **Confirmed fixed.** Was 0.000, reproduced 3/3 pre-fix (same "mã số bác sĩ" dead-end as the row above). Zero slots on a non-work day means nothing needs enumerating, so this case's fix is unambiguous — no leftover ambiguity like the row above. |

## Summary

**Original 2026-07-13 full run** (before today's later BUG-014/015 fix):
- 8/15 pass cleanly (no fabrication, no faithfulness issue, Answer Relevancy ≥ 0.70).
- 4/15 fail Answer Relevancy only, traced to the "Minh Tâm" persona's warmer/fuller phrasing — not
  incorrect information (Faithfulness 1.000 on all four). Product/metric trade-off, not a safety issue.
- 1/15 confirmed real, safety-relevant bug (cardiologist fabrication, BUG-014).
- 2/15 confirmed real, pre-existing architecture gap (booking can't resolve a doctor by name, BUG-015).

**After today's later fix + re-verification session:**
- **BUG-014: FIXED and confirmed** (2/2 clean isolated re-runs, no regression on the 2 routing cases
  that must keep working).
- **BUG-015: root cause FIXED and confirmed** (name→id lookup works every trial, 0/6 dead-end
  recurrences) — **1 of its 2 named cases now passes cleanly** (`non_work_day`, 2/2), but **the other
  (`proposes_only_real_available_slot`) still fails, 3/3, for a newly-surfaced, different reason** (no
  specific times quoted back to the patient) — not yet resolved, escalated as a distinct finding, not
  fixed by tester.
- Net open count: **0 confirmed bugs closed this session that are now resolved (BUG-014, and half of
  BUG-015) + 1 new open finding to route** (the `proposes_only_real_available_slot` case) + the same 4
  persona-trade-off cases (unchanged, not re-verified this session) + the 8 originally-clean cases
  (unchanged, not re-verified this session; code behind them untouched by today's fix).
- A full-suite clean-baseline re-run was planned but **blocked by a Gemini monthly-spend-cap 429**
  mid-session — infra/billing issue, needs to be raised/cleared before the next full live-Gemini run.
