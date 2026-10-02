"""Phase 4B-1 tests: strict output schema, prompt freeze, client boundary, refusal and failure
handling, challenge-hash validation, v2 immutability and evaluation-artifact parsing.

No test in this module calls the OpenAI API. The client boundary is driven entirely by fakes, and
``OPENAI_API_KEY`` is explicitly removed for the duration of the module so any accidental real call
would fail loudly instead of silently spending money.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.ml.labels import ALL_LABELS

REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_DIR = REPO_ROOT / "evaluation" / "incident_understanding_llm"
REPORTS_DIR = LLM_DIR / "reports"
V2_DIR = REPO_ROOT / "evaluation" / "incident_understanding_v2"
CHALLENGE_PATH = V2_DIR / "challenge.json"
V2_FREEZE_PATH = V2_DIR / "reports" / "freeze_v2.json"
PROMPT_FREEZE_PATH = REPORTS_DIR / "prompt_freeze.json"
QUALITY_GATE_PATH = REPORTS_DIR / "quality_gate.json"

FREEZE_SKIP = pytest.mark.skipif(
    not PROMPT_FREEZE_PATH.exists(), reason="prompt not frozen; run freeze_prompt.py first"
)

# The evaluation modules import each other by bare name, so the directory goes on sys.path. Every
# following import is therefore intentionally after that statement.
if str(LLM_DIR) not in sys.path:
    sys.path.insert(0, str(LLM_DIR))

import challenge_io  # noqa: E402
import client as llm_client  # noqa: E402
import metrics as llm_metrics  # noqa: E402
import prompt_contract  # noqa: E402


@pytest.fixture(autouse=True)
def _no_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guarantee the default suite cannot reach the API even by accident."""

    monkeypatch.delenv(llm_client.API_KEY_ENV_VAR, raising=False)


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def analyze_errors() -> Any:
    return _load_module("phase4b1_analyze_errors", LLM_DIR / "analyze_errors.py")


@pytest.fixture(scope="module")
def evaluate_llm() -> Any:
    return _load_module("phase4b1_evaluate_llm", LLM_DIR / "evaluate_llm.py")


# --- Fakes for the client boundary -------------------------------------------------------


class FakeResponse:
    def __init__(
        self,
        output_text: str | None = None,
        status: str = "completed",
        refusal: str | None = None,
        input_tokens: int | None = 100,
        output_tokens: int | None = 5,
        incomplete_reason: str | None = None,
    ) -> None:
        self.output_text = output_text
        self.status = status
        self.usage = None
        if input_tokens is not None or output_tokens is not None:
            self.usage = SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)
        self.output = []
        if refusal is not None:
            self.output = [
                SimpleNamespace(content=[SimpleNamespace(type="refusal", refusal=refusal)])
            ]
        self.incomplete_details = (
            SimpleNamespace(reason=incomplete_reason) if incomplete_reason else None
        )


class FakeResponses:
    def __init__(self, response: Any = None, error: BaseException | None = None) -> None:
        self._response = response
        self._error = error
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._response


class FakeClient:
    def __init__(self, response: Any = None, error: BaseException | None = None) -> None:
        self.responses = FakeResponses(response=response, error=error)


