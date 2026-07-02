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
# Description: Import helper for the ai-agents/ package. ARCH-001 §8 names
#              that directory with a hyphen, which the `import`/`from ... import`
#              statement grammar cannot reference (hyphen is not a valid
#              identifier character). importlib.import_module() bypasses that
#              grammar check and loads it by string, so this is the only
#              sanctioned way for code outside ai-agents/ (app/, modules/,
#              tests/) to reach into it. Code *inside* ai-agents/ should keep
#              using ordinary relative imports (e.g. `from ..faq.agent import
#              faq_agent`), which never need to spell the hyphenated name.
###############################################################################

import importlib
from types import ModuleType


def load_ai_agents(dotted_path: str) -> ModuleType:
    """Import a module from ai-agents/ by its dotted path under that root.

    Args:
        dotted_path: Path under ai-agents/, e.g. "core.domain.emergency_rules"
                      or "orchestrator.agent".

    Returns:
        The imported module object.
    """
    return importlib.import_module(f"ai-agents.{dotted_path}")
