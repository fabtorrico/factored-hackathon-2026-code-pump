"""Phase 6 system evaluation driver.

Runs every case in `cases.py` against the real application, writes three artifacts next to this
file (`evaluation_cases.json`, `report.json`, `report.md`) and prints a scorecard.

    backend\\.venv\\Scripts\\python.exe evaluation\\system\\run_evaluation.py

No network access, no `OPENAI_API_KEY`, no mutation of the repository's `data/` tree. All curated
and operational state is created under a temporary directory and removed afterwards.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import traceback
from collections import OrderedDict
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from cases import ALL_CASES, CheckFailure, EvalContext, Observation, adapt  # noqa: E402

REPORT_JSON = HERE / "report.json"
REPORT_MD = HERE / "report.md"
CASES_JSON = HERE / "evaluation_cases.json"

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def _run_case(ctx: EvalContext, case, check) -> Observation:
    try:
        return adapt(check, case.id)(ctx)
    except CheckFailure as exc:
        return Observation(False, str(exc), "", skipped=False)
    except Exception as exc:  # noqa: BLE001 - an unexpected error is itself a finding
        detail = traceback.format_exc(limit=4).strip().splitlines()[-1]
        return Observation(False, f"{type(exc).__name__}: {exc}", detail)


def _case_catalogue() -> list[dict[str, str]]:
    return [
        {
            "id": case.id,
            "category": case.category,
            "scenario": case.scenario,
            "expected_behavior": case.expected_behavior,
            "severity_if_failed": case.severity_if_failed,
        }
        for case, _ in ALL_CASES
    ]


def _scorecard(results: list[dict]) -> OrderedDict[str, dict]:
    categories: OrderedDict[str, dict] = OrderedDict()
    for result in results:
        bucket = categories.setdefault(
            result["category"],
            {"cases": 0, "passed": 0, "failed": 0, "skipped": 0},
        )
        bucket["cases"] += 1
        key = {"PASS": "passed", "FAIL": "failed", "SKIP": "skipped"}[result["result"]]
        bucket[key] += 1
    return categories


def _write_markdown(report: dict) -> None:
    lines: list[str] = []
    lines.append("# Phase 6 system evaluation report\n")
    lines.append(f"Generated: {report['generated_at']}\n")
    lines.append(
        "Prototype safety and robustness evidence, not production assurance. "
        "Every case runs against the real application in-process.\n"
    )
    totals = report["totals"]
    lines.append(
        f"**Totals:** {totals['cases']} cases - "
        f"{totals['passed']} PASS, {totals['failed']} FAIL, {totals['skipped']} SKIP.\n"
    )
    lines.append("## Scorecard\n")
    lines.append("| Category | Cases | Pass | Fail | Skip |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for category, bucket in report["categories"].items():
        lines.append(
            f"| {category} | {bucket['cases']} | {bucket['passed']} | "
            f"{bucket['failed']} | {bucket['skipped']} |"
        )
    lines.append("")

    lines.append("## Latency (local, small sample, not an SLA)\n")
    lines.append("| Operation | Iterations | p50 (ms) | p95 (ms) |")
    lines.append("| --- | ---: | ---: | ---: |")
    for name, stats in report["latency"].items():
        lines.append(f"| {name} | {stats['iterations']} | {stats['p50_ms']} | {stats['p95_ms']} |")
    lines.append("")

    failures = [r for r in report["results"] if r["result"] == "FAIL"]
    lines.append("## Failures\n")
    if not failures:
        lines.append("None.\n")
    else:
        for result in failures:
            lines.append(
                f"- **{result['id']}** ({result['severity']}) - {result['scenario']}: "
                f"{result['observed_behavior']}"
            )
        lines.append("")

    lines.append("## Cases\n")
    grouped: OrderedDict[str, list[dict]] = OrderedDict()
    for result in report["results"]:
        grouped.setdefault(result["category"], []).append(result)
    for category, items in grouped.items():
        lines.append(f"### {category}\n")
        for result in items:
            marker = {"PASS": "PASS", "FAIL": "FAIL", "SKIP": "SKIP"}[result["result"]]
            lines.append(
                f"- `{marker}` **{result['id']}** {result['scenario']} - "
                f"{result['observed_behavior']}"
            )
    lines.append("")

    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    workdir = Path(tempfile.mkdtemp(prefix="phase6-system-"))
    ctx = EvalContext(workdir)
    try:
        results: list[dict] = []
        for case, check in ALL_CASES:
            observation = _run_case(ctx, case, check)
            record = {
                "id": case.id,
                "category": case.category,
                "scenario": case.scenario,
                "expected_behavior": case.expected_behavior,
                "observed_behavior": observation.observed,
                "result": "SKIP"
                if observation.skipped
                else ("PASS" if observation.passed else "FAIL"),
                "evidence": observation.evidence,
            }
            if record["result"] == "FAIL":
                record["severity"] = case.severity_if_failed
            results.append(record)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    categories = _scorecard(results)
    totals = {
        "cases": len(results),
        "passed": sum(1 for r in results if r["result"] == "PASS"),
        "failed": sum(1 for r in results if r["result"] == "FAIL"),
        "skipped": sum(1 for r in results if r["result"] == "SKIP"),
    }
    report = {
        "suite": "phase6-system-evaluation",
        "generated_at": generated_at,
        "totals": totals,
        "categories": categories,
        "latency": ctx.latency,
        "results": results,
    }

    CASES_JSON.write_text(json.dumps(_case_catalogue(), indent=2) + "\n", encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    _write_markdown(report)

    print(f"Phase 6 system evaluation - {generated_at}")
    print(
        f"cases={totals['cases']} pass={totals['passed']} "
        f"fail={totals['failed']} skip={totals['skipped']}"
    )
    for category, bucket in categories.items():
        if bucket["failed"]:
            print(f"  FAIL in {category}: {bucket['failed']}")
    failures = [r for r in results if r["result"] == "FAIL"]
    for result in sorted(
        failures, key=lambda r: (SEVERITY_ORDER.get(r.get("severity", "LOW"), 9), r["id"])
    ):
        print(
            f"  [{result['severity']}] {result['id']} {result['scenario']}: "
            f"{result['observed_behavior']}"
        )
    print(f"wrote {CASES_JSON.name}, {REPORT_JSON.name}, {REPORT_MD.name}")
    return 1 if totals["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
