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
# Description: Unit tests for ai-agents/faq/tools.py — the sibling-category
#              fallback (_FAQ_CATEGORY_FALLBACK) and the FAQ-specific
#              grounding threshold (faq_similarity_threshold) used by
#              _grounded_search/search_knowledge_base. Offline: search(),
#              embed_batch() and settings are mocked/patched — no real
#              Gemini/Qdrant call, no docker, no eval marker.
###############################################################################

import importlib
from unittest.mock import AsyncMock, patch

import pytest

tools = importlib.import_module("ai-agents.faq.tools")
grounding = importlib.import_module("ai-agents.core.domain.grounding")

FAKE_VECTOR = [0.1, 0.2, 0.3]


def _grounded_result(knowledge_id: str, score: float = 0.9) -> dict:
    return {
        "score": score,
        "payload": {
            "knowledge_id": knowledge_id,
            "title": f"title-{knowledge_id}",
            "text": f"text-{knowledge_id}",
        },
    }


@pytest.mark.asyncio
async def test_search_knowledge_base_falls_back_to_sibling_category_once():
    """No grounded hit in 'policy' -> retries sibling 'clinic_info' once, and
    that sibling result is what gets returned."""
    sibling_result = _grounded_result("kb-42")

    def fake_search(query_vector, category, top_k=None):
        if category == "policy":
            return []
        if category == "clinic_info":
            return [sibling_result]
        raise AssertionError(f"unexpected category searched: {category}")

    with (
        patch.object(tools, "embed_batch", new=AsyncMock(return_value=[FAKE_VECTOR])),
        patch.object(tools, "search", side_effect=fake_search) as mock_search,
    ):
        result_text = await tools.search_knowledge_base("some question", "policy")

    assert mock_search.call_count == 2
    called_categories = [call.kwargs.get("category", call.args[1] if len(call.args) > 1 else None) for call in mock_search.call_args_list]
    assert called_categories == ["policy", "clinic_info"]
    assert "kb-42" in result_text
    assert result_text != grounding.NOT_FOUND_MESSAGE


@pytest.mark.asyncio
async def test_search_knowledge_base_never_falls_back_from_medical_guide():
    """medical_guide has no configured sibling — a miss there must not trigger
    a second search call into any other category."""

    def fake_search(query_vector, category, top_k=None):
        assert category == "medical_guide", f"unexpected category searched: {category}"
        return []

    with (
        patch.object(tools, "embed_batch", new=AsyncMock(return_value=[FAKE_VECTOR])),
        patch.object(tools, "search", side_effect=fake_search) as mock_search,
    ):
        result_text = await tools.search_knowledge_base("some question", "medical_guide")

    assert mock_search.call_count == 1
    assert result_text == grounding.NOT_FOUND_MESSAGE


def test_grounded_search_uses_faq_similarity_threshold_not_global_one():
    """_grounded_search must filter using settings.faq_similarity_threshold,
    not the stricter global settings.similarity_threshold."""
    # A score that clears the (lower) FAQ threshold but not the (higher)
    # global one, so the two settings are distinguishable by outcome.
    mid_score_result = _grounded_result("kb-mid", score=0.65)

    with (
        patch.object(tools, "search", return_value=[mid_score_result]) as mock_search,
        patch.object(tools.settings, "faq_similarity_threshold", 0.6),
        patch.object(tools.settings, "similarity_threshold", 0.7),
    ):
        grounded = tools._grounded_search(FAKE_VECTOR, "policy")

    mock_search.assert_called_once_with(FAKE_VECTOR, category="policy")
    # 0.65 clears faq_similarity_threshold (0.6) but would fail the global
    # similarity_threshold (0.7) -- confirms the FAQ-specific one was used.
    assert grounded == [mid_score_result]


def test_grounded_search_excludes_results_below_faq_similarity_threshold():
    """Sanity check the other direction: raising faq_similarity_threshold
    above the result's score excludes it, confirming the setting is actually
    read live (not a stale/cached value)."""
    low_score_result = _grounded_result("kb-low", score=0.65)

    with (
        patch.object(tools, "search", return_value=[low_score_result]),
        patch.object(tools.settings, "faq_similarity_threshold", 0.9),
    ):
        grounded = tools._grounded_search(FAKE_VECTOR, "policy")

    assert grounded == []
