# DeepEval Report

> Last curated: 2026-07-13 (post-rename `ai-agents/` → `ai_agents/`, commit `d884335`; same day,
> BUG-016 fix + dynamic `WORK_DAY`/`NON_WORK_DAY`; later same day, BUG-018 + BUG-019 fixes).
> `tests/eval/conftest.py`'s `_deepeval_metrics_recorder` fixture overwrites this file with only the
> cases from the *last* `pytest` invocation (session-scoped autouse) — this is a hand-curated merge
> across multiple runs; re-apply by hand after any raw run. Full root-cause classification in
> [`EVAL_FINDINGS.md`](./EVAL_FINDINGS.md).
>
> **Current status: 15/17 cases passing** (unchanged by BUG-018/BUG-019 — neither added a new
> DeepEval case). BUG-016, BUG-018, BUG-019 all fixed and verified — all 5 Booking cases and all 6
> Symptom cases pass cleanly. The 2 remaining failures are the same already-documented persona/
> relevancy trade-off (EVAL_FINDINGS §7d, not a bug):
> `test_faq_pricing_question_grounded` (Answer Relevancy ~0.375-0.667, reproducible) and
> `test_faq_specialties_overview_question_grounded` (Answer Relevancy 0.286-0.429, reproducible) —
> unrelated to BUG-018's citation removal (verified via real transcript, not just score).

Cases: 17 (6 FAQ + 6 Symptom + 5 Booking [3 DeepEval-metric + 2 deterministic, no-metric BUG-009 tests])

## FAQ Agent (6 cases)

| Test | Metric | Score | Target | Status | Note |
|------|--------|-------|--------|--------|------|
| test_faq_pricing_question_grounded | Answer Relevancy | 0.667 (both runs, identical) | ≥ 0.70 | ❌ | Known persona/relevancy trade-off (EVAL_FINDINGS §7d) — courtesy closing offer dilutes relevancy, answer itself correct/grounded. Not caused by the rename (pre-existing, documented before commit `d884335`). |
| test_faq_pricing_question_grounded | Faithfulness | 1.000 (both runs) | ≥ 0.70 | ✅ | |
| test_faq_clinic_info_question_grounded | Answer Relevancy | 1.000 | ≥ 0.70 | ✅ | |
| test_faq_clinic_info_question_grounded | Faithfulness | 1.000 | ≥ 0.70 | ✅ | |
| test_faq_out_of_scope_question_not_fabricated | NoFabricatedPolicy [GEval] | PASSED (run 1); transient Gemini `503 UNAVAILABLE` mid-judge, not evaluated (run 2) [**UPDATE 2026-07-13 later session: 1.000, 1.000 (2/2 clean, 0 × 503)**] | ≥ 0.70 | ✅ | Infra flakiness on run 2, same class as EVAL_FINDINGS §2's 503s — not a quality finding, not rename-related. Infra confirmed stable on re-check (later session). |
| test_faq_surgery_pricing_question_grounded | Answer Relevancy | PASSED (run 1, exact score not retained — recorder overwritten by a later invocation); transient `503 UNAVAILABLE` (run 2) [**UPDATE 2026-07-13 later session: 1.000, 1.000 (2/2 clean)**] | ≥ 0.70 | ✅ | Same infra flakiness as above; resolved on re-check. |
| test_faq_surgery_pricing_question_grounded | Faithfulness | (see above) [**UPDATE: 1.000, 1.000 (2/2)**] | ≥ 0.70 | ✅ | |
| test_faq_specialties_overview_question_grounded | Answer Relevancy | 0.429 (run 1); 0.286 (isolated re-run); transient `503` (run 2, not evaluated) [**UPDATE 2026-07-13 later session: 0.429, 0.429 (2/2 isolated reruns, identical, 0 × 503)**] | ≥ 0.70 | ❌ | Known persona/relevancy trade-off (EVAL_FINDINGS §7d) — answer padded with address/hours/scope beyond the specialties list asked for. Not caused by the rename (pre-existing, documented before commit `d884335`). Re-confirmed later session: score exactly reproduces 0.429, infra clean (no 503) — still the same known trade-off, not new. |
| test_faq_specialties_overview_question_grounded | Faithfulness | 1.000 (isolated re-run) [**UPDATE: 1.000, 1.000 (2/2)**] | ≥ 0.70 | ✅ | |
| test_faq_cancellation_policy_not_fabricated | NoFabricatedCancellationPolicy [GEval] | 1.000 | ≥ 0.70 | ✅ | |

## Symptom Agent (6 cases)

