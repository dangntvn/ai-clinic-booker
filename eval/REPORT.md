# Eval Report

> `runner.py::run_eval()` overwrites this file with a minimal raw dump each time it runs; this
> curated version is the human-maintained one — re-apply it by hand after any raw gate run (see
> `.claude/memory/2026-07-09-eval-run-host-environment.md`). Last curated: 2026-07-13 (post-rename
> `ai-agents/` → `ai_agents/`, commit `d884335`).

RAG questions: 27 · cutoff k = 5

## 1. RAG retrieval + generation quality

| Metric | 2026-07-09 baseline | 2026-07-13 (today, post-rename) | Target | Status |
|--------|---|---|---|---|
| Span Hit Rate@5 | — | 1.000 | ≥ 0.80 | ✅ |
| Span MRR | — | 0.812 | ≥ 0.60 | ✅ |
| Context Precision@5 | — | 0.233 | ≥ 0.20 | ✅ |
| Hit Rate@5 (doc-id) | 1.000 | 1.000 | ≥ 0.70 | ✅ |
| MRR (doc-id) | 0.971 | 0.970 | ≥ 0.90 | ✅ |
| Keyword Match | — | 0.802 | ≥ 0.70 | ✅ |
| Faithfulness | — | 0.904 | ≥ 0.75 | ✅ |

Doc-id Hit Rate@5/MRR and the span-level metrics are computed via a **direct Qdrant query**
(in-process, `dal/qdrant_client.search`) — not container-dependent, valid and comparable to the
2026-07-09 baseline. **No regression** (doc-id MRR 0.970 vs 0.971 baseline is rounding noise, not a
drop). Keyword Match/Faithfulness are generated via the real conversation HTTP API against the shared
`app` container, which was still running pre-rename code at the time of this run — these numbers PASS
comfortably but aren't evidence about commit `d884335` specifically (need re-measuring once that
container is rebuilt from this branch, or after merge to `main`).

### Per-question breakdown

| # | Query | Span rank | Span Prec@5 | Keyword | Faithfulness |
|---|-------|-----------|-------------|---------|--------------|
| 1 | Phòng khám mở cửa mấy giờ | 3 | 0.40 | 1.00 | 1.00 |
| 2 | Khoa da liễu điều trị những bệnh gì | 1 | 0.20 | 1.00 | 1.00 |
| 3 | Khoa mắt chữa những bệnh nào | 1 | 0.20 | 1.00 | 1.00 |
| 4 | Khoa nhi khám các bệnh gì cho trẻ em | 1 | 0.20 | 1.00 | 1.00 |
| 5 | Khoa siêu âm có những dịch vụ gì | 1 | 0.20 | 1.00 | 1.00 |
| 6 | Khoa sản phụ khoa có khám thai không | 3 | 0.20 | 1.00 | 1.00 |
| 7 | Khoa tai mũi họng điều trị viêm xoang viêm tai không | 1 | 0.20 | 0.67 | 1.00 |
| 8 | Chụp CT Cone Beam làm ở khoa nào | 1 | 0.20 | 1.00 | 1.00 |
| 9 | Khoa răng hàm mặt có chỉnh nha và điều trị tủy răng không | 1 | 0.20 | 1.00 | 1.00 |
| 10 | Khoa xét nghiệm làm những xét nghiệm gì | 1 | 0.20 | 1.00 | 1.00 |
| 11 | bên bạn khám những gì | 1 | 0.20 | 0.00 | 0.50 |
| 12 | có những chuyên khoa nào | 3 | 0.40 | 1.00 | 0.90 |
| 13 | phòng khám có dịch vụ gì | 3 | 0.20 | 1.00 | 1.00 |
| 14 | phòng khám có những khoa nào | 1 | 0.20 | 1.00 | 1.00 |
| 15 | danh sách các chuyên khoa của phòng khám | 1 | 0.20 | 1.00 | 1.00 |
| 16 | phòng khám có bao nhiêu chuyên khoa | 1 | 0.20 | 1.00 | 1.00 |
| 17 | khi đến anh liên hệ ai? | 2 | 0.40 | 0.00 | 0.00 |
| 18 | số điện thoại lễ tân | 2 | 0.40 | 1.00 | 1.00 |
| 19 | liên hệ ai khi đến khám | 3 | 0.20 | 1.00 | 1.00 |
| 20 | gặp ai khi tới phòng khám | 4 | 0.20 | 0.00 | 0.00 |
| 21 | Huyết áp bao nhiêu thì được coi là cao huyết áp | 1 | 0.25 | 0.00 | 1.00 |
| 22 | Dấu hiệu nhận biết hở van tim là gì | 1 | 0.25 | 0.00 | 1.00 |
| 23 | Xét nghiệm tổng phân tích tế bào máu giá bao nhiêu | 1 | 0.20 | 1.00 | 1.00 |
| 24 | Cắt u lành phần mềm chi phí bao nhiêu | 1 | 0.20 | 1.00 | 1.00 |
| 25 | Đo chỉ số cơ thể giá bao nhiêu | 1 | 0.20 | 1.00 | 1.00 |
| 26 | Chích áp xe tầng sinh môn giá bao nhiêu | 1 | 0.20 | 1.00 | 1.00 |
| 27 | Quy trình khám sức khỏe gồm mấy bước | 1 | 0.20 | 1.00 | 1.00 |

