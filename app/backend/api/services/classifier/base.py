from __future__ import annotations

import json
import os
import re
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ClassificationResult:
    target_area: str
    target_subtema: str
    rationale: str
    confidence: float = 1.0

    def as_tuple(self) -> Tuple[str, str, str]:
        return (self.target_area, self.target_subtema, self.rationale)


def normalize_text(text: Optional[str]) -> str:
    """Normaliza texto removendo acentos, convertendo para minúsculas e limpando espaços."""
    raw = unicodedata.normalize('NFD', str(text or ''))
    stripped = ''.join(c for c in raw if unicodedata.category(c) != 'Mn')
    return stripped.lower().strip()


def match_any(text: str, patterns: List[str]) -> bool:
    """Verifica se qualquer um dos padrões em regex (limites de palavra) coincide com o texto."""
    for p in patterns:
        if re.search(r'\b' + p + r'\b', text):
            return True
    return False


def match_all(text: str, patterns: List[str]) -> bool:
    """Verifica se todos os padrões coincidem com o texto."""
    for p in patterns:
        if not re.search(r'\b' + p + r'\b', text):
            return False
    return True


def load_canonical_taxonomy() -> Dict[str, List[str]]:
    """Carrega a taxonomia canônica oficial dos 170 temas via serviço central."""
    from ..taxonomy import get_taxonomy
    return get_taxonomy()


class BaseClassifier(ABC):
    """Classe base para classificadores determinísticos médicos."""

    def __init__(self):
        self.taxonomy = load_canonical_taxonomy()
        self.all_canonical: Dict[str, str] = {}
        for area, themes in self.taxonomy.items():
            for theme in themes:
                self.all_canonical[theme] = area

    @abstractmethod
    def classify(self, q: dict) -> ClassificationResult:
        """Classifica uma questão em (target_area, target_subtema, rationale)."""
        pass

    def is_canonical(self, area: str, subtema: str) -> bool:
        """Valida se o par (area, subtema) existe na taxonomia oficial de 170 temas."""
        return subtema in self.taxonomy.get(area, [])
