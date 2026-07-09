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


async def search_knowledge_base(query: str, category: str) -> str:
    """Search the knowledge base for grounded FAQ context.

    Args:
        query: The user's question, in their own words.
        category: "policy" or "clinic_info" — never "medical_guide" (that's
                   the Symptom Agent's domain).

    Returns:
        A context block with citable [knowledge_id=...] tags, or
        NOT_FOUND_MESSAGE if nothing clears the grounding threshold.
    """
    vectors = await embed_batch([query])
    results = search(vectors[0], category=category)
    grounded = filter_grounded_results(results, settings.similarity_threshold)

    if not grounded:
        return NOT_FOUND_MESSAGE

    return build_context_text(grounded)
