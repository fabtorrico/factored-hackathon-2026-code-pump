"""Phase 4B-1 error analysis, comparison and model recommendation.

Runs only after the metrics artifacts exist and are frozen. It never calls the API and never
modifies the prompt, the schema, the models or the frozen Challenge Set v2.

Reads:
    reports/prompt_freeze.json
    reports/metrics_<model>.json
    reports/gate_<model>.json
    reports/cost_<model>.json

Writes:
    reports/error_analysis_<model>.json
    reports/comparison.json

Error categories are derived from the observed gold -> predicted pairs only. A category that does
not appear in the results is not reported, and no category is invented to describe a hypothetical
failure.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

REPORTS_DIR = BASE_DIR / "reports"

# Which observed confusion each gold class is most at risk of. Derived from the taxonomy of the
# label domain, then applied only to pairs that actually occur in the results.
CLASS_CATEGORY = {
    "APPROVED_BUT_UNRESOLVED": "approved_vs_pending",
    "PENDING_OR_DELAYED": "approved_vs_pending",
    "REVERSED": "reversal_confusion",
    "FAILED_OR_DECLINED": "failure_bucket",
    "AMBIGUOUS_TRANSACTION": "ambiguity_confusion",
    "OUT_OF_SCOPE": "scope_confusion",
}


def _slug(model: str) -> str:
    return model.replace(".", "_").replace("-", "_")


def categorize(record: dict[str, Any]) -> str:
    outcome = record.get("outcome")
    if outcome == "refused":
        return "model_refusal"
    if outcome == "api_failure":
        return "api_failure"
    if record.get("predicted_label") is None:
        return "invalid_structured_output"

    gold = record["gold_label"]
    predicted = record["predicted_label"]
    if gold == predicted:
        return "correct"

    if {gold, predicted} == {"APPROVED_BUT_UNRESOLVED", "PENDING_OR_DELAYED"}:
        return "approved_vs_pending"
    if predicted == "FAILED_OR_DECLINED":
        return "failure_bucket"
    return CLASS_CATEGORY.get(gold, "other_confusion")


def analyze(model: str, predictions: dict[str, Any]) -> dict[str, Any]:
    records = predictions["records"]
    errors = [record for record in records if record.get("predicted_label") != record["gold_label"]]

    per_error = []
    for record in errors:
        per_error.append(
            {
                "id": record["id"],
                "language": record["language"],
                "tier": record["tier"],
                "gold": record["gold_label"],
                "predicted": record.get("predicted_label"),
                "outcome": record.get("outcome"),
                "category": categorize(record),
            }
        )

    by_category = Counter(item["category"] for item in per_error)
    by_gold = Counter(item["gold"] for item in per_error)
    by_tier = Counter(item["tier"] for item in per_error)
    by_language = Counter(item["language"] for item in per_error)
    pairs = Counter(
        f"{item['gold']} -> {item['predicted'] if item['predicted'] else item['outcome']}"
        for item in per_error
    )

    tiers = sorted({record["tier"] for record in records})
    tier_error_share = {
        tier: {
            "errors": by_tier.get(tier, 0),
            "share_of_all_errors": (by_tier.get(tier, 0) / len(errors) if errors else 0.0),
        }
        for tier in tiers
    }

    return {
        "phase": "4B-1",
        "analysis_stage": "after_metrics_frozen",
        "model": model,
        "complete_run": predictions.get("complete_run"),
        "challenge": predictions.get("challenge"),
        "prompt_version": predictions.get("prompt_version"),
        "prompt_sha256": predictions.get("prompt_sha256"),
        "total": len(records),
        "errors": len(errors),
        "error_rate": len(errors) / len(records) if records else 0.0,
        "categories": dict(sorted(by_category.items(), key=lambda kv: (-kv[1], kv[0]))),
        "errors_by_gold_class": dict(sorted(by_gold.items(), key=lambda kv: (-kv[1], kv[0]))),
        "errors_by_tier": tier_error_share,
        "errors_by_language": dict(sorted(by_language.items())),
        "confusion_pairs": dict(sorted(pairs.items(), key=lambda kv: (-kv[1], kv[0]))),
        "per_example": per_error,
    }


def compare() -> dict[str, Any]:
    from prompt_contract import FROZEN_V2_REFERENCE, MODELS

    freeze_path = REPORTS_DIR / "prompt_freeze.json"
    if not freeze_path.exists():
        raise SystemExit("prompt_freeze.json missing; freeze before comparing")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))

    blocks: dict[str, Any] = {}
    costs: dict[str, Any] = {}
    gates: dict[str, Any] = {}

    for model in MODELS:
        slug = _slug(model)
        predictions_path = REPORTS_DIR / f"predictions_{slug}.json"
        metrics_path = REPORTS_DIR / f"metrics_{slug}.json"
        if not (predictions_path.exists() and metrics_path.exists()):
            continue
        predictions = json.loads(predictions_path.read_text(encoding="utf-8"))
        analysis = analyze(model, predictions)
        (REPORTS_DIR / f"error_analysis_{slug}.json").write_text(
            json.dumps(analysis, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        blocks[model] = analysis

        gate_path = REPORTS_DIR / f"gate_{slug}.json"
        if gate_path.exists():
            gates[model] = json.loads(gate_path.read_text(encoding="utf-8"))
        cost_path = REPORTS_DIR / f"cost_{slug}.json"
        if cost_path.exists():
            costs[model] = json.loads(cost_path.read_text(encoding="utf-8"))["cost"]

    passed = {
        model: bool(gate.get("result", {}).get("passed")) and bool(gate.get("complete_run"))
        for model, gate in gates.items()
    }

    recommendation = _recommend(passed, costs, freeze, gates)

    return {
        "phase": "4B-1",
        "challenge": freeze.get("frozen_challenge"),
        "prompt_version": freeze["prompt_version"],
        "prompt_sha256": freeze["prompt_sha256"],
        "schema_sha256": freeze["schema_sha256"],
        "models_evaluated": sorted(blocks),
        "complete_runs": {
            model: bool(block.get("complete_run")) for model, block in blocks.items()
        },
        "gate_passed": passed,
        "gate_results": gates,
        "error_analysis_summary": {
            model: {
                "errors": block["errors"],
                "error_rate": block["error_rate"],
                "categories": block["categories"],
                "errors_by_tier": block["errors_by_tier"],
                "confusion_pairs": block["confusion_pairs"],
            }
            for model, block in blocks.items()
        },
        "cost": costs,
        "frozen_v2_reference": FROZEN_V2_REFERENCE,
        "model_selection_rule": freeze.get("model_selection_rule"),
        "recommendation": recommendation,
        "integration_performed": False,
    }


def _recommend(
    passed: dict[str, bool],
    costs: dict[str, Any],
    freeze: dict[str, Any],
    gates: dict[str, Any],
) -> dict[str, Any]:
    rule = freeze["model_selection_rule"]
    from prompt_contract import MODEL_CHALLENGER, MODEL_PRIMARY

    luna_pass = passed.get(MODEL_PRIMARY)
    terra_pass = passed.get(MODEL_CHALLENGER)

    def macro_f1(model: str) -> float | None:
        gate = gates.get(model)
        if not gate:
            return None
        return gate["result"]["checks"]["overall_macro_f1"]["value"]

    def unit_cost(model: str) -> float | None:
        block = costs.get(model)
        return None if block is None else block.get("cost_per_example_usd")

    delta_material = rule["material_quality_delta_macro_f1"]

    if luna_pass is None and terra_pass is None:
        decision, reason = "no_evaluation", "no model has been evaluated yet"
    elif not luna_pass and not terra_pass:
        decision = "no_production_integration"
        reason = "neither Luna nor Terra passes the pre-registered quality gate"
    elif luna_pass and not terra_pass:
        decision, reason = MODEL_PRIMARY, "only Luna passes the pre-registered gate"
    elif terra_pass and not luna_pass:
        decision, reason = MODEL_CHALLENGER, "only Terra passes the pre-registered gate"
    else:
        luna_f1 = macro_f1(MODEL_PRIMARY)
        terra_f1 = macro_f1(MODEL_CHALLENGER)
        luna_cost = unit_cost(MODEL_PRIMARY)
        terra_cost = unit_cost(MODEL_CHALLENGER)
        if luna_f1 is None or terra_f1 is None:
            decision = "undetermined"
            reason = "both passed but a macro-F1 value is unavailable"
        elif terra_f1 - luna_f1 >= delta_material:
            decision = MODEL_CHALLENGER
            reason = (
                f"both pass and Terra's macro-F1 is materially higher by "
                f"{terra_f1 - luna_f1:.4f} >= {delta_material}"
            )
        else:
            decision = MODEL_PRIMARY
            reason = (
                f"both pass and the quality difference {terra_f1 - luna_f1:.4f} is below the "
                f"material delta {delta_material}; Luna is preferred on cost "
                f"({luna_cost} vs {terra_cost} USD per example)"
            )

    return {
        "decision": decision,
        "reason": reason,
        "luna_passes_gate": luna_pass,
        "terra_passes_gate": terra_pass,
        "scope": rule["scope_note"],
        "integration_performed_in_4b1": False,
    }


def main() -> int:
    result = compare()
    models = result["models_evaluated"]
    if not models:
        # Nothing has been benchmarked, so there is nothing to compare. Writing an empty comparison
        # would put a result-shaped artifact on disk before any result exists, which would violate
        # the pre-registered gate-before-results ordering.
        print("Phase 4B-1 comparison skipped: no model has been evaluated yet.")
        print("Run evaluate_llm.py for each candidate first.")
        return 0

    path = REPORTS_DIR / "comparison.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Phase 4B-1 comparison written.")
    print(f"  models evaluated : {', '.join(models)}")
    for model, verdict in result["gate_passed"].items():
        print(f"  gate {model:<16}: {'PASS' if verdict else 'FAIL'}")
    print(f"  recommendation   : {result['recommendation']['decision']}")
    print(f"  reason           : {result['recommendation']['reason']}")
    print(f"  wrote            : {path.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
