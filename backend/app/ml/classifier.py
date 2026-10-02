from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder

from app.ml.labels import IncidentLabel


@dataclass
class Prediction:
    label: IncidentLabel
    confidence: float


@dataclass
class ClassifierResult:
    predictions: list[Prediction]
    embeddings: np.ndarray | None = None


class EmbeddingClassifier:
    def __init__(
        self,
        model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        max_iter: int = 1000,
    ) -> None:
        self.model_name = model_name
        self.max_iter = max_iter
        self._model = None
        self._clf: LogisticRegression | None = None
        self._le: LabelEncoder | None = None

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name)
            except Exception as e:
                raise RuntimeError(f"Failed to load model {self.model_name}: {e}") from e
        return self._model

    def fit(self, texts: list[str], labels: list[str]) -> None:
        model = self._load_model()
        X = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        self._le = LabelEncoder()
        y = self._le.fit_transform(labels)
        self._clf = LogisticRegression(max_iter=self.max_iter, random_state=42, n_jobs=None)
        self._clf.fit(X, y)

    def predict_proba(self, texts: list[str]) -> np.ndarray:
        if self._clf is None or self._le is None or self._model is None:
            raise RuntimeError("Classifier not trained")
        X = self._model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        return self._clf.predict_proba(X)

    def predict(
        self, texts: list[str], threshold: float = 0.5
    ) -> list[tuple[IncidentLabel | None, float]]:
        proba = self.predict_proba(texts)
        classes = self._le.classes_
        results = []
        for p in proba:
            idx = int(np.argmax(p))
            conf = float(p[idx])
            if conf < threshold:
                results.append((None, conf))
            else:
                cls_name = str(classes[idx])
                try:
                    lbl = IncidentLabel(cls_name)
                except Exception:
                    results.append((None, conf))
                else:
                    results.append((lbl, conf))
        return results
