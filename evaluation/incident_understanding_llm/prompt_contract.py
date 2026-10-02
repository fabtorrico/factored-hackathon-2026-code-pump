"""Frozen prompt, output schema, model identifiers and pre-registered quality gate.

Phase 4B-1. This module is the single source of truth for everything that must not change once the
benchmark starts. It contains no I/O and no sibling imports so both the evaluation scripts and the
unit tests can load it in isolation.

Frozen BEFORE any Challenge Set v2 example was sent to any model. Nothing here may be edited to
improve a result; a change requires a new PROMPT_VERSION and a new freeze artifact.

Contamination rules enforced by construction:

- No Challenge Set v2 example appears anywhere in this file. The prompt is built from the six
  class definitions only, so the challenge set is never used as a few-shot demonstration source.
- The task is customer-reported intent, not banking truth. The prompt forbids emitting a cause, a
  transaction status, an amount, an account or an identity, and the schema admits no field that
  could carry one.
- There is no seventh class. The output schema is a closed six-value enum, and abstention is
  recorded as a refusal/API failure rather than as a predicted label.

Provenance of the wording:

- Class definitions and the six tie-breakers are written from the Phase 4A label domain in
  ``app/ml/labels.py`` and from the already-frozen Phase 4A error analysis on Challenge Set v2
  (baseline and MiniLM, commit cea5c54). No LLM run and no per-example LLM result informed them.
- The out-of-scope subject list (exchange rate, new account, credit card, branch, password, loan)
  is the out-of-scope keyword domain of the frozen deterministic baseline
  ``app/ml/baseline.py``, which is committed code.
"""

from __future__ import annotations

import hashlib
from typing import Any

PROMPT_VERSION = "4b1-v1"

SYSTEM_PROMPT = """You classify one message from a bank customer who is asking about a digital \
transfer or payment.

Classify what the CUSTOMER REPORTS, not what the bank recorded. Choose exactly one label.
Do not infer a cause, a banking status, an amount, an account or an identity. Report only the \
customer's own account of the situation.

PENDING_OR_DELAYED
The customer says the transfer or payment is delayed, has not arrived yet, or is still in progress.

FAILED_OR_DECLINED
The customer says the transfer or payment was rejected, refused, declined, denied, or did not go \
through.

REVERSED
The customer says the transfer or payment was returned, refunded, reversed, cancelled, credited \
back, or undone.

APPROVED_BUT_UNRESOLVED
The customer says the transfer or payment was approved, completed or went through, yet something \
is still missing or still not resolved for them.

AMBIGUOUS_TRANSACTION
The customer cannot say which transaction the problem is about, cannot tell which of several \
movements is affected, or is too vague to attribute the problem to any single transaction.

OUT_OF_SCOPE
The request is not about a transfer or payment incident: for example a new account, an exchange \
rate, a credit card, a branch, a password, or a loan.

Tie-breakers, in order:
1. If the customer says the payment was approved or completed AND something is still missing for \
them, answer APPROVED_BUT_UNRESOLVED, not PENDING_OR_DELAYED.
2. If the customer says they do not know which transaction is at fault, answer \
AMBIGUOUS_TRANSACTION.
3. A message may mention something unrelated and still be about a transfer or payment incident. \
If it reports a transfer or payment problem, answer with that incident's label, not OUT_OF_SCOPE.
4. Answer OUT_OF_SCOPE only when no transfer or payment incident is being reported.

The message may be in Spanish or Portuguese. Judge its meaning, not its wording.

Answer with the single label only. Do not explain, do not restate the message, and return no other \
field."""

# The smallest strict schema that carries the whole task: one required closed-enum string. No
# confidence, no rationale, no evidence, no chain of thought, no free text of any kind.
LABELS: tuple[str, ...] = (
    "PENDING_OR_DELAYED",
    "FAILED_OR_DECLINED",
    "REVERSED",
    "APPROVED_BUT_UNRESOLVED",
    "AMBIGUOUS_TRANSACTION",
    "OUT_OF_SCOPE",
)

# OUT_OF_SCOPE is the scope class, not an incident class, so it is excluded from the per-class
# critical-failure check in the quality gate.
IN_SCOPE_LABELS: tuple[str, ...] = tuple(label for label in LABELS if label != "OUT_OF_SCOPE")

SCHEMA_NAME = "incident_label"

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"label": {"type": "string", "enum": list(LABELS)}},
    "required": ["label"],
    "additionalProperties": False,
}

