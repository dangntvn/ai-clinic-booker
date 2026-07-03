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
# Description: Regression guard for TASK-018 — .dockerignore must exclude
#              .env (never bake secrets into the image) and .venv (avoid a
#              343MB Windows venv bloating the build context).
###############################################################################

from pathlib import Path

DOCKERIGNORE = Path(__file__).resolve().parents[2] / ".dockerignore"


def test_dockerignore_excludes_env_and_venv():
    content = DOCKERIGNORE.read_text()
    lines = {line.strip() for line in content.splitlines()}

    assert ".env" in lines
    assert ".venv" in lines or ".venv/" in lines
