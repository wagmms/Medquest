"""
Shim de retrocompatibilidade para o motor de classificação de Cirurgia.
A implementação canônica reside em `app.backend.api.services.classifier.cirurgia`.
"""
import sys
import os

# Adiciona app/backend ao sys.path se necessário
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "app", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from api.services.classifier.cirurgia import CirurgiaClassifier
from api.services.classifier.base import (
    load_canonical_taxonomy,
    match_any,
    match_all,
    normalize_text as norm,
)

_classifier = CirurgiaClassifier()
tax = _classifier.taxonomy
CANONICAL_THEMES = _classifier.all_canonical


def classify_question(q):
    """Classifica a questão retornando tupla (area, subtema, rationale)."""
    res = _classifier.classify(q)
    return res.as_tuple()


if __name__ == "__main__":
    print(f"Classify Engine (Cirurgia) carregado via api.services.classifier com {len(CANONICAL_THEMES)} temas canônicos.")
