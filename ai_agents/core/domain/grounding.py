# Copyright 2026 DANG NT (dangnt.vn@gmail.com)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Description: RAG grounding helpers — similarity-threshold check driving
#              the not-found fallback (ADR-0008). Pure functions, no I/O —
#              unit-testable without a live Qdrant/LLM call.
###############################################################################

NOT_FOUND_MESSAGE = "Xin lỗi, tôi chưa có thông tin về vấn đề này trong dữ liệu hiện có."


def is_grounded(similarity_score: float, threshold: float) -> bool:
    """Check whether retrieval similarity clears the grounding threshold (ADR-0008)."""
    return similarity_score >= threshold


def filter_grounded_results(results: list[dict], threshold: float) -> list[dict]:
    """Keep only search results whose score clears the grounding threshold.

    Args:
        results: Qdrant search results, each ``{"score": float, "payload": dict}``.
        threshold: Minimum similarity score to trust (ADR-0008).

    Returns:
        The subset of ``results`` that pass ``is_grounded``, same order.
    """
    return [r for r in results if is_grounded(r["score"], threshold)]


def build_context_text(results: list[dict]) -> str:
    """Render grounded results into a context block for the LLM prompt.

    Each entry is tagged with its source knowledge_id for internal traceability
    only — never surfaced to the patient in the reply (BUG-018).
    """
    blocks = []
    for r in results:
        payload = r["payload"]
        header = f"[knowledge_id={payload['knowledge_id']}] {payload['title']}"
        blocks.append(f"{header}\n{payload['text']}")
    return "\n\n".join(blocks)
