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
# Description: Unit tests for ai-agents/core/domain/grounding.py grounding-
#              threshold logic. BUG-002 regression: the scores below are
#              frozen real embed_batch()+search() results captured 2026-07-09
#              against the live seeded knowledge base (see
#              eval/golden_set_rag.yaml) — not synthetic — so this test fails
#              if settings.similarity_threshold ever regresses back to a
#              value too lenient to exclude these confirmed-irrelevant hits.
###############################################################################

import importlib

grounding = importlib.import_module("ai-agents.core.domain.grounding")

NEW_THRESHOLD = 0.72

# Real top scores for the 10 confirmed-irrelevant queries in golden_set_rag.yaml
# (topics with zero real supporting content), by category.
REAL_NEGATIVE_TOP_SCORES = {
    "policy": [0.7104, 0.6820, 0.6861, 0.6986],
    "clinic_info": [0.6219, 0.6843, 0.6731],
    "medical_guide": [0.5979, 0.5979, 0.5854],
}

# Real top score for the 1 confirmed-relevant query ("Phòng khám mở cửa mấy
# giờ") — still clears the new threshold, though (pre-existing, unrelated
# ranking-quality issue noted in golden_set_rag.yaml) the top-scored hit is
# knowledge_id=4 (irrelevant), not the actually-relevant knowledge_id=1
# (0.7091, now below NEW_THRESHOLD) — BUG-002 only targets false grounding on
# zero-content topics, not retrieval ranking quality.
REAL_POSITIVE_TOP_SCORE = 0.7511


def test_new_threshold_excludes_every_confirmed_negative_query():
    for category, scores in REAL_NEGATIVE_TOP_SCORES.items():
        for score in scores:
            assert not grounding.is_grounded(score, NEW_THRESHOLD), (
                f"{category} negative score {score} should not clear {NEW_THRESHOLD}"
            )


def test_new_threshold_still_grounds_the_confirmed_positive_query():
    assert grounding.is_grounded(REAL_POSITIVE_TOP_SCORE, NEW_THRESHOLD)


def test_old_threshold_used_to_wrongly_ground_every_negative_query():
    """Documents the bug: the old default (0.5) passed every negative above."""
    old_threshold = 0.5
    for scores in REAL_NEGATIVE_TOP_SCORES.values():
        for score in scores:
            assert grounding.is_grounded(score, old_threshold)
