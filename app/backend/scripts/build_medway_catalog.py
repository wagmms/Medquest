#!/usr/bin/env python3
"""
Build Medway Filtered Catalog for MedQuest.
Parses the Medway Similarity Guide PDF and cross-references all 1,547 Medway exam bank tracks.
Filters exams >= 2020 belonging to institutions similar to USP, UNICAMP, UNIFESP, etc.
Categorizes exams into Tier 1 (Core Premier & Direct Similars) and Tier 2 (Expanded Guide).
Outputs: app/backend/data/medway_catalog_mapped.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Paths
BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
SCRIPTS_DIR = BACKEND_DIR / "scripts"
OUTPUT_FILE = DATA_DIR / "medway_catalog_mapped.json"
PDF_PATH = Path("/home/wagmoraes/Downloads/guia_de_similaridade_ies_corrigido_v3_d7uuu3d.pdf")

sys.path.insert(0, str(SCRIPTS_DIR))
from medway_client import MedwayClient

def normalize_text(s: str) -> str:
    """Strips accents and special characters for fuzzy matching."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", s)


# Canonical Institution Mapping (Codes, Labels, and Match Patterns)
INSTITUTION_REGISTRY: Dict[str, Dict[str, Any]] = {
    # Tier 1 - Core SP & Premier Peers
    "USP-SP": {
        "label": "USP - Hospital das Clínicas da Faculdade de Medicina da USP (HC-FMUSP)",
        "patterns": ["USP-SP", "USP SP", "FMUSP", "HC-FMUSP"],
        "tier": 1,
    },
    "USP-RP": {
        "label": "USP - Hospital das Clínicas da Faculdade de Medicina de Ribeirão Preto (HCRP)",
        "patterns": ["USP-RP", "USP RP", "FMRP", "HCRP"],
        "tier": 1,
    },
    "UNICAMP": {
        "label": "UNICAMP - Hospital de Clínicas da Unicamp (FCM-Unicamp)",
        "patterns": ["UNICAMP", "FCM-UNICAMP"],
        "tier": 1,
    },
    "UNIFESP": {
        "label": "UNIFESP - Hospital Universitário da UNIFESP (EPM)",
        "patterns": ["UNIFESP", "EPM"],
        "tier": 1,
    },
    "EINSTEIN": {
        "label": "Hospital Israelita Albert Einstein (HIAE)",
        "patterns": ["EINSTEIN", "HIAE"],
        "tier": 1,
    },
    "SIRIO": {
        "label": "Hospital Sírio-Libanês (HSL)",
        "patterns": ["SIRIO", "SÍRIO", "HSL"],
        "tier": 1,
    },
    "ENARE": {
        "label": "Exame Nacional de Residência (ENARE)",
        "patterns": ["ENARE"],
        "tier": 1,
    },
    "ENAMED": {
        "label": "Exame Nacional de Medicina (ENAMED)",
        "patterns": ["ENAMED"],
        "tier": 1,
    },
    "SCMSP": {
        "label": "Santa Casa de Misericórdia de São Paulo (SCMSP)",
        "patterns": ["SCMSP", "ISCMSP", "SANTA CASA DE SAO PAULO", "SANTA CASA - SP", "SCM-SP", "SCM SP"],
        "tier": 1,
    },
    "IAMSPE": {
        "label": "Instituto de Assistência Médica ao Servidor Público Estadual de SP (IAMSPE)",
        "patterns": ["IAMSPE"],
        "tier": 1,
    },
    "SUS-SP": {
        "label": "Sistema Único de Saúde de São Paulo (SUS-SP)",
        "patterns": ["SUS-SP", "SUS - SP", "SUS (SP)", "SUS SP"],
        "tier": 1,
    },
    "UNESP": {
        "label": "Universidade Estadual Paulista (UNESP - Botucatu)",
        "patterns": ["UNESP"],
        "tier": 1,
    },
    "HCPA": {
        "label": "Hospital de Clínicas de Porto Alegre (HCPA - UFRGS)",
        "patterns": ["HCPA"],
        "tier": 1,
    },
    "UFCSPA": {
        "label": "Universidade Federal de Ciências da Saúde de Porto Alegre (UFCSPA)",
        "patterns": ["UFCSPA"],
        "tier": 1,
    },
    "FMABC": {
        "label": "Faculdade de Medicina do ABC (FMABC)",
        "patterns": ["FMABC", "ABC"],
        "tier": 1,
    },
    "FAMEMA": {
        "label": "Faculdade de Medicina de Marília (FAMEMA)",
        "patterns": ["FAMEMA"],
        "tier": 1,
    },
    "UERJ": {
        "label": "Universidade do Estado do Rio de Janeiro (UERJ)",
        "patterns": ["UERJ"],
        "tier": 1,
    },
    "UFRJ": {
        "label": "Universidade Federal do Rio de Janeiro (UFRJ)",
        "patterns": ["UFRJ"],
        "tier": 1,
    },
    "AMRIGS": {
        "label": "Associação Médica do Rio Grande do Sul (AMRIGS)",
        "patterns": ["AMRIGS"],
        "tier": 1,
    },
    "SES-PE": {
        "label": "Secretaria Estadual de Saúde de Pernambuco (SES-PE)",
        "patterns": ["SES-PE", "SES - PE", "SES (PE)"],
        "tier": 1,
    },
    "FMJ": {
        "label": "Faculdade de Medicina de Jundiaí (FMJ)",
        "patterns": ["FMJ"],
        "tier": 1,
    },
    "BOS": {
        "label": "Banco de Olhos de Sorocaba (BOS)",
        "patterns": ["BOS"],
        "tier": 1,
    },
    "SCM-RP": {
        "label": "Santa Casa de Misericórdia de Ribeirão Preto (SCM-RP)",
        "patterns": ["SCM-RP", "SCM - RP", "SCMRP"],
        "tier": 1,
    },
    "HRPP": {
        "label": "Hospital Regional de Presidente Prudente (HRPP)",
        "patterns": ["HRPP"],
        "tier": 1,
    },
    "UEL": {
        "label": "Universidade Estadual de Londrina (UEL)",
        "patterns": ["UEL"],
        "tier": 1,
    },
    "AMP": {
        "label": "Associação Médica do Paraná (AMP)",
        "patterns": ["AMP - PR", "AMP (PR)"],
        "tier": 1,
    },
    "UNITAU": {
        "label": "Universidade de Taubaté (UNITAU)",
        "patterns": ["UNITAU"],
        "tier": 1,
    },
    "INEP": {
        "label": "INEP / Revalida Nacional",
        "patterns": ["INEP", "REVALIDA"],
        "tier": 1,
    },
    "PUC-SP": {
        "label": "Pontifícia Universidade Católica de São Paulo (PUC-SP / Sorocaba)",
        "patterns": ["PUC - SOROCABA", "PUC-SOROCABA", "PUC SOROCABA"],
        "tier": 1,
    },
}


