"""
MedQuest - Pacote Unificado de Classificação Médica

Fornece motores determinísticos de alta precisão e validação contra
a taxonomia canônica oficial dos 170 temas.
"""

from .base import (
    BaseClassifier,
    ClassificationResult,
    load_canonical_taxonomy,
    match_all,
    match_any,
    normalize_text,
)
from .cirurgia import CirurgiaClassifier
from .pediatria import PediatriaClassifier
from .registry import classify, get_classifier

__all__ = [
    "BaseClassifier",
    "ClassificationResult",
    "CirurgiaClassifier",
    "PediatriaClassifier",
    "classify",
    "get_classifier",
    "load_canonical_taxonomy",
    "match_all",
    "match_any",
    "normalize_text",
]
