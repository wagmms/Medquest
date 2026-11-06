"""Facade e Loader de dados estáticos do OSCE.

Os dados canônicos residem desacoplados em `app/backend/data/osce/canonical_stations.json`.
Este módulo expõe as constantes reidratadas mantendo compatibilidade total com os imports da aplicação.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Dict

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "osce" / "canonical_stations.json"


@lru_cache(maxsize=1)
def load_osce_canonical_data() -> dict[str, Any]:
    """Carrega sob demanda e com cache em memória o catálogo canônico de dados do OSCE."""
    with _DATA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


_canonical_payload = load_osce_canonical_data()

CANONICAL_STATIONS: list[dict[str, Any]] = _canonical_payload["CANONICAL_STATIONS"]
EMERGENCY_DRUGS_CATALOG: list[dict[str, Any]] = _canonical_payload["EMERGENCY_DRUGS_CATALOG"]
FMRP_USP_TEMPLATES: list[dict[str, Any]] = _canonical_payload["FMRP_USP_TEMPLATES"]
PROCEDURES_CATALOG: list[dict[str, Any]] = _canonical_payload["PROCEDURES_CATALOG"]

globals().update(_canonical_payload)
