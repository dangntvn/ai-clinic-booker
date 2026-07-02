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
# Description: The real AI quality gate — pytest.mark.eval, calls eval/runner.py, exits 1 on FAIL (ARCH-001 §7, §8).
###############################################################################


import pytest


@pytest.mark.eval
@pytest.mark.skip(reason="TASK-001 scaffold - implementation pending")
def test_placeholder():
    pass
