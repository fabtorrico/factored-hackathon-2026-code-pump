"""Phase 4A tests: label domain, frozen rule baseline, synthetic dataset integrity and the
learned classifier output contract.

Model-backed tests download/load sentence-transformers weights, so they are opt-in via the
``CODE_PUMP_RUN_ML_MODEL_TESTS=1`` environment variable and skipped by default.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

import pytest

from app.ml.baseline import RuleBaseline
from app.ml.classifier import EmbeddingClassifier
from app.ml.labels import ALL_LABELS, IncidentLabel

RUN_MODEL_TESTS = os.environ.get("CODE_PUMP_RUN_ML_MODEL_TESTS") == "1"
MODEL_SKIP = pytest.mark.skipif(
    not RUN_MODEL_TESTS,
    reason="set CODE_PUMP_RUN_ML_MODEL_TESTS=1 to run model-backed tests (downloads weights)",
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = REPO_ROOT / "evaluation" / "incident_understanding" / "dataset.json"
DATASET_SKIP = pytest.mark.skipif(
    not DATASET_PATH.exists(), reason="synthetic dataset not generated"
)


@pytest.fixture(scope="module")
def dataset() -> dict:
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


# --- Label domain ---------------------------------------------------------------------


def test_label_enum_has_six_unique_string_labels():
    values = [label.value for label in ALL_LABELS]
    assert len(values) == 6
    assert len(set(values)) == 6
    assert all(isinstance(value, str) for value in values)
    assert IncidentLabel("REVERSED") is IncidentLabel.REVERSED


# --- Frozen rule baseline -------------------------------------------------------------


def test_baseline_is_deterministic():
    baseline = RuleBaseline()
    first = baseline.predict("Mi transferencia fue rechazada", "es")
    second = baseline.predict("Mi transferencia fue rechazada", "es")
    assert first == second
    assert first.label is IncidentLabel.FAILED_OR_DECLINED


def test_baseline_returns_valid_label_or_abstains_with_bounded_confidence():
    baseline = RuleBaseline()
    samples = [
        ("Mi transferencia todavia no llega a destino", "es"),
        ("O pagamento foi recusado pela loja", "pt"),
        ("Me devolvieron el dinero de la compra", "es"),
        ("A transferencia foi aprovada mas nao chegou", "pt"),
        ("No se que paso con mi pago", "es"),
        ("Quiero abrir una cuenta nueva", "es"),
    ]
    for text, language in samples:
        result = baseline.predict(text, language)
        assert result.label is None or result.label in ALL_LABELS
        assert 0.0 <= result.confidence <= 1.0


@pytest.mark.parametrize("text", ["", "   ", "\n\t", "zzz qqq wwww", "1234567890"])
def test_baseline_abstains_on_empty_or_invalid_text(text: str):
    baseline = RuleBaseline()
    result = baseline.predict(text, "es")
    assert result.label is None
    assert result.matched is False


# --- Dataset integrity ----------------------------------------------------------------


@DATASET_SKIP
def test_dataset_examples_have_unique_ids(dataset: dict):
    examples = dataset["examples"]
    ids = [example["id"] for example in examples]
    assert len(ids) == len(set(ids))


@DATASET_SKIP
def test_dataset_labels_are_in_domain(dataset: dict):
    valid = {label.value for label in ALL_LABELS}
    assert {example["label"] for example in dataset["examples"]} <= valid


@DATASET_SKIP
def test_dataset_only_spanish_and_portuguese(dataset: dict):
    languages = {example["language"] for example in dataset["examples"]}
    assert languages == {"es", "pt"}


@DATASET_SKIP
def test_every_example_has_a_semantic_family(dataset: dict):
    for example in dataset["examples"]:
        assert example.get("semantic_family")


@DATASET_SKIP
def test_splits_have_no_semantic_family_leakage(dataset: dict):
    family_sets = {
        split: {example["semantic_family"] for example in dataset[split]}
        for split in ("train", "dev", "test")
    }
    assert family_sets["train"].isdisjoint(family_sets["dev"])
    assert family_sets["train"].isdisjoint(family_sets["test"])
    assert family_sets["dev"].isdisjoint(family_sets["test"])


@DATASET_SKIP
def test_every_split_covers_every_label(dataset: dict):
    valid = {label.value for label in ALL_LABELS}
    for split in ("train", "dev", "test"):
        present = {example["label"] for example in dataset[split]}
        assert present == valid, f"{split} is missing {valid - present}"


@DATASET_SKIP
def test_split_sizes_match_metadata(dataset: dict):
    metadata = dataset["metadata"]
    for split in ("train", "dev", "test"):
        assert len(dataset[split]) == metadata[split]
    assert metadata["total"] == len(dataset["examples"])


@DATASET_SKIP
def test_dataset_generation_is_reproducible(dataset: dict):
    assert dataset["metadata"]["seed"] == 42
    counts = Counter(example["label"] for example in dataset["examples"])
    assert set(counts) == {label.value for label in ALL_LABELS}


# --- Learned classifier output contract (model-backed) --------------------------------


@MODEL_SKIP
def test_classifier_output_structure_and_bounds():
    train_texts = [
        "Mi transferencia todavia no llega",
        "A transferencia ainda nao chegou",
        "Mi pago fue rechazado",
        "O pagamento foi recusado",
        "Me devolvieron el dinero",
        "Devolveram o dinheiro",
        "La transferencia fue aprobada pero no llega",
        "A transferencia foi aprovada mas nao chegou",
        "No se que paso con mi pago",
        "Nao sei o que aconteceu",
        "Quiero abrir una cuenta nueva",
        "Quero abrir uma conta nova",
    ]
    labels = [
        "PENDING_OR_DELAYED",
        "PENDING_OR_DELAYED",
        "FAILED_OR_DECLINED",
        "FAILED_OR_DECLINED",
        "REVERSED",
        "REVERSED",
        "APPROVED_BUT_UNRESOLVED",
        "APPROVED_BUT_UNRESOLVED",
        "AMBIGUOUS_TRANSACTION",
        "AMBIGUOUS_TRANSACTION",
        "OUT_OF_SCOPE",
        "OUT_OF_SCOPE",
    ]
    classifier = EmbeddingClassifier()
    classifier.fit(train_texts, labels)

    results = classifier.predict(["Mi transferencia todavia no llega", ""], threshold=0.0)
    assert len(results) == 2
    for label, confidence in results:
        assert label is None or label in ALL_LABELS
        assert 0.0 <= confidence <= 1.0

    high_threshold = classifier.predict(train_texts, threshold=1.01)
    assert all(label is None for label, _ in high_threshold)
