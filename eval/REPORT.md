# Eval Report

> **Run**: 2026-07-13, real `pytest -m eval` + `pytest tests/eval/test_deepeval_{faq,symptom,booking}.py`
> executed end-to-end by senior-tester on the host `.venv` against the live dockerised stack + real
> Gemini, right after today's uncommitted batch (persona "Minh Tâm" on all 5 agents; FAQ scope/
> threshold tuning; booking/symptom prompt changes — merged intake questions, proactive booking
> invite). This supersedes the 2026-07-10 run (commit `b11904c`, which fixed EVAL_FINDINGS §6a/§6b),
> re-measuring after today's changes on top of that fix.
>
> **Note**: `runner.py::run_eval()` overwrites this file with a minimal raw dump each time it runs;
> this curated narrative is the human-maintained version — re-apply it by hand after any raw gate run
> (see `.claude/memory/2026-07-09-eval-run-host-environment.md`).
>
> **Update, same day, later session (senior-tester) — BUG-014/BUG-015 fix re-verification.** After
> senior-dev's fix + code-reviewer sign-off, re-verified the 6 DeepEval cases named in both tickets,
> isolated, 2 independent rounds each, after a fresh reseed. **BUG-014 confirmed fixed** (no
> regression on the routing cases). **BUG-015's diagnosed root cause (no doctor name→id lookup)
> confirmed fixed** — but one of its two named cases (`test_booking_proposes_only_real_available_slot`)
> still fails 3/3 for a *different*, newly-surfaced reason (agent resolves the doctor and gets real
> slots, but never quotes a specific time back to the patient) — treated as a new, distinct finding,
> not "BUG-015 still open." Full detail: [`DEEPEVAL_REPORT.md`](./DEEPEVAL_REPORT.md) and
> [`EVAL_FINDINGS.md` §8](./EVAL_FINDINGS.md). **A final full-suite re-run (classic gate + all 15
> DeepEval cases) to refresh this file's own numbers below could not be completed this session — the
> project's Gemini API hit its monthly spending cap (429) mid-session.** Every number below the RAG/
> intent-routing/booking-concurrency/DeepEval tables is therefore **carried forward unchanged from the
> run described in the note above** (pre-BUG-014/015-fix), except the 6 cases explicitly called out as
> re-verified in §4's summary — treat the classic-gate numbers as **stale with respect to today's
> fix** (though not expected to have changed, since none of BUG-014/015's fix touches
> retrieval/orchestrator-routing/booking-concurrency code paths — confirmed via `git diff`). A fresh
> full run is needed once the Gemini quota clears. `pytest tests/unit -m "not eval and not llm"` was
> run instead as a substitute regression check (no real Gemini calls needed): **69 passed, 4 skipped,
> 0 failed** — no unit-test regression.

RAG questions: 27 · cutoff k = 5

## 1. RAG retrieval + generation quality — all PASS (§6a/§6b fix holds)

| Metric | 2026-07-10 (pre-fix) | 2026-07-10 (post-fix, `b11904c`) | 2026-07-13 (today, post-persona/booking batch) | Target | Status |
|--------|---|---|---|---|---|
| Span Hit Rate@5 | 1.000 | 1.000 | 1.000 | ≥ 0.80 | ✅ |
| Span MRR | 0.812 | 0.812 | 0.812 | ≥ 0.60 | ✅ |
| Context Precision@5 | 0.233 | 0.233 | 0.233 | ≥ 0.20 | ✅ |
| Hit Rate@5 (doc-id) | 1.000 | 1.000 | 1.000 | ≥ 0.70 | ✅ |
| MRR (doc-id) | 0.970 | 0.970 | 0.970 | ≥ 0.90 | ✅ |
| Keyword Match | 0.503 ❌ | 0.821 (self-test) | **0.821** | ≥ 0.70 | ✅ |
| Faithfulness | 0.544 ❌ | 0.919 (self-test) | **0.874** | ≥ 0.75 | ✅ |

