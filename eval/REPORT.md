# Eval Report

**Last run: 2026-07-17 (TASK-038, senior-tester-1)** — full regression run against branch
`feature/task-034-035-036-037-booking-injection-hardening` (TASK-034 booking auto-defaults +
TASK-035 prompt-injection hardening + TASK-036 README cleanup + TASK-037 injection test suite),
against a fresh `scripts/seed_eval_fixtures.py` reseed (28 doctors, 24 knowledge docs), real
Gemini/Postgres/Qdrant, via a throwaway container running the branch's own HTTP server (not the
shared `ai-clinic-booker-app-1`, which was stale relative to this branch — see
`eval/EVAL_FINDINGS.md` §12 for the full run notes and comparison against the 2026-07-14 baseline
(§11). This table reflects the numbers from the last of 3 full `pytest -m eval` runs performed this
session (all 3 were consistent; see §12 for the other 2 runs' numbers).

RAG questions: 27 · cutoff k = 5

## 1. RAG retrieval + generation quality

| Metric | Score | Target | Status |
|--------|-------|--------|--------|
| Span Hit Rate@5 | 1.000 | ≥ 0.80 | ✅ |
| Span MRR | 0.812 | ≥ 0.60 | ✅ |
| Context Precision@5 | 0.233 | ≥ 0.20 | ✅ |
| Hit Rate@5 (doc-id) | 1.000 | ≥ 0.70 | ✅ |
| MRR (doc-id) | 0.970 | ≥ 0.90 | ✅ |
| Keyword Match | 0.796 | ≥ 0.70 | ✅ |
| Faithfulness | 0.865 | ≥ 0.75 | ✅ |

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
| 11 | bên bạn khám những gì | 1 | 0.20 | 0.00 | 0.70 |
| 12 | có những chuyên khoa nào | 3 | 0.40 | 1.00 | 0.90 |
| 13 | phòng khám có dịch vụ gì | 3 | 0.20 | 1.00 | 1.00 |
| 14 | phòng khám có những khoa nào | 1 | 0.20 | 0.50 | 1.00 |
| 15 | danh sách các chuyên khoa của phòng khám | 1 | 0.20 | 1.00 | 1.00 |
| 16 | phòng khám có bao nhiêu chuyên khoa | 1 | 0.20 | 1.00 | 1.00 |
| 17 | khi đến anh liên hệ ai? | 2 | 0.40 | 0.00 | 0.00 |
| 18 | số điện thoại lễ tân | 2 | 0.40 | 1.00 | 1.00 |
| 19 | liên hệ ai khi đến khám | 3 | 0.20 | 1.00 | 1.00 |
| 20 | gặp ai khi tới phòng khám | 4 | 0.20 | 0.00 | 0.00 |
| 21 | Huyết áp bao nhiêu thì được coi là cao huyết áp | 1 | 0.25 | 0.00 | 0.00 |
| 22 | Dấu hiệu nhận biết hở van tim là gì | 1 | 0.25 | 0.33 | 0.75 |
| 23 | Xét nghiệm tổng phân tích tế bào máu giá bao nhiêu | 1 | 0.20 | 1.00 | 1.00 |
| 24 | Cắt u lành phần mềm chi phí bao nhiêu | 1 | 0.20 | 1.00 | 1.00 |
| 25 | Đo chỉ số cơ thể giá bao nhiêu | 1 | 0.20 | 1.00 | 1.00 |
| 26 | Chích áp xe tầng sinh môn giá bao nhiêu | 1 | 0.20 | 1.00 | 1.00 |
| 27 | Quy trình khám sức khỏe gồm mấy bước | 1 | 0.20 | 1.00 | 1.00 |

## 2. Intent routing

| Metric | Score | Target | Status |
|--------|-------|--------|--------|
| Intent Routing Accuracy | 1.000 | ≥ 0.80 | ✅ |

## 3. Booking concurrency

| Metric | Score | Target | Status |
|--------|-------|--------|--------|
| Booking Concurrency Pass Rate | 1.000 | = 1.00 | ✅ |
