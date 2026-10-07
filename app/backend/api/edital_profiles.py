"""Catálogo Local e Versionado de Perfis de Editais para Residência Médica.

Define pesos de grandes áreas, versões e status de validação curricular de forma
puramente local, hermética e determinística, sem dependência de serviços externos.
"""

from typing import Dict, Literal, Optional
from pydantic import BaseModel, Field


CANONICAL_AREAS = [
    "Clínica Médica",
    "Cirurgia",
    "Ginecologia e Obstetrícia",
    "Pediatria",
    "Medicina Preventiva",
]


class EditalProfile(BaseModel):
    institution_code: str
    institution_label: str
    version: str
    validity_period: str
    curation_source: str
    status: Literal["validated", "experimental"]
    weights: Dict[str, float] = Field(description="Pesos por grande área médica normalizados para soma 1.0")


def _clean_weights(raw_weights: Dict[str, float]) -> Dict[str, float]:
    """Extrai e sanitiza os pesos brutos."""
    cleaned: Dict[str, float] = {}
    for area in CANONICAL_AREAS:
        val = raw_weights.get(area, 0.0)
        try:
            val_f = float(val)
            cleaned[area] = max(0.0, val_f)
        except (ValueError, TypeError):
            cleaned[area] = 0.0
    return cleaned

def _get_fallback_weights() -> Dict[str, float]:
    """Retorna pesos equitativos padrão (20% para cada área canônica)."""
    equal_w = 1.0 / len(CANONICAL_AREAS)
    return {area: equal_w for area in CANONICAL_AREAS}

def normalize_weights(raw_weights: Dict[str, float]) -> Dict[str, float]:
    """Valida e normaliza pesos de grandes áreas para somarem exatamente 1.0."""
    cleaned = _clean_weights(raw_weights)
    total = sum(cleaned.values())

    if total <= 0:
        return _get_fallback_weights()

    return {area: round(w / total, 4) for area, w in cleaned.items()}


# Catálogo local provisório de editais. Os pesos uniformes abaixo preservam o
# contrato e permitem testar a experiência, mas não representam uma extração
# ou validação oficial dos editais. Só um perfil com fonte verificável e
# revisão clínica pode receber o status ``validated``.
EDITAL_PROFILES_REGISTRY: Dict[str, EditalProfile] = {
    "USP-SP": EditalProfile(
        institution_code="USP-SP",
        institution_label="USP - São Paulo",
        version="2025.1",
        validity_period="2025-2026",
        curation_source="Perfil local provisório MedQuest; requer validação documental antes de uso decisório.",
        status="experimental",
        weights=normalize_weights({
            "Clínica Médica": 0.20,
            "Cirurgia": 0.20,
            "Ginecologia e Obstetrícia": 0.20,
            "Pediatria": 0.20,
            "Medicina Preventiva": 0.20,
        }),
    ),
    "USP-RP": EditalProfile(
        institution_code="USP-RP",
        institution_label="USP - Ribeirão Preto",
        version="2025.1",
        validity_period="2025-2026",
        curation_source="Perfil local provisório MedQuest; requer validação documental antes de uso decisório.",
        status="experimental",
        weights=normalize_weights({
            "Clínica Médica": 0.20,
            "Cirurgia": 0.20,
            "Ginecologia e Obstetrícia": 0.20,
            "Pediatria": 0.20,
            "Medicina Preventiva": 0.20,
        }),
    ),
    "UNICAMP": EditalProfile(
        institution_code="UNICAMP",
        institution_label="Unicamp",
        version="2025.1",
        validity_period="2025-2026",
        curation_source="Perfil local provisório MedQuest; requer validação documental antes de uso decisório.",
        status="experimental",
        weights=normalize_weights({
            "Clínica Médica": 0.20,
            "Cirurgia": 0.20,
            "Ginecologia e Obstetrícia": 0.20,
            "Pediatria": 0.20,
            "Medicina Preventiva": 0.20,
        }),
    ),
    "ENARE": EditalProfile(
        institution_code="ENARE",
        institution_label="ENARE / Ebserh",
        version="2025.1",
        validity_period="2025-2026",
        curation_source="Perfil local provisório MedQuest; requer validação documental antes de uso decisório.",
        status="experimental",
        weights=normalize_weights({
            "Clínica Médica": 0.20,
            "Cirurgia": 0.20,
            "Ginecologia e Obstetrícia": 0.20,
            "Pediatria": 0.20,
            "Medicina Preventiva": 0.20,
        }),
    ),
    "SUS-SP": EditalProfile(
        institution_code="SUS-SP",
        institution_label="SUS-SP",
        version="2025.1",
        validity_period="2025-2026",
        curation_source="Perfil local provisório MedQuest; requer validação documental antes de uso decisório.",
        status="experimental",
        weights=normalize_weights({
            "Clínica Médica": 0.20,
            "Cirurgia": 0.20,
            "Ginecologia e Obstetrícia": 0.20,
            "Pediatria": 0.20,
            "Medicina Preventiva": 0.20,
        }),
    ),
    "UNIFESP": EditalProfile(
        institution_code="UNIFESP",
        institution_label="Unifesp / EPM",
        version="2025.1",
        validity_period="2025-2026",
        curation_source="Perfil local provisório MedQuest; requer validação documental antes de uso decisório.",
        status="experimental",
        weights=normalize_weights({
            "Clínica Médica": 0.20,
            "Cirurgia": 0.20,
            "Ginecologia e Obstetrícia": 0.20,
            "Pediatria": 0.20,
            "Medicina Preventiva": 0.20,
        }),
    ),
}

