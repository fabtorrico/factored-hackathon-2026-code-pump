"""Build the independently authored Challenge Set v2 and freeze it.

This script only builds and validates the dataset. It must be run and frozen
BEFORE any baseline/learned model is executed on it.

Usage (from the repository root):

    backend/.venv/Scripts/python evaluation/incident_understanding_v2/generate_challenge_v2.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

VERSION = "2.0.0"
SEED = 42
EXPECTED_FAMILIES = 150
EXPECTED_TOTAL = 600
MIN_PER_CLASS = 30
MIN_PER_TIER = 20
MIN_LANGUAGE_FRACTION = 0.40
NEAR_DUPLICATE_JACCARD = 0.85
TIERS = (
    "DIRECT",
    "INDIRECT",
    "HARD_NEGATIVE",
    "LEXICAL_OVERLAP",
    "COLLOQUIAL_OR_NOISY",
    "LOW_CONTEXT",
)
AUTHORING_MODULES = (
    "pending",
    "failed",
    "reversed",
    "approved",
    "ambiguous",
    "out_of_scope",
)
REQUIRED_FIELDS = ("id", "text", "language", "label", "tier", "semantic_family")
VALID_LABELS = (
    "PENDING_OR_DELAYED",
    "FAILED_OR_DECLINED",
    "REVERSED",
    "APPROVED_BUT_UNRESOLVED",
    "AMBIGUOUS_TRANSACTION",
    "OUT_OF_SCOPE",
)

BASE_DIR = Path(__file__).resolve().parent
AUTHORING_DIR = BASE_DIR / "authoring"
REPORTS_DIR = BASE_DIR / "reports"
CHALLENGE_PATH = BASE_DIR / "challenge.json"
V1_DATASET_PATH = BASE_DIR.parent / "incident_understanding" / "dataset.json"


def _load_authoring_modules() -> list[Any]:
    modules = []
    for name in AUTHORING_MODULES:
        path = AUTHORING_DIR / f"{name}.py"
        spec = importlib.util.spec_from_file_location(f"v2_authoring_{name}", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot import authoring module: {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules.append(module)
    return modules


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    cleaned = "".join(ch if ch.isalnum() else " " for ch in without_accents)
    return " ".join(cleaned.split())


def _tokens(text: str) -> set[str]:
    return set(_normalize(text).split())


def _token_hash(family_id: str, variant_index: int, text: str) -> str:
    payload = f"{family_id}|{variant_index}|{text}".encode()
    return hashlib.md5(payload).hexdigest()[:8]


def _build_examples(modules: list[Any]) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for module in modules:
        for family_id, tier, language, variants in module.FAMILIES:
            for index, text in enumerate(variants):
                digest = _token_hash(family_id, index, text)
                examples.append(
                    {
                        "id": f"{family_id}__v{index + 1:02d}__{digest}",
                        "text": text,
                        "language": language,
                        "label": module.LABEL,
                        "tier": tier,
                        "semantic_family": family_id,
                    }
                )
    return examples


def _load_v1_test_texts() -> list[str]:
    if not V1_DATASET_PATH.exists():
        return []
    with open(V1_DATASET_PATH, encoding="utf-8") as handle:
        dataset = json.load(handle)
    return [row["text"] for row in dataset.get("test", [])]


def _validate(examples: list[dict[str, Any]]) -> dict[str, Any]:
    failures: list[str] = []
    label_counts = Counter(e["label"] for e in examples)
    language_counts = Counter(e["language"] for e in examples)
    tier_counts = Counter(e["tier"] for e in examples)
    family_ids = {e["semantic_family"] for e in examples}
    ids = [e["id"] for e in examples]
    normalized_texts = [_normalize(e["text"]) for e in examples]

    if len(examples) != EXPECTED_TOTAL:
        failures.append(f"expected {EXPECTED_TOTAL} examples, found {len(examples)}")
    if len(family_ids) != EXPECTED_FAMILIES:
        failures.append(f"expected {EXPECTED_FAMILIES} families, found {len(family_ids)}")
    if set(label_counts) != set(VALID_LABELS):
        failures.append(f"label set mismatch: {sorted(label_counts)}")
    for label in VALID_LABELS:
        if label_counts[label] < MIN_PER_CLASS:
            failures.append(f"class {label} has {label_counts[label]} < {MIN_PER_CLASS}")
    if set(language_counts) != {"es", "pt"}:
        failures.append(f"language set mismatch: {sorted(language_counts)}")
    for language, count in language_counts.items():
        if count < MIN_LANGUAGE_FRACTION * len(examples):
            failures.append(f"language {language} share too low: {count}/{len(examples)}")
    if set(tier_counts) != set(TIERS):
        failures.append(f"tier set mismatch: {sorted(tier_counts)}")
    for tier in TIERS:
        if tier_counts[tier] < MIN_PER_TIER:
            failures.append(f"tier {tier} has {tier_counts[tier]} < {MIN_PER_TIER}")
    if len(ids) != len(set(ids)):
        duplicates = [item for item, count in Counter(ids).items() if count > 1]
        failures.append(f"duplicate ids: {duplicates[:5]}")
    if len(normalized_texts) != len(set(normalized_texts)):
        duplicates = [t for t, c in Counter(normalized_texts).items() if c > 1]
        failures.append(f"duplicate texts: {duplicates[:5]}")

    seen_fields: set[tuple[str, str]] = set()
    for example in examples:
        for field in REQUIRED_FIELDS:
            if field not in example:
                failures.append(f"example {example.get('id')} missing field {field}")
        if not isinstance(example["text"], str) or not example["text"].strip():
            failures.append(f"example {example['id']} has empty text")
        key = (example["language"], example["text"])
        if key in seen_fields:
            failures.append(f"duplicate (language, text): {example['id']}")
        seen_fields.add(key)

    family_meta: dict[str, set[tuple[str, str, str]]] = {}
    for example in examples:
        family_meta.setdefault(example["semantic_family"], set()).add(
            (example["label"], example["language"], example["tier"])
        )
    for family_id, meta in family_meta.items():
        if len(meta) != 1:
            failures.append(f"family {family_id} is not consistent: {sorted(meta)}")

    v1_test = _load_v1_test_texts()
    v1_exact = {_normalize(text) for text in v1_test}
    v1_token_sets = [_tokens(text) for text in v1_test]
    for example in examples:
        normalized = _normalize(example["text"])
        if normalized in v1_exact:
            failures.append(f"exact duplicate of v1 TEST: {example['id']}")
            continue
        tokens = _tokens(example["text"])
        for v1_tokens in v1_token_sets:
            union = tokens | v1_tokens
            if not union:
                continue
            jaccard = len(tokens & v1_tokens) / len(union)
            if jaccard >= NEAR_DUPLICATE_JACCARD:
                failures.append(
                    f"near-duplicate of v1 TEST (jaccard={jaccard:.2f}): {example['id']}"
                )

    report = {
        "version": VERSION,
        "total": len(examples),
        "families": len(family_ids),
        "labels": dict(sorted(label_counts.items())),
        "languages": dict(sorted(language_counts.items())),
        "tiers": dict(sorted(tier_counts.items())),
        "v1_test_compared": len(v1_test),
        "failures": failures,
        "passed": not failures,
    }
    if failures:
        raise ValueError("Challenge Set v2 validation failed:\n- " + "\n- ".join(failures))
    return report


def _write(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    modules = _load_authoring_modules()
    examples = _build_examples(modules)
    examples.sort(key=lambda e: e["id"])
    report = _validate(examples)

    payload = {
        "metadata": {
            "name": "Code Pump Incident Understanding Challenge Set",
            "version": VERSION,
            "seed": SEED,
            "description": (
                "Independently authored challenge set (no organizer records, no PII). "
                "Built to stress-test both the frozen deterministic baseline and the "
                "frozen learned classifier on Spanish and Portuguese."
            ),
            "total": len(examples),
            "num_families": report["families"],
            "languages": report["languages"],
            "labels": report["labels"],
            "tiers": report["tiers"],
            "tier_definitions": {
                "DIRECT": "Explicit, unambiguous phrasing of the label.",
                "INDIRECT": "Describes consequences rather than the label keyword.",
                "HARD_NEGATIVE": "Mentions a competing class but the true label wins.",
                "LEXICAL_OVERLAP": "Shares keywords with another class.",
                "COLLOQUIAL_OR_NOISY": "Informal, typo-laden, or chatty phrasing.",
                "LOW_CONTEXT": "Very short, context-free phrasing.",
            },
        },
        "examples": examples,
        "test": examples,
    }
    _write(CHALLENGE_PATH, payload)

    digest = hashlib.sha256(CHALLENGE_PATH.read_bytes()).hexdigest()
    freeze = {
        "version": VERSION,
        "artifact": "challenge.json",
        "sha256": digest,
        "bytes": CHALLENGE_PATH.stat().st_size,
        "seed": SEED,
        "total": report["total"],
        "num_families": report["families"],
        "labels": report["labels"],
        "languages": report["languages"],
        "tiers": report["tiers"],
        "v1_test_compared": report["v1_test_compared"],
        "frozen_before_any_model_run": True,
    }
    _write(REPORTS_DIR / "quality_report.json", report)
    _write(REPORTS_DIR / "freeze_v2.json", freeze)
    print(json.dumps(freeze, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
