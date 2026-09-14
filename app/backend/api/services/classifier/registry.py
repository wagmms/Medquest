from __future__ import annotations

from typing import Dict, Optional
from .base import BaseClassifier, ClassificationResult, load_canonical_taxonomy, normalize_text
from .cirurgia import CirurgiaClassifier
from .pediatria import PediatriaClassifier

_CLASSIFIERS: Dict[str, BaseClassifier] = {}


def get_classifier(area: Optional[str] = None) -> BaseClassifier:
    """Retorna a instância do classificador registrado para a grande área."""
    global _CLASSIFIERS

    if not _CLASSIFIERS:
        _CLASSIFIERS["Cirurgia"] = CirurgiaClassifier()
        _CLASSIFIERS["Pediatria"] = PediatriaClassifier()

    if area:
        norm_area = normalize_text(area)
        if "cirurgia" in norm_area:
            return _CLASSIFIERS["Cirurgia"]
        if "pediatria" in norm_area:
            return _CLASSIFIERS["Pediatria"]

    # Default fallback: Cirurgia
    return _CLASSIFIERS.get("Cirurgia", CirurgiaClassifier())


def classify(question: dict, target_area: Optional[str] = None) -> ClassificationResult:
    """
    Classifica deterministicamente uma questão contra a taxonomia médica canônica dos 170 temas.
    Se target_area for informada (ex: "Pediatria", "Cirurgia"), direciona ao classificador correspondente.
    """
    area_hint = target_area or question.get("area") or question.get("current_area")
    classifier = get_classifier(area_hint)
    result = classifier.classify(question)

    # Asserção de conformidade com os 170 temas canônicos
    taxonomy = load_canonical_taxonomy()
    if taxonomy and result.target_area in taxonomy:
        valid_subtemas = taxonomy[result.target_area]
        if result.target_subtema not in valid_subtemas:
            # Fallback seguro caso o tema retornado divirja da taxonomia canônica
            fallback_subtema = valid_subtemas[0]
            return ClassificationResult(
                target_area=result.target_area,
                target_subtema=fallback_subtema,
                rationale=f"{result.rationale} (Ajustado para subtema canônico válido).",
                confidence=0.8,
            )

    return result
