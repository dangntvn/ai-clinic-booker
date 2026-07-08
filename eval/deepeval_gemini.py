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
# Description: DeepEval judge-model adapter — wraps common/gemini_client.py's
#              generate() so DeepEval's LLM-as-judge metrics (AnswerRelevancy,
#              Faithfulness, GEval) reuse the same Gemini client the app
#              itself uses (TASK-027 DoD: no separate Gemini client). Judge
#              calls use a fixed neutral system prompt since DeepEval builds
#              its own full evaluation prompt as the "user_message".
###############################################################################

import asyncio

from deepeval.models.base_model import DeepEvalBaseLLM

from common.config import settings
from common.gemini_client import generate

_JUDGE_SYSTEM_PROMPT = (
    "You are an impartial evaluator. Follow the instructions in the user "
    "message exactly and respond in the exact format requested."
)


class GeminiDeepEvalModel(DeepEvalBaseLLM):
    """DeepEval judge model backed by common/gemini_client.py::generate()."""

    def load_model(self):
        return self

    def generate(self, prompt: str) -> str:
        return asyncio.get_event_loop().run_until_complete(self.a_generate(prompt))

    async def a_generate(self, prompt: str) -> str:
        return await generate(
            _JUDGE_SYSTEM_PROMPT,
            prompt,
            max_output_tokens=8192,
            disable_thinking=True,
        )

    def get_model_name(self) -> str:
        return settings.gemini_llm_model


def build_judge() -> GeminiDeepEvalModel:
    """Return a fresh judge-model instance for a DeepEval metric."""
    return GeminiDeepEvalModel(model=settings.gemini_llm_model)
