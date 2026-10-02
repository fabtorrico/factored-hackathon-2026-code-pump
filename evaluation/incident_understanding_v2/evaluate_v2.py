"""Evaluate the FROZEN v1 baseline and FROZEN v1 learned model on Challenge Set v2.

Steps:
  1. Verify the frozen Challenge Set v2 artifact hash against reports/freeze_v2.json.
  2. Reconstruct the frozen v1 systems (baseline unchanged; learned = MiniLM + LR fit
     ONLY on v1 TRAIN).
  3. Evaluate both systems on v2 and write comparative / error-analysis reports.

This never trains on v2 data and never mutates v1 or v2.

Usage (from the repository root):

    backend/.venv/Scripts/python evaluation/incident_understanding_v2/evaluate_v2.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
REPORTS_DIR = BASE_DIR / "reports"
CHALLENGE_PATH = BASE_DIR / "challenge.json"
FREEZE_PATH = REPORTS_DIR / "freeze_v2.json"
EXPECTED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EXPECTED_THRESHOLD = 0.7
EXPECTED_CLASSIFIER = "sklearn.linear_model.LogisticRegression"
EXPECTED_CLASSIFIER_PARAMS = {"max_iter": 1000, "random_state": 42}

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _load_v1_module() -> Any:
    path = REPO_ROOT / "evaluation" / "incident_understanding" / "run_evaluation.py"
    spec = importlib.util.spec_from_file_location("v1_run_evaluation", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import frozen v1 evaluation module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_v1_train() -> list[dict[str, Any]]:
    path = REPO_ROOT / "evaluation" / "incident_understanding" / "dataset.json"
    with open(path, encoding="utf-8") as handle:
        dataset = json.load(handle)
    return dataset["train"]


def _load_v2() -> dict[str, Any]:
    with open(CHALLENGE_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def _verify_freeze() -> dict[str, Any]:
    if not FREEZE_PATH.exists():
        raise RuntimeError("reports/freeze_v2.json missing: freeze Challenge Set v2 first")
    with open(FREEZE_PATH, encoding="utf-8") as handle:
        freeze = json.load(handle)
    digest = hashlib.sha256(CHALLENGE_PATH.read_bytes()).hexdigest()
    if digest != freeze["sha256"]:
        raise RuntimeError(
            f"Challenge Set v2 hash mismatch: {digest} != {freeze['sha256']} "
            "(the frozen dataset must not be edited)"
        )
    if not freeze.get("frozen_before_any_model_run"):
        raise RuntimeError("freeze artifact does not assert pre-model freezing")
    return freeze


def _verify_frozen_systems(v1: Any) -> dict[str, Any]:
    checks = {
        "baseline_module": "app.ml.baseline.RuleBaseline",
        "embedding_model": v1.PRIMARY_MODEL,
        "classifier": EXPECTED_CLASSIFIER,
        "classifier_params": EXPECTED_CLASSIFIER_PARAMS,
        "threshold": v1.THRESHOLD,
        "fits_only_on_v1_train": True,
    }
    if v1.PRIMARY_MODEL != EXPECTED_MODEL:
        raise RuntimeError(f"frozen model changed: {v1.PRIMARY_MODEL}")
    if v1.THRESHOLD != EXPECTED_THRESHOLD:
        raise RuntimeError(f"frozen threshold changed: {v1.THRESHOLD}")
    return checks


def _per_tier(examples: list[dict[str, Any]], predictions: list[str], v1: Any) -> dict[str, Any]:
    tiers = sorted({e["tier"] for e in examples})
    out: dict[str, Any] = {}
    for tier in tiers:
        sub_true = [e["label"] for e in examples if e["tier"] == tier]
        sub_pred = [p for e, p in zip(examples, predictions, strict=True) if e["tier"] == tier]
        metrics = v1._metrics(sub_true, sub_pred)
        accepted = v1._accepted_metrics(sub_true, sub_pred)
        out[tier] = {
            "n": len(sub_true),
            "accuracy": metrics["accuracy"],
            "macro_f1": metrics["macro_f1"],
            "coverage": accepted["coverage"],
        }
    return out


def _per_class(examples: list[dict[str, Any]], predictions: list[str], v1: Any) -> dict[str, Any]:
    labels = sorted({e["label"] for e in examples})
    y_true = [e["label"] for e in examples]
    out: dict[str, Any] = {}
    for label in labels:
        sub_true = [t for t in y_true if t == label]
        sub_pred = [p for t, p in zip(y_true, predictions, strict=True) if t == label]
        metrics = v1._metrics(sub_true, sub_pred)["per_class"][label]
        out[label] = {
            "support": metrics["support"],
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1": metrics["f1"],
        }
    return out


def _system_report(
    name: str, examples: list[dict[str, Any]], predictions: list[str], v1: Any
) -> dict[str, Any]:
    y_true = [e["label"] for e in examples]
    languages = [e["language"] for e in examples]
    return {
        "system": name,
        "overall": v1._metrics(y_true, predictions),
        "accepted": v1._accepted_metrics(y_true, predictions),
        "per_language": v1._per_language(y_true, predictions, languages),
        "per_class": _per_class(examples, predictions, v1),
        "per_tier": _per_tier(examples, predictions, v1),
    }


def _comparison(
    baseline: dict[str, Any], raw: dict[str, Any], threshold: dict[str, Any]
) -> dict[str, Any]:
    def key(report: dict[str, Any]) -> dict[str, Any]:
        return {
            "accuracy": report["overall"]["accuracy"],
            "macro_f1": report["overall"]["macro_f1"],
            "coverage": report["accepted"]["coverage"],
            "accepted_accuracy": report["accepted"]["accepted_accuracy"],
            "abstention_rate": report["accepted"]["abstention_rate"],
        }

    return {
        "baseline": key(baseline),
        "learned_raw_th0": key(raw),
        "learned_th0_7": key(threshold),
    }


def main() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    freeze = _verify_freeze()
    v1 = _load_v1_module()
    frozen_systems = _verify_frozen_systems(v1)

    v2 = _load_v2()
    examples = v2["examples"]
    train = _load_v1_train()

    baseline_preds = v1._baseline_predict(examples)
    baseline = _system_report("baseline", examples, baseline_preds, v1)

    raw = v1.evaluate_learned(train, examples, v1.PRIMARY_MODEL, 0.0)
    raw_preds = raw.pop("_predictions")
    raw.pop("_confidences")
    raw_report = _system_report("learned_raw_th0", examples, raw_preds, v1)
    raw_report["latency_ms"] = raw["latency_ms"]

    threshold = v1.evaluate_learned(train, examples, v1.PRIMARY_MODEL, v1.THRESHOLD)
    threshold_preds = threshold.pop("_predictions")
    threshold_confidences = threshold.pop("_confidences")
    threshold_report = _system_report("learned_th0_7", examples, threshold_preds, v1)
    threshold_report["latency_ms"] = threshold["latency_ms"]
    threshold_report["model_load_seconds"] = threshold["model_load_seconds"]
    threshold_report["classifier_fit_seconds"] = threshold["classifier_fit_seconds"]

    errors = v1.error_analysis(examples, threshold_preds, threshold_confidences)

    comparison = _comparison(baseline, raw_report, threshold_report)
    summary = {
        "challenge_version": freeze["version"],
        "challenge_sha256": freeze["sha256"],
        "total_examples": len(examples),
        "frozen_systems": frozen_systems,
        "comparison": comparison,
        "baseline_errors": sum(
            1 for e, p in zip(examples, baseline_preds, strict=True) if p != e["label"]
        ),
        "learned_raw_errors": sum(
            1 for e, p in zip(examples, raw_preds, strict=True) if p != e["label"]
        ),
        "learned_threshold_errors": sum(
            1 for e, p in zip(examples, threshold_preds, strict=True) if p != e["label"]
        ),
        "learned_threshold_abstentions": threshold_report["accepted"]["abstained"],
    }

    v1._write(REPORTS_DIR / "v2_baseline.json", baseline)
    v1._write(REPORTS_DIR / "v2_learned_raw.json", raw_report)
    v1._write(REPORTS_DIR / "v2_learned_threshold.json", threshold_report)
    v1._write(REPORTS_DIR / "v2_error_analysis.json", errors)
    v1._write(REPORTS_DIR / "v2_comparison.json", comparison)
    v1._write(REPORTS_DIR / "v2_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
