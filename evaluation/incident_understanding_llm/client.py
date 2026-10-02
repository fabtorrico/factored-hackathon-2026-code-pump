"""The only boundary that talks to the OpenAI Responses API.

Phase 4B-1. Deliberately thin and deliberately injectable: every function takes an already-built
client, so unit tests drive the full parsing, refusal and failure paths with a fake and never reach
the network. ``openai`` is imported lazily inside ``build_client`` so importing this module, and
therefore the default test suite, needs no SDK and no API key.

Request shape, fixed for both models:

- ``client.responses.create`` with strict Structured Outputs via ``text.format.json_schema``.
- No ``tools`` argument at all, so web search, file search, code interpreter, image generation and
  every other hosted tool are absent by construction rather than by a flag.
- ``store=False`` so nothing is retained server-side.
- One system message (the frozen prompt) and one user message (the example text only). The
  language, tier and gold label are never sent.

No hidden reasoning is requested or stored: the schema has no rationale field, and the returned
record carries only the predicted label, latency and token counts.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from prompt_contract import (
    LABELS,
    MODEL_PRIMARY,
    OUTPUT_SCHEMA,
    REASONING_EFFORT,
    SCHEMA_NAME,
    SYSTEM_PROMPT,
)

API_KEY_ENV_VAR = "OPENAI_API_KEY"

OUTCOME_VALID = "valid"
OUTCOME_REFUSED = "refused"
OUTCOME_API_FAILURE = "api_failure"

_VALID_LABELS = frozenset(LABELS)


class MissingCredentialError(RuntimeError):
    """OPENAI_API_KEY is not set. Evaluation must stop rather than guess a credential."""


def require_api_key() -> str:
    """Return the API key from the environment, or raise. Never logs, returns or stores it."""

    key = os.environ.get(API_KEY_ENV_VAR)
    if key is None or not key.strip():
        raise MissingCredentialError(
            f"{API_KEY_ENV_VAR} is not set; the Phase 4B-1 benchmark cannot run without it"
        )
    return key


def build_client(api_key: str | None = None) -> Any:
    """Construct a real SDK client. Only call this from an explicit benchmark command.

    ``max_retries=0`` is required for correctness, not as a style choice. The SDK retries twice by
    default, so leaving it unset would silently retry failed requests while the frozen evaluation
    configuration declares ``retries: 0``. Retries would also make per-example latency and cost
    describe something other than a single request. One example is one request.
    """

    from openai import OpenAI  # imported lazily: the default test suite must not need the SDK

    return OpenAI(api_key=api_key or require_api_key(), max_retries=0)


def build_request(example_text: str) -> dict[str, Any]:
    """The exact request payload. Shared by both models so the prompt cannot diverge."""

    return {
        "input": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": example_text},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": SCHEMA_NAME,
                "strict": True,
                "schema": OUTPUT_SCHEMA,
            }
        },
        "reasoning": {"effort": REASONING_EFFORT},
        "store": False,
        "stream": False,
    }


def _refusal_text(response: Any) -> str | None:
    """Best-effort refusal detection. Returns the refusal text, or None if there was none."""

    for item in getattr(response, "output", None) or []:
        content = getattr(item, "content", None) or []
        for part in content:
            if getattr(part, "type", None) == "refusal":
                return getattr(part, "refusal", "") or "refusal"
    return None


def _usage(response: Any) -> tuple[int | None, int | None]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None, None
    return getattr(usage, "input_tokens", None), getattr(usage, "output_tokens", None)


def classify(client: Any, model: str, text: str) -> dict[str, Any]:
    """Classify one customer message. Returns a per-example record; never raises.

    A transport or API error is recorded as an API failure rather than propagated, so one bad
    example cannot abort a 600-example run.
    """

    payload = build_request(text)
    started = time.perf_counter()
    try:
        response = client.responses.create(model=model, **payload)
    except Exception as error:  # noqa: BLE001 - any SDK/transport failure is data, not a crash
        return {
            "model": model,
            "predicted_label": None,
            "outcome": OUTCOME_API_FAILURE,
            "api_error_type": type(error).__name__,
            "api_error": str(error)[:300],
            "latency_ms": (time.perf_counter() - started) * 1000.0,
            "input_tokens": None,
            "output_tokens": None,
        }
    latency_ms = (time.perf_counter() - started) * 1000.0
    input_tokens, output_tokens = _usage(response)

    record: dict[str, Any] = {
        "model": model,
        "latency_ms": latency_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "api_error_type": None,
        "api_error": None,
    }

    status = getattr(response, "status", "completed")
    refusal = _refusal_text(response)
    raw = getattr(response, "output_text", None)

    if refusal is not None:
        record.update(
            {
                "predicted_label": None,
                "outcome": OUTCOME_REFUSED,
                "refusal": refusal[:300],
            }
        )
        return record

    if status != "completed" or not raw:
        details = getattr(response, "incomplete_details", None)
        record.update(
            {
                "predicted_label": None,
                "outcome": OUTCOME_API_FAILURE,
                "api_error_type": "incomplete_response",
                "api_error": str(getattr(details, "reason", status))[:300],
            }
        )
        return record

    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError) as error:
        record.update(
            {
                "predicted_label": None,
                "outcome": OUTCOME_VALID,
                "structured_output_valid": False,
                "api_error_type": "unparseable_structured_output",
                "api_error": str(error)[:300],
            }
        )
        return record

    label = parsed.get("label") if isinstance(parsed, dict) else None
    valid = isinstance(label, str) and label in _VALID_LABELS
    record.update(
        {
            "predicted_label": label if valid else None,
            "outcome": OUTCOME_VALID,
            "structured_output_valid": valid,
            "unexpected_label": None if valid else str(label)[:80],
        }
    )
    return record


def classify_all(
    client: Any,
    model: str,
    examples: list[dict[str, Any]],
    progress: Any = None,
) -> list[dict[str, Any]]:
    """Classify every frozen example. Only the example text is sent to the model."""

    records: list[dict[str, Any]] = []
    for index, example in enumerate(examples, start=1):
        record = classify(client, model, example["text"])
        record.update(
            {
                "id": example["id"],
                "language": example["language"],
                "tier": example["tier"],
                "gold_label": example["label"],
            }
        )
        records.append(record)
        if progress is not None:
            progress(index, len(examples), record)
    return records


__all__ = [
    "API_KEY_ENV_VAR",
    "MissingCredentialError",
    "MODEL_PRIMARY",
    "OUTCOME_API_FAILURE",
    "OUTCOME_REFUSED",
    "OUTCOME_VALID",
    "build_client",
    "build_request",
    "classify",
    "classify_all",
    "require_api_key",
]
