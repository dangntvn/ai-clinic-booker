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
# Description: FAQ Agent tools — search_knowledge_base(query, category)
#              wrapper over dal/qdrant_client, no raw SQL/filter here.
#              Enforces grounding (ADR-0008) before returning anything to
#              the LLM — below-threshold results never reach the prompt.
###############################################################################

from common.config import settings
from common.gemini_client import embed_batch
from dal.qdrant_client import search

from ..core.domain.grounding import (
    NOT_FOUND_MESSAGE,
    build_context_text,
    filter_grounded_results,
)

# The policy/clinic_info boundary is genuinely fuzzy for some topics (e.g. the
# visiting procedure "quy trình khám" is filed under `policy` but reads like
# clinic operations), and the category here is chosen by the LLM from a soft
# prompt rule — so a plausible misclassification would otherwise turn a
# perfectly-indexed doc into a false "not found". If the chosen FAQ category
# yields nothing grounded, retry the sibling FAQ category once before giving
# up. Never falls back into "medical_guide": that's the Symptom Agent's domain,
# and FAQ must not bleed into medical triage content.
_FAQ_CATEGORY_FALLBACK = {"policy": "clinic_info", "clinic_info": "policy"}


def _grounded_search(query_vector: list[float], category: str) -> list[dict]:
    """Search one category and keep only results clearing the grounding threshold."""
    results = search(query_vector, category=category)
    return filter_grounded_results(results, settings.similarity_threshold)


async def search_knowledge_base(query: str, category: str) -> str:
    """Search the knowledge base for grounded FAQ context.

    Args:
        query: The user's question, in their own words.
        category: "policy" or "clinic_info" — never "medical_guide" (that's
                   the Symptom Agent's domain).

    Returns:
        A context block with citable [knowledge_id=...] tags, or
        NOT_FOUND_MESSAGE if nothing clears the grounding threshold. If the
        requested FAQ category has no grounded hit, the sibling FAQ category
        (policy<->clinic_info) is tried once before returning NOT_FOUND, so a
        category misclassification doesn't become a false not-found.
    """
    vectors = await embed_batch([query])
    grounded = _grounded_search(vectors[0], category)

    if not grounded:
        fallback_category = _FAQ_CATEGORY_FALLBACK.get(category)
        if fallback_category is not None:
            grounded = _grounded_search(vectors[0], fallback_category)

    if not grounded:
        return NOT_FOUND_MESSAGE

    return build_context_text(grounded)