MODEL_PRIMARY = "gpt-5.6-luna"
MODEL_CHALLENGER = "gpt-5.6-terra"
MODELS: tuple[str, ...] = (MODEL_PRIMARY, MODEL_CHALLENGER)

# Same reasoning effort, same schema, same prompt text for both models. GPT-5.6 accepts
# reasoning.effort in {none, low, medium, high, xhigh, max}; "low" is the lowest-variance setting
# that still leaves room for the HARD_NEGATIVE and LEXICAL_OVERLAP tiers. temperature is
# deliberately not sent: it is not listed among the model's supported features and sending one
# risks a request rejection.
REASONING_EFFORT = "low"

# USD per 1M tokens, short context, standard processing. Source: OpenAI API pricing for the
# GPT-5.6 family, rates effective 2026-07-30. Cached input is recorded so a cache-aware cost
# estimate is possible, but the benchmark sends uncached requests.
PRICING: dict[str, dict[str, float]] = {
    MODEL_PRIMARY: {"input": 0.20, "cached_input": 0.02, "output": 1.20},
    MODEL_CHALLENGER: {"input": 2.00, "cached_input": 0.20, "output": 12.00},
}
PRICING_SOURCE = (
    "https://developers.openai.com/api/docs/pricing (GPT-5.6 family, effective 2026-07-30)"
)
PRICING_EFFECTIVE_DATE = "2026-07-30"

# Pre-registered quality gate. Recorded before any benchmark result exists and never changed
# afterwards. Passing means "eligible for guarded integration into the hackathon prototype"; it
# does not mean production-ready banking AI.
QUALITY_GATE = {
    "gate_version": "4b1-gate-v1",
    "meaning": (
        "Eligible for guarded integration into the hackathon prototype. "
        "Explicitly NOT production-ready banking AI."
    ),
    "overall_macro_f1_min": 0.85,
    "es_macro_f1_min": 0.82,
    "pt_macro_f1_min": 0.82,
    "structured_output_validity_min": 0.99,
    "structured_output_validity_note": "pre-registered as 'approximately 100%'",
    "critical_systematic_class_failure_definition": (
        "An in-scope class (any of the five classes other than OUT_OF_SCOPE) is a critical "
        "systematic failure if its F1 is below 0.70, OR if it contributes at least 25% of all "
        "errors while its own F1 is below 0.80. The gate fails if any in-scope class meets either "
        "condition."
    ),
    "in_scope_labels": list(IN_SCOPE_LABELS),
}

# Pre-registered model-selection rule, fixed before results so the tie-break cannot be chosen
# after seeing which model won.
MATERIAL_QUALITY_DELTA = 0.02

MODEL_SELECTION_RULE = {
    "rule_version": "4b1-selection-v1",
    "material_quality_delta_macro_f1": MATERIAL_QUALITY_DELTA,
    "material_quality_delta_definition": (
        "Two models differ materially in quality when their overall macro-F1 differs by at least "
        f"{MATERIAL_QUALITY_DELTA}. Below that, quality is treated as equivalent."
    ),
    "steps": [
        "Evaluate the gate for Luna and for Terra independently.",
        "If neither passes, recommend no production integration yet.",
        "If only one passes, recommend that one.",
        "If both pass, prefer the lower-cost and lower-latency model unless the other model's "
        "overall macro-F1 is higher by at least the material quality delta. Luna is 10x cheaper "
        "per token than Terra, so cost and latency break the tie when quality is equivalent.",
    ],
    "scope_note": (
        "A passing recommendation authorizes only guarded integration into the hackathon "
        "prototype in a later phase. Phase 4B-1 performs no integration."
    ),
}

# Reference numbers from the frozen Challenge Set v2 reports of the Phase 4A systems. These are
# read-only context for comparison; they are never recomputed or altered here.
FROZEN_V2_REFERENCE = {
    "source": "evaluation/incident_understanding_v2/reports/v2_summary.json",
    "challenge_version": "2.0.0",
    "baseline": {
        "accuracy": 0.24833333333333332,
        "macro_f1": 0.3084636874148236,
        "coverage": 0.3283333333333333,
        "accepted_accuracy": 0.7563451776649747,
        "abstention_rate": 0.6716666666666666,
    },
    "learned_raw_th0": {
        "accuracy": 0.5816666666666667,
        "macro_f1": 0.5914926408627067,
        "coverage": 1.0,
        "accepted_accuracy": 0.5816666666666667,
        "abstention_rate": 0.0,
    },
    "learned_th0_7": {
        "accuracy": 0.24666666666666667,
        "macro_f1": 0.36137068021052093,
        "coverage": 0.2866666666666667,
        "accepted_accuracy": 0.8604651162790697,
        "abstention_rate": 0.7133333333333334,
    },
}