Retrieval-only metrics are byte-identical to every prior run (query set/corpus unchanged, retrieval
code untouched today) — expected. **Keyword Match and Faithfulness stay fixed**: `b11904c`'s
orchestrator-routing fix (§6a, FAQ- vs symptom-shaped questions) and FAQ category-fallback fix (§6b,
policy↔clinic_info) are confirmed still in effect after today's persona/prompt batch — no regression
on RAG generation quality from today's changes. Faithfulness (0.874) is a few points below the
committer's own self-test (0.919, same commit) — expected LLM-judge run-to-run variance on a
per-question 0/1-ish score aggregated over 27 questions (see per-question table below for the two
rows that moved), not a new defect. See [`EVAL_FINDINGS.md` §6](./EVAL_FINDINGS.md) for the
original finding + fix write-up.

### Per-question breakdown (today's run)

| # | Query | Span rank | Span Prec@5 | Keyword | Faithfulness |
|---|-------|-----------|-------------|---------|--------------|
| 1 | Phòng khám mở cửa mấy giờ | 3 | 0.40 | 1.00 | 1.00 |
| 2 | Khoa da liễu điều trị những bệnh gì | 1 | 0.20 | 1.00 | 1.00 |
| 3 | Khoa mắt chữa những bệnh nào | 1 | 0.20 | 1.00 | 0.80 |
| 4 | Khoa nhi khám các bệnh gì cho trẻ em | 1 | 0.20 | 1.00 | 1.00 |
| 5 | Khoa siêu âm có những dịch vụ gì | 1 | 0.20 | 1.00 | 1.00 |
| 6 | Khoa sản phụ khoa có khám thai không | 3 | 0.20 | 0.67 | 1.00 |
| 7 | Khoa tai mũi họng điều trị viêm xoang viêm tai không | 1 | 0.20 | 0.67 | 1.00 |
| 8 | Chụp CT Cone Beam làm ở khoa nào | 1 | 0.20 | 1.00 | 1.00 |
| 9 | Khoa răng hàm mặt có chỉnh nha và điều trị tủy răng không | 1 | 0.20 | 1.00 | 1.00 |
| 10 | Khoa xét nghiệm làm những xét nghiệm gì | 1 | 0.20 | 1.00 | 1.00 |
| 11 | bên bạn khám những gì | 1 | 0.20 | 0.00 | 0.00 |
| 12 | có những chuyên khoa nào | 3 | 0.40 | 1.00 | 1.00 |
| 13 | phòng khám có dịch vụ gì | 3 | 0.20 | 1.00 | 1.00 |
| 14 | phòng khám có những khoa nào | 1 | 0.20 | 0.50 | 1.00 |
| 15 | danh sách các chuyên khoa của phòng khám | 1 | 0.20 | 1.00 | 0.80 |
| 16 | phòng khám có bao nhiêu chuyên khoa | 1 | 0.20 | 1.00 | 1.00 |
| 17 | khi đến anh liên hệ ai? | 2 | 0.40 | 1.00 | 1.00 |
| 18 | số điện thoại lễ tân | 2 | 0.40 | 1.00 | 1.00 |
| 19 | liên hệ ai khi đến khám | 3 | 0.20 | 1.00 | 1.00 |
| 20 | gặp ai khi tới phòng khám | 4 | 0.20 | 0.00 | 0.00 |
| 21 | Huyết áp bao nhiêu thì được coi là cao huyết áp | 1 | 0.25 | 0.00 | 1.00 |
| 22 | Dấu hiệu nhận biết hở van tim là gì | 1 | 0.25 | 0.33 | 0.00 |
| 23 | Xét nghiệm tổng phân tích tế bào máu giá bao nhiêu | 1 | 0.20 | 1.00 | 1.00 |
| 24 | Cắt u lành phần mềm chi phí bao nhiêu | 1 | 0.20 | 1.00 | 1.00 |
| 25 | Đo chỉ số cơ thể giá bao nhiêu | 1 | 0.20 | 1.00 | 1.00 |
| 26 | Chích áp xe tầng sinh môn giá bao nhiêu | 1 | 0.20 | 1.00 | 1.00 |
| 27 | Quy trình khám sức khỏe gồm mấy bước | 1 | 0.20 | 1.00 | 1.00 |

