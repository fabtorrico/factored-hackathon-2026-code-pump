"""Phase 4A reproducible evaluation driver.

Runs the frozen deterministic baseline and the frozen learned model (multilingual
sentence embeddings + Logistic Regression) end to end and writes small JSON/Markdown
artifacts. TEST is only read after the experiment configuration is frozen.

Usage (from the backend directory so `app` is importable):

    backend/.venv/Scripts/python -m evaluation.incident_understanding.run_evaluation

or run this file directly with `--data-dir` pointing at the dataset directory.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any

from app.ml.baseline import RuleBaseline
from app.ml.classifier import EmbeddingClassifier
from app.ml.labels import ALL_LABELS

PRIMARY_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
CHALLENGER_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
SEED = 42
THRESHOLD = 0.7
LABEL_NAMES = [label.value for label in ALL_LABELS]
ABSTAIN = "__ABSTAIN__"


def _load(data_dir: Path) -> dict[str, Any]:
    with open(data_dir / "dataset.json", encoding="utf-8") as handle:
        return json.load(handle)


def _safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _metrics(y_true: list[str], y_pred: list[str]) -> dict[str, Any]:
    # Abstention is handled via coverage; it must never be scored as a class.
    labels = sorted((set(y_true) | set(y_pred)) - {ABSTAIN})
    per_class: dict[str, dict[str, float]] = {}
    for label in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == label and p == label)
        fp = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t != label and p == label)
        fn = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == label and p != label)
        precision = _safe_divide(tp, tp + fp)
        recall = _safe_divide(tp, tp + fn)
        f1 = _safe_divide(2 * precision * recall, precision + recall)
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": sum(1 for t in y_true if t == label),
        }
    macro_precision = statistics.fmean(c["precision"] for c in per_class.values())
    macro_recall = statistics.fmean(c["recall"] for c in per_class.values())
    macro_f1 = statistics.fmean(c["f1"] for c in per_class.values())
    accuracy = _safe_divide(
        sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == p), len(y_true)
    )
    # Confusion matrix over the full label set plus abstention.
    columns = LABEL_NAMES + [ABSTAIN]
    confusion = {label: {c: 0 for c in columns} for label in LABEL_NAMES}
    for t, p in zip(y_true, y_pred, strict=True):
        if t in confusion and p in confusion[t]:
            confusion[t][p] += 1
    return {
        "accuracy": accuracy,
        "macro_precision": macro_precision,
        "macro_recall": macro_recall,
        "macro_f1": macro_f1,
        "per_class": per_class,
        "confusion_matrix": confusion,
    }


def _accepted_metrics(y_true: list[str], raw_predictions: list[str]) -> dict[str, Any]:
    accepted_true = [t for t, p in zip(y_true, raw_predictions, strict=True) if p != ABSTAIN]
    accepted_pred = [p for p in raw_predictions if p != ABSTAIN]
    total = len(raw_predictions)
    abstained = total - len(accepted_pred)
    result: dict[str, Any] = {
        "coverage": _safe_divide(len(accepted_pred), total),
        "abstention_rate": _safe_divide(abstained, total),
        "abstained": abstained,
        "accepted": len(accepted_pred),
        "total": total,
    }
    if accepted_pred:
        result["accepted_accuracy"] = _safe_divide(
            sum(1 for t, p in zip(accepted_true, accepted_pred, strict=True) if t == p),
            len(accepted_pred),
        )
        result["accepted_macro_f1"] = statistics.fmean(
            metrics["f1"]
            for metrics in _metrics(accepted_true, accepted_pred)["per_class"].values()
        )
    else:
        result["accepted_accuracy"] = None
        result["accepted_macro_f1"] = None
    return result


def _per_language(y_true: list[str], y_pred: list[str], languages: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for language in ("es", "pt"):
        sub_true = [t for t, lang in zip(y_true, languages, strict=True) if lang == language]
        sub_pred = [p for p, lang in zip(y_pred, languages, strict=True) if lang == language]
        if not sub_true:
            continue
        metrics = _metrics(sub_true, sub_pred)
        out[language] = {
            "n": len(sub_true),
            "accuracy": metrics["accuracy"],
            "macro_f1": metrics["macro_f1"],
        }
    return out


def _baseline_predict(examples: list[dict[str, Any]]) -> list[str]:
    baseline = RuleBaseline()
    predictions = []
    for example in examples:
        result = baseline.predict(example["text"], example["language"])
        predictions.append(result.label.value if result.label else ABSTAIN)
    return predictions


def evaluate_baseline(examples: list[dict[str, Any]]) -> dict[str, Any]:
    y_true = [e["label"] for e in examples]
    languages = [e["language"] for e in examples]
    y_pred = _baseline_predict(examples)
    return {
        "overall": _metrics(y_true, y_pred),
        "accepted": _accepted_metrics(y_true, y_pred),
        "per_language": _per_language(y_true, y_pred, languages),
    }


def _latency_percentile(samples_ms: list[float], percentile: float) -> float:
    if not samples_ms:
        return 0.0
    ordered = sorted(samples_ms)
    index = min(len(ordered) - 1, int(round((percentile / 100) * (len(ordered) - 1))))
    return ordered[index]


def evaluate_learned(
    train: list[dict[str, Any]],
    examples: list[dict[str, Any]],
    model_name: str,
    threshold: float,
) -> dict[str, Any]:
    classifier = EmbeddingClassifier(model_name=model_name)
    load_start = time.perf_counter()
    classifier._load_model()
    model_load_seconds = time.perf_counter() - load_start

    fit_start = time.perf_counter()
    classifier.fit([e["text"] for e in train], [e["label"] for e in train])
    fit_seconds = time.perf_counter() - fit_start

    texts = [e["text"] for e in examples]
    for text in texts:  # warm-up, excluded from latency measurement
        classifier.predict([text], threshold=threshold)
    samples_ms: list[float] = []
    raw_predictions: list[str] = []
    confidences: list[float] = []
    for text in texts:
        start = time.perf_counter()
        (label, confidence) = classifier.predict([text], threshold=threshold)[0]
        samples_ms.append((time.perf_counter() - start) * 1000)
        raw_predictions.append(label.value if label else ABSTAIN)
        confidences.append(confidence)

    y_true = [e["label"] for e in examples]
    languages = [e["language"] for e in examples]
    return {
        "model": model_name,
        "threshold": threshold,
        "overall": _metrics(y_true, raw_predictions),
        "accepted": _accepted_metrics(y_true, raw_predictions),
        "per_language": _per_language(y_true, raw_predictions, languages),
        "model_load_seconds": model_load_seconds,
        "classifier_fit_seconds": fit_seconds,
        "embedding_dimension": int(classifier._model.get_sentence_embedding_dimension()),
        "latency_ms": {
            "p50": _latency_percentile(samples_ms, 50),
            "p95": _latency_percentile(samples_ms, 95),
        },
        "_predictions": raw_predictions,
        "_confidences": confidences,
    }


def threshold_grid(
    train: list[dict[str, Any]], dev: list[dict[str, Any]], model_name: str
) -> list[dict[str, Any]]:
    classifier = EmbeddingClassifier(model_name=model_name)
    classifier.fit([e["text"] for e in train], [e["label"] for e in train])
    y_true = [e["label"] for e in dev]
    texts = [e["text"] for e in dev]
    grid = []
    for threshold in (0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9):
        raw = [
            (label.value if label else ABSTAIN)
            for label, _ in classifier.predict(texts, threshold=threshold)
        ]
        accepted = _accepted_metrics(y_true, raw)
        grid.append({"threshold": threshold, **accepted})
    return grid


def error_analysis(
    examples: list[dict[str, Any]],
    predictions: list[str],
    confidences: list[float],
) -> list[dict[str, Any]]:
    errors = []
    for example, predicted, confidence in zip(examples, predictions, confidences, strict=True):
        if predicted == example["label"]:
            continue
        errors.append(
            {
                "id": example["id"],
                "language": example["language"],
                "expected_label": example["label"],
                "predicted_label": predicted,
                "confidence": round(confidence, 4),
                "semantic_family": example["semantic_family"],
                "error_category": _categorize(example["label"], predicted, example["text"]),
            }
        )
    return errors


def _categorize(expected: str, predicted: str, text: str) -> str:
    if predicted == ABSTAIN:
        return "low_confidence_abstention"
    if {expected, predicted} == {"FAILED_OR_DECLINED", "AMBIGUOUS_TRANSACTION"}:
        return "failed_vs_ambiguous_boundary"
    if {expected, predicted} == {"PENDING_OR_DELAYED", "APPROVED_BUT_UNRESOLVED"}:
        return "pending_vs_approved_boundary"
    lowered = text.lower()
    if any(token in lowered for token in ("no ", "não ", "nao ", "sin ")):
        return "negation"
    return "lexical_overlap_or_indirect"


def _write(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
    )
    parser.add_argument("--skip-challenger", action="store_true")
    args = parser.parse_args()
    data_dir: Path = args.data_dir
    reports = data_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    dataset = _load(data_dir)
    train, dev, test = dataset["train"], dataset["dev"], dataset["test"]

    # DEV phase: model comparison and threshold selection (TEST untouched here).
    dev_baseline = evaluate_baseline(dev)
    _write(reports / "dev_baseline.json", dev_baseline)

    grid = threshold_grid(train, dev, PRIMARY_MODEL)
    _write(reports / "threshold_analysis.json", grid)

    dev_primary = evaluate_learned(train, dev, PRIMARY_MODEL, THRESHOLD)
    dev_comparison = {
        "primary": {k: v for k, v in dev_primary.items() if not k.startswith("_")},
    }
    if not args.skip_challenger:
        try:
            dev_challenger = evaluate_learned(train, dev, CHALLENGER_MODEL, THRESHOLD)
            dev_comparison["challenger"] = {
                k: v for k, v in dev_challenger.items() if not k.startswith("_")
            }
        except Exception as exc:  # noqa: BLE001 - operational constraint must be recorded
            dev_comparison["challenger"] = {"error": repr(exc)}
    _write(reports / "dev_comparison.json", dev_comparison)

    # Freeze artifact is written before TEST is read.
    freeze = {
        "embedding_model": PRIMARY_MODEL,
        "challenger_model": CHALLENGER_MODEL,
        "classifier": "sklearn.linear_model.LogisticRegression",
        "classifier_params": {"max_iter": 1000, "random_state": SEED},
        "random_seed": SEED,
        "split_seed": dataset["metadata"]["seed"],
        "selected_confidence_threshold": THRESHOLD,
        "label_set": LABEL_NAMES,
        "baseline": "app.ml.baseline.RuleBaseline (frozen regex rules, v1)",
        "frozen_at": "after DEV comparison and threshold selection, before TEST",
    }
    _write(reports / "freeze_config.json", freeze)

    # TEST phase: only after freeze.
    test_baseline = evaluate_baseline(test)
    _write(reports / "test_baseline.json", test_baseline)

    test_learned = evaluate_learned(train, test, PRIMARY_MODEL, THRESHOLD)
    predictions = test_learned.pop("_predictions")
    confidences = test_learned.pop("_confidences")
    _write(reports / "test_learned.json", test_learned)

    errors = error_analysis(test, predictions, confidences)
    _write(reports / "error_analysis.json", errors)

    summary = {
        "dev_baseline": dev_baseline["overall"],
        "dev_primary": dev_primary["overall"],
        "test_baseline": test_baseline["overall"],
        "test_learned": test_learned["overall"],
        "test_learned_accepted": test_learned["accepted"],
        "test_learned_per_language": test_learned["per_language"],
        "latency_ms": test_learned["latency_ms"],
        "errors": len(errors),
    }
    _write(reports / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
