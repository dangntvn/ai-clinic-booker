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
# Description: Unit tests for ai_agents/core/domain/grounding.py grounding-
#              threshold logic. BUG-002 regression: the scores below are
#              frozen real embed_batch()+search() results captured 2026-07-09
#              against a freshly wiped-and-reseeded knowledge base
#              (scripts/seed_eval_fixtures.py, see eval/golden_set_rag.yaml) —
#              not synthetic, and re-run twice to confirm they're stable, not
#              a one-off fluke. Confirms both what NEW_THRESHOLD fixes and
#              what it deliberately still doesn't (see the module below).
###############################################################################

from ai_agents.core.domain import grounding

NEW_THRESHOLD = 0.7

# Real top scores for the 10 confirmed-irrelevant queries in golden_set_rag.yaml
# (topics with zero real supporting content), by category.
REAL_NEGATIVE_TOP_SCORES = {
    "policy": [0.7096, 0.6820, 0.6940, 0.7162],
    "clinic_info": [0.6515, 0.6732, 0.6731],
    "medical_guide": [0.6089, 0.6173, 0.6016],
}

# Real top score for the 1 confirmed-relevant query ("Phòng khám mở cửa mấy giờ").
REAL_POSITIVE_TOP_SCORE = 0.7172

# The real negative max (policy, 0.7162) sits only 0.001 below the one real
# positive's own score (0.7172) — too close for any single global threshold
# to separate both perfectly. 0.7 was chosen (over 0.72) specifically to keep
# the positive case grounded; the accepted cost is these 2 policy queries
# ("Nội soi dạ dày giá bao nhiêu" 0.7096, "Chính sách hủy lịch khám..." 0.7162)
# stay wrongly grounded. User-confirmed tradeoff 2026-07-09 — do not "fix" by
# quietly raising the threshold again without re-checking this margin first.
KNOWN_REMAINING_FALSE_POSITIVES = [0.7096, 0.7162]


def test_new_threshold_excludes_most_confirmed_negative_queries():
    for category, scores in REAL_NEGATIVE_TOP_SCORES.items():
        for score in scores:
            if score in KNOWN_REMAINING_FALSE_POSITIVES:
                continue
            assert not grounding.is_grounded(score, NEW_THRESHOLD), (
                f"{category} negative score {score} should not clear {NEW_THRESHOLD}"
            )


def test_new_threshold_still_grounds_the_confirmed_positive_query():
    assert grounding.is_grounded(REAL_POSITIVE_TOP_SCORE, NEW_THRESHOLD)


def test_known_remaining_false_positives_are_still_grounded():
    """Documents the accepted tradeoff — fails loudly if this ever silently changes."""
    for score in KNOWN_REMAINING_FALSE_POSITIVES:
        assert grounding.is_grounded(score, NEW_THRESHOLD)


def test_old_threshold_used_to_wrongly_ground_every_negative_query():
    """Documents the bug: the old default (0.5) passed every negative above."""
    old_threshold = 0.5
    for scores in REAL_NEGATIVE_TOP_SCORES.values():
        for score in scores:
            assert grounding.is_grounded(score, old_threshold)