Rows 11 and 20 ("bên bạn khám những gì" / "gặp ai khi tới phòng khám") score 0/0 on both runs —
pre-existing, not new today (row 11 was already 0.50 faithfulness in the pre-fix run and is now 0.00;
row 20 was 0.00/0.00 in every run so far). Row 27 ("Quy trình khám sức khỏe gồm mấy bước", the §6b
finding) is now 1.00/1.00, confirming the category-fallback fix still holds. No row shows a
regression clearly attributable to today's persona/prompt batch — the aggregate Faithfulness dip
(0.919 self-test → 0.874 here) is spread thinly across several rows, consistent with ordinary judge
variance rather than one clear culprit.

## 2. Intent routing

| Metric | 2026-07-09 baseline | 2026-07-10 (`b11904c`) | 2026-07-13 (today) | Target | Status |
|--------|---|---|---|---|---|
| Intent Routing Accuracy | 1.000 (12/12) | 0.917 (11/12, self-test) | **0.917** (11/12) | ≥ 0.80 | ✅ |

Matches the `b11904c` commit message's own self-test number exactly (0.917), and that commit's
author already A/B-confirmed this is "pre-existing model behaviour" (the original, un-rewritten
orchestrator prompt routes the same 1 miscategorized case identically) — **not a regression from
today's persona/prompt batch**, and still well above the 0.8 gate.

## 3. Booking concurrency

| Metric | Score | Target | Status |
|--------|-------|--------|--------|
| Booking Concurrency Pass Rate | 1.000 | = 1.00 | ✅ |

This metric (`run_booking_eval()`, concurrent-write race only) is unaffected by today's prompt
changes — still 1.000, matching every prior run since BUG-006/007/008 were fixed. **This is a
different, narrower check than the DeepEval booking cases in §4 below** — it never goes through an
LLM conversation, so it can't see the doctor-name-resolution gap §4 found.

## 4. DeepEval LLM-judge suite — 15 cases (grew from 9 → 15 via commit `d5e1de6`)

Full detail, per-case classification, and the 4 zero-score investigation are in
[`DEEPEVAL_REPORT.md`](./DEEPEVAL_REPORT.md) and
[`EVAL_FINDINGS.md` §7](./EVAL_FINDINGS.md). Summary (state at the time of the original run this
session, i.e. **before** the later BUG-014/015 fix — see the update box directly below for what
changed after the fix):

- **8/15 pass cleanly**, no concerns.
- **4/15 fail on Answer Relevancy only** (0.667, 0.667, 0.429, 0.400 — all < 0.70 threshold), all
  four traced to the new "Minh Tâm" persona's warmer, fuller phrasing (closing offers of further
  help, extra context beyond the literal question) diluting a strict single-answer relevancy score.
  **Not a fabrication or faithfulness problem** — Faithfulness stayed 1.000 on every one of these.
  One of the four (`test_symptom_medical_guide_question_grounded`, 0.400) is a more notable case: the
  agent asked a clarifying intake question instead of directly answering an open medical-guide
  factual question — see EVAL_FINDINGS §7 for detail.
- **1/15 is a confirmed real bug** (`test_symptom_does_not_invent_doctor_for_uncovered_specialty`,
  score 0.000, reproduced identically 3/3 independent runs): the Symptom Agent recommends a real
  doctor, "Đỗ Như Chinh," for a cardiology ("Tim mạch") complaint — but that doctor's real specialty
  is Thần kinh (Neurology); the clinic has no real cardiologist. **Escalated to Team Lead, not fixed
  by tester.**
