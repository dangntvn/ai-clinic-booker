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
# Description: BaseAgent — lifecycle and session-transfer contract shared
#              by every ADK agent (ARCH-001 §4, §8). Currently unused —
#              every agent so far builds a google.adk.agents.Agent directly
#              and hasn't needed a shared base beyond what ADK provides.
###############################################################################


class BaseAgent:
    """Base class for every ADK agent — lifecycle + session transfer contract."""

    pass
