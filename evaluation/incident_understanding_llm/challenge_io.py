"""Read-only access to the frozen Challenge Set v2.

Phase 4B-1. Every read re-verifies the artifact hash against the committed freeze, so a run fails
loudly instead of silently scoring a modified challenge set. Nothing in this module writes to the
challenge directory: the artifact is opened for reading only and no API function is exposed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from prompt_contract import (
    CHALLENGE_FREEZE_RELATIVE_PATH,
    CHALLENGE_RELATIVE_PATH,
    EXPECTED_CHALLENGE_SHA256,
    EXPECTED_CHALLENGE_TOTAL,
    EXPECTED_CHALLENGE_VERSION,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CHALLENGE_PATH = REPO_ROOT / CHALLENGE_RELATIVE_PATH
FREEZE_PATH = REPO_ROOT / CHALLENGE_FREEZE_RELATIVE_PATH

# The single permitted label vocabulary. A prediction outside it is a structured-output failure, not
# a seventh class.
ALLOWED_LABELS = frozenset(
    {
        "PENDING_OR_DELAYED",
        "FAILED_OR_DECLINED",
        "REVERSED",
        "APPROVED_BUT_UNRESOLVED",
        "AMBIGUOUS_TRANSACTION",
        "OUT_OF_SCOPE",
    }
)


class ChallengeVerificationError(RuntimeError):
    """The frozen challenge artifact is missing, altered, or fails its own freeze assertions."""


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_freeze() -> dict[str, Any]:
    return json.loads(FREEZE_PATH.read_text(encoding="utf-8"))


def verify_challenge() -> dict[str, Any]:
    """Verify the challenge artifact against the committed freeze. Returns the freeze record.

    Raises ChallengeVerificationError on any mismatch. Does not validate or relabel examples.
    """

    if not CHALLENGE_PATH.exists():
        raise ChallengeVerificationError(f"challenge artifact missing: {CHALLENGE_PATH}")
    if not FREEZE_PATH.exists():
        raise ChallengeVerificationError(f"freeze artifact missing: {FREEZE_PATH}")

    freeze = load_freeze()
    digest = sha256_of(CHALLENGE_PATH)

    if digest != freeze.get("sha256"):
        raise ChallengeVerificationError(
            f"challenge.json hash mismatch: {digest} != {freeze.get('sha256')} "
            "(the frozen artifact must not be edited)"
        )
    if digest != EXPECTED_CHALLENGE_SHA256:
        raise ChallengeVerificationError(
            "challenge.json hash does not match the Phase 4B-1 pinned hash "
            f"{EXPECTED_CHALLENGE_SHA256}"
        )
    if freeze.get("version") != EXPECTED_CHALLENGE_VERSION:
        raise ChallengeVerificationError(f"unexpected challenge version: {freeze.get('version')}")
    if freeze.get("frozen_before_any_model_run") is not True:
        raise ChallengeVerificationError(
            "freeze artifact does not assert that it predates any model run"
        )
    if freeze.get("total") != EXPECTED_CHALLENGE_TOTAL:
        raise ChallengeVerificationError(
            f"freeze artifact total is {freeze.get('total')!r}, expected {EXPECTED_CHALLENGE_TOTAL}"
        )

    return {
        "verified": True,
        "version": freeze["version"],
        "sha256": digest,
        "bytes": CHALLENGE_PATH.stat().st_size,
        "total": freeze["total"],
        "frozen_before_any_model_run": True,
    }


def load_examples() -> list[dict[str, Any]]:
    """Return the frozen examples after hash verification, in file order.

    Each record exposes id, text, language, tier, gold label and semantic family. The text is the
    only field ever sent to a model; language, tier and label stay local for scoring.
    """

    verify_challenge()
    payload = json.loads(CHALLENGE_PATH.read_text(encoding="utf-8"))
    examples = payload["examples"]

    if len(examples) != 600:
        raise ChallengeVerificationError(f"expected 600 examples, found {len(examples)}")

    for example in examples:
        if not example["text"].strip():
            raise ChallengeVerificationError(f"empty example text: {example['id']}")
        if example["label"] not in ALLOWED_LABELS:
            raise ChallengeVerificationError(
                f"example label outside the six classes: {example['id']}"
            )

    return examples
