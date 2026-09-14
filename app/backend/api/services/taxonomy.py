"""
MedQuest - Serviço de Taxonomia Canônica dos 170 Temas
Single Source of Truth para metadados taxonômicos em tempo de execução.
"""
from __future__ import annotations

import json
import os
import unicodedata
from typing import Dict, List, Optional, Tuple

_TAXONOMY_CACHE: Optional[Dict[str, List[str]]] = None
_SUBTEMA_TO_AREA: Optional[Dict[str, str]] = None


def _load_raw_taxonomy() -> Dict[str, List[str]]:
    """Carrega o JSON oficial dos 170 temas."""
    global _TAXONOMY_CACHE, _SUBTEMA_TO_AREA
    if _TAXONOMY_CACHE is not None:
        return _TAXONOMY_CACHE

    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    root_dir = os.path.abspath(os.path.join(backend_dir, "..", ".."))
    candidates = [
        os.path.join(backend_dir, "data", "canonical_taxonomy_170.json"),
        os.path.join(root_dir, "canonical_taxonomy_170.json"),
        os.path.join(backend_dir, "data", "canonical_taxonomy.json"),
        os.path.join(backend_dir, "data", "taxonomy.json"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and len(data) > 0:
                        _TAXONOMY_CACHE = data
                        _SUBTEMA_TO_AREA = {}
                        for area, subtemas in _TAXONOMY_CACHE.items():
                            for s in subtemas:
                                _SUBTEMA_TO_AREA[s] = area
                        return _TAXONOMY_CACHE
            except Exception:
                continue

    _TAXONOMY_CACHE = {}
    _SUBTEMA_TO_AREA = {}
    return _TAXONOMY_CACHE


def get_taxonomy() -> Dict[str, List[str]]:
    """Retorna o dicionário completo da taxonomia canônica {área: [subtemas]}."""
    return _load_raw_taxonomy()


def get_areas() -> List[str]:
    """Retorna a lista das 5 Grandes Áreas médicas."""
    return list(get_taxonomy().keys())


def get_subtemas(area: Optional[str] = None) -> List[str]:
    """Retorna os subtemas de uma grande área específica ou todos os 170 se area=None."""
    tax = get_taxonomy()
    if area:
        return list(tax.get(area, []))
    all_sub = []
    for subtemas in tax.values():
        all_sub.extend(subtemas)
    return all_sub


def is_valid_subtema(area: str, subtema: str) -> bool:
    """Verifica se o subtema pertence legitimamente à área informada."""
    tax = get_taxonomy()
    return subtema in tax.get(area, [])


def find_area_for_subtema(subtema: str) -> Optional[str]:
    """Descobre a grande área correspondente a um subtema canônico."""
    _load_raw_taxonomy()
    if _SUBTEMA_TO_AREA is not None:
        return _SUBTEMA_TO_AREA.get(subtema)
    return None


def search_subtemas(query: str, area: Optional[str] = None) -> List[str]:
    """Busca subtemas por substring normalizada."""
    def norm(t: str) -> str:
        r = unicodedata.normalize('NFD', t)
        return ''.join(c for c in r if unicodedata.category(c) != 'Mn').lower().strip()

    q_norm = norm(query)
    candidates = get_subtemas(area)
    if not q_norm:
        return candidates
    return [s for s in candidates if q_norm in norm(s)]
