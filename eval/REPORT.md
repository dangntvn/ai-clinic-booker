# Eval Report

> **Run**: 2026-07-10, real `python -m eval.runner` executed end-to-end by senior-tester on the
> host `.venv` against the live dockerised stack + real Gemini, right after TASK-015 batch 3/4
> rewrote this report's format and closed the eval-metric gap (span-level retrieval, keyword
> match, real LLM-judge faithfulness — see `eval/metrics.py`/`eval/runner.py`). This is the
> **first run where "generation" for the RAG golden set goes through the real HTTP conversation
> API** instead of being retrieval-only — that change is exactly what surfaced the two ❌ rows
> below; the classic retrieval/intent/booking metrics (unaffected by this change) remain fully
> green, matching the 2026-07-09 baseline.
>
> **Two new findings, not silently worked around** (full detail in
> [`EVAL_FINDINGS.md` §6](./EVAL_FINDINGS.md)):
> 1. **Orchestrator routing ambiguity**: 13/27 RAG golden-set queries phrased as "Khoa X điều trị
>    bệnh gì / có dịch vụ gì" get routed to `symptom_agent` (which answers from its own hardcoded
>    triage knowledge) instead of `faq_agent` (which is grounded in the real `clinic_info`/`policy`
>    content these questions target) — dragging down Keyword Match/Faithfulness even though the
>    underlying retrieval is correct.
> 2. **Reproducible (2/2) category mismatch**: "Quy trình khám sức khỏe gồm mấy bước" consistently
>    gets answered with a not-found fallback citing the wrong document (#15, contact info, not #24,
>    the actual 7-step visiting procedure) — traced to the FAQ Agent's own prompt rule 1 plausibly
>    classifying this query as `clinic_info` (a visiting-procedure question), while the doc itself
>    is filed under `category: policy` in the knowledge base, so the agent's own
>    `search_knowledge_base(query, category)` call never looks in the category the doc lives in,
>    independent of the similarity threshold.
>
> **RAG_TARGETS provenance** (see `eval/runner.py` for the full note): the two doc-id rows keep
> this project's pre-existing thresholds (0.70 / 0.90, unchanged); the five new metrics (Span
> Hit Rate@5/MRR, Context Precision@5, Keyword Match, Faithfulness) use the rag-health reference
> project's suggested targets as a starting point since this project never measured them before —
> flagged for Team Lead review, not something to treat as already-validated.

RAG questions: 27 · cutoff k = 5

## 1. RAG retrieval + generation quality

| Metric | Score | Target | Status |
|--------|-------|--------|--------|
| Span Hit Rate@5 | 1.000 | ≥ 0.80 | ✅ |
| Span MRR | 0.812 | ≥ 0.60 | ✅ |
| Context Precision@5 | 0.233 | ≥ 0.20 | ✅ |
| Hit Rate@5 (doc-id) | 1.000 | ≥ 0.70 | ✅ |
| MRR (doc-id) | 0.970 | ≥ 0.90 | ✅ |
| Keyword Match | 0.503 | ≥ 0.70 | ❌ |
| Faithfulness | 0.544 | ≥ 0.75 | ❌ |

### Per-question breakdown

| # | Query | Span rank | Span Prec@5 | Keyword | Faithfulness |
|---|-------|-----------|-------------|---------|--------------|
| 1 | Phòng khám mở cửa mấy giờ | 3 | 0.40 | 1.00 | 1.00 |
| 2 | Khoa da liễu điều trị những bệnh gì | 1 | 0.20 | 0.75 | 0.20 |
| 3 | Khoa mắt chữa những bệnh nào | 1 | 0.20 | 0.00 | 0.00 |
| 4 | Khoa nhi khám các bệnh gì cho trẻ em | 1 | 0.20 | 0.00 | 1.00 |
| 5 | Khoa siêu âm có những dịch vụ gì | 1 | 0.20 | 0.00 | 0.00 |
| 6 | Khoa sản phụ khoa có khám thai không | 3 | 0.20 | 0.33 | 1.00 |
| 7 | Khoa tai mũi họng điều trị viêm xoang viêm tai không | 1 | 0.20 | 0.00 | 0.00 |
| 8 | Chụp CT Cone Beam làm ở khoa nào | 1 | 0.20 | 0.50 | 0.00 |
| 9 | Khoa răng hàm mặt có chỉnh nha và điều trị tủy răng không | 1 | 0.20 | 1.00 | 1.00 |
| 10 | Khoa xét nghiệm làm những xét nghiệm gì | 1 | 0.20 | 1.00 | 1.00 |
| 11 | bên bạn khám những gì | 1 | 0.20 | 0.00 | 0.50 |
| 12 | có những chuyên khoa nào | 3 | 0.40 | 0.00 | 0.00 |
| 13 | phòng khám có dịch vụ gì | 3 | 0.20 | 1.00 | 1.00 |
| 14 | phòng khám có những khoa nào | 1 | 0.20 | 0.00 | 0.00 |
| 15 | danh sách các chuyên khoa của phòng khám | 1 | 0.20 | 0.67 | 0.00 |
| 16 | phòng khám có bao nhiêu chuyên khoa | 1 | 0.20 | 1.00 | 1.00 |
| 17 | khi đến anh liên hệ ai? | 2 | 0.40 | 0.00 | 0.00 |
| 18 | số điện thoại lễ tân | 2 | 0.40 | 1.00 | 1.00 |
| 19 | liên hệ ai khi đến khám | 3 | 0.20 | 1.00 | 1.00 |
| 20 | gặp ai khi tới phòng khám | 4 | 0.20 | 0.00 | 0.00 |
| 21 | Huyết áp bao nhiêu thì được coi là cao huyết áp | 1 | 0.25 | 0.00 | 0.00 |
| 22 | Dấu hiệu nhận biết hở van tim là gì | 1 | 0.25 | 0.33 | 0.50 |
| 23 | Xét nghiệm tổng phân tích tế bào máu giá bao nhiêu | 1 | 0.20 | 1.00 | 1.00 |
| 24 | Cắt u lành phần mềm chi phí bao nhiêu | 1 | 0.20 | 1.00 | 1.00 |
| 25 | Đo chỉ số cơ thể giá bao nhiêu | 1 | 0.20 | 1.00 | 1.00 |
| 26 | Chích áp xe tầng sinh môn giá bao nhiêu | 1 | 0.20 | 1.00 | 1.00 |
| 27 | Quy trình khám sức khỏe gồm mấy bước | 1 | 0.20 | 0.00 | 0.50 |

## 2. Intent routing

| Metric | Score | Target | Status |
|--------|-------|--------|--------|
| Intent Routing Accuracy | 1.000 | ≥ 0.80 | ✅ |

## 3. Booking concurrency

| Metric | Score | Target | Status |
|--------|-------|--------|--------|
| Booking Concurrency Pass Rate | 1.000 | = 1.00 | ✅ |