class FakeBillingError(RuntimeError):
    """Mirrors the provider's credit-exhaustion error without importing the SDK.

    Declared locally so the default suite still needs no OpenAI SDK and no credential.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.status_code = 429
        self.code = "insufficient_quota"


# --- Structured output schema ------------------------------------------------------------


def test_schema_is_the_smallest_strict_single_label_object():
    schema = prompt_contract.OUTPUT_SCHEMA
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["label"]
    assert list(schema["properties"]) == ["label"]
    assert schema["properties"]["label"] == {
        "type": "string",
        "enum": list(prompt_contract.LABELS),
    }


def test_schema_admits_exactly_the_six_labels_and_no_seventh():
    assert len(prompt_contract.LABELS) == 6
    assert len(set(prompt_contract.LABELS)) == 6
    assert set(prompt_contract.LABELS) == {label.value for label in ALL_LABELS}
    assert len(prompt_contract.OUTPUT_SCHEMA["properties"]["label"]["enum"]) == 6


def test_schema_carries_no_field_that_could_hold_banking_fact_or_reasoning():
    forbidden = {
        "reason",
        "rationale",
        "explanation",
        "confidence",
        "transaction_status",
        "customer_id",
        "authorized",
        "ownership",
        "outcome",
        "policy",
        "amount",
        "text",
    }
    assert not forbidden & set(prompt_contract.OUTPUT_SCHEMA["properties"])


def test_out_of_scope_is_excluded_from_the_in_scope_gate_classes():
    assert "OUT_OF_SCOPE" not in prompt_contract.IN_SCOPE_LABELS
    assert len(prompt_contract.IN_SCOPE_LABELS) == 5


# --- Prompt freeze and contamination controls --------------------------------------------


@FREEZE_SKIP
def test_frozen_prompt_hash_matches_the_live_prompt():
    frozen = json.loads(PROMPT_FREEZE_PATH.read_text(encoding="utf-8"))
    assert frozen["prompt_sha256"] == prompt_contract.prompt_sha256()
    assert frozen["schema_sha256"] == prompt_contract.schema_sha256()
    assert frozen["system_prompt"] == prompt_contract.SYSTEM_PROMPT


@FREEZE_SKIP
def test_no_challenge_v2_example_text_appears_in_the_prompt():
    challenge = json.loads(CHALLENGE_PATH.read_text(encoding="utf-8"))
    prompt = prompt_contract.SYSTEM_PROMPT
    for example in challenge["examples"]:
        assert example["text"] not in prompt
        # Also guard against a truncated near-verbatim snippet being pasted in as a demo.
        snippet = " ".join(example["text"].split()[:6])
        assert snippet not in prompt


def test_prompt_defines_every_label_and_asks_for_no_explanation():
    prompt = prompt_contract.SYSTEM_PROMPT
    for label in prompt_contract.LABELS:
        assert label in prompt
    assert "Do not explain" in prompt
    assert "Answer with the single label only" in prompt


def test_prompt_forbids_inferring_banking_truth():
    prompt = prompt_contract.SYSTEM_PROMPT
    assert "not what the bank recorded" in prompt
    assert "Do not infer a cause" in prompt


# --- Request shape ----------------------------------------------------------------------


def test_request_uses_strict_structured_outputs_and_enables_no_tool():
    payload = llm_client.build_request("Mi pago sigue pendiente")
    text_format = payload["text"]["format"]
    assert text_format["type"] == "json_schema"
    assert text_format["strict"] is True
    assert text_format["schema"] is prompt_contract.OUTPUT_SCHEMA
    # Absent by construction, not switched off.
    assert "tools" not in payload
    assert "tool_choice" not in payload
    for tool in ("web_search", "file_search", "code_interpreter"):
        assert tool not in json.dumps(payload)


def test_request_is_identical_for_both_models():
    """The prompt cannot diverge per model: it does not depend on the model at all."""

    first = llm_client.build_request("hola")
    second = llm_client.build_request("hola")
    assert first == second


def test_request_sends_only_the_prompt_and_the_example_text():
    payload = llm_client.build_request("No se cual de todos es")
    roles = [message["role"] for message in payload["input"]]
    assert roles == ["system", "user"]
    assert payload["input"][0]["content"] == prompt_contract.SYSTEM_PROMPT
    assert payload["input"][1]["content"] == "No se cual de todos es"
    # No language, tier, gold label or identifier travels with the example.
    assert "language" not in json.dumps(payload)
    assert "tier" not in json.dumps(payload)
    assert "AMBIGUOUS_TRANSACTION" not in payload["input"][1]["content"]


def test_request_is_deterministic_and_does_not_store_server_side():
    payload = llm_client.build_request("hola")
    assert payload["store"] is False
    assert payload["stream"] is False
    assert "temperature" not in payload
    assert payload["reasoning"]["effort"] == prompt_contract.REASONING_EFFORT


# --- Valid six-label output --------------------------------------------------------------


@pytest.mark.parametrize("label", prompt_contract.LABELS)
def test_every_six_label_output_is_parsed_as_valid(label: str):
    client = FakeClient(FakeResponse(output_text=json.dumps({"label": label})))
    record = llm_client.classify(client, prompt_contract.MODEL_PRIMARY, "texto")
    assert record["predicted_label"] == label
    assert record["outcome"] == llm_client.OUTCOME_VALID
    assert record["api_error"] is None


def test_classification_records_latency_and_usage_when_returned():
    client = FakeClient(
        FakeResponse(output_text='{"label":"REVERSED"}', input_tokens=120, output_tokens=7)
    )
    record = llm_client.classify(client, prompt_contract.MODEL_PRIMARY, "texto")
    assert record["latency_ms"] > 0
    assert record["input_tokens"] == 120
    assert record["output_tokens"] == 7


def test_classification_survives_absent_usage():
    client = FakeClient(
        FakeResponse(output_text='{"label":"REVERSED"}', input_tokens=None, output_tokens=None)
    )
    record = llm_client.classify(client, prompt_contract.MODEL_PRIMARY, "texto")
    assert record["input_tokens"] is None
    assert record["output_tokens"] is None


def test_out_of_enum_label_is_an_invalid_structured_output_not_a_seventh_class():
    client = FakeClient(FakeResponse(output_text='{"label":"ESCALATE"}'))
    record = llm_client.classify(client, prompt_contract.MODEL_PRIMARY, "texto")
    assert record["predicted_label"] is None
    assert record["structured_output_valid"] is False
    assert record["unexpected_label"] == "ESCALATE"


def test_unparseable_output_is_recorded_not_guessed():
    client = FakeClient(FakeResponse(output_text="not json at all"))
    record = llm_client.classify(client, prompt_contract.MODEL_PRIMARY, "texto")
    assert record["predicted_label"] is None
    assert record["api_error_type"] == "unparseable_structured_output"


# --- Refusal and failure handling -------------------------------------------------------


def test_model_refusal_is_recorded_separately_with_no_prediction():
    client = FakeClient(FakeResponse(refusal="I cannot classify this."))
    record = llm_client.classify(client, prompt_contract.MODEL_PRIMARY, "texto")
    assert record["outcome"] == llm_client.OUTCOME_REFUSED
    assert record["predicted_label"] is None
    assert record["refusal"] == "I cannot classify this."


def test_transport_failure_never_raises_and_records_no_prediction():
    client = FakeClient(error=RuntimeError("connection reset"))
    record = llm_client.classify(client, prompt_contract.MODEL_PRIMARY, "texto")
    assert record["outcome"] == llm_client.OUTCOME_API_FAILURE
    assert record["predicted_label"] is None
    assert record["api_error_type"] == "RuntimeError"
    assert "connection reset" in record["api_error"]


def test_billing_quota_failure_is_infrastructure_not_a_model_prediction():
    """The condition that closed Phase 4B-1: exhausted credits must never become a label.

    Pinned so that no future change can quietly map a 429 onto a class, invent usage to price it, or
    let an outage satisfy the pre-registered gate.
    """

    client = FakeClient(
        error=FakeBillingError("Error code: 429 - credit_balance_exhausted: no credits remaining")
    )
    record = llm_client.classify(client, prompt_contract.MODEL_PRIMARY, "texto")
    assert record["outcome"] == llm_client.OUTCOME_API_FAILURE
    assert record["predicted_label"] is None
    assert "credit_balance_exhausted" in record["api_error"]

    records = [
        {
            **record,
            "id": f"x{index}",
            "gold_label": label,
            "language": "es",
            "tier": "DIRECT",
            "input_tokens": None,
            "output_tokens": None,
        }
        for index, label in enumerate(prompt_contract.LABELS)
    ]
    summary = llm_metrics.summarize(records, prompt_contract.MODEL_PRIMARY)
    overall = summary["overall"]
    assert overall["valid_predictions"] == 0
    assert overall["api_failures"] == len(prompt_contract.LABELS)
    assert overall["refusals"] == 0
    assert overall["errors"] == len(prompt_contract.LABELS)
    # No seventh class appears and no class borrows credit from the outage.
    assert set(overall["per_class"]) == set(prompt_contract.LABELS)
    assert all(block["f1"] == 0.0 for block in overall["per_class"].values())
    # Usage was never returned, so no cost may be invented for it.
    cost = llm_metrics.estimate_cost(summary, prompt_contract.PRICING)
    assert cost["estimated_cost_usd"] is None
    # An outage must not be able to pass the gate.
    gate = llm_metrics.evaluate_gate(summary, prompt_contract.QUALITY_GATE)
    assert gate["passed"] is False
    assert gate["checks"]["structured_output_validity"]["passed"] is False


def test_incomplete_response_is_an_api_failure():
    client = FakeClient(
        FakeResponse(output_text=None, status="incomplete", incomplete_reason="content_filter")
    )
    record = llm_client.classify(client, prompt_contract.MODEL_PRIMARY, "texto")
    assert record["outcome"] == llm_client.OUTCOME_API_FAILURE
    assert record["api_error_type"] == "incomplete_response"


def test_missing_credential_stops_before_any_call():
    with pytest.raises(llm_client.MissingCredentialError):
        llm_client.require_api_key()


def test_missing_credential_means_no_client_can_be_built(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(llm_client.API_KEY_ENV_VAR, raising=False)
    with pytest.raises(llm_client.MissingCredentialError):
        llm_client.require_api_key()


def test_classify_all_runs_entirely_offline_and_keeps_local_fields():
    examples = [
        {
            "id": "x1",
            "text": "a",
            "language": "es",
            "tier": "DIRECT",
            "label": "REVERSED",
        },
        {
            "id": "x2",
            "text": "b",
            "language": "pt",
            "tier": "HARD_NEGATIVE",
            "label": "PENDING_OR_DELAYED",
        },
    ]
    client = FakeClient(FakeResponse(output_text='{"label":"REVERSED"}'))
    records = llm_client.classify_all(client, prompt_contract.MODEL_PRIMARY, examples)
    assert [record["id"] for record in records] == ["x1", "x2"]
    assert records[0]["gold_label"] == "REVERSED"
    assert records[1]["gold_label"] == "PENDING_OR_DELAYED"
    assert records[1]["predicted_label"] == "REVERSED"
    # Only the text was ever sent.
    assert [call["input"][1]["content"] for call in client.responses.calls] == ["a", "b"]


# --- Challenge hash validation and v2 immutability -------------------------------------


def test_challenge_hash_matches_the_frozen_v2_artifact():
    verified = challenge_io.verify_challenge()
    assert verified["verified"] is True
    assert verified["sha256"] == prompt_contract.EXPECTED_CHALLENGE_SHA256
    assert verified["sha256"] == hashlib.sha256(CHALLENGE_PATH.read_bytes()).hexdigest()
    assert verified["version"] == prompt_contract.EXPECTED_CHALLENGE_VERSION
    assert verified["frozen_before_any_model_run"] is True


def test_altered_challenge_hash_is_rejected(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(challenge_io, "sha256_of", lambda _path: "0" * 64)
    with pytest.raises(challenge_io.ChallengeVerificationError):
        challenge_io.verify_challenge()


def test_missing_freeze_flag_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    freeze = json.loads(V2_FREEZE_PATH.read_text(encoding="utf-8"))
    tampered = dict(freeze)
    tampered["frozen_before_any_model_run"] = False
    fake_freeze = tmp_path / "freeze.json"
    fake_freeze.write_text(json.dumps(tampered), encoding="utf-8")
    monkeypatch.setattr(challenge_io, "FREEZE_PATH", fake_freeze)
    with pytest.raises(challenge_io.ChallengeVerificationError):
        challenge_io.verify_challenge()


def test_loading_examples_does_not_mutate_challenge_v2():
    def snapshot() -> dict[str, str]:
        return {
            path.relative_to(CHALLENGE_PATH.parent).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sorted(CHALLENGE_PATH.parent.rglob("*"))
            if path.is_file()
        }

    before = snapshot()
    examples = challenge_io.load_examples()
    assert len(examples) == 600
    assert snapshot() == before
    assert before[f"reports/{V2_FREEZE_PATH.name}"] is not None
    assert before["challenge.json"] == prompt_contract.EXPECTED_CHALLENGE_SHA256


def test_challenge_reader_exposes_no_write_path():
    """Structural guard: the v2 reader must never contain a write call."""

    source = (LLM_DIR / "challenge_io.py").read_text(encoding="utf-8")
    for forbidden in ("write_text", "write_bytes", "unlink", "rmtree", "shutil", '"w"'):
        assert forbidden not in source


def test_evaluation_area_never_references_a_v2_write_or_regeneration_script():
    for path in LLM_DIR.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "generate_challenge_v2" not in source
        assert "CHALLENGE_PATH.write" not in source


# --- Metrics ----------------------------------------------------------------------------


def _record(gold: str, predicted: str | None, outcome: str, **extra: Any) -> dict[str, Any]:
    return {
        "id": extra.get("id", f"id-{gold}-{predicted}-{outcome}"),
        "gold_label": gold,
        "predicted_label": predicted,
        "outcome": outcome,
        "language": extra.get("language", "es"),
        "tier": extra.get("tier", "DIRECT"),
        "latency_ms": extra.get("latency_ms", 100.0),
        "input_tokens": extra.get("input_tokens", 10),
        "output_tokens": extra.get("output_tokens", 2),
        **extra,
    }


def _balanced_perfect() -> list[dict[str, Any]]:
    return [
        _record(label, label, llm_client.OUTCOME_VALID)
        for label in prompt_contract.LABELS
        for _ in range(10)
    ]


def test_perfect_predictions_score_a_perfect_macro_f1():
    summary = llm_metrics.summarize(_balanced_perfect(), prompt_contract.MODEL_PRIMARY)
    overall = summary["overall"]
    assert overall["accuracy"] == 1.0
    assert overall["macro_f1"] == 1.0
    assert overall["macro_precision"] == 1.0
    assert overall["macro_recall"] == 1.0
    assert overall["structured_output_validity"] == 1.0
    assert overall["errors"] == 0
    assert overall["refusals"] == 0


def test_every_class_reports_precision_recall_f1_and_support():
    summary = llm_metrics.summarize(_balanced_perfect(), prompt_contract.MODEL_PRIMARY)
    per_class = summary["overall"]["per_class"]
    assert set(per_class) == set(prompt_contract.LABELS)
    for block in per_class.values():
        assert set(block) == {"precision", "recall", "f1", "support"}
        assert block["support"] == 10


def test_refusals_count_as_errors_and_never_as_a_seventh_class():
    records = _balanced_perfect()
    reversed_indexes = [
        index for index, record in enumerate(records) if record["gold_label"] == "REVERSED"
    ]
    records[reversed_indexes[0]] = _record("REVERSED", None, llm_client.OUTCOME_REFUSED)
    records[reversed_indexes[1]] = _record("REVERSED", None, llm_client.OUTCOME_API_FAILURE)
    summary = llm_metrics.summarize(records, prompt_contract.MODEL_PRIMARY)
    overall = summary["overall"]
    assert overall["refusals"] == 1
    assert overall["api_failures"] == 1
    assert overall["errors"] == 2
    assert overall["accuracy"] == pytest.approx(58 / 60)
    assert overall["structured_output_validity"] == pytest.approx(58 / 60)
    assert overall["per_class"]["REVERSED"]["support"] == 10
    assert set(overall["per_class"]) == set(prompt_contract.LABELS)
    # The gold class loses recall; no extra class appears.
    assert overall["per_class"]["REVERSED"]["recall"] == pytest.approx(8 / 10)


def test_a_never_predicted_class_scores_zero_rather_than_being_excluded():
    records = [_record("OUT_OF_SCOPE", "REVERSED", llm_client.OUTCOME_VALID) for _ in range(10)]
    summary = llm_metrics.summarize(records, prompt_contract.MODEL_PRIMARY)
    assert summary["overall"]["per_class"]["OUT_OF_SCOPE"]["f1"] == 0.0
    assert len(summary["overall"]["per_class"]) == 6


def test_language_and_tier_blocks_are_reported():
    records = _balanced_perfect()
    # Both languages must contain all six classes, otherwise the per-language macro figure would
    # score zero on the classes that language never shows.
    for offset in range(0, len(records), 10):
        for position, record in enumerate(records[offset : offset + 10]):
            record["language"] = "es" if position < 5 else "pt"
    summary = llm_metrics.summarize(records, prompt_contract.MODEL_PRIMARY)
    assert summary["per_language"]["es"]["n"] == 30
    assert summary["per_language"]["pt"]["n"] == 30
    assert summary["per_language"]["es"]["macro_f1"] == 1.0
    assert summary["per_language"]["pt"]["macro_f1"] == 1.0
    tier = summary["per_tier"]["DIRECT"]
    assert tier["n"] == 60
    assert tier["accuracy"] == 1.0
    assert tier["classes_present"] == 6


def test_per_language_macro_f1_is_zero_when_a_class_is_absent_from_that_language():
    records = [
        _record("REVERSED", "REVERSED", llm_client.OUTCOME_VALID, language="es"),
        _record("REVERSED", "REVERSED", llm_client.OUTCOME_VALID, language="pt"),
    ]
    summary = llm_metrics.summarize(records, prompt_contract.MODEL_PRIMARY)
    # Accuracy is perfect, but the fixed six-class macro figure still charges for absent classes.
    assert summary["per_language"]["es"]["accuracy"] == 1.0
    assert summary["per_language"]["es"]["macro_f1"] == pytest.approx(1 / 6)


def test_confusion_pairs_are_ordered_by_frequency():
    records = [
        _record("APPROVED_BUT_UNRESOLVED", "PENDING_OR_DELAYED", llm_client.OUTCOME_VALID),
        _record("APPROVED_BUT_UNRESOLVED", "PENDING_OR_DELAYED", llm_client.OUTCOME_VALID),
        _record("REVERSED", "FAILED_OR_DECLINED", llm_client.OUTCOME_VALID),
    ]
    pairs = llm_metrics.confusion_pairs(records)
    assert list(pairs.values()) == [2, 1]
    assert "APPROVED_BUT_UNRESOLVED -> PENDING_OR_DELAYED" in pairs


def test_latency_percentiles_and_token_totals():
    records = [
        _record("REVERSED", "REVERSED", llm_client.OUTCOME_VALID, latency_ms=float(value))
        for value in range(1, 101)
    ]
    summary = llm_metrics.summarize(records, prompt_contract.MODEL_PRIMARY)
    assert summary["latency_ms"]["p50"] == pytest.approx(50.5)
    assert summary["latency_ms"]["p95"] == pytest.approx(95.05)
    assert summary["latency_ms"]["n"] == 100
    assert summary["tokens"]["total_input_tokens"] == 1000
    assert summary["tokens"]["total_output_tokens"] == 200
    assert summary["tokens"]["usage_coverage"] == 1.0


def test_cost_is_none_when_the_api_returns_no_usage():
    records = [
        _record(
            "REVERSED", "REVERSED", llm_client.OUTCOME_VALID, input_tokens=None, output_tokens=None
        )
        for _ in range(5)
    ]
    cost = llm_metrics.estimate_cost(
        llm_metrics.summarize(records, prompt_contract.MODEL_PRIMARY), prompt_contract.PRICING
    )
    assert cost["estimated_cost_usd"] is None
    assert "unavailable" in cost["cost_status"]


def test_cost_uses_documented_rates_and_flags_partial_usage():
    records = [_record("REVERSED", "REVERSED", llm_client.OUTCOME_VALID) for _ in range(4)]
    records[0]["input_tokens"] = None
    summary = llm_metrics.summarize(records, prompt_contract.MODEL_PRIMARY)
    cost = llm_metrics.estimate_cost(summary, prompt_contract.PRICING)
    rates = prompt_contract.PRICING[prompt_contract.MODEL_PRIMARY]
    expected = 3 * 10 / 1e6 * rates["input"] + 4 * 2 / 1e6 * rates["output"]
    assert cost["estimated_cost_usd"] == pytest.approx(expected)
    assert "PARTIAL" in cost["cost_status"]


def test_luna_is_cheaper_than_terra_in_the_frozen_pricing():
    rates_luna = prompt_contract.PRICING[prompt_contract.MODEL_PRIMARY]
    rates_terra = prompt_contract.PRICING[prompt_contract.MODEL_CHALLENGER]
    assert rates_luna["input"] == 0.20
    assert rates_luna["output"] == 1.20
    assert rates_terra["input"] == 2.00
    assert rates_terra["output"] == 12.00


# --- Pre-registered gate -----------------------------------------------------------------


def _summary_with(macro_f1: float, validity: float = 1.0) -> dict[str, Any]:
    per_class = {}
    for label in prompt_contract.LABELS:
        f1 = macro_f1
        if label == "OUT_OF_SCOPE":
            f1 = max(macro_f1, 0.9)
        per_class[label] = {"precision": f1, "recall": f1, "f1": f1, "support": 100}
    return {
        "model": prompt_contract.MODEL_PRIMARY,
        "overall": {
            "n": 600,
            "accuracy": macro_f1,
            "correct": int(macro_f1 * 600),
            "errors": int((1 - macro_f1) * 600),
            "macro_precision": macro_f1,
            "macro_recall": macro_f1,
            "macro_f1": macro_f1,
            "per_class": per_class,
            "structured_output_validity": validity,
            "valid_predictions": int(validity * 600),
            "invalid_structured_output": 0,
            "refusals": 0,
            "api_failures": 0,
            "refusal_rate": 0.0,
            "api_failure_rate": 0.0,
            "unusable_rate": 0.0,
        },
        "per_language": {
            "es": {"n": 312, "accuracy": macro_f1, "macro_f1": macro_f1},
            "pt": {"n": 288, "accuracy": macro_f1, "macro_f1": macro_f1},
        },
        "per_tier": {},
        "latency_ms": {"n": 600, "p50": 100.0, "p95": 200.0, "min": 50.0, "max": 400.0},
        "tokens": {
            "records_with_usage": 600,
            "records_total": 600,
            "usage_coverage": 1.0,
            "total_input_tokens": 6000,
            "total_output_tokens": 600,
        },
    }


def test_gate_passes_a_strong_clean_run():
    result = llm_metrics.evaluate_gate(_summary_with(0.90), prompt_contract.QUALITY_GATE)
    assert result["passed"] is True
    assert result["checks"]["overall_macro_f1"]["passed"] is True
    assert result["checks"]["no_critical_systematic_class_failure"]["passed"] is True


def test_gate_fails_below_the_overall_threshold():
    result = llm_metrics.evaluate_gate(_summary_with(0.70), prompt_contract.QUALITY_GATE)
    assert result["passed"] is False
    assert result["checks"]["overall_macro_f1"]["passed"] is False


def test_gate_fails_on_a_language_shortfall():
    summary = _summary_with(0.95)
    summary["per_language"]["pt"]["macro_f1"] = 0.50
    result = llm_metrics.evaluate_gate(summary, prompt_contract.QUALITY_GATE)
    assert result["passed"] is False
    assert result["checks"]["pt_macro_f1"]["passed"] is False
    assert result["checks"]["es_macro_f1"]["passed"] is True


def test_gate_fails_on_structured_output_validity():
    result = llm_metrics.evaluate_gate(
        _summary_with(0.95, validity=0.90), prompt_contract.QUALITY_GATE
    )
    assert result["checks"]["structured_output_validity"]["passed"] is False
    assert result["passed"] is False


def test_gate_flags_a_critical_systematic_in_scope_class():
    summary = _summary_with(0.95)
    summary["overall"]["per_class"]["REVERSED"] = {
        "precision": 0.2,
        "recall": 0.2,
        "f1": 0.2,
        "support": 100,
    }
    result = llm_metrics.evaluate_gate(summary, prompt_contract.QUALITY_GATE)
    assert result["passed"] is False
    critical = result["checks"]["no_critical_systematic_class_failure"]["value"]
    labels = [item["label"] for item in critical]
    assert "REVERSED" in labels


def test_gate_thresholds_are_the_pre_registered_values():
    gate = prompt_contract.QUALITY_GATE
    assert gate["overall_macro_f1_min"] == 0.85
    assert gate["es_macro_f1_min"] == 0.82
    assert gate["pt_macro_f1_min"] == 0.82
    assert gate["structured_output_validity_min"] == 0.99
    assert "NOT production-ready banking AI" in gate["meaning"]


@FREEZE_SKIP
def test_quality_gate_was_recorded_before_any_result_artifact_exists():
    gate = json.loads(QUALITY_GATE_PATH.read_text(encoding="utf-8"))
    assert gate["recorded_before_any_benchmark_result"] is True
    assert gate["immutable_after_results"] is True
    assert gate["gate_version"] == prompt_contract.QUALITY_GATE["gate_version"]
    assert gate["overall_macro_f1_min"] == 0.85
    result_artifacts = [
        path
        for path in REPORTS_DIR.glob("*.json")
        if path.name.startswith(
            ("metrics_", "predictions_", "comparison", "gate_", "cost_", "error_analysis_")
        )
    ]
    assert not result_artifacts, f"gate must precede results; found {result_artifacts}"


def test_closure_record_reports_a_benchmark_that_never_ran():
    """Phase 4B-1 closed without results: the record must say so and carry no metric values."""

    status = json.loads((REPORTS_DIR / "execution_status.json").read_text(encoding="utf-8"))
    assert status["benchmark_state"] == "not_executed"
    assert status["harness_state"] == "complete_and_validated"
    assert status["blocker"]["error_code"] == "credit_balance_exhausted"
    assert status["blocker"]["error_type"] == "insufficient_quota"
    assert status["blocker"]["accepted_model_responses"] == 0
    # Absent, not zero: no populated metric may exist for either candidate.
    assert status["results"]["models_evaluated"] == []
    assert status["results"]["complete_runs"] == []
    for field, value in status["results"].items():
        if field not in {"note", "models_evaluated", "complete_runs"}:
            assert value is None, f"{field} must stay unmeasured, found {value!r}"
    # The gate is pre-registered and unobserved, so neither candidate passed or failed it.
    assert status["quality_gate"]["verdict_for_luna"] == "unobserved"
    assert status["quality_gate"]["verdict_for_terra"] == "unobserved"
    assert status["quality_gate"]["observed_for"] == []
    # Nothing was promoted, and the runtime needs no credential.
    assert status["production_impact"]["approved_for_production_integration"] == []
    assert status["production_impact"]["llm_integrated_into_production"] is False
    assert status["production_impact"]["minilm_integrated_into_production"] is False
    assert status["production_impact"]["application_requires_openai_api_key"] is False
    # Phase 4A stays authoritative and keeps its recorded numbers.
    assert status["authoritative_evidence"]["minilm_logistic_regression_raw"]["macro_f1"] == (
        pytest.approx(0.5914926408627067)
    )
    assert status["secrets"]["api_key_stored_here"] is False
    assert status["secrets"]["request_identifiers_stored_here"] is False
    # The closure changed nothing that must stay frozen.
    assert status["frozen_artifacts_unmodified"]["prompt_sha256"] == prompt_contract.prompt_sha256()
    assert status["frozen_artifacts_unmodified"]["schema_sha256"] == prompt_contract.schema_sha256()
    assert status["frozen_artifacts_unmodified"]["challenge_sha256"] == (
        prompt_contract.EXPECTED_CHALLENGE_SHA256
    )


@FREEZE_SKIP
def test_model_selection_rule_was_frozen():
    frozen = json.loads(PROMPT_FREEZE_PATH.read_text(encoding="utf-8"))
    rule = frozen["model_selection_rule"]
    assert rule["material_quality_delta_macro_f1"] == 0.02
    assert "no integration" in rule["scope_note"]
    assert "guarded integration" in rule["scope_note"]


# --- Evaluation artifact parsing ---------------------------------------------------------


@FREEZE_SKIP
def test_prompt_freeze_artifact_parses_and_pins_everything():
    frozen = json.loads(PROMPT_FREEZE_PATH.read_text(encoding="utf-8"))
    assert frozen["phase"] == "4B-1"
    assert frozen["frozen_before_any_benchmark_result"] is True
    assert frozen["models"] == list(prompt_contract.MODELS)
    assert frozen["frozen_challenge"]["sha256"] == prompt_contract.EXPECTED_CHALLENGE_SHA256
    assert frozen["quality_gate"]["overall_macro_f1_min"] == 0.85
    config = frozen["evaluation_config"]
    assert config["endpoint"] == "responses"
    assert config["structured_outputs"] is True
    assert config["tools_enabled"] is False
    assert config["web_search"] is False
    assert config["total_examples"] == 600
    assert config["reasoning_effort"] == prompt_contract.REASONING_EFFORT


@FREEZE_SKIP
def test_frozen_config_never_advertises_unimplemented_behaviour():
    # Regression guard: the config once declared max_retries/retry_backoff_seconds while the
    # client never retried. The frozen config must describe only what the harness actually does.
    config = json.loads(PROMPT_FREEZE_PATH.read_text(encoding="utf-8"))["evaluation_config"]
    assert config == prompt_contract.evaluation_config()
    assert config["retries"] == 0
    assert "max_retries" not in config
    assert "retry_backoff_seconds" not in config
    assert [key for key in config if "retr" in key] == ["retries", "retries_reason"]

    client_source = (LLM_DIR / "client.py").read_text(encoding="utf-8")
    assert "retry_backoff" not in client_source
    # Retries are disabled explicitly, because the SDK defaults to retrying twice.
    assert "max_retries=0" in client_source
    # The request payload itself must not ask for automatic retries either.
    request = llm_client.build_request("hola")
    assert "max_retries" not in json.dumps(request)


@FREEZE_SKIP
def test_freeze_records_that_it_predates_the_model_run():
    frozen = json.loads(PROMPT_FREEZE_PATH.read_text(encoding="utf-8"))
    assert frozen["challenge_verified_at_freeze_time"]["sha256"] == (
        prompt_contract.EXPECTED_CHALLENGE_SHA256
    )
    assert frozen["no_challenge_examples_in_prompt"] is True


def test_prediction_artifact_round_trips(evaluate_llm: Any, tmp_path: Path):
    records = llm_client.classify_all(
        FakeClient(FakeResponse(output_text='{"label":"REVERSED"}')),
        prompt_contract.MODEL_PRIMARY,
        [
            {
                "id": "a",
                "text": "x",
                "language": "es",
                "tier": "DIRECT",
                "label": "REVERSED",
            }
        ],
    )
    payload = {
        "phase": "4B-1",
        "model": prompt_contract.MODEL_PRIMARY,
        "complete_run": False,
        "records": records,
    }
    path = tmp_path / "predictions.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    parsed = json.loads(path.read_text(encoding="utf-8"))
    summary = llm_metrics.summarize(parsed["records"], parsed["model"])
    assert summary["overall"]["n"] == 1
    assert summary["overall"]["accuracy"] == 1.0
    assert evaluate_llm._slug("gpt-5.6-luna") == "gpt_5_6_luna"


# --- Error analysis ----------------------------------------------------------------------


def test_error_categories_are_derived_from_observed_pairs(analyze_errors: Any):
    record = _record("APPROVED_BUT_UNRESOLVED", "PENDING_OR_DELAYED", llm_client.OUTCOME_VALID)
    assert analyze_errors.categorize(record) == "approved_vs_pending"

    assert (
        analyze_errors.categorize(
            _record("REVERSED", "FAILED_OR_DECLINED", llm_client.OUTCOME_VALID)
        )
        == "failure_bucket"
    )
    assert (
        analyze_errors.categorize(
            _record("AMBIGUOUS_TRANSACTION", None, llm_client.OUTCOME_REFUSED)
        )
        == "model_refusal"
    )
    assert (
        analyze_errors.categorize(_record("REVERSED", None, llm_client.OUTCOME_API_FAILURE))
        == "api_failure"
    )
    assert (
        analyze_errors.categorize(_record("REVERSED", "REVERSED", llm_client.OUTCOME_VALID))
        == "correct"
    )


def test_error_analysis_records_one_row_per_error(analyze_errors: Any):
    records = [
        _record("REVERSED", "REVERSED", llm_client.OUTCOME_VALID),
        _record("REVERSED", "FAILED_OR_DECLINED", llm_client.OUTCOME_VALID, language="pt"),
        _record("PENDING_OR_DELAYED", None, llm_client.OUTCOME_REFUSED, tier="HARD_NEGATIVE"),
    ]
    analysis = analyze_errors.analyze(
        prompt_contract.MODEL_PRIMARY,
        {"records": records, "complete_run": False, "challenge": {"sha256": "x"}},
    )
    assert analysis["errors"] == 2
    # Only categories that actually occurred are reported.
    assert analysis["categories"] == {"failure_bucket": 1, "model_refusal": 1}
    assert analysis["confusion_pairs"]["REVERSED -> FAILED_OR_DECLINED"] == 1
    assert analysis["confusion_pairs"]["PENDING_OR_DELAYED -> refused"] == 1
    assert analysis["errors_by_tier"]["HARD_NEGATIVE"]["errors"] == 1
    assert analysis["errors_by_language"]["pt"] == 1
    for row in analysis["per_example"]:
        assert set(row) == {"id", "language", "tier", "gold", "predicted", "outcome", "category"}
    assert analysis["analysis_stage"] == "after_metrics_frozen"


# --- Production code must stay untouched -------------------------------------------------


def test_no_llm_code_is_wired_into_the_production_application():
    for path in (REPO_ROOT / "backend" / "app").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "openai" not in source.lower()
        assert "incident_understanding_llm" not in source


def test_production_contract_is_unchanged():
    from app.workflow.models import IncidentInput

    assert set(IncidentInput.model_fields) == {
        "in_scope",
        "approved_with_unresolved_issue",
        "transaction_id",
        "filters",
    }
    assert IncidentInput.model_config["extra"] == "forbid"
    assert IncidentInput.model_config["strict"] is True


def test_evaluation_dependency_is_not_a_runtime_dependency():
    import tomllib

    pyproject = tomllib.loads(
        (REPO_ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8")
    )
    runtime = pyproject["project"]["dependencies"]
    evaluation = pyproject["project"]["optional-dependencies"]["evaluation"]
    assert not any(dep.startswith("openai") for dep in runtime)
    assert any(dep.startswith("openai") for dep in evaluation)


def test_no_abstraction_layer_was_introduced():
    banned = ("langchain", "langgraph", "instructor", "llama_index", "haystack", "autogen")
    import tomllib

    pyproject = tomllib.loads(
        (REPO_ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8")
    )
    declared = " ".join(pyproject["project"]["dependencies"]) + " ".join(
        pyproject["project"]["optional-dependencies"]["evaluation"]
    )
    for name in banned:
        assert name not in declared.lower()


def test_no_secret_material_is_stored_in_the_evaluation_area():
    for path in LLM_DIR.rglob("*"):
        if not path.is_file() or path.suffix == ".json":
            continue
        source = path.read_text(encoding="utf-8", errors="ignore")
        assert "sk-" not in source
        assert "OPENAI_API_KEY=" not in source