Rows 11/17/20 scoring 0.00 keyword/faithfulness are pre-existing, already-documented findings (see
`EVAL_FINDINGS.md` §6a/§7d), not new today, and unrelated to the rename (unaffected either way since
these are measured through the stale container regardless).

## 2. Intent routing

| Metric | 2026-07-09 baseline | 2026-07-13 (today, via classic gate HTTP path) | Target | Status |
|--------|---|---|---|---|
| Intent Routing Accuracy | 1.000 (12/12) | 1.000 (12/12) | ≥ 0.80 | ✅ |

**Caveat**: this specific number is measured via the classic gate's real HTTP call to the shared
`app` container, which was confirmed to still be running **pre-rename** code — so while it shows no
regression in absolute terms, it does **not** itself verify commit `d884335`'s routing behavior. The
rename's routing behavior was separately, more reliably verified in-process (see §4) — all 4 domains
confirmed routing correctly against this exact commit.

## 3. Booking concurrency

| Metric | Score | Target | Status |
|--------|-------|--------|--------|
| Booking Concurrency Pass Rate | 1.000 | = 1.00 | ✅ |

In-process (`BookingRepository` direct calls, no container/HTTP dependency) — valid, no regression
vs the 2026-07-09/2026-07-10 baseline (1.000 throughout). Unaffected by the rename either way (this
path never touches `ai_agents`).

## 4. DeepEval LLM-judge suite — 17 cases (grew from 9 → 17 via commits `d5e1de6`/TASK-029)

Full per-case detail in [`DEEPEVAL_REPORT.md`](./DEEPEVAL_REPORT.md); root-cause classification
cross-referenced with [`EVAL_FINDINGS.md` §7d/§8b/§9](./EVAL_FINDINGS.md). Two independent full runs
today (fresh reseed before each):

- **Run 1: 13/17 passed.** 4 failures, all real judge/assertion outcomes (no infra errors):
  `test_faq_pricing_question_grounded` (Answer Relevancy 0.667), `test_faq_specialties_overview_question_grounded`
  (Answer Relevancy 0.429), `test_booking_proposes_only_real_available_slot` (FaithfulToCheckAvailableSlots
  0.0), `test_booking_resolves_ambiguous_weekday_phrase_to_a_future_weekday` (deterministic assert,
  no tool call made).
- **Run 2: 11/17 passed.** 6 "failures", but 3 are a **transient Gemini `503 UNAVAILABLE`
  mid-judge** (`test_faq_out_of_scope_question_not_fabricated`, `test_faq_surgery_pricing_question_grounded`,
  `test_faq_specialties_overview_question_grounded` — infra flakiness, not evaluated, same class as
  the 503s already documented in `EVAL_FINDINGS.md` §2). The other 3 are real outcomes and **exactly
  reproduce Run 1**: `test_faq_pricing_question_grounded` (0.667, identical), `test_booking_proposes_only_real_available_slot`
  (0.0, identical), `test_booking_resolves_ambiguous_weekday_phrase_to_a_future_weekday` (same
  deterministic failure).

**Consistently reproducible across both runs** (2/2): the 2 booking cases — both are pre-existing,
already-escalated findings (see `EVAL_FINDINGS.md` §8b for the booking-doesn't-quote-times gap; §9
for a new observation on the ambiguous-weekday case's date-dependence), **not caused by the rename**.
`test_faq_pricing_question_grounded` is also stable at 0.667 both times it got a real score — a known
persona/relevancy trade-off (§7d), not new. `test_faq_specialties_overview_question_grounded` scored
a real 0.429/0.286 (isolated re-run) across this session's real evaluations — same known finding as
§7d, not new. None of the 4-6 observed failures are attributable to the `ai-agents` → `ai_agents`
rename — every one matches an already-documented pre-rename finding, or is a transient Gemini 503.

## Conclusion

**TASK-030 Group A (package rename `ai-agents/` → `ai_agents/`, commit `d884335`) is verified: no
rename-caused regression found, and the code-reviewer's residual risk (a silently-missing sub-agent
from `_load_sub_agents()`'s swallowed `ImportError`) is ruled out.** All 4 domains
(faq/symptom/booking/emergency) were confirmed routing correctly through the real Orchestrator built
from this exact commit, verified in-process (not dependent on the shared docker `app` container,
which was found to still be running stale pre-rename code and was correctly left untouched rather
than unilaterally rebuilt). Classic-gate retrieval/booking-concurrency metrics show no regression
vs the 2026-07-09 baseline. The DeepEval suite's 4-6 observed failures across two runs are all
pre-existing, already-documented findings (persona/relevancy trade-offs, a booking UX gap, and one
newly-observed date-fixture fragility) or transient Gemini 503s — none newly caused by the rename.
No threshold was loosened anywhere to make any of the above numbers look better than they are.
