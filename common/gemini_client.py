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
# Description: Gemini LLM + embedding client wrapper, shared across
#              ai-agents/modules (ADR-0006). Replaces rag-health's
#              OpenAIEmbeddings/ChatOpenAI (ADR-0021) with the google-genai
#              SDK; model names stay env-driven via common/config.py.
###############################################################################

from google import genai
from google.genai import types

from common.config import settings
from common.resilience import gemini_retry

_client: genai.Client | None = None


def get_client() -> genai.Client:
    """Return the process-wide Gemini client, creating it on first use."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


@gemini_retry
async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts with the configured Gemini embedding model.

    Args:
        texts: Batch of chunk texts to vectorise (ADR-0021 batches these at
               ``settings.embedding_batch_size``).

    Returns:
        One embedding vector per input text, same order as ``texts``.
    """
    client = get_client()
    response = await client.aio.models.embed_content(
        model=settings.gemini_embedding_model,
        contents=texts,
    )
    return [embedding.values for embedding in response.embeddings]


@gemini_retry
async def generate(
    system_prompt: str,
    user_message: str,
    max_output_tokens: int | None = None,
    disable_thinking: bool = False,
) -> str:
    """Generate a chat completion with the configured Gemini LLM model.

    Args:
        system_prompt: System instruction for the call (agent prompt.py content).
        user_message: The user-turn content to respond to.
        max_output_tokens: Override for ``settings.llm_max_tokens`` — callers
            whose prompts demand long structured output (e.g. eval/deepeval_gemini.py's
            judge, which needs room for both JSON reasoning and the verdict)
            need more budget than a normal short chat reply.
        disable_thinking: Zero out gemini-2.5-flash's thinking budget — the
            judge prompts already ask the model to reason inside the JSON
            response itself, so hidden thinking tokens just eat into
            max_output_tokens for no visible benefit.

    Returns:
        The generated response text.
    """
    client = get_client()
    response = await client.aio.models.generate_content(
        model=settings.gemini_llm_model,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=settings.llm_temperature,
            max_output_tokens=max_output_tokens or settings.llm_max_tokens,
            thinking_config=types.ThinkingConfig(thinking_budget=0) if disable_thinking else None,
        ),
    )
    return response.text
