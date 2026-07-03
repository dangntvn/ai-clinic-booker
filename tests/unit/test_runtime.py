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
# Description: Unit test for TASK-019 — both Runners built by app/runtime.py
#              must set auto_create_session=True, otherwise the first
#              message from any new webhook user_id raises ADK's
#              SessionNotFoundError instead of starting a conversation.
###############################################################################

import app.runtime as runtime_module


def test_build_runtime_auto_creates_sessions(monkeypatch):
    runtime_module._runner = None
    monkeypatch.setattr(runtime_module, "get_session_service", lambda: object())

    runner = runtime_module.build_runtime()

    assert runner.auto_create_session is True


def test_build_emergency_runtime_auto_creates_sessions(monkeypatch):
    runtime_module._emergency_runner = None
    monkeypatch.setattr(runtime_module, "get_session_service", lambda: object())

    runner = runtime_module.build_emergency_runtime()

    assert runner.auto_create_session is True
