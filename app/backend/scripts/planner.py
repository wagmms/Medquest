"""
MedQuest - Planner (Shim de retrocompatibilidade)

Este módulo foi migrado para `api.services.planner`.
Todos os novos desenvolvimentos devem importar de `api.services.planner`.
"""

from api.services.planner import (  # noqa: F401
    USP_WEIGHTS,
    DEFAULT_PRACTICE_HOURS_PER_SUBTEMA,
    get_normalized_area,
    generate_annual_plan,
)

__all__ = [
    "USP_WEIGHTS",
    "DEFAULT_PRACTICE_HOURS_PER_SUBTEMA",
    "get_normalized_area",
    "generate_annual_plan",
]
