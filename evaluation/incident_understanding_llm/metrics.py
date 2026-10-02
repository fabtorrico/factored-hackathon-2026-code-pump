"""Metrics for the Phase 4B-1 LLM classification benchmark.

Pure functions over per-example records. No I/O, no API access, no sibling imports beyond the frozen
label vocabulary in ``prompt_contract``.

Scoring rules, fixed before results:

- A record with a valid prediction is scored normally.
- A refusal or an API failure produces no prediction. It is counted as an incorrect result for
  accuracy and it contributes no predicted label to any class, so it lowers recall. It is never
  mapped to a seventh class and never silently dropped.
- Macro precision, recall and F1 are computed over the fixed six-class label set, so a class the
  system never predicts scores 0.0 rather than being excluded.
- Cost is computed only from records where the API actually returned usage. Partial usage is
  reported as such; cost is never estimated from an assumed token count.
"""

from __future__ import annotations

from typing import Any

from prompt_contract import IN_SCOPE_LABELS, LABELS

VALID = "valid"
REFUSED = "refused"
API_FAILURE = "api_failure"


def _counts(records: list[dict[str, Any]]) -> dict[str, Any]:
    labels = list(LABELS)
    tp = {label: 0 for label in labels}
    fp = {label: 0 for label in labels}
    fn = {label: 0 for label in labels}

    correct = 0
    valid_predictions = 0
    refused = 0
    api_failures = 0
    invalid_structure = 0

    for record in records:
        gold = record["gold_label"]
        predicted = record.get("predicted_label")
        outcome = record.get("outcome")

        if outcome == REFUSED:
            refused += 1
            fn[gold] += 1
        elif outcome == API_FAILURE:
            api_failures += 1
            fn[gold] += 1
        elif predicted not in labels:
            # Structurally invalid output: the schema guarantees this cannot happen, so treat it
            # exactly like a failure instead of crediting a guess.
            invalid_structure += 1
            fn[gold] += 1
        else:
            valid_predictions += 1
            if predicted == gold:
                correct += 1
                tp[gold] += 1
            else:
                fn[gold] += 1
                fp[predicted] += 1

    per_class = {}
    for label in labels:
        support = tp[label] + fn[label]
        precision = tp[label] / (tp[label] + fp[label]) if (tp[label] + fp[label]) else 0.0
        recall = tp[label] / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }

    macro_precision = sum(per_class[label]["precision"] for label in labels) / len(labels)
    macro_recall = sum(per_class[label]["recall"] for label in labels) / len(labels)
    macro_f1 = sum(per_class[label]["f1"] for label in labels) / len(labels)

    total = len(records)

    return {
        "n": total,
        "accuracy": correct / total if total else 0.0,
        "correct": correct,
        "errors": total - correct,
        "macro_precision": macro_precision,
        "macro_recall": macro_recall,
        "macro_f1": macro_f1,
        "per_class": per_class,
        "structured_output_validity": valid_predictions / total if total else 0.0,
        "valid_predictions": valid_predictions,
        "invalid_structured_output": invalid_structure,
        "refusals": refused,
        "api_failures": api_failures,
        "refusal_rate": refused / total if total else 0.0,
        "api_failure_rate": api_failures / total if total else 0.0,
        "unusable_rate": (total - valid_predictions) / total if total else 0.0,
    }


def _percentile(values: list[float], fraction: float) -> float | None:
    """Linear-interpolation percentile on the sorted sample. None for an empty sample."""

    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = fraction * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _subset(records: list[dict[str, Any]], key: str, value: str) -> list[dict[str, Any]]:
    return [record for record in records if record.get(key) == value]


def summarize(records: list[dict[str, Any]], model: str) -> dict[str, Any]:
    """Full metric block for one model's per-example records."""

    overall = _counts(records)

    languages = {}
    for language in ("es", "pt"):
        subset = _subset(records, "language", language)
        if subset:
            languages[language] = {
                "n": len(subset),
                "accuracy": _counts(subset)["accuracy"],
                "macro_f1": _counts(subset)["macro_f1"],
                "macro_precision": _counts(subset)["macro_precision"],
                "macro_recall": _counts(subset)["macro_recall"],
            }

    tiers = {}
    for tier in sorted({record.get("tier") for record in records if record.get("tier")}):
        subset = _subset(records, "tier", tier)
        block = _counts(subset)
        tiers[tier] = {
            "n": len(subset),
            "accuracy": block["accuracy"],
            # A tier subset rarely contains all six classes; the macro figure is reported with the
            # classes actually present so it is not mistaken for a six-class score.
            "macro_f1_present_classes": block["macro_f1"],
            "classes_present": sum(
                1 for label in LABELS if block["per_class"][label]["support"] > 0
            ),
        }

    latencies = [record["latency_ms"] for record in records if record.get("latency_ms") is not None]
    records_with_any_usage = [
        record
        for record in records
        if record.get("input_tokens") is not None or record.get("output_tokens") is not None
    ]
    # A record is only complete when both counters came back, so a partial record cannot be
    # reported as a complete run and cannot silently understate input cost.
    records_complete_usage = [
        record
        for record in records
        if record.get("input_tokens") is not None and record.get("output_tokens") is not None
    ]
    # Counted independently: a record that returned input usage but no output usage must still
    # contribute whatever the API did report, so cost is never under-reported.
    input_tokens = sum(
        record["input_tokens"] for record in records if record.get("input_tokens") is not None
    )
    output_tokens = sum(
        record["output_tokens"] for record in records if record.get("output_tokens") is not None
    )

    return {
        "model": model,
        "overall": overall,
        "per_language": languages,
        "per_tier": tiers,
        "latency_ms": {
            "n": len(latencies),
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
            "min": min(latencies) if latencies else None,
            "max": max(latencies) if latencies else None,
        },
        "tokens": {
            "records_with_any_usage": len(records_with_any_usage),
            "records_with_complete_usage": len(records_complete_usage),
            "records_total": len(records),
            "usage_coverage": len(records_complete_usage) / len(records) if records else 0.0,
            "total_input_tokens": input_tokens,
            "total_output_tokens": output_tokens,
        },
    }


