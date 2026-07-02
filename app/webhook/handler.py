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
# Description: Webhook entrypoint for the Web chat channel — runs Layer-1 emergency screening (ai-agents/core/domain/emergency_rules.py) before handing the message to the ADK runtime/orchestrator (ARCH-001 §5.4, ADR-0019).
###############################################################################


async def handle_webhook(request):
    """Entry point for the Web chat webhook channel."""
    raise NotImplementedError
