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
# Description: Integration test — concurrent booking requests must not
#              double-book (ARCH-001 §5.1, ADR-0009). Needs a live Postgres
#              to actually exercise the race; eval/golden_set_booking.yaml
#              + eval/runner.py::run_booking_eval() already implements this
#              logic for real — this file stays a placeholder until a
#              dedicated pytest-level version is worth writing separately.
###############################################################################


import pytest


@pytest.mark.skip(reason="TASK-001 scaffold - implementation pending")
def test_placeholder():
    pass