def load_similarity_pdf_institutions(pdf_path: Path = PDF_PATH) -> Set[str]:
    """Extracts all target institutions from the similarity guide PDF."""
    if not pdf_path.exists():
        return set()

    import fitz  # PyMuPDF
    doc = fitz.open(pdf_path)
    all_targets = set()

    for page in doc:
        text = page.get_text()
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("Guia") or line in ["IEs", "Similares", "Mesma banca"]:
                continue
            all_targets.add(line)

    return all_targets


def detect_institution(name: str) -> Tuple[str, str, int]:
    """
    Detects institution code, label, and tier from exam name.
    Defaults to Tier 2 if institution is recognized from guide, or Tier 1 if premier.
    """
    norm_name = normalize_text(name)

    # 1. Check Tier 1 registry first
    for code, info in INSTITUTION_REGISTRY.items():
        for pat in info["patterns"]:
            norm_pat = normalize_text(pat)
            if norm_pat in norm_name:
                return code, info["label"], info["tier"]

    # 2. General fallback for recognized state institutions
    state_match = re.search(r"\b([A-Z]{3,8})\s*-\s*([A-Z]{2})\b", name)
    if state_match:
        code = f"{state_match.group(1)}-{state_match.group(2)}"
        return code, f"{code} (Guia de Similaridade)", 2

    # Clean fallback prefix
    clean_prefix = name.split("-")[0].strip() if "-" in name else name.split()[0].strip()
    return clean_prefix.upper(), f"{clean_prefix.upper()} (Concurso)", 2


