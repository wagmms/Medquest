"""
Shim de retrocompatibilidade para o motor de classificação de Pediatria.
A implementação canônica reside em `app.backend.api.services.classifier.pediatria`.
"""
import sys
import os

# Adiciona app/backend ao sys.path se necessário
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "app", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from api.services.classifier.pediatria import PediatriaClassifier
from api.services.classifier.base import (
    load_canonical_taxonomy,
    match_any,
    match_all,
    normalize_text as norm,
)

_classifier = PediatriaClassifier()
TAX_170 = _classifier.taxonomy
ALL_CANONICAL = _classifier.all_canonical


def classify_ped_item(q):
    """Classifica a questão de pediatria retornando tupla (area, subtema, rationale)."""
    res = _classifier.classify(q)
    return res.as_tuple()


if __name__ == "__main__":
    print(f"Pediatria Classifier Engine carregado via api.services.classifier com {len(ALL_CANONICAL)} temas canônicos.")
