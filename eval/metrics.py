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
# Description: Single source of truth for every evaluation metric formula (Hit Rate@k, MRR, faithfulness scoring) — ARCH-001 §8 metric rule.
###############################################################################


def hit_rate_at_k(results, k: int) -> float:
    """Compute Hit Rate@k from a list of retrieval results."""
    raise NotImplementedError


def mrr(results) -> float:
    """Compute Mean Reciprocal Rank from a list of retrieval results."""
    raise NotImplementedError
