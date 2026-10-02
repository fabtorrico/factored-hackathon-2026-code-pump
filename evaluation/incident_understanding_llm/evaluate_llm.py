"""Run the Phase 4B-1 LLM classification benchmark against the frozen Challenge Set v2.

This is the explicit benchmark command. It requires OPENAI_API_KEY and refuses to run without it,
refuses to run before the prompt freeze exists, and refuses to run if the prompt or schema has
drifted from the freeze.

    # freeze once, before any model is called
    backend/.venv/Scripts/python evaluation/incident_understanding_llm/freeze_prompt.py

    # then, with OPENAI_API_KEY set in the environment, one model at a time
    backend/.venv/Scripts/python evaluation/incident_understanding_llm/evaluate_llm.py \
        --model gpt-5.6-luna
    backend/.venv/Scripts/python evaluation/incident_understanding_llm/evaluate_llm.py \
        --model gpt-5.6-terra

Artifacts written per model, all under ``evaluation/incident_understanding_llm/reports/``:
``predictions_<model>.json``, ``metrics_<model>.json``, ``gate_<model>.json``,
``cost_<model>.json``. Nothing in the challenge directory is read for anything but verified,
hash-checked, read-only input.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

REPORTS_DIR = BASE_DIR / "reports"
PROMPT_FREEZE_PATH = REPORTS_DIR / "prompt_freeze.json"
QUALITY_GATE_PATH = REPORTS_DIR / "quality_gate.json"


def _slug(model: str) -> str:
    return model.replace(".", "_").replace("-", "_")


def _fail(message: str) -> None:
    raise SystemExit(f"Phase 4B-1 stopped: {message}")


def _missing_credential_error() -> type[BaseException]:
    """Import the credential error lazily so this module stays importable without the SDK."""

    from client import MissingCredentialError

    return MissingCredentialError


def verify_freeze_alignment() -> dict[str, Any]:
    """Refuse to run unless the freeze exists and the live prompt/schema still match it."""

    if not PROMPT_FREEZE_PATH.exists():
        _fail(f"prompt freeze missing at {PROMPT_FREEZE_PATH}; run freeze_prompt.py first")
    if not QUALITY_GATE_PATH.exists():
        _fail(f"quality gate missing at {QUALITY_GATE_PATH}; run freeze_prompt.py first")

    from prompt_contract import freeze_artifact

    frozen = json.loads(PROMPT_FREEZE_PATH.read_text(encoding="utf-8"))
    live = freeze_artifact()

    for field in ("prompt_version", "prompt_sha256", "schema_sha256"):
        if frozen.get(field) != live[field]:
            _fail(f"{field} changed after the freeze: {frozen.get(field)!r} -> {live[field]!r}")

    return frozen


def load_gate() -> dict[str, Any]:
    return json.loads(QUALITY_GATE_PATH.read_text(encoding="utf-8"))


def run(model: str, limit: int | None, out_dir: Path) -> dict[str, Any]:
    freeze = verify_freeze_alignment()
    gate = load_gate()

    from challenge_io import load_examples, verify_challenge
    from client import API_KEY_ENV_VAR, build_client, classify_all, require_api_key
    from metrics import confusion_pairs, estimate_cost, evaluate_gate, summarize
    from prompt_contract import PRICING, evaluation_config

    # Credential check happens before any example is sent, and the key itself is never stored,
    # logged or written to an artifact.
    require_api_key()
    print(f"{API_KEY_ENV_VAR} present.")

    challenge = verify_challenge()
    print(f"Challenge Set v2 verified: {challenge['sha256']} (version {challenge['version']})")

    examples = load_examples()
    total_available = len(examples)
    selected = examples if limit is None else examples[:limit]
    if len(selected) != total_available:
        print(
            f"PARTIAL RUN: {len(selected)} of {total_available} examples. "
            "Artifacts will be marked incomplete and cannot pass the gate."
        )

    client = build_client()
    started_at = datetime.now(UTC)
    started_perf = time.perf_counter()

    def progress(index: int, total: int, record: dict[str, Any]) -> None:
        if index % 25 == 0 or index == total:
            print(f"  [{index}/{total}] last={record.get('predicted_label')}", flush=True)

    records = classify_all(client, model, selected, progress=progress)
    elapsed = time.perf_counter() - started_perf

    summary = summarize(records, model)
    gate_result = evaluate_gate(summary, gate)
    cost = estimate_cost(summary, PRICING)
    config = evaluation_config()

    out_dir.mkdir(parents=True, exist_ok=True)
    slug = _slug(model)
    complete = len(selected) == total_available

    predictions = {
        "phase": "4B-1",
        "model": model,
        "challenge": challenge,
        "complete_run": complete,
        "examples_evaluated": len(records),
        "examples_available": total_available,
        "prompt_version": freeze["prompt_version"],
        "prompt_sha256": freeze["prompt_sha256"],
        "schema_sha256": freeze["schema_sha256"],
        "evaluation_config": config,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "records": records,
    }
    (out_dir / f"predictions_{slug}.json").write_text(
        json.dumps(predictions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    metrics = {
        "phase": "4B-1",
        "complete_run": complete,
        "model": model,
        "challenge": challenge,
        "prompt_version": freeze["prompt_version"],
        "prompt_sha256": freeze["prompt_sha256"],
        "schema_sha256": freeze["schema_sha256"],
        "evaluation_config": config,
        "summary": summary,
        "confusion_pairs": confusion_pairs(records),
    }
    (out_dir / f"metrics_{slug}.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    gate_block = {
        "phase": "4B-1",
        "complete_run": complete,
        "model": model,
        "gate": gate,
        "result": gate_result,
    }
    (out_dir / f"gate_{slug}.json").write_text(
        json.dumps(gate_block, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    (out_dir / f"cost_{slug}.json").write_text(
        json.dumps(
            {
                "phase": "4B-1",
                "complete_run": complete,
                "model": model,
                "wall_clock_seconds": elapsed,
                "cost": cost,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    overall = summary["overall"]
    print(f"\n{model} ({len(records)} examples)")
    print(f"  accuracy          : {overall['accuracy']:.4f}")
    print(f"  macro F1          : {overall['macro_f1']:.4f}")
    print(f"  structured valid  : {overall['structured_output_validity']:.4f}")
    print(f"  refusals          : {overall['refusals']}")
    print(f"  API failures      : {overall['api_failures']}")
    print(f"  latency p50/p95ms : {summary['latency_ms']['p50']} / {summary['latency_ms']['p95']}")
    print(
        f"  tokens in/out     : {summary['tokens']['total_input_tokens']} / "
        f"{summary['tokens']['total_output_tokens']}"
    )
    print(f"  cost USD          : {cost['estimated_cost_usd']}")
    print(f"  gate              : {'PASS' if gate_result['passed'] and complete else 'NOT PASSED'}")
    return {"summary": summary, "gate": gate_result, "cost": cost, "complete": complete}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 4B-1 LLM benchmark (explicit API command).")
    parser.add_argument(
        "--model",
        required=True,
        help="Model id, e.g. gpt-5.6-luna or gpt-5.6-terra.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Evaluate only the first N examples. Marks the run incomplete; never the benchmark.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPORTS_DIR,
        help="Artifact directory. Defaults to this evaluation area's reports/.",
    )
    args = parser.parse_args(argv)

    from prompt_contract import MODELS

    if args.model not in MODELS:
        _fail(f"unknown model {args.model!r}; the frozen candidates are {', '.join(MODELS)}")

    try:
        run(args.model, args.limit, args.out_dir)
    except _missing_credential_error() as error:
        # Stop before any example is sent. The key is never read from a file, never prompted for
        # and never written to an artifact.
        print(f"Phase 4B-1 stopped: {error}", file=sys.stderr)
        print(
            "Set OPENAI_API_KEY in the shell environment and rerun. No key belongs in source, "
            "in .env, or in any report.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