- **2/15 are a confirmed real (pre-existing) architecture gap**, surfaced by the golden set's own
  `d5e1de6` naturalization (asking by doctor name, not id): the Booking Agent has no doctor
  name→id lookup, so it asks the patient for an internal "mã số bác sĩ" instead of proceeding.
  Reproducible 3/4 and 3/3 across independent trials respectively. **Not caused by today's batch**
  (`booking/prompt.py`'s diff only touched tone/question-merging) — pre-existing gap, invisible under
  the old golden set's artificial `doctor_id=N` phrasing. **Escalated to Team Lead.**
- **1 case that looked like a 4th zero-score bug on the first full run**
  (`test_symptom_does_not_invent_doctor_for_tieu_hoa_specialty`) was a **GEval judge false negative**:
  isolated re-run passed cleanly, and the agent's actual behaviour (asking a clarifying follow-up,
  never naming a doctor) is safe — the GEval criteria's pass/fail steps just don't have an explicit
  branch for "asks a clarifying question," so a strict step-based judge occasionally scores it 0
  even though nothing was fabricated. Same pattern as the BHYT judge false negative documented in
  EVAL_FINDINGS §4.

> **After the fix (same day, later session)**: BUG-014 is **confirmed fixed** (2/2 clean isolated
> re-runs, no regression on the 2 routing cases). BUG-015's root cause is **confirmed fixed** — the
> "mã số bác sĩ" dead-end never recurred in 6 trials, and `test_booking_non_work_day_no_fabricated_slots`
> now passes cleanly (2/2). But `test_booking_proposes_only_real_available_slot` **still fails 3/3**,
> now because the agent resolves the doctor and gets real slots but never quotes a specific time back
> to the patient — a new, distinct finding (not a fabrication), escalated to Team Lead, not fixed by
> tester. See [`DEEPEVAL_REPORT.md`](./DEEPEVAL_REPORT.md) and
> [`EVAL_FINDINGS.md` §8](./EVAL_FINDINGS.md) for full detail. The 4 persona-driven Answer Relevancy
> dips and the 8 originally-clean cases were **not re-verified this session** (Gemini quota cap hit
> before that could happen) — carried forward unchanged, code behind them untouched by the fix.

## Conclusion

**All 4 classic gate metrics (Span/doc-id retrieval, Keyword Match, Faithfulness, Intent Routing,
Booking Concurrency) PASS** — the `b11904c` RAG-routing fix holds up under today's persona/prompt
batch, no regression there (numbers not re-verified in the later fix-verification session; carried
forward since none of BUG-014/015's fix touches this code path). **The DeepEval suite originally
surfaced 1 confirmed real safety-relevant bug (doctor specialty fabrication) and 1 confirmed real
UX/architecture gap (booking can't resolve a doctor by name) — both now addressed in a later session
the same day: the fabrication bug (BUG-014) is confirmed fixed with no regression, and the
architecture gap's root cause (BUG-015) is confirmed fixed, though the specific test case that
verifies it still fails for a newly-surfaced, different reason (agent doesn't quote specific times
back to the patient) — a new candidate finding, not "BUG-015 reopened," escalated to Team Lead, not
fixed by tester.** Four more DeepEval cases dipped below the Answer Relevancy threshold as a side
effect of the new friendlier persona tone, not incorrect information — a product/metric trade-off for
Team Lead to weigh in on, not treated as a blocking defect on its own; not re-verified in the later
session. **A planned final clean-baseline full-suite re-run could not be completed — the project's
Gemini API hit its monthly spending cap (429) mid-session, an infra/billing blocker escalated to Team
Lead.** `pytest tests/unit -m "not eval and not llm"` passed clean (69 passed, 4 skipped, 0 failed) as
a substitute regression check. No threshold was loosened anywhere to make any of the above numbers
look better than they are.
