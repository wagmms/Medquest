import os
import re
import sqlite3
import sys
from pathlib import Path

import pytest

# Ensure scripts dir is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BACKEND_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from build_medway_catalog import detect_institution, normalize_text
from extract_medway import (
    clean_html_to_markdown,
    extract_gabarito,
    format_medway_golden_explanation,
    TaxonomyMapper,
)


class TestImageAndMarkdownFormatting:
    """Verifies that all image links and HTML structures are converted to ![imagem](url)."""

    def test_converts_html_img_tag(self):
        html_input = '<p>Texto da questão</p><img alt="Figura 1" src="https://cdn.medway.com.br/media/fig1.png"/>'
        out = clean_html_to_markdown(html_input)
        assert "![imagem](https://cdn.medway.com.br/media/fig1.png)" in out
        assert "<img" not in out

    def test_converts_html_anchor_with_image(self):
        html_input = '<p>Veja o achado em <a href="https://cdn.medway.com.br/media/rx.jpg">Radiografia</a>.</p>'
        out = clean_html_to_markdown(html_input)
        assert "![imagem](https://cdn.medway.com.br/media/rx.jpg)" in out
        assert "<a" not in out

    def test_converts_markdown_link_missing_exclamation(self):
        md_input = "Conforme o gráfico [Figura](https://cdn.medway.com.br/media/grafico.png), nota-se melhora."
        out = clean_html_to_markdown(md_input)
        assert "![imagem](https://cdn.medway.com.br/media/grafico.png)" in out
        assert "[Figura]" not in out

    def test_converts_standalone_image_url(self):
        text_input = "Segue a curva evolutiva:\nhttps://cdn.medway.com.br/media/curva.png\nO paciente teve alta."
        out = clean_html_to_markdown(text_input)
        assert "![imagem](https://cdn.medway.com.br/media/curva.png)" in out

    def test_preserves_valid_markdown_image_without_duplication(self):
        text_input = "Veja a imagem: ![imagem](https://cdn.medway.com.br/media/valid.png)"
        out = clean_html_to_markdown(text_input)
        assert "![imagem](https://cdn.medway.com.br/media/valid.png)" in out
        assert "![" in out
        assert "!![" not in out


class TestInstitutionDetectionAndTiers:
    """Verifies institution recognition and Tier 1 assignment."""

    def test_detects_tier_1_institutions(self):
        test_cases = [
            ("USP-SP - SP-2024-Objetiva", "USP-SP", 1),
            ("UNICAMP - SP-2025-Objetiva", "UNICAMP", 1),
            ("UNIFESP - SP-2023-Objetiva", "UNIFESP", 1),
            ("ENARE-2024-Objetiva", "ENARE", 1),
            ("EINSTEIN - SP-2026-Objetiva", "EINSTEIN", 1),
            ("Hospital Sírio-Libanês 2024", "SIRIO", 1),
            ("ISCMSP - SP-2025-Objetiva", "SCMSP", 1),
            ("IAMSPE - SP-2023-Objetiva", "IAMSPE", 1),
            ("SUS-SP - SP-2024-Objetiva", "SUS-SP", 1),
            ("HCPA - RS-2025-Objetiva", "HCPA", 1),
        ]
        for name, expected_code, expected_tier in test_cases:
            code, label, tier = detect_institution(name)
            assert code == expected_code, f"Failed for {name}: got {code}, expected {expected_code}"
            assert tier == expected_tier, f"Failed tier for {name}: got {tier}, expected {expected_tier}"


class TestDeduplicationLogic:
    """Verifies that questions with identical stems are deduplicated."""

    def test_normalized_stem_match(self):
        stem_a = "Paciente, sexo masculino, 45 anos, com dor epigástrica há 2 semanas."
        stem_b = "  PACIENTE, sexo masculino, 45 ANOS, com dor epigastrica ha 2 semanas!  "
        assert normalize_text(stem_a)[:180] == normalize_text(stem_b)[:180]

    def test_deduplication_in_memory_simulation(self):
        existing_stems = {
            normalize_text("Mulher de 28 anos, G2P1, com 32 semanas de gestação, queixa-se de cefaleia.")[:180]
        }
        candidate_dup = "mulher de 28 anos, g2p1, com 32 semanas de gestacao, queixa-se de cefaleia."
        norm_candidate = normalize_text(candidate_dup)[:180]
        assert norm_candidate in existing_stems, "Candidate should be flagged as duplicate"

        candidate_new = "Homem de 60 anos, hipertenso, admitido com dor torácica súbita."
        assert normalize_text(candidate_new)[:180] not in existing_stems


class TestGoldenExplanationStructure:
    """Verifies that the generated explanation follows MedQuest's 5-Pillar Golden Template."""

    def test_golden_explanation_pillars(self):
        exp_dict = {
            "conclusion": "Critério de Duke modificado para endocardite infecciosa.",
            "introduction": "A endocardite é diagnosticada através de critérios maiores e menores.",
            "option_a": "Incorreta. Não atende aos critérios maiores.",
            "option_b": "Correta. Hemocultura positiva para S. aureus e ecocardiograma com vegetação.",
            "bibliography": "Diretriz Brasileira de Valvopatias 2020.",
        }
        options = [
            {"letter": "a", "content": "Critério menor isolado"},
            {"letter": "b", "content": "Critérios maiores presentes"},
        ]
        out = format_medway_golden_explanation(exp_dict, options, "B")

        assert "**Gabarito**: Letra B" in out
        assert "**Pulo do Gato**:" in out
        assert "**Raciocínio Clínico**:" in out
        assert "**Por que a Letra B é a Correta?**:" in out
        assert "**Análise dos Distratores**:" in out
        assert "**Referências Bibliográficas**:" in out
