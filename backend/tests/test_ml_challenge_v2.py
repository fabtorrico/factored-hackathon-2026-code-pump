"""Challenge Set v2 integrity tests.

These tests validate the independently authored, frozen Challenge Set v2 artifact and
confirm it is frozen before any model run. The single model-backed test (reconstructing
the frozen v1 systems) is opt-in via ``CODE_PUMP_RUN_ML_MODEL_TESTS=1`` and skipped by
default.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from collections import Counter
from pathlib import Path

import pytest

from app.ml.labels import ALL_LABELS

RUN_MODEL_TESTS = os.environ.get("CODE_PUMP_RUN_ML_MODEL_TESTS") == "1"
MODEL_SKIP = pytest.mark.skipif(
    not RUN_MODEL_TESTS,
    reason="set CODE_PUMP_RUN_ML_MODEL_TESTS=1 to run model-backed tests (downloads weights)",
)

REPO_ROOT = Path(__file__).resolve().parents[2]
V2_DIR = REPO_ROOT / "evaluation" / "incident_understanding_v2"
CHALLENGE_PATH = V2_DIR / "challenge.json"
FREEZE_PATH = V2_DIR / "reports" / "freeze_v2.json"
GENERATOR_PATH = V2_DIR / "generate_challenge_v2.py"
V1_DATASET_PATH = REPO_ROOT / "evaluation" / "incident_understanding" / "dataset.json"

CHALLENGE_SKIP = pytest.mark.skipif(
    not CHALLENGE_PATH.exists(), reason="Challenge Set v2 not generated"
)


def _load_generator():
    spec = importlib.util.spec_from_file_location("challenge_v2_generator", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def challenge() -> dict:
    return json.loads(CHALLENGE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def freeze() -> dict:
    return json.loads(FREEZE_PATH.read_text(encoding="utf-8"))


@CHALLENGE_SKIP
def test_challenge_is_version_2_0_0(challenge: dict):
    assert challenge["metadata"]["version"] == "2.0.0"


@CHALLENGE_SKIP
def test_challenge_has_no_train_split(challenge: dict):
    forbidden = {"train", "dev"}
    assert forbidden.isdisjoint(challenge)
    assert "train" not in challenge["metadata"]


@CHALLENGE_SKIP
def test_challenge_examples_have_required_fields(challenge: dict):
    required = {"id", "text", "language", "label", "tier", "semantic_family"}
    for example in challenge["examples"]:
        assert required <= set(example)
        assert isinstance(example["text"], str) and example["text"].strip()
        assert isinstance(example["id"], str)
        assert example["language"] in {"es", "pt"}


@CHALLENGE_SKIP
def test_challenge_labels_balanced_and_in_domain(challenge: dict):
    valid = {label.value for label in ALL_LABELS}
    counts = Counter(example["label"] for example in challenge["examples"])
    assert set(counts) == valid
    assert all(count >= 30 for count in counts.values())


@CHALLENGE_SKIP
def test_challenge_languages_are_balanced(challenge: dict):
    counts = Counter(example["language"] for example in challenge["examples"])
    assert set(counts) == {"es", "pt"}
    total = sum(counts.values())
    assert min(counts.values()) >= 0.4 * total


@CHALLENGE_SKIP
def test_challenge_uses_all_tiers(challenge: dict):
    expected = {
        "DIRECT",
        "INDIRECT",
        "HARD_NEGATIVE",
        "LEXICAL_OVERLAP",
        "COLLOQUIAL_OR_NOISY",
        "LOW_CONTEXT",
    }
    counts = Counter(example["tier"] for example in challenge["examples"])
    assert set(counts) == expected
    assert all(count >= 20 for count in counts.values())


@CHALLENGE_SKIP
def test_challenge_ids_are_unique(challenge: dict):
    ids = [example["id"] for example in challenge["examples"]]
    assert len(ids) == len(set(ids))


@CHALLENGE_SKIP
def test_challenge_texts_are_unique(challenge: dict):
    generator = _load_generator()
    keys = [
        (example["language"], generator._normalize(example["text"]))
        for example in challenge["examples"]
    ]
    assert len(keys) == len(set(keys))


@CHALLENGE_SKIP
def test_challenge_families_are_consistent(challenge: dict):
    families: dict[str, set[tuple[str, str, str]]] = {}
    for example in challenge["examples"]:
        families.setdefault(example["semantic_family"], set()).add(
            (example["label"], example["language"], example["tier"])
        )
    assert len(families) == challenge["metadata"]["num_families"]
    assert all(len(meta) == 1 for meta in families.values())


@CHALLENGE_SKIP
def test_freeze_hash_matches_artifact(challenge: dict, freeze: dict):
    digest = hashlib.sha256(CHALLENGE_PATH.read_bytes()).hexdigest()
    assert freeze["sha256"] == digest
    assert freeze["version"] == "2.0.0"
    assert freeze["frozen_before_any_model_run"] is True
    assert freeze["total"] == len(challenge["examples"])


@CHALLENGE_SKIP
def test_generator_is_deterministic(challenge: dict):
    generator = _load_generator()
    rebuilt = generator._build_examples(generator._load_authoring_modules())
    rebuilt.sort(key=lambda example: example["id"])
    assert rebuilt == challenge["examples"]


@CHALLENGE_SKIP
def test_generator_validation_passes(challenge: dict):
    generator = _load_generator()
    rebuilt = generator._build_examples(generator._load_authoring_modules())
    report = generator._validate(rebuilt)
    assert report["passed"] is True
    assert report["total"] == 600
    assert report["families"] == 150


@MODEL_SKIP
def test_frozen_v1_systems_fit_only_on_v1_train():
    from app.ml.baseline import RuleBaseline
    from app.ml.classifier import EmbeddingClassifier

    assert V1_DATASET_PATH.exists(), "v1 TRAIN is required to reconstruct the frozen systems"
    dataset = json.loads(V1_DATASET_PATH.read_text(encoding="utf-8"))
    train = dataset["train"]
    expected = {label.value for label in ALL_LABELS}
    assert {example["label"] for example in train} == expected

    classifier = EmbeddingClassifier()
    classifier.fit([example["text"] for example in train], [example["label"] for example in train])
    predictions = classifier.predict(["Me devolvieron el dinero de la compra"], threshold=0.0)
    assert len(predictions) == 1
    assert predictions[0][0] in ALL_LABELS

    baseline = RuleBaseline()
    assert baseline.predict("Me devolvieron el dinero", "es").label is not None