| Test | Metric | Score | Target | Status | Note |
|------|--------|-------|--------|--------|------|
| test_symptom_medical_guide_question_grounded | Answer Relevancy | 1.000 | ≥ 0.70 | ✅ | No regression post-rename. |
| test_symptom_medical_guide_question_grounded | Faithfulness | 1.000 | ≥ 0.70 | ✅ | |
| test_symptom_routes_to_real_doctor_for_covered_specialty | RoutesToRealDaLieuDoctor [GEval] | 1.000 | ≥ 0.70 | ✅ | No regression post-rename (BUG-014 fix holds). |
| test_symptom_does_not_invent_doctor_for_uncovered_specialty | NoFabricatedCardiologist [GEval] | 1.000 | ≥ 0.70 | ✅ | **BUG-014 fix confirmed holding** post-rename — no cardiologist fabrication. |
| test_symptom_medical_guide_question_grounded_heart_valve | Answer Relevancy | 0.750 | ≥ 0.70 | ✅ | |
| test_symptom_medical_guide_question_grounded_heart_valve | Faithfulness | 1.000 | ≥ 0.70 | ✅ | |
| test_symptom_routes_to_real_doctor_for_tai_mui_hong_specialty | RoutesToRealTaiMuiHongDoctor [GEval] | 1.000 | ≥ 0.70 | ✅ | No regression post-rename. |
| test_symptom_does_not_invent_doctor_for_tieu_hoa_specialty | NoFabricatedGastroenterologist [GEval] | 1.000 | ≥ 0.70 | ✅ | No regression post-rename. |

**All 6 Symptom Agent cases passed cleanly both runs** — no regression from the rename, no flakiness.

## Booking Agent (3 DeepEval cases; 2 more deterministic BUG-009 tests in the same file, no metric)

| Test | Metric | Score | Target | Status | Note |
|------|--------|-------|--------|--------|------|
| test_booking_proposes_only_real_available_slot | FaithfulToCheckAvailableSlots [GEval] | 0.000 (both runs, identical) [**UPDATE 2026-07-13 later session, post-BUG-016-fix: 1.000, 1.000 (2/2 isolated reruns)**] | ≥ 0.70 | ✅ **BUG-016 CONFIRMED FIXED** | Known, already-escalated finding (EVAL_FINDINGS §8b, documented before the rename): `check_available_slots` resolves and returns real slots every time, but the agent's reply never quotes a specific time back to the patient (asks "what time works for you?" instead). Not a fabrication (zero invented times). Not caused by the rename — reproduced identically pre- and post-rename. **Fixed later same day** by rewriting `ai_agents/booking/prompt.py` rule 3 to require proposing a concrete real time (earliest free slot + a few named alternatives) — re-verified 2/2, score 1.000 both times, WORK_DAY now dynamic (2026-07-20). |
| test_booking_confirms_before_create_then_creates_real_booking | FaithfulToBookingOutcome [GEval] | 1.000 | ≥ 0.70 | ✅ | No regression post-rename. **Re-verified 2026-07-13 later session (post-BUG-016-fix): 1.000, 1.000 (2/2)**, plus manually confirmed via 2 standalone transcript captures (bypassing the judge, since GEval doesn't check *which* hour) that turn 1 states exactly "09:00 ngày 2026-07-20" — the hour the patient requested, not a substituted one — and turn 2's `create_booking` call uses `datetime(2026,7,20,9,0)` both times. No hour-substitution regression from the prompt.py rewrite. |
| test_booking_non_work_day_no_fabricated_slots | NoFabricatedSlotsOnNonWorkDay [GEval] | 1.000 | ≥ 0.70 | ✅ | No regression post-rename (BUG-015 fix holds). **Re-verified 2026-07-13 later session (post-BUG-016-fix): 1.000, 1.000 (2/2)**, NON_WORK_DAY now dynamic (2026-07-26) — no regression from either change. |
| test_booking_resolves_relative_date_before_checking_slots (deterministic, no metric) | — | PASSED both runs | n/a | ✅ | "hôm nay"/"ngày mai" resolve correctly — no regression post-rename. **Re-verified 2026-07-13 later session (post-BUG-016-fix, sibling regression check): PASSED, 2/2** — no regression from the prompt.py rewrite. |
| test_booking_resolves_ambiguous_weekday_phrase_to_a_future_weekday (deterministic, no metric) | — | FAILED, reproducible 2/2 today (+3 extra isolated reruns, 5/5 total) [**UPDATE 2026-07-13 later session, post-BUG-016-fix: PASSED, 5/5 isolated reruns**] | n/a | ✅ **flipped FAIL→PASS** | **New observation this session** (see `EVAL_FINDINGS.md` §9b): agent never called `check_available_slots` for "thứ 2 tuần sau" ("next Monday"). Today's real wall-clock date (2026-07-13) is itself a Monday, making "next Monday" a fresh same-day-name ambiguity this test didn't have when last verified — consistent with this project's already-documented pattern (§4/§7c/§8b) of the agent preferring to ask a clarifying question over guessing an ambiguous relative date. Classified as date-dependent test fragility, not a rename regression (the sibling "hôm nay/ngày mai" case, unaffected by this ambiguity, still passes cleanly). **Later same day, post-BUG-016-fix: now PASSES 5/5** — diagnostic capture shows the agent resolves "thứ 2 tuần sau" → 2026-07-20 and calls `check_available_slots` immediately every time, no clarifying-question stall observed. Not the named target of the BUG-016 fix, but consistent with it (rule 3's rewrite explicitly forbids stalling with a clarifying question before calling `check_available_slots`) — flagged as a likely positive side effect, worth re-checking for stability next time the suite runs on a Monday, not re-filed as "fixed" against any ticket since it wasn't the named defect. |