def estimate_cost(summary: dict[str, Any], pricing: dict[str, dict[str, float]]) -> dict[str, Any]:
    """Cost from observed token usage and documented rates. None when usage is unavailable."""

    model = summary["model"]
    rates = pricing.get(model)
    tokens = summary["tokens"]
    block: dict[str, Any] = {
        "model": model,
        "pricing_usd_per_million_tokens": rates,
        "records_with_any_usage": tokens["records_with_any_usage"],
        "records_with_complete_usage": tokens["records_with_complete_usage"],
        "records_total": tokens["records_total"],
        "usage_coverage": tokens["usage_coverage"],
        "total_input_tokens": tokens["total_input_tokens"],
        "total_output_tokens": tokens["total_output_tokens"],
    }
    if not rates or tokens["records_with_any_usage"] == 0:
        block["estimated_cost_usd"] = None
        block["cost_status"] = "unavailable: the API returned no token usage for this run"
        return block

    cost = (
        tokens["total_input_tokens"] / 1_000_000 * rates["input"]
        + tokens["total_output_tokens"] / 1_000_000 * rates["output"]
    )
    block["estimated_cost_usd"] = cost
    complete = tokens["records_with_complete_usage"] == tokens["records_total"]
    block["cost_status"] = (
        "observed usage, all records with usage"
        if complete
        else "observed usage, PARTIAL: excludes tokens for records with missing usage counters"
    )
    block["cost_per_example_usd"] = cost / tokens["records_with_any_usage"]
    return block


def evaluate_gate(summary: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
    """Apply the pre-registered gate. Recorded before any result existed; never re-tuned."""

    overall = summary["overall"]
    languages = summary["per_language"]
    per_class = overall["per_class"]

    critical = []
    for label in gate["in_scope_labels"]:
        block = per_class[label]
        if block["f1"] < 0.70:
            critical.append(
                {
                    "label": label,
                    "reason": "in-scope class F1 below 0.70",
                    "f1": block["f1"],
                    "support": block["support"],
                }
            )
        elif block["f1"] < 0.80 and overall["errors"] > 0:
            share = (block["support"] - round(block["f1"] * block["support"])) / overall["errors"]
            if share >= 0.25:
                critical.append(
                    {
                        "label": label,
                        "reason": (
                            "in-scope class below F1 0.80 and contributes >=25% of all errors"
                        ),
                        "f1": block["f1"],
                        "share_of_errors": share,
                        "support": block["support"],
                    }
                )

    checks = {
        "overall_macro_f1": {
            "value": overall["macro_f1"],
            "threshold": gate["overall_macro_f1_min"],
            "passed": overall["macro_f1"] >= gate["overall_macro_f1_min"],
        },
        "es_macro_f1": {
            "value": languages.get("es", {}).get("macro_f1"),
            "threshold": gate["es_macro_f1_min"],
            "passed": (languages.get("es", {}).get("macro_f1") or 0.0) >= gate["es_macro_f1_min"],
        },
        "pt_macro_f1": {
            "value": languages.get("pt", {}).get("macro_f1"),
            "threshold": gate["pt_macro_f1_min"],
            "passed": (languages.get("pt", {}).get("macro_f1") or 0.0) >= gate["pt_macro_f1_min"],
        },
        "structured_output_validity": {
            "value": overall["structured_output_validity"],
            "threshold": gate["structured_output_validity_min"],
            "passed": overall["structured_output_validity"]
            >= gate["structured_output_validity_min"],
        },
        "no_critical_systematic_class_failure": {
            "value": critical,
            "threshold": "no in-scope class may trigger the definition",
            "passed": not critical,
        },
    }

    return {
        "model": summary["model"],
        "gate_version": gate["gate_version"],
        "checks": checks,
        "passed": all(check["passed"] for check in checks.values()),
    }


def confusion_pairs(records: list[dict[str, Any]]) -> dict[str, int]:
    """Observed gold -> predicted error pairs, most frequent first."""

    counts: dict[str, int] = {}
    for record in records:
        gold = record["gold_label"]
        predicted = record.get("predicted_label")
        if predicted == gold:
            continue
        target = predicted if predicted is not None else record.get("outcome", "none")
        counts[f"{gold} -> {target}"] = counts.get(f"{gold} -> {target}", 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def in_scope_labels() -> tuple[str, ...]:
    return IN_SCOPE_LABELS
