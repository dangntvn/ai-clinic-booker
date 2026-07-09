# Eval Findings — 2026-07-08 real run

Separate from [`../../../../01-docs/99-project-management/backlog/BUGS.md`](../../../../01-docs/99-project-management/backlog/BUGS.md)
(scoped only to backlog-task 5-attempt-limit escalations). This file logs what the real eval run
(`pytest -m eval`, real Gemini/Postgres/Qdrant, TASK-028) found, classified per task instructions
into **bug thật** / **thiếu data** / **threshold chưa hợp lý**. Every confirmed real bug also has
its own fixable file under
[`../../../../01-docs/99-project-management/backlog/bugs/`](../../../../01-docs/99-project-management/backlog/bugs/README.md) —
this file is the narrative "what happened during the eval run", the `bugs/` folder is "here's
exactly what to fix".

---

## 1. Retrieval Hit-Rate@5 / MRR — FAIL (0.091 / 0.023) — classification: **thiếu data**

**Not a new finding** — this is TASK-026's already-documented conclusion, confirmed again by
actually running the metric formula for real. `golden_set_rag.yaml` has 11 queries, 10 of them
patched to `relevant_knowledge_ids: []` because TASK-026's real retrieval test proved
`phongkham5sao.vn`'s real content has zero topical support for those questions (BHYT, cancellation
policy, parking, Tet hours, promotions, pre-test/scan prep). A query with `relevant_knowledge_ids:
[]` can never contribute a hit, so `mean_hit_rate_at_k`/`mrr` are mechanically bounded near
`1/11 ≈ 0.09` no matter how good retrieval is.

**Related task**: none — this is by design until a future data-collection round (outside
`phongkham5sao.vn`) adds real content for those 10 topics, or TASK-027-style queries replace them.
Not something TASK-028 should "fix" by loosening the threshold — the threshold is fine, the golden
set's queries are the problem, and TASK-026 already said so.

---

## 2. Intent routing accuracy — FAIL then PASS (0.917 → 1.0) — classification: **threshold/flakiness, not a bug**

First run scored 11/12 (0.917), just above... actually just below the 0.8 threshold check passed
(`0.917 >= 0.8` → the metric itself technically passed the gate check in `run_eval()`'s reported
`REPORT.md`, worth noting the FAIL label above is about the first background diagnostic run hitting
a transient `google.genai.errors.ServerError: 503 UNAVAILABLE` mid-conversation, not the accuracy
number itself). Re-running `run_intent_eval()` cleanly (no 503) scored **12/12 = 1.0**. Classified
as **infrastructure flakiness** (Gemini API transient overload), not a product or eval-design bug —
`common/resilience.py::gemini_retry` already exists for exactly this, worth confirming it covers
the ADK Runner's own internal LLM calls too (it wraps `common/gemini_client.py`, but the ADK
`Agent`'s own model calls go through `google-adk`'s internal client, not `gemini_client.py` — so
this retry decorator likely does NOT cover ADK-driven calls). **Not filed as a bug** — a single
transient 503 on one real API call during one eval run isn't evidence of a code defect, and
`google-adk`'s own request path already has its own retry/tenacity wrapping visible in the
traceback. Worth a note for whoever runs this gate in CI: expect occasional transient failures,
consider a re-run-on-503 policy at the CI level rather than the code level.

---

## 3. Booking concurrency pass rate — FAIL (0.800, then 0.1 on re-run) — classification: **2 bug thật + 1 eval-methodology bug**

Investigated the failing cases directly against the real DB (no LLM involved, pure
`BookingRepository` calls) and found two distinct, code-confirmed real bugs:

### 3a. `check_available_slots()` never excludes an already-taken slot — **bug thật, CRITICAL**

- **Agent**: Booking Agent (`ai-agents/booking/tools.py::check_available_slots`) and the admin
  booking flow generally — this is a `data/` layer bug, reachable from any caller.
- **Input**: `check_available_slots(doctor_id=3, date=2026-07-13)`, where doctor 3 already has a
  real confirmed booking at `2026-07-13T09:00:00+00:00` (booking id 5).
- **Actual output**: `09:00` is included in the returned "available" list.
- **Expected output**: `09:00` should be excluded — it's taken.
- **Root cause**: `_candidate_slots()` builds naive `datetime`s; the `bookings.slot_time` column is
  `timestamp with time zone`, so `taken` is a set of timezone-aware `datetime`s. Comparing naive vs.
  aware `datetime`s with `==`/`in` in Python silently evaluates to "not equal" instead of raising —
  the exclusion filter is a complete no-op for every slot, every doctor, every day.
- **Task to fix**: filed as **BUG-006**
  (`../../../../01-docs/99-project-management/backlog/bugs/BUG-006-check-available-slots-never-excludes-taken-slots.md`).
  Whoever picks this up should also revisit TASK-008's own DoD (booking concurrency) since this
  directly undermines what that task was supposed to guarantee.

### 3b. `create_booking()` never validates doctor `work_days`/clinic hours — **bug thật, HIGH**

- **Agent**: same file, `create_booking()`.
- **Input**: `create_booking(doctor_id=3, slot_time="2026-07-12T09:00:00")` — 2026-07-12 is a
  Sunday; doctor 3's real `work_days` is `["Mon","Tue","Wed","Thu","Fri","Sat"]`.
