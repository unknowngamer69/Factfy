

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import spacy
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

logger = logging.getLogger(__name__)


_MODEL_PATH = Path(__file__).parent / "model.pkl"


_FACTUAL_NER_LABELS = {"DATE", "TIME", "MONEY", "QUANTITY", "ORDINAL", "CARDINAL", "PERCENT", "NORP", "GPE", "LOC"}


_DECLARATIVE_PATTERNS = [
    re.compile(r"\b(is|are|was|were|has|have|had|did|does|can|will|shall)\b", re.IGNORECASE),
]


@dataclass
class ClassificationResult:
 

    is_claim: bool
    confidence: float
    matched_signals: list[str] = field(default_factory=list)


class ClaimDetector:
  

    def __init__(self, nlp: spacy.language.Language, vectorizer: TfidfVectorizer, classifier: LogisticRegression):
        self._nlp = nlp
        self._vectorizer = vectorizer
        self._classifier = classifier

    @classmethod
    def load(cls, nlp: spacy.language.Language) -> "ClaimDetector":
     
        if not _MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Trained classifier not found at {_MODEL_PATH}. "
                "Run 'python -m bot.detection.train_classifier' first."
            )

        import pickle

        with open(_MODEL_PATH, "rb") as f:
            data = pickle.load(f)  
            vectorizer = data["vectorizer"]
            classifier = data["classifier"]

        logger.info("Loaded claim classifier from %s", _MODEL_PATH)
        return cls(nlp=nlp, vectorizer=vectorizer, classifier=classifier)

    def _check_spacy_signals(self, text: str) -> tuple[bool, list[str]]:
  
        doc = self._nlp(text)
        signals: list[str] = []

    
        ner_labels = {ent.label_ for ent in doc.ents}
        factual_ents = ner_labels & _FACTUAL_NER_LABELS
        if factual_ents:
            signals.append(f"NER:{','.join(sorted(factual_ents))}")

       
        for pattern in _DECLARATIVE_PATTERNS:
            if pattern.search(text):
                signals.append("declarative_verb")
                break

       
        if re.search(r"\b\d{4}\b|\b\d+[\.,]?\d*\b|%|\$", text):
            signals.append("contains_number")

      
        if re.search(r"\b(more|less|bigger|smaller|faster|slower|before|after|because|caused|led to)\b", text, re.IGNORECASE):
            signals.append("comparative_or_causal")


        has_root_verb = any(
            token.dep_ in ("ROOT", "conj") and token.pos_ in ("VERB", "AUX")
            for token in doc
        )
        if has_root_verb:
            signals.append("has_root_verb")


        strong_ner = factual_ents & {"DATE", "TIME", "MONEY", "QUANTITY", "ORDINAL", "CARDINAL", "PERCENT"}
        has_strong_indicator = (
            "declarative_verb" in signals or
            "contains_number" in signals or
            bool(strong_ner)
        )

        passed = len(signals) >= 2 and has_strong_indicator
        return passed, signals

    def _check_classifier(self, text: str, threshold: float = 0.5) -> tuple[bool, float]:
       
        tfidf_features = self._vectorizer.transform([text])
        proba = self._classifier.predict_proba(tfidf_features)[0]
        classes = [str(c) for c in self._classifier.classes_]
        if "claim" in classes:
            claim_index = classes.index("claim")
        else:
           
            claim_index = 1
        claim_probability = float(proba[claim_index])
        passed = claim_probability >= threshold
        return passed, claim_probability

    def is_claim(self, text: str, threshold: float = 0.65) -> ClassificationResult:
      
        matched_signals: list[str] = []

        
        spacy_pass, spacy_signals = self._check_spacy_signals(text)
        matched_signals.extend(spacy_signals)

        
        clf_pass, clf_confidence = self._check_classifier(text, threshold)
        matched_signals.append(f"classifier_conf={clf_confidence:.3f}")

       
        is_claim = spacy_pass and clf_pass
        overall_confidence = clf_confidence if is_claim else 0.0

        return ClassificationResult(
            is_claim=is_claim,
            confidence=overall_confidence,
            matched_signals=matched_signals,
        )
