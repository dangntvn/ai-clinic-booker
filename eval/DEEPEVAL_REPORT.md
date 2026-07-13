# DeepEval Report

> **CURRENT STATUS (2026-07-13, latest): 15/17 cases passing.** BUG-016 fixed and verified
> (`test_booking_proposes_only_real_available_slot` now 1.000/1.000, was 0.000/0.000) — all 5
> Booking cases and all 6 Symptom cases now pass cleanly. Remaining 2 known failures are both the
> same already-documented persona/relevancy trade-off (§7d, not a bug, not caused by today's fix):
> `test_faq_pricing_question_grounded` (Answer Relevancy 0.667) and
> `test_faq_specialties_overview_question_grounded` (Answer Relevancy 0.429). Full detail in the
> "Summary — 2026-07-13 (later session)" section near the bottom of this file.

> **Curated 2026-07-13 (later session, senior-tester) — BUG-016 fix + dynamic WORK_DAY/NON_WORK_DAY
> verification.** Same overwrite gotcha as the note below (`_deepeval_metrics_recorder` is
> session-scoped and this session ran many separate isolated `pytest -k <name>` invocations, each
> reseeding first per Team Lead's request) — this is the hand-curated merge of all of today's later
> re-runs into the rows below. Scope: **only** the Booking rows + 3 named FAQ rows were re-run this
> session (Team Lead explicitly asked NOT to re-run the other cases, which stay carried forward
> unchanged from the TASK-030 run below). Two changes under verification:
> 1. `tests/eval/test_deepeval_booking.py`: `WORK_DAY`/`NON_WORK_DAY` changed from hardcoded absolute
>    dates to dynamically computed ("next Monday ≥7 days out" / the Sunday of that week), fixing the
>    staleness this file's own 2026-07-13 (TASK-030) note flagged. Today: WORK_DAY=2026-07-20,
>    NON_WORK_DAY=2026-07-26.
> 2. `ai_agents/booking/prompt.py`: BUG-016 fix — the agent must now proactively state a concrete real
>    time when slots are free (fixing the exact gap `EVAL_FINDINGS.md` §8b flagged: agent used to only
>    ask "what time works for you?" without ever naming a real slot), must not silently substitute a
>    different hour than the one the patient requested, and must call `check_available_slots`
>    immediately when asked about free slots rather than asking for name/phone first.
>
> **Results (all re-run isolated, reseeded before each run):**
> - `test_booking_proposes_only_real_available_slot`: **1.000, 1.000** (2/2) — was 0.000/0.000 before
>   the fix (§8b). **BUG-016's core defect confirmed fixed.**
> - `test_booking_confirms_before_create_then_creates_real_booking`: **1.000, 1.000** (2/2) via
>   pytest/GEval — but GEval's criteria only checks the *outcome* is reported faithfully, not *which*
>   hour, so this alone doesn't prove the "don't silently change the customer's requested hour" half of
>   BUG-016. Manually verified with 2 additional standalone (non-judge) transcript captures: turn 1
>   states "Thời gian: 09:00 ngày 2026-07-20" (exactly the hour the patient asked for, matching
>   `check_available_slots`'s real returned list) both times, and turn 2's `create_booking` call uses
>   `datetime(2026, 7, 20, 9, 0)` — **no hour substitution observed in either run.**
> - `test_booking_non_work_day_no_fabricated_slots`: **1.000, 1.000** (2/2) — no regression.
> - `test_booking_resolves_relative_date_before_checking_slots` (sibling regression check, no metric):
>   **PASSED, 2/2** — no regression from the prompt.py change.
> - `test_booking_resolves_ambiguous_weekday_phrase_to_a_future_weekday` (no metric): **PASSED, 5/5**
>   — flipped from the 5/5 FAIL documented in §9b (same scenario: today is a Monday, phrase asks for
>   "next Monday"). Diagnostic capture confirms the agent now resolves "thứ 2 tuần sau" → 2026-07-20 and
>   calls `check_available_slots` immediately every time. Not the named target of the fix, but
>   consistent with it: §9b's failure mode was the agent stalling with a clarifying question instead of
>   resolving the date and calling the tool — rule 3's rewrite explicitly forbids that stalling pattern
>   now. Flagged as a positive side effect, not re-filed as "fixed" against any ticket since it wasn't
>   the named defect — worth re-checking for continued stability next time the suite runs on a Monday.
> - 3 Group-B FAQ cases (`test_faq_out_of_scope_question_not_fabricated`,
>   `test_faq_surgery_pricing_question_grounded`, `test_faq_specialties_overview_question_grounded`) —
>   re-run only to check whether the Gemini `503` infra flakiness noted in the TASK-030 run below had
>   cleared: **0/2 503s this session** (infra now stable). `test_faq_specialties_overview_question_grounded`
>   still fails Answer Relevancy at **0.429, 0.429** (2/2, identical) — exactly matches the TASK-030
>   run's 0.429 below; confirmed still the known persona/relevancy trade-off (§7d/§9c), not new, not
>   infra.
>
> Full narrative in `.claude/memory/` (this session) and `EVAL_FINDINGS.md` §8b/§9b (superseded
> findings) — **not** re-narrated as a new EVAL_FINDINGS section since both are fix-confirmations of
> already-filed findings, not new findings themselves (the one exception, the ambiguous-weekday
> flip-to-pass, is noted as a §9b update, not a new numbered section).

> **Curated 2026-07-13 (senior-tester, TASK-030 Group A verification)** — `tests/eval/conftest.py`'s
> `_deepeval_metrics_recorder` fixture overwrites this file with only the cases from the *last*
> `pytest` invocation (session-scoped autouse), so after running the full 17-case suite **twice**
> today (fresh `scripts/seed_eval_fixtures.py` reseed before each), the raw file only had the second
> run's data. This is the hand-curated merge of both runs' real scores. Context: this is the
> post-rename (`ai-agents/` → `ai_agents/`, commit `d884335`, branch
> `chore/TASK-030-readme-portfolio-polish`) verification run — see `eval/REPORT.md`'s header for the
> full rationale (code-reviewer's residual risk about `_load_sub_agents()`) and the container-
> staleness nuance. Both runs executed **fully in-process** via `app.runtime.build_runtime()` (see
> `tests/eval/conftest.py::run_conversation()`) — no shared-container dependency, so every score below
> genuinely reflects commit `d884335`'s `ai_agents` package. Cases grew from 9 to **17** via
> commit `d5e1de6`/TASK-029 (the previous curated report on `main` at commit `ad1f601` said "15" —
> that count excluded the 2 deterministic BUG-009 tests that carry no DeepEval metric; this file now
> states the full pytest-collected count).
>
> Full narrative/root-cause classification in [`EVAL_FINDINGS.md` §7d/§8b/§9](./EVAL_FINDINGS.md).

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

## Summary (SUPERSEDED — see "Summary — 2026-07-13 (later session)" below for current status)

> ⚠️ The numbers below (13/17, 11/17) are a **historical snapshot from BEFORE today's BUG-016 fix**,
> kept for audit trail only. They are NOT the current state. `test_booking_proposes_only_real_available_slot`
> (the case behind most of these "failures") is now **1.000/1.000** — see the later section below.

**Cases: 17.** Run 1: 13/17 passed. Run 2: 11/17 passed (3 of the 6 "failures" were a transient
Gemini `503 UNAVAILABLE` mid-judge, not a real evaluation — infra flakiness, not a quality finding).

- **All 6 Symptom Agent cases**: clean pass both runs, no flakiness, no regression — BUG-014's fix
  (no cardiologist fabrication) confirmed still holding post-rename.
- **2 of 3 Booking DeepEval cases + 1 of 2 deterministic Booking tests**: clean pass both runs, no
  regression — BUG-015's fix (doctor name→id lookup) confirmed still holding post-rename.
- **1 Booking DeepEval case** (`test_booking_proposes_only_real_available_slot`) and **1 deterministic
  Booking test** (`test_booking_resolves_ambiguous_weekday_phrase_to_a_future_weekday`): fail
  reproducibly (2/2 today). Both are explainable without invoking the rename: the first is an
  already-documented, already-escalated finding from before the rename existed (EVAL_FINDINGS §8b);
  the second is newly observed but attributable to today's specific calendar date creating a fresh
  phrase ambiguity (EVAL_FINDINGS §9), not to any code change.
- **2 FAQ cases** (`test_faq_pricing_question_grounded`, `test_faq_specialties_overview_question_grounded`):
  fail on Answer Relevancy with real, stable scores (0.667 and 0.429/0.286 respectively) — both are
  the same already-documented persona/relevancy trade-off from EVAL_FINDINGS §7d, unchanged by the
  rename.
- **3 FAQ cases** hit a transient Gemini `503` on run 2 only (passed cleanly on run 1) — infra
  flakiness, not a code or rename issue.
- **Emergency Agent** (no DeepEval file): verified separately, in-process, all 3 golden-set cases
  route correctly.

**Net: 0 findings attributable to the `ai-agents` → `ai_agents` rename.** Every failure this session
either reproduces an already-documented pre-rename finding, is explainable by today's specific
calendar date, or is transient Gemini infra flakiness. The code-reviewer's residual risk (a silently
dropped sub-agent) is ruled out — all 4 domains verified routing correctly through the real,
in-process Orchestrator built from commit `d884335`.

## Summary — 2026-07-13 (later session): BUG-016 fix + dynamic WORK_DAY/NON_WORK_DAY verification

**Scope: 5 Booking cases + 3 named FAQ cases only** (Team Lead explicitly scoped this session; all
other cases above are carried forward unchanged, not re-run today). Every named case re-run **at
least 2 independent times, reseeded before each run** (the ambiguous-weekday case ran 5 times to
directly compare against its previously-documented 5/5-fail baseline).

- **BUG-016 CONFIRMED FIXED**: `test_booking_proposes_only_real_available_slot` flipped from
  0.000/0.000 (§8b) to **1.000/1.000**. The agent now proposes a concrete real time instead of only
  asking "what time works for you?".
- **BUG-016's second half also confirmed** (no silent hour substitution): 2 standalone transcript
  captures of `test_booking_confirms_before_create_then_creates_real_booking` show the agent stating
  exactly the patient-requested "09:00" in both turns, matching the real `create_booking` call
  argument — GEval's own score (1.000/1.000) doesn't check this, so this was verified by reading the
  raw transcript directly, not just the metric.
- **No regression** on `test_booking_non_work_day_no_fabricated_slots` (1.000/1.000) or
  `test_booking_resolves_relative_date_before_checking_slots` (2/2 PASS) from either code change.
- **Notable positive side effect, not a regression**: `test_booking_resolves_ambiguous_weekday_phrase_to_a_future_weekday`
  flipped from the previously-documented 5/5 FAIL (§9b) to **5/5 PASS** today, under the exact same
  "today is a Monday" scenario that caused the original failure. Root cause understood (agent no
  longer stalls with a clarifying question before calling `check_available_slots`, per the BUG-016
  prompt rewrite) — flagged as an observation to re-confirm next time, not claimed as a fix for any
  filed ticket.
- **Group B infra check**: 0 × Gemini `503` across 2 full reruns of the 3 previously-flaky FAQ cases —
  infra confirmed stable. `test_faq_specialties_overview_question_grounded`'s Answer Relevancy failure
  (0.429/0.429) exactly reproduces the prior documented score — re-confirmed as the known persona
  trade-off (§7d/§9c), not new, not infra.

**Net for this session: BUG-016 closed with direct transcript evidence (not just metric scores); 0
regressions found in the re-run scope; 1 previously-documented flaky/failing case
(ambiguous-weekday) now passes consistently as an apparent side effect of the same fix, not yet
re-classified as permanently fixed pending a future re-check.**
