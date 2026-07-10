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
# Description: Loads DeepEval case data (eval/golden_set_deepeval_*.yaml)
#              into deepeval's own EvaluationDataset/Golden objects, and
#              builds the real deepeval Metric objects a case's declarative
#              `metrics` spec describes (TASK-029). This module only
#              replaces WHERE the static case data (input/turns/criteria/
#              threshold) comes from — tests/eval/test_deepeval_*.py still
#              run the real orchestrator (run_conversation()/
#              run_conversation_turns()) and the real RetrievalCapture/
#              BookingToolCapture spies at test time; nothing about HOW a
#              case is judged changed.
###############################################################################

from pathlib import Path

import yaml
from deepeval.dataset import EvaluationDataset, Golden
from deepeval.metrics import AnswerRelevancyMetric, BaseMetric, FaithfulnessMetric, GEval
from deepeval.test_case import LLMTestCaseParams

_EVAL_DIR = Path(__file__).parent

_EVALUATION_PARAM_BY_NAME = {
    "input": LLMTestCaseParams.INPUT,
    "actual_output": LLMTestCaseParams.ACTUAL_OUTPUT,
    "expected_output": LLMTestCaseParams.EXPECTED_OUTPUT,
    "context": LLMTestCaseParams.CONTEXT,
    "retrieval_context": LLMTestCaseParams.RETRIEVAL_CONTEXT,
}


def load_dataset(filename: str) -> EvaluationDataset:
    """Load a DeepEval golden_set_deepeval_*.yaml file into an EvaluationDataset.

    Each YAML case becomes one ``Golden``:
        - ``name``: the case's stable id (was the test function name
          pre-refactor) — used as the pytest parametrize id so `pytest -m eval`
          output still shows one distinctly-named result per case, never an
          anonymous "case 1"/"case 2".
        - ``input``: the case's question, or its first turn for a multi-turn
          case (the ``turns`` list itself lives in ``additional_metadata`` —
          ``Golden.input`` is a required plain ``str``, so it can't hold a
          conversation).
        - ``additional_metadata``: the full raw case dict (metrics spec,
          ``context_kind``, ``turns``, ``not_found_fallback``,
          ``requires_tool_call``) — Golden's own documented extension point
          for exactly this "carry whatever your test needs" use case.

    Args:
        filename: Golden-set filename under ``eval/`` (e.g.
                  ``"golden_set_deepeval_faq.yaml"``).

    Returns:
        An ``EvaluationDataset`` with one ``Golden`` per YAML case, in file order.
    """
    with open(_EVAL_DIR / filename, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    goldens = []
    for case in data["cases"]:
        turns = case.get("turns")
        goldens.append(
            Golden(
                name=case["name"],
                input=turns[0] if turns else case["input"],
                additional_metadata=case,
            )
        )
    return EvaluationDataset(goldens=goldens)


def substitute(text: str, **values: str) -> str:
    """Replace ``{key}`` placeholders in ``text`` with ``values[key]``.

    Plain ``str.replace()`` per placeholder, NOT ``str.format()`` — some
    GEval criteria text in the booking golden set contains literal
    ``{'status': 'confirmed', ...}`` dict-repr text that ``str.format()``
    would misparse as a format field. A targeted, literal substring replace
    only touches the exact ``{PLACEHOLDER_NAME}`` tokens the golden set uses.

    Args:
        text:   Raw string that may contain ``{key}`` placeholders.
        values: Placeholder name -> replacement value.

    Returns:
        ``text`` with every ``{key}`` placeholder replaced.
    """
    for key, value in values.items():
        text = text.replace(f"{{{key}}}", str(value))
    return text


def build_metrics(case: dict, judge, **placeholder_values: str) -> list[BaseMetric]:
    """Build the real deepeval Metric objects a case's YAML `metrics` spec describes.

    Args:
        case:                The raw case dict (``golden.additional_metadata``).
        judge:                A DeepEval judge model (``eval.deepeval_gemini.build_judge()``).
        **placeholder_values: Passed to ``substitute()`` for GEval criteria text
                              (e.g. ``NON_WORK_DAY="2026-07-19"``).

    Returns:
        List of instantiated ``AnswerRelevancyMetric``/``FaithfulnessMetric``/``GEval`` objects.

    Raises:
        ValueError: If a case declares an unrecognised metric ``type``.
    """
    metrics: list[BaseMetric] = []
    for spec in case["metrics"]:
        kind = spec["type"]
        threshold = spec["threshold"]
        if kind == "answer_relevancy":
            metrics.append(AnswerRelevancyMetric(threshold=threshold, model=judge))
        elif kind == "faithfulness":
            metrics.append(FaithfulnessMetric(threshold=threshold, model=judge))
        elif kind == "geval":
            criteria = substitute(spec["criteria"], **placeholder_values)
            metrics.append(
                GEval(
                    name=spec["name"],
                    criteria=criteria,
                    evaluation_params=[
                        _EVALUATION_PARAM_BY_NAME[p] for p in spec["evaluation_params"]
                    ],
                    threshold=threshold,
                    model=judge,
                )
            )
        else:
            raise ValueError(f"Unknown metric type {kind!r} in case {case.get('name')!r}")
    return metrics