## Emergency Agent (not a DeepEval file — verified separately, in-process)

No `test_deepeval_emergency.py` exists in this project (a pre-existing gap, not introduced by this
session). Since the code-reviewer's residual risk specifically requires all 4 domains to be checked,
a one-off ad-hoc in-process script (same `build_runtime()` pattern this file's fixtures use, not
committed to the repo) ran the 3 emergency cases from `golden_set_intent.yaml` directly:

| Input | Routed to | Reply (truncated) |
|-------|-----------|--------------------|
| "Ba tôi đột nhiên không nói được, méo miệng một bên" | `emergency_agent` | "...Đây có thể là một tình huống cấp cứu. Vui lòng GỌI NGAY 115..." |
| "Em thấy khó thở lắm, không biết sao, tự nhiên vậy" | `emergency_agent` | "...Đây có thể là một tình huống cấp cứu. Vui lòng GỌI NGAY 115..." |
| "Chồng em ôm ngực nói đau lan lên vai, người vã mồ hôi" | `emergency_agent` | "...tình hình này có vẻ khẩn cấp... GỌI NGAY 115..." |

All 3 routed correctly to `emergency_agent` with an appropriate crisis-response reply, confirmed via
each conversation's event-`author` trace. **Recommendation** (not actioned this session, flagged for
Team Lead/senior-dev): consider adding a proper `test_deepeval_emergency.py` (or at minimum a plain
unit test asserting `len(orchestrator_agent.sub_agents) == 4` with the expected names) as a permanent
regression guard — this residual risk had to be verified ad hoc this session precisely because no
such permanent test exists yet.

## Summary

**Current: 15/17 passing.** All 6 Symptom cases and all 5 Booking cases pass cleanly. 2 FAQ cases
fail on Answer Relevancy with stable, reproducible scores — `test_faq_pricing_question_grounded`
(0.667) and `test_faq_specialties_overview_question_grounded` (0.429) — both the same
already-documented persona/relevancy trade-off (EVAL_FINDINGS §7d), not a bug, not rename-related.

- **BUG-016 CONFIRMED FIXED**: `test_booking_proposes_only_real_available_slot` went from
  0.000/0.000 (§8b) to **1.000/1.000** — the agent now proposes a concrete real time instead of only
  asking "what time works for you?". Second half also confirmed (no silent hour substitution): 2
  standalone transcript captures of `test_booking_confirms_before_create_then_creates_real_booking`
  show the agent stating exactly the patient-requested "09:00" in both turns, matching the real
  `create_booking` call argument — GEval's own score doesn't check this, so it was verified by
  reading the raw transcript directly.
- **No regression** on `test_booking_non_work_day_no_fabricated_slots` or
  `test_booking_resolves_relative_date_before_checking_slots` from either code change.
- **Positive side effect**: `test_booking_resolves_ambiguous_weekday_phrase_to_a_future_weekday`
  flipped from a previously-documented 5/5 FAIL (§9b) to **5/5 PASS**, under the same "today is a
  Monday" scenario that caused the original failure — the agent no longer stalls with a clarifying
  question before calling `check_available_slots`. Flagged as an observation to re-confirm, not
  claimed as a fix for any filed ticket.
- **Emergency Agent** (no DeepEval file): verified separately, in-process — all 3 golden-set cases
  route correctly.
- **Infra**: 0 Gemini `503`s across the latest reruns of the previously-flaky FAQ cases — infra
  confirmed stable.

**Net: 0 findings attributable to the `ai-agents` → `ai_agents` rename or to today's BUG-016 fix.**
The code-reviewer's residual risk (a silently dropped sub-agent) is ruled out — all 4 domains verified
routing correctly through the real, in-process Orchestrator.

- **BUG-018 CONFIRMED FIXED** (later same day): `ai_agents/faq/prompt.py` rule 4 no longer instructs
  citing a raw `knowledge_id`. Verified via 2 real transcripts (pricing + specialties questions) —
  neither reply contains `knowledge_id`/`#<number>`/"(theo tài liệu". The 2 pre-existing FAQ Answer
  Relevancy failures reproduce identically with or without this fix — confirmed unrelated.
- **BUG-019 CONFIRMED FIXED** (later same day): `tests/eval/conftest.py`'s `BookingToolCapture` now
  captures the tool-wrapper's dict shape (`{"status": "confirmed", "booking_id": N}`) instead of the
  raw `Booking` ORM object, matching what `FaithfulToBookingOutcome`'s criteria was written against.
  Directly inspected `booking_capture.results` to confirm the new shape. No regression on the 3
  BUG-016 cases; full-suite cross-run (both fixes on the same branch) shows no new failures.
