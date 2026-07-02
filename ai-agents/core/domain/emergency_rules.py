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
# Description: Layer-1 emergency red-flag screening, called from app/webhook/handler.py before the ADK runtime — rule code only, no LLM call (BIZ-001 §3, ADR-0019).
###############################################################################


def is_emergency(text: str) -> bool:
    """Screen text for red-flag emergency keywords (BIZ-001 §3) — no LLM call."""
    raise NotImplementedError
