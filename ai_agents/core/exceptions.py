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
# Description: AI-specific exceptions raised by the agent/tool layer
#              (ARCH-001 §8). SlotTakenError actually lives in
#              core/exceptions.py (ARCH-001 §4 explicitly allows either
#              location) — re-exported here so ai_agents/booking/tools.py
#              can catch it with a normal relative import.
###############################################################################

from core.exceptions import SlotTakenError

__all__ = ["SlotTakenError", "LowConfidenceError"]


class LowConfidenceError(Exception):
    """Raised when RAG retrieval similarity is below the grounding threshold."""

    pass