CHALLENGE_RELATIVE_PATH = "evaluation/incident_understanding_v2/challenge.json"
CHALLENGE_FREEZE_RELATIVE_PATH = "evaluation/incident_understanding_v2/reports/freeze_v2.json"
EXPECTED_CHALLENGE_SHA256 = "f571726ad934e87e7d0663776071cdacfc2b922a882b9960143708362bdedc26"
EXPECTED_CHALLENGE_VERSION = "2.0.0"
EXPECTED_CHALLENGE_TOTAL = 600


def prompt_sha256() -> str:
    return hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()


def schema_sha256() -> str:
    import json

    canonical = json.dumps(OUTPUT_SCHEMA, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def evaluation_config() -> dict[str, Any]:
    """Frozen, model-independent evaluation configuration.

    Every field here describes behaviour the harness actually implements. Configuration must never
    advertise retry, sampling, tooling or storage behaviour that the client does not perform.
    """

    return {
        "endpoint": "responses",
        "structured_outputs": True,
        "strict": True,
        "schema_name": SCHEMA_NAME,
        "reasoning_effort": REASONING_EFFORT,
        "temperature": None,
        "temperature_omitted_reason": (
            "not among the supported features of the GPT-5.6 models; omitting avoids a "
            "request rejection and keeps the run deterministic"
        ),
        "tools_enabled": False,
        "web_search": False,
        "file_search": False,
        "code_interpreter": False,
        "streaming": False,
        "store": False,
        "challenge_path": CHALLENGE_RELATIVE_PATH,
        "challenge_sha256": EXPECTED_CHALLENGE_SHA256,
        "challenge_version": EXPECTED_CHALLENGE_VERSION,
        "total_examples": 600,
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": prompt_sha256(),
        "schema_sha256": schema_sha256(),
        "models": list(MODELS),
        "retries": 0,
        "retries_reason": (
            "no retry is attempted: an API failure is recorded as-is and counted as an error. "
            "Retries would alter cost and latency semantics and are not needed for this "
            "classification experiment."
        ),
        "inter_request_delay_seconds": 0.0,
        "pricing_usd_per_million_tokens": PRICING,
        "pricing_source": PRICING_SOURCE,
        "pricing_effective_date": PRICING_EFFECTIVE_DATE,
    }


def freeze_artifact() -> dict[str, Any]:
    """The complete frozen record: prompt, schema, models, config and gate."""

    return {
        "phase": "4B-1",
        "purpose": (
            "Offline evaluation of a stronger pretrained language-understanding component. "
            "No production integration is performed in this phase."
        ),
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": prompt_sha256(),
        "schema_name": SCHEMA_NAME,
        "schema_sha256": schema_sha256(),
        "schema": OUTPUT_SCHEMA,
        "labels": list(LABELS),
        "in_scope_labels": list(IN_SCOPE_LABELS),
        "system_prompt": SYSTEM_PROMPT,
        "models": list(MODELS),
        "model_roles": {MODEL_PRIMARY: "primary", MODEL_CHALLENGER: "challenger"},
        "evaluation_config": evaluation_config(),
        "quality_gate": QUALITY_GATE,
        "model_selection_rule": MODEL_SELECTION_RULE,
        "frozen_v2_reference": FROZEN_V2_REFERENCE,
        "frozen_challenge": {
            "path": CHALLENGE_RELATIVE_PATH,
            "version": EXPECTED_CHALLENGE_VERSION,
            "sha256": EXPECTED_CHALLENGE_SHA256,
        },
        "contamination_controls": [
            "No Challenge Set v2 example is present in the prompt or the schema.",
            "Challenge Set v2 is read-only: it is verified by hash and never written.",
            "Challenge Set v2 is never used for training, tuning or few-shot demonstration.",
            "Identical prompt text, schema and reasoning effort for Luna and Terra.",
            "The quality gate was recorded before any benchmark result existed.",
            "No prompt or model change is permitted after results are observed.",
        ],
    }