# Lista canônica restrita de bancas válidas para a aba de Análise
ALLOWED_ANALYSIS_INSTITUTIONS: list[str] = [
    "USP-SP",
    "USP-RP",
    "UNICAMP",
    "UNIFESP",
    "SUS-SP",
]

# Mapeamento de códigos/aliases históricos no banco para as 5 bancas alvo
INSTITUTION_ALIASES: Dict[str, list[str]] = {
    "USP-SP": ["USP-SP", "USP SP", "USP SP 2020", "USP SP 2021", "USP SP 2022", "USP SP 2023", "USP SP 2024"],
    "USP-RP": ["USP-RP", "USP RP 2020", "USP RP 2021", "USP RP 2022", "USP RP 2023", "USP RP 2024"],
    "UNICAMP": ["UNICAMP"],
    "UNIFESP": ["UNIFESP"],
    "SUS-SP": ["SUS-SP", "SUS", "SUS SP 2020", "SUS SP 2021", "SUS SP 2022", "SUS SP 2023", "SUS SP 2024"],
}

def resolve_institution_codes(code: Optional[str]) -> list[str]:
    """Retorna os códigos e variantes de banco para a instituição informada."""
    if not code:
        return []
    cleaned = code.strip().upper()
    for k, aliases in INSTITUTION_ALIASES.items():
        if cleaned == k.upper():
            return aliases
    return [code.strip()]

def get_canonical_institution(code: Optional[str]) -> Optional[str]:
    """Mapeia um código ou alias para a instituição canônica (se pertencer às 5 bancas alvo)."""
    if not code:
        return None
    cleaned = code.strip().upper()
    for canonical, aliases in INSTITUTION_ALIASES.items():
        if any(cleaned == a.upper() for a in aliases):
            return canonical
    return None


def get_edital_profile(institution_code: Optional[str]) -> EditalProfile:
    """Recupera o perfil de edital para a instituição ou constrói fallback experimental."""
    canonical = get_canonical_institution(institution_code)
    code = (canonical or institution_code or "").strip().upper()
    if code in EDITAL_PROFILES_REGISTRY:
        return EDITAL_PROFILES_REGISTRY[code]

    return EditalProfile(
        institution_code=institution_code or "GERAL",
        institution_label=institution_code or "Banco Geral",
        version="custom.1",
        validity_period="2025-2026",
        curation_source="Perfil padrão experimental (pesos equitativos pelas 5 grandes áreas)",
        status="experimental",
        weights=_get_fallback_weights(),
    )