def build_catalog(
    min_year: int = 2020,
    force_fetch: bool = False,
    output_path: Path = OUTPUT_FILE,
) -> List[Dict[str, Any]]:
    """Builds and saves the mapped catalog of filtered exams."""
    print("=" * 65)
    print("Building Medway Filtered Catalog (Tier 1 & Tier 2 >= 2020)")
    print("=" * 65)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    pdf_insts = load_similarity_pdf_institutions()
    print(f"[PDF] Loaded {len(pdf_insts)} institutions from similarity guide.")

    # Fetch or load raw exam catalog
    client = MedwayClient()
    cached_catalog = BACKEND_DIR / "data" / "all_medway_exams_raw.json"
    raw_exams: List[Dict[str, Any]] = []

    if not force_fetch and cached_catalog.exists():
        print(f"[CACHE] Loading raw catalog from {cached_catalog.name}...")
        with open(cached_catalog, "r", encoding="utf-8") as f:
            raw_exams = json.load(f)
    else:
        print("[API] Fetching full exam catalog from Medway API...")
        limit = 100
        offset = 0
        while True:
            res = client.list_exams(limit=limit, offset=offset)
            items = res.get("results", [])
            if not items:
                break
            raw_exams.extend(items)
            offset += limit
            total = res.get("count", 0)
            sys.stdout.write(f"\r  Fetched {len(raw_exams)} / {total} exams...")
            sys.stdout.flush()
            if len(raw_exams) >= total:
                break

        print(f"\n[API] Successfully retrieved {len(raw_exams)} exams.")
        with open(cached_catalog, "w", encoding="utf-8") as f:
            json.dump(raw_exams, f, ensure_ascii=False, indent=2)

    mapped_exams = []
    skipped_under_min_year = 0
    skipped_non_similar = 0

    for exam in raw_exams:
        year = exam.get("year") or 0
        if year < min_year:
            skipped_under_min_year += 1
            continue

        name = exam.get("name", "")
        inst_code, inst_label, tier = detect_institution(name)

        # Check if matched or in PDF guide
        norm_name = normalize_text(name)
        in_pdf = any(normalize_text(p) in norm_name for p in pdf_insts) or (inst_code in INSTITUTION_REGISTRY)

        if not in_pdf and tier == 2:
            skipped_non_similar += 1
            continue

        mapped_exams.append({
            "track_id": exam["id"],
            "name": name,
            "year": year,
            "question_count": exam.get("question_count", 0),
            "institution_code": inst_code,
            "institution_label": inst_label,
            "tier": tier,
            "tier_label": "Tier 1 (Core Premier & Direct Similars)" if tier == 1 else "Tier 2 (Expanded Guide)",
            "priority": (1 if tier == 1 else 2, -year, -exam.get("question_count", 0)),
        })

    # Sort by priority: Tier 1 first, newest year first, largest question count first
    mapped_exams.sort(key=lambda x: x["priority"])

    tier1_count = sum(1 for e in mapped_exams if e["tier"] == 1)
    tier1_questions = sum(e["question_count"] for e in mapped_exams if e["tier"] == 1)
    tier2_count = sum(1 for e in mapped_exams if e["tier"] == 2)
    tier2_questions = sum(e["question_count"] for e in mapped_exams if e["tier"] == 2)

    print("\n--- Catalog Summary ---")
    print(f"Total Filtered Exams (>= {min_year}): {len(mapped_exams)}")
    print(f"  • Tier 1 (Core USP/UNICAMP/UNIFESP Peers): {tier1_count} exams | {tier1_questions} questions")
    print(f"  • Tier 2 (Expanded Similarity Guide):      {tier2_count} exams | {tier2_questions} questions")
    print(f"Skipped (Year < {min_year}): {skipped_under_min_year}")
    print(f"Skipped (Not in Similarity Guide): {skipped_non_similar}")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(mapped_exams, f, ensure_ascii=False, indent=2)

    print(f"\n[SAVED] Output catalog saved to: {output_path}")
    return mapped_exams


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Medway Filtered Catalog")
    parser.add_argument("--min-year", type=int, default=2020, help="Minimum exam year (default: 2020)")
    parser.add_argument("--force-fetch", action="store_true", help="Re-fetch catalog from Medway API")
    args = parser.parse_args()

    build_catalog(min_year=args.min_year, force_fetch=args.force_fetch)


if __name__ == "__main__":
    main()
