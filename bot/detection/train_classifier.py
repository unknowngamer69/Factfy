

from __future__ import annotations

import csv
import pickle
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import classification_report
from sklearn.model_selection import cross_val_score

_DATA_DIR = Path(__file__).parent
_CSV_PATH = _DATA_DIR / "training_data.csv"
_MODEL_PATH = _DATA_DIR / "model.pkl"


def load_data() -> tuple[list[str], list[str]]:

    texts: list[str] = []
    labels: list[str] = []
    with open(_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            texts.append(row["text"].strip())
            labels.append(row["label"].strip())
    return texts, labels


def train() -> None:

    texts, labels = load_data()
    print(f"Loaded {len(texts)} samples from {_CSV_PATH}")


    vectorizer = TfidfVectorizer(
        max_features=2000,
        ngram_range=(1, 2),
        stop_words="english",
    )
    X = vectorizer.fit_transform(texts)


    base_clf = LogisticRegression(max_iter=1000, random_state=42)
    base_clf.fit(X, labels)

    classifier = CalibratedClassifierCV(estimator=base_clf, cv=min(5, len(texts) // 2))
    classifier.fit(X, labels)

    scores = cross_val_score(classifier, X, labels, cv=min(5, len(texts) // 2), scoring="accuracy")
    print(f"Cross-validation accuracy: {scores.mean():.3f} (+/- {scores.std():.3f})")


    y_pred = classifier.predict(X)
    print("\nFull training set report:")
    print(classification_report(labels, y_pred))


    with open(_MODEL_PATH, "wb") as f:
        pickle.dump({"vectorizer": vectorizer, "classifier": classifier}, f)
    print(f"\nModel saved to {_MODEL_PATH}")


if __name__ == "__main__":
    train()
