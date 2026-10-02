"""Freeze the Phase 4B-1 prompt, schema, models, configuration and quality gate.

Run this BEFORE the benchmark. It is the only script that writes the freeze artifacts, it refuses
to overwrite an existing freeze, and it touches nothing in the challenge directory.

    backend/.venv/Scripts/python evaluation/incident_understanding_llm/freeze_prompt.py
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from prompt_contract import (  # noqa: E402
    CHALLENGE_RELATIVE_PATH,
    EXPECTED_CHALLENGE_SHA256,
    EXPECTED_CHALLENGE_VERSION,
    MODEL_SELECTION_RULE,
    PROMPT_VERSION,
    QUALITY_GATE,
    SYSTEM_PROMPT,
    freeze_artifact,
)

REPORTS_DIR = BASE_DIR / "reports"
PROMPT_FREEZE_PATH = REPORTS_DIR / "prompt_freeze.json"
QUALITY_GATE_PATH = REPORTS_DIR / "quality_gate.json"


def write_freeze() -> dict[str, Any]:
    if PROMPT_FREEZE_PATH.exists():
        raise SystemExit(
            f"{PROMPT_FREEZE_PATH.name} already exists; the prompt is frozen. "
            "A change requires a new PROMPT_VERSION and a deliberate re-freeze."
        )
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    from challenge_io import verify_challenge

    artifact = freeze_artifact()
    challenge = verify_challenge()
    artifact["frozen_at"] = datetime.now(UTC).isoformat()
    artifact["frozen_before_any_benchmark_result"] = True
    artifact["challenge_verified_at_freeze_time"] = challenge
    artifact["no_challenge_examples_in_prompt"] = True

    PROMPT_FREEZE_PATH.write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    gate = dict(QUALITY_GATE)
    gate["prompt_version"] = PROMPT_VERSION
    gate["model_selection_rule"] = MODEL_SELECTION_RULE
    gate["recorded_at"] = artifact["frozen_at"]
    gate["recorded_before_any_benchmark_result"] = True
    gate["immutable_after_results"] = True
    gate["challenge"] = {
        "path": CHALLENGE_RELATIVE_PATH,
        "version": EXPECTED_CHALLENGE_VERSION,
        "sha256": EXPECTED_CHALLENGE_SHA256,
    }
    QUALITY_GATE_PATH.write_text(
        json.dumps(gate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return artifact


def main() -> int:
    artifact = write_freeze()
    print("Phase 4B-1 freeze written.")
    print(f"  prompt_version     : {artifact['prompt_version']}")
    print(f"  prompt_sha256      : {artifact['prompt_sha256']}")
    print(f"  schema_sha256      : {artifact['schema_sha256']}")
    print(f"  models             : {', '.join(artifact['models'])}")
    print(f"  challenge sha256   : {artifact['challenge_verified_at_freeze_time']['sha256']}")
    print(f"  gate               : {artifact['quality_gate']['gate_version']}")
    print(f"  prompt chars       : {len(SYSTEM_PROMPT)}")
    print(f"  wrote              : {PROMPT_FREEZE_PATH.relative_to(REPO_ROOT)}")
    print(f"  wrote              : {QUALITY_GATE_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
