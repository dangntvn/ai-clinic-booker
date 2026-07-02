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
# Description: The real AI quality gate — pytest.mark.eval, calls
#              eval/runner.py against live Gemini/Qdrant/Postgres, asserts
#              real thresholds, exits 1 on FAIL (ARCH-001 §7, §8). Only runs
#              via `pytest -m eval`, never picked up by a plain `pytest`.
###############################################################################

import pytest

from common.config import settings


@pytest.mark.eval
@pytest.mark.skipif(not settings.gemini_api_key, reason="requires a live GEMINI_API_KEY")
def test_eval_gate():
    from eval.runner import run_eval

    exit_code = run_eval()
    assert exit_code == 0, "eval/REPORT.md has the metric that missed its threshold"