- **Actual output**: booking created and confirmed (id 35).
- **Expected output**: rejected — the doctor doesn't work that day at all.
- **Root cause**: `create_booking()`'s only correctness mechanism is the DB's partial unique index
  (conflict detection); there is no work-day/hours validation at the data layer at all, by design
  (per its own docstring) — that check is assumed to live entirely in the Booking Agent's prompt
  instructions, which a direct repository call (like this eval's own concurrency runner) bypasses
  completely.
- **Task to fix**: filed as **BUG-007**
  (`../../../../01-docs/99-project-management/backlog/bugs/BUG-007-create-booking-no-workday-hours-validation.md`).

### 3c. The golden set itself isn't repeatable — **eval-methodology bug, not a product bug**

Re-running `run_booking_eval()` a second time (to double check 3a/3b) dropped the pass rate further
(0.8 → 0.1) purely because the first run's successful bookings are still sitting in the real DB —
`golden_set_booking.yaml` has no cleanup step and uses fixed dates/doctors. This makes the metric
non-reproducible across runs for reasons unrelated to code changes. Filed as **BUG-008**
(`../../../../01-docs/99-project-management/backlog/bugs/BUG-008-eval-golden-sets-not-repeatable.md`).
**Do not re-run `golden_set_booking.yaml` as-is expecting a clean signal** until BUG-008 is
addressed or the leftover bookings (ids 5, 9, 11, 16, 26, 27, 29, 32, 35 for doctor 3; 28 for
doctor 4) are cancelled.

---

## 4. DeepEval FAQ/Symptom cases — 3 flipped FAIL→PASS on isolated retry — classification: **LLM-judge nondeterminism, not a bug**

`test_faq_pricing_question_grounded`, `test_symptom_medical_guide_question_grounded`, and
`test_symptom_routes_to_real_doctor_for_covered_specialty` each failed once during the full
9-test-plus-gate run, then passed cleanly when re-run in isolation immediately after, with no code
change. This is expected variance for an LLM-as-judge setup (`AnswerRelevancyMetric`/
`FaithfulnessMetric`/`GEval`, all backed by a real Gemini call per TASK-027) — not itself a defect.

One contributing factor worth flagging: `ai-agents/*/agent.py` never passes an explicit temperature
to `google.adk.agents.Agent(...)` — the per-agent `*_LLM_TEMPERATURE` env vars from TASK-017
(`SYMPTOM_LLM_TEMPERATURE=0.2`, etc.) are part of the orphaned config already filed as **BUG-005**.
If those were actually wired in with `temperature=0.0`, real-agent-response variance (one of the
two variance sources feeding into judge-score variance, the other being the judge model's own
temperature) would shrink, likely reducing — not eliminating — this kind of flakiness. Not
re-filing as a new bug; this just reinforces BUG-005's priority.

**Related task**: none required. If judge flakiness becomes a recurring CI pain, consider
`deepeval`'s built-in retry/majority-vote options or running each case N times and averaging,
rather than treating a single run's pass/fail as ground truth.

---

## 5. `test_booking_confirms_before_create_then_creates_real_booking` — reproducible FAIL (2/2) — classification: **eval-methodology bug (BUG-008), compounded by BUG-006**

Unlike the flaky cases above, this one failed consistently on 2 separate re-runs. Root cause:

- The test's hardcoded slot (`doctor_id=3`, `2026-07-13T09:00:00`) was already **confirmed-booked**
  by this exact test's own successful run during TASK-027 (booking id 5) — so `create_booking` was
  never going to succeed the same way twice.
- Compounding it, `check_available_slots` (BUG-006) still reports `09:00` as free, so the agent
  legitimately (from its own point of view) offers a slot that's actually taken — the conversation
  no longer reaches a clean "confirm → create_booking succeeds" path the test asserts on.

**Not treated as a new distinct product bug** — it's the direct, expected consequence of BUG-006 +
BUG-008 acting together on this specific test's fixed data. Fixing either (ideally both) should
restore this test to a genuine pass/fail signal.

---

## Conclusion (TASK-028 Step 5)

**The eval suite as it stands today is not yet a reliable long-term quality gate — it needs another
iteration, but the reason is not "the eval framework is broken," it's "the eval run did exactly its
job and found real product bugs plus a real eval-design gap that need fixing first":**

1. `golden_set_rag.yaml`'s Hit-Rate/MRR metric cannot pass with the current real dataset by
   construction (10/11 queries have no real answer) — this is a genuine, previously-flagged (TASK-026)
   data gap, not something to threshold-tune away. Needs either a new data-collection round or
   (more practical, per TASK-026's own recommendation) replacing those 10 queries with new ones
   grounded in the 22 real rows that do exist.
2. Two real, confirmed, non-flaky product bugs (BUG-006, BUG-007) currently make
   `booking_concurrency_pass_rate` fail for reasons that are genuine defects, not test problems —
   worth fixing before trusting this metric as a release gate.
3. One eval-methodology bug (BUG-008) makes the booking golden set (and one DeepEval case)
   non-repeatable — any CI setup that runs `pytest -m eval` more than once against a persistent DB
   will get misleading results regardless of code correctness.
4. The DeepEval suite (TASK-027) itself is fundamentally sound — 6/9 cases passed cleanly, and the
   3 that flipped are explained by ordinary LLM-judge variance, not a design flaw — this part is
   close to reliable already, modulo BUG-005 (fixing per-agent temperature=0.0 wiring would likely
   tighten it further).

**Recommendation**: fix BUG-006, BUG-007, BUG-008 first (all filed, all have a suggested fix and a
verification method), replace `golden_set_rag.yaml`'s 10 gap queries per TASK-026's recommendation,
then re-run `pytest -m eval` once clean as the actual baseline this project should track going
forward — don't treat today's numbers as that baseline.
