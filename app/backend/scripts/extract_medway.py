#!/usr/bin/env python3
"""
Medway Extractor CLI for MedQuest.
Extracts questions, alternatives, images, and full structured explanations
directly from Medway CMS API, saves to local JSON, and imports into medquest.db.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import html
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Set up paths
BACKEND_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BACKEND_DIR / "medquest.db"
DEFAULT_OUTPUT_DIR = BACKEND_DIR / "data" / "medway_extracted"

# Add scripts directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from medway_client import MedwayClient

# Institutions registry
INSTITUTIONS = {
    "USP-SP": ("USP-SP", "USP - Hospital das Clínicas da Faculdade de Medicina da USP (HC-FMUSP)"),
    "USP-RP": ("USP-RP", "USP - Hospital das Clínicas da Faculdade de Medicina de Ribeirão Preto (HCRP)"),
    "UNIFESP": ("UNIFESP", "UNIFESP - Hospital Universitário da UNIFESP"),
    "UNICAMP": ("UNICAMP", "UNICAMP - Hospital de Clínicas da Unicamp (FCM-Unicamp)"),
    "SCMSP": ("SCMSP", "Santa Casa de Misericórdia de São Paulo (SCMSP)"),
    "HSL": ("HSL", "Hospital Sírio-Libanês (HSL)"),
    "EINSTEIN": ("EINSTEIN", "Hospital Israelita Albert Einstein (HIAE)"),
    "ENARE": ("ENARE", "Exame Nacional de Residência (ENARE)"),
    "ENAMED": ("ENAMED", "Exame Nacional de Medicina (ENAMED)"),
    "SUS-SP": ("SUS-SP", "Sistema Único de Saúde de São Paulo (SUS-SP)"),
    "AMRIGS": ("AMRIGS", "Associação Médica do Rio Grande do Sul (AMRIGS)"),
    "PSU-MG": ("PSU-MG", "Processo Seletivo Unificado de Minas Gerais (PSU-MG)"),
    "SES-PE": ("SES-PE", "Secretaria Estadual de Saúde de Pernambuco (SES-PE)"),
    "SUS-BA": ("SUS-BA", "Sistema Único de Saúde da Bahia (SUS-BA)"),
    "FAMERP": ("FAMERP", "Faculdade de Medicina de São José do Rio Preto (FAMERP)"),
    "UFCSPA": ("UFCSPA", "Universidade Federal de Ciências da Saúde de Porto Alegre (UFCSPA)"),
    "INEP": ("INEP", "Instituto Nacional de Estudos e Pesquisas Educacionais Anísio Teixeira (INEP)"),
}


def detect_inst_from_title(title: str) -> Tuple[str, str]:
    """Infers canonical institution code and label from exam/track title."""
    t = title.upper()
    for code, (c, label) in INSTITUTIONS.items():
        if code in t:
            return c, label
    if "SANTA CASA" in t or "SCM-SP" in t:
        return INSTITUTIONS["SCMSP"]
    if "SÍRIO" in t or "SIRIO" in t:
        return INSTITUTIONS["HSL"]
    if "REVALIDA" in t:
        return INSTITUTIONS["INEP"]
    # Default fallback
    clean_name = title.split("-")[0].strip() if "-" in title else title[:15].strip()
    return clean_name.upper(), title


def clean_html_to_markdown(raw_html: Any) -> str:
    """Converts HTML formatting into clean GitHub-flavored markdown with embedded images."""
    if not isinstance(raw_html, str) or not raw_html.strip():
        return ""
    txt = html.unescape(raw_html)

    # Standardize paragraph breaks and line breaks
    txt = re.sub(r"</p>\s*<p[^>]*>", "\n\n", txt, flags=re.IGNORECASE)
    txt = re.sub(r"<br\s*/?>", "\n", txt, flags=re.IGNORECASE)

    # Bold and italic
    txt = re.sub(r"<(strong|b)[^>]*>(.*?)</\1>", r"**\2**", txt, flags=re.DOTALL | re.IGNORECASE)
    txt = re.sub(r"<(em|i)[^>]*>(.*?)</\1>", r"*\2*", txt, flags=re.DOTALL | re.IGNORECASE)

    # 1. Convert <img ... src="url" ...> to ![imagem](url)
    txt = re.sub(r'<img\b[^>]*\bsrc=["\'](https?://[^"\']+)["\'][^>]*>', r"\n\n![imagem](\1)\n\n", txt, flags=re.IGNORECASE)

    # 2. Convert <a href="image_url">...</a> to ![imagem](image_url)
    txt = re.sub(r'<a\b[^>]*\bhref=["\'](https?://[^"\']+\.(?:png|jpe?g|gif|webp|svg)(?:\?[^"\']*)?)["\'][^>]*>.*?</a>', r"\n\n![imagem](\1)\n\n", txt, flags=re.IGNORECASE)

    # Strip remaining HTML tags
    txt = re.sub(r"<[^>]+>", " ", txt)

    # 3. Convert markdown links pointing to images missing leading !: [text](url.png) -> ![imagem](url.png)
    txt = re.sub(r'(?<!!)(?:\[([^\]]*)\])\((https?://[^\)]+\.(?:png|jpe?g|gif|webp|svg)(?:\?[^\)]*)?)\)', r'![imagem](\2)', txt, flags=re.IGNORECASE)

    # 4. Convert standalone raw image URLs (on their own line or text)
    txt = re.sub(r'(?<![(\'"])(https?://(?:cdn\.medway\.com\.br|storage\.googleapis\.com)[^\s"\'<>]+\.(?:png|jpe?g|gif|webp|svg)(?:\?[^\s"\'<>]*)?)(?![)\'"])', r'\n\n![imagem](\1)\n\n', txt, flags=re.IGNORECASE)

    # Normalize horizontal spacing while preserving newlines
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in txt.splitlines()]
    txt = "\n".join(lines)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt.strip()


import unicodedata

def normalize_text(s: str) -> str:
    """Normalizes text by stripping accents and special characters."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", s)


class TaxonomyMapper:
    """Maps Medway tags and specialties to MedQuest's 170 canonical (area, subtema) pairs."""

    def __init__(self, data_dir: Path = BACKEND_DIR / "data"):
        self.data_dir = data_dir
        self.aliases: Dict[str, Tuple[str, str]] = {}
        self.sub_to_area: Dict[str, Tuple[str, str]] = {}
        self._load()

    def _load(self) -> None:
        canon_file = self.data_dir / "canonical_taxonomy.json"
        if canon_file.exists():
            with open(canon_file, "r", encoding="utf-8") as f:
                tax = json.load(f)
            for area, subs in tax.items():
                for s in subs:
                    self.sub_to_area[normalize_text(s)] = (area, s)

        dp_file = self.data_dir / "de_para_temas.json"
        if dp_file.exists():
            with open(dp_file, "r", encoding="utf-8") as f:
                dp = json.load(f)
            for area, items in dp.get("areas", {}).items():
                for it in items:
                    self.aliases[normalize_text(it["nome_original"])] = (it["area"], it["nome_novo"])

        # Curated Medway tag variants -> canonical subtema
        curated: Dict[str, Tuple[str, str]] = {
            "epilepsias e crises convulsivas": ("Pediatria", "Convulsão Febril, Epilepsias e Síndromes Convulsivas na Infância"),
            "rotura prematura das membranas ovulares e infeccao ovular": ("Ginecologia e Obstetrícia", "Amniorrexe Prematura (RPMO) e Corioamnionite"),
            "sindromes hipertensivas na gestacao": ("Ginecologia e Obstetrícia", "Síndromes Hipertensivas na Gravidez (Pré-eclâmpsia e Eclâmpsia)"),
            "abdome agudo perfurativo": ("Cirurgia", "Abdome Agudo Perfurativo e Úlcera Péptica Perfurada"),
            "abdome agudo isquemico": ("Cirurgia", "Abdome Agudo Vascular e Isquemia Mesentérica"),
            "abordagem inicial xabcde": ("Cirurgia", "Atendimento Inicial ao Politraumatizado (Protocolo xABCDE)"),
            "afeccoes benignas das vias biliares": ("Cirurgia", "Litíase Biliar, Colecistite, Coledocolitíase e Colangite"),
            "afeccoes urologicas benignas": ("Cirurgia", "Hiperplasia Prostática Benigna (HPB) e Litíase Urinária"),
            "colon e reto na cirurgia": ("Cirurgia", "Coloproctologia: Doenças Orificiais e Afecções Colorretais"),
            "cuidados e complicacoes posoperatorias": ("Cirurgia", "Manejo Pós-Operatório e Tratamento de Complicações Cirúrgicas"),
            "cuidados preoperatorios": ("Cirurgia", "Avaliação Pré-Operatória e Estratificação de Risco Cirúrgico"),
            "doencas sexualmente transmissiveis": ("Clínica Médica", "Infecções Sexualmente Transmissíveis (ISTs) no Adulto"),
            "doenca arterial periferica": ("Cirurgia", "Doença Arterial Obstrutiva Periférica e Oclusões Arteriais Agudas"),
            "estenose de carotidas": ("Cirurgia", "Doença Arterial Obstrutiva Periférica e Oclusões Arteriais Agudas"),
            "fraturas osseas": ("Cirurgia", "Fraturas Ósseas e Princípios Gerais de Osteossíntese"),
            "hemorragia digestiva cirurgia": ("Cirurgia", "Hemorragia Digestiva Alta e Baixa na Emergência Cirúrgica"),
            "hiv e aids no adulto naogestante": ("Clínica Médica", "Infecção pelo HIV: Diagnóstico, TARV e Infecções Oportunistas"),
            "infeccoes fungicas": ("Clínica Médica", "Dermatoses Infecciosas, Hanseníase e Leishmanioses"),
            "sindrome disfagica": ("Cirurgia", "Distúrbios Motores do Esôfago, Megaesôfago e Síndrome Disfágica"),
            "sindromes dispepticas": ("Cirurgia", "Doença do Refluxo Gastroesofágico (DRGE) e Úlcera Péptica"),
            "tendinites tenossinovites fasceites e bursites": ("Cirurgia", "Tendinopatias, Bursites e Síndromes por Sobrecarga Musculoesquelética"),
            "trauma de face e pescoco": ("Cirurgia", "Trauma de Face e Pescoço (Trauma Cervical e Fraturas Maxilofaciais)"),
            "trauma de membros e extremidades": ("Cirurgia", "Trauma Ortopédico de Extremidades e Síndrome Compartimental"),
            "trauma abdominal": ("Cirurgia", "Trauma Abdominal Fechado e Penetrante (FAST e Laparotomia)"),
            "trauma toracico": ("Cirurgia", "Trauma Torácico: Pneumotórax, Hemotórax e Tamponamento Cardíaco"),
            "tumores dermatologicos": ("Cirurgia", "Oncologia Cutânea: Melanoma, CBC e CEC"),
            "tumores do aparelho digestivo": ("Cirurgia", "Neoplasias do Trato Gastrointestinal (Esôfago, Estômago, Pâncreas e Cólon)"),
            "tumores cabeca e pescoco": ("Cirurgia", "Neoplasias de Cabeça e Pescoço e Nódulos Tireoidianos Cirúrgicos"),
            "tumores pulmonares e do mediastino": ("Cirurgia", "Câncer de Pulmão, Nódulo Pulmonar Solitário e Tumores do Mediastino"),
        }
        for k, v in curated.items():
            self.aliases[k] = v

    def map(self, tags: List[str], speciality: str) -> Tuple[str, str]:
        """Maps tags and speciality to (canonical_area, canonical_subtema)."""
        # 1. Exact match in aliases or canonical dictionary
        for cand in tags + [speciality]:
            n = normalize_text(cand)
            if n in self.aliases:
                return self.aliases[n]
            if n in self.sub_to_area:
                return self.sub_to_area[n]

        # 2. Substring matching against canonical subtemas
        for cand in tags:
            n = normalize_text(cand)
            if len(n) > 5:
                for sub_norm, pair in self.sub_to_area.items():
                    if n in sub_norm or sub_norm in n:
                        return pair

        area = infer_area_from_tags(speciality, tags)
        sub = tags[0] if tags else (speciality or "Clínica Médica Geral")
        return area, sub


def infer_area_from_tags(speciality: str, tags: list[str]) -> str:
    """Classifies a question into one of the 5 canonical medical areas."""
    combined = (speciality + " " + " ".join(tags)).lower()
    if any(k in combined for k in ["cir", "cirurgia", "trauma", "abdome agudo", "urologia", "ortopedia", "queimadur"]):
        return "Cirurgia"
    if any(k in combined for k in ["ped", "pediatria", "puericultura", "neonatologia", "infân", "criança"]):
        return "Pediatria"
    if any(k in combined for k in ["go", "ginecologia", "obstetrícia", "fetal", "parto", "gestação", "prenatal", "puerpério"]):
        return "Ginecologia e Obstetrícia"
    if any(k in combined for k in ["prev", "preventiva", "sus", "epidemiologia", "saúde coletiva", "trabalhador", "bioética", "ética"]):
        return "Medicina Preventiva"
    return "Clínica Médica"


def extract_gabarito(
    exp_dict: Any,
    options_list: List[Dict[str, Any]],
    q_detail: Optional[Dict[str, Any]] = None,
) -> str:
    """Determines the correct alternative letter using a high-precision multi-tier scoring algorithm."""
    if not isinstance(exp_dict, dict):
        exp_dict = {}

    # Tier 1: Check if the question detail explicitly contains correct_letters
    if q_detail and q_detail.get("correct_letters"):
        return q_detail["correct_letters"][0].upper()

    # Tier 1b: Check if any option explicitly has is_correct == True / 1
    for opt in options_list:
        if opt.get("is_correct") in (True, 1, "true", "1"):
            let = opt.get("letter")
            if let:
                return str(let).upper()

    # Tier 1c: Check full_explanation for unambiguous gold standard labels
    full_text = exp_dict.get("full_explanation", "") or ""
    if full_text:
        c_matches = list(set([m.upper() for m in re.findall(r"(?:<br>|\n|^|>)\s*([A-E])\s*[-–:]\s*(?:<[^>]+>)*\s*(?<!in)corret[ao]\b", full_text, re.IGNORECASE)]))
        inc_matches = list(set([m.upper() for m in re.findall(r"(?:<br>|\n|^|>)\s*([A-E])\s*[-–:]\s*(?:<[^>]+>)*\s*incorret[ao]\b", full_text, re.IGNORECASE)]))
        if len(c_matches) == 1 and len(inc_matches) >= 2 and c_matches[0] not in inc_matches:
            return c_matches[0]

    if not options_list:
        return "A"

    # Tier 2: Check for explicit markers in option commentary
    scores: Dict[str, int] = {}
    for opt in options_list:
        let = opt.get("letter", "").lower()
        raw_opt = exp_dict.get(f"option_{let}", "") or ""
        raw_short = exp_dict.get(f"short_option_{let}", "") or ""
        txt = html.unescape(raw_opt + " " + raw_short)
        txt_clean = re.sub(r"<[^>]+>", " ", txt).strip().lower()

        score = 0
        first_80 = txt_clean[:80]

        # Explicit distractor markers at the start
        if any(w in first_80 for w in ["incorret", "errad", "distrator", "falsa", "não é a conduta", "não seria a conduta"]):
            score -= 100
        # Explicit affirmative markers at the start
        elif any(w in first_80 for w in ["gabarito", "resposta certa", "resposta correta", "alternativa correta", "está correta", "é a correta"]):
            score += 100
        elif re.search(r"^\*{0,2}corret[oa]\b", first_80):
            score += 100

        # Frases inequívocas de que esta opção é a resposta / gabarito (inclusive para questões que pedem a incorreta)
        if any(w in txt_clean for w in [
            "resposta desta questão", "resposta da questão", "gabarito desta questão", "gabarito da questão",
            "portanto, a resposta", "portanto, o gabarito", "deve ser assinalada", "alternativa a ser assinalada"
        ]):
            score += 150

        # Contextual distractor indicators anywhere in the explanation
        if any(w in txt_clean for w in [
            "não é um", "não é uma", "esta alternativa comete", "esta alternativa cria",
            "esta alternativa representa", "confunde ", "não decorre", "não há obrigatoriedade",
            "não seria a conduta", "não condiz com", "está contraindicad", "é contraindicad",
            "não tem indicação", "não é recomendad"
        ]):
            score -= 50

        # High-confidence affirmative indicators anywhere in the explanation
        if any(w in txt_clean for w in [
            "esta é a resposta correta", "esta é a alternativa correta", "portanto, alternativa correta",
            "portanto, a alternativa correta", "logo, a alternativa correta", "gabarito: letra",
            "gabarito oficial"
        ]):
            score += 50

        scores[let.upper()] = score

    # Check for strong explicit winner (score >= 100 and no other option has >= 100)
    top_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    if top_scores and top_scores[0][1] >= 100:
        if len(top_scores) == 1 or top_scores[0][1] > top_scores[1][1]:
            return top_scores[0][0]

    # Tier 3: Wisdom of the crowd via response_percentage
    # If students overwhelmingly selected an option and its explanation is not marked incorrect
    sorted_by_pct = sorted(options_list, key=lambda o: float(o.get("response_percentage") or 0.0), reverse=True)
    if sorted_by_pct:
        top_pct_opt = sorted_by_pct[0]
        top_pct = float(top_pct_opt.get("response_percentage") or 0.0)
        top_let = (top_pct_opt.get("letter") or "").upper()
        sec_pct = float(sorted_by_pct[1].get("response_percentage") or 0.0) if len(sorted_by_pct) > 1 else 0.0

        if top_pct >= 45.0 and scores.get(top_let, 0) >= 0 and (top_pct - sec_pct >= 10.0 or top_pct >= 60.0):
            return top_let

    # Tier 4: Fallback to best non-negative text score
    if top_scores and top_scores[0][1] > 0:
        return top_scores[0][0]

    # Tier 5: Best percentage fallback
    if sorted_by_pct:
        top_pct_opt = sorted_by_pct[0]
        top_pct = float(top_pct_opt.get("response_percentage") or 0.0)
        if top_pct >= 35.0:
            return (top_pct_opt.get("letter") or "A").upper()

    return "A"


def format_medway_golden_explanation(
    exp_dict: Any,
    options_list: List[Dict[str, Any]],
    correct_letter: str,
    is_discursive: bool = False,
) -> str:
    """Transforms raw Medway explanation fields into MedQuest's 5-Pillar Golden Template."""
    if not isinstance(exp_dict, dict):
        raw_str = exp_dict if isinstance(exp_dict, str) else ""
        exp_dict = {"introduction": raw_str}

    # 1. Header & Gabarito
    if is_discursive or not options_list:
        gabarito_header = "**Gabarito**: DISCURSIVA / RESPOSTA CURTA (Ver Padrão de Resposta abaixo)"
    else:
        gabarito_header = f"**Gabarito**: Letra {correct_letter}"

    # 2. Pulo do Gato (Takeaway / Key Clinical Concept)
    conclusion_raw = exp_dict.get("conclusion") or ""
    conclusion_clean = clean_html_to_markdown(conclusion_raw)
    pulo_gato = (
        f"**Pulo do Gato**:\n{conclusion_clean}"
        if conclusion_clean
        else "**Pulo do Gato**:\nAtenção aos conceitos centrais e critérios diagnósticos explorados pela banca examinadora."
    )

    # 3. Clinical Reasoning (Introduction)
    intro_raw = (
        exp_dict.get("introduction")
        or exp_dict.get("actual_explanation")
        or exp_dict.get("full_explanation")
        or ""
    )
    intro_clean = clean_html_to_markdown(intro_raw)
    header_raciocinio = (
        "**Raciocínio Clínico / Padrão de Resposta Esperado**:"
        if (is_discursive or not options_list)
        else "**Raciocínio Clínico**:"
    )
    raciocinio = f"{header_raciocinio}\n{intro_clean}" if intro_clean else ""

    # 4. Analysis of Correct Alternative & Distractors
    if not is_discursive and options_list:
        correct_text = ""
        distractors_lines = []
        for opt in options_list:
            let = opt.get("letter", "").upper()
            let_lower = let.lower()
            opt_raw = exp_dict.get(f"option_{let_lower}") or exp_dict.get(f"short_option_{let_lower}") or ""
            opt_clean = clean_html_to_markdown(opt_raw)
            opt_clean_body = re.sub(r"^[A-E]\)\s*", "", opt_clean, flags=re.IGNORECASE)
            opt_clean_body = re.sub(r"^(?:[-*•]\s*)?(?:Alternativa|Letra)\s+[A-E](?:\s*\([^)]*\))?\s*:?\s*", "", opt_clean_body, flags=re.IGNORECASE)
            opt_clean_body = re.sub(r"^[A-E]\s*-\s*(?:Correta|Incorreta)\.?\s*", "", opt_clean_body, flags=re.IGNORECASE).strip()

            if let == correct_letter:
                correct_text = (
                    opt_clean_body
                    if opt_clean_body
                    else "Alternativa correta conforme as diretrizes e raciocínio clínico apresentados."
                )
            else:
                if opt_clean_body:
                    distractors_lines.append(f"- **Letra {let}**: {opt_clean_body}")
                else:
                    distractors_lines.append(f"- **Letra {let}**: Incorreta.")

        por_que_certa = f"**Por que a Letra {correct_letter} é a Correta?**:\n{correct_text}"
        distratores_str = (
            "**Análise dos Distratores**:\n" + "\n".join(distractors_lines)
            if distractors_lines
            else ""
        )
    else:
        por_que_certa = ""
        distratores_str = ""

    # 5. References / Guidelines
    bib_raw = exp_dict.get("bibliography") or ""
    bib_clean = clean_html_to_markdown(bib_raw)
    bib_str = f"**Referências Bibliográficas**:\n{bib_clean}" if bib_clean else ""

    sections = [gabarito_header, pulo_gato]
    if raciocinio:
        sections.append(raciocinio)
    if por_que_certa:
        sections.append(por_que_certa)
    if distratores_str:
        sections.append(distratores_str)
    if bib_str:
        sections.append(bib_str)

    res = "\n\n".join(sections)
    if not is_discursive and options_list:
        try:
            from fix_misplaced_distractors import parse_and_fix_explanation
            changed, fixed_res, _ = parse_and_fix_explanation(
                0, correct_letter, res, [opt.get("letter", "") for opt in options_list]
            )
            if changed:
                return fixed_res
        except Exception:
            pass

    return res


class MedwayExtractor:
    """Orchestrates extraction from Medway API and importation into MedQuest."""

    def __init__(self, client: Optional[MedwayClient] = None, output_dir: Path = DEFAULT_OUTPUT_DIR):
        self.client = client or MedwayClient()
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.taxonomy_mapper = TaxonomyMapper()

    def extract_track(
        self,
        track_id: int | str,
        category_name: str = "exams",
        track_title: Optional[str] = None,
        year: Optional[int] = None,
        delay: float = 0.0,
        resume: bool = True,
        workers: int = 4,
    ) -> Dict[str, Any]:
        """
        Extracts all questions and explanations for a given track ID and saves to JSON.
        Uses ThreadPoolExecutor for high-speed concurrent downloads while respecting rate limits.
        """
        dest_dir = self.output_dir / category_name
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / f"track_{track_id}.json"

        # Check existing cached file
        if resume and dest_file.exists():
            try:
                with open(dest_file, "r", encoding="utf-8") as f:
                    cached_pkg = json.load(f)
                if cached_pkg.get("complete"):
                    print(f"[{track_id}] Already completely extracted in {dest_file.name}. Skipping API fetch.")
                    return cached_pkg
            except Exception:
                pass

        print(f"\n=======================================================")
        print(f"[EXTRACTING] Track ID: {track_id}")

        track_fast = self.client.get_track_fast(track_id)
        name = track_title or track_fast.get("name", f"Track {track_id}")
        exam_year = year or track_fast.get("year", 2026)
        print(f"Name: {name} (Year: {exam_year})")

        # Get questions list
        q_list = self.client.get_track_questions(track_id)
        total_q = len(q_list)
        print(f"Total questions to fetch: {total_q} (using {workers} workers)")
        print(f"=======================================================")

        def _fetch_one(q_meta: Dict[str, Any]) -> Dict[str, Any]:
            qid = q_meta["id"]
            q_detail = {}
            try:
                q_detail = self.client.get_question_detail(qid, track_id=track_id)
            except Exception as e:
                q_detail = {}

            if delay > 0:
                time.sleep(delay)

            exp_detail = {}
            try:
                exp_detail = self.client.get_question_explanation(qid, track_id=track_id)
            except Exception as e:
                exp_detail = {}

            if delay > 0:
                time.sleep(delay)

            return {
                "meta": q_meta,
                "detail": q_detail,
                "explanation": exp_detail,
            }

        extracted_questions = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for idx, item in enumerate(pool.map(_fetch_one, q_list), start=1):
                sys.stdout.write(f"\rFetching questions {idx}/{total_q}...")
                sys.stdout.flush()
                extracted_questions.append(item)

        # Validation & Healing Pass: re-fetch any question that failed or was rate limited
        missing = [
            it for it in extracted_questions
            if not it.get("detail") or not it.get("detail", {}).get("content")
        ]
        if missing:
            print(f"\n[RETRY PASS] {len(missing)} questions had empty details due to rate limits. Cooling down 6s before retry pass...")
            time.sleep(6)
            for m_idx, it in enumerate(missing, start=1):
                qid = it["meta"]["id"]
                for attempt in range(1, 6):
                    try:
                        print(f"  [{m_idx}/{len(missing)}] Re-fetching question {qid} (attempt {attempt}/5)...")
                        det = self.client.get_question_detail(qid, track_id=track_id)
                        if det and det.get("content"):
                            it["detail"] = det
                            break
                    except Exception as err:
                        print(f"    Failed attempt {attempt}: {err}. Retrying in {attempt * 4}s...")
                        time.sleep(attempt * 4)

                # Also verify explanation is present
                if not it.get("explanation"):
                    try:
                        exp = self.client.get_question_explanation(qid, track_id=track_id)
                        if exp:
                            it["explanation"] = exp
                    except Exception:
                        pass

        # Final Strict Integrity Guard
        still_unresolved = [
            it for it in extracted_questions
            if not it.get("detail") or not it.get("detail", {}).get("content")
        ]
        if still_unresolved:
            raise RuntimeError(
                f"[CORRUPTION GUARD] Track {track_id} has {len(still_unresolved)} questions with missing statements "
                f"after all retries. Refusing to mark package as complete or ingest to DB."
            )

        print(f"\n[DONE] Successfully downloaded {len(extracted_questions)} questions with complete explanations.")

        package = {
            "track_id": track_id,
            "name": name,
            "year": exam_year,
            "track_fast": track_fast,
            "total_questions": len(extracted_questions),
            "questions": extracted_questions,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "complete": True,
        }

        with open(dest_file, "w", encoding="utf-8") as f:
            json.dump(package, f, ensure_ascii=False, indent=2)
        print(f"[SAVED] Saved track package to {dest_file}")

        return package

    def import_package_to_db(
        self,
        package: Dict[str, Any],
        editorial_status: str = "autoral",
        db_path: Path = DB_PATH,
        deduplicate: bool = True,
    ) -> Tuple[int, int, int]:
        """
        Inserts questions, alternatives, explanations, and images into medquest.db.
        Idempotent: removes older entries for the same source_file before inserting.
        Returns: (inserted_count, images_count, duplicates_skipped_count)
        """
        track_name = package.get("name", "Medway Track")
        year = package.get("year", 2026)
        track_id = package.get("track_id", "")
        inst_code, inst_label = detect_inst_from_title(track_name)

        # Standardize source_file label: use clean track title + track_id to ensure clean isolation
        clean_title = re.sub(r"\s+", " ", track_name).strip()
        track_suffix = f" [{track_id}]" if track_id else ""
        if editorial_status == "autoral" and "AUTORAL" not in clean_title.upper():
            source_file = f"{clean_title} AUTORAL{track_suffix}".strip()
        else:
            source_file = f"{clean_title}{track_suffix}".strip()

        print(f"\n[DB IMPORT] Ingesting into {db_path.name}:")
        print(f"  Source File: {source_file}")
        print(f"  Institution: {inst_code} ({inst_label})")
        print(f"  Editorial Status: {editorial_status}")

        conn = sqlite3.connect(db_path, timeout=60.0)
        conn.execute("PRAGMA busy_timeout = 60000")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Delete previous batch for same source_file if existing to ensure clean idempotency
        cursor.execute("SELECT id FROM questions WHERE source_file = ?", (source_file,))
        old_ids = [r["id"] for r in cursor.fetchall()]
        if old_ids:
            placeholders = ",".join("?" * len(old_ids))
            cursor.execute(f"DELETE FROM alternatives WHERE question_id IN ({placeholders})", old_ids)
            cursor.execute(f"DELETE FROM explanations WHERE question_id IN ({placeholders})", old_ids)
            cursor.execute(f"DELETE FROM question_images WHERE question_id IN ({placeholders})", old_ids)
            cursor.execute(f"DELETE FROM questions WHERE id IN ({placeholders})", old_ids)
            print(f"  [CLEANUP] Replaced {len(old_ids)} existing rows for '{source_file}'.")

        # Load existing question stems to guarantee zero duplication across medquest.db
        existing_stems: Set[str] = set()
        if deduplicate:
            cursor.execute("SELECT stem FROM questions WHERE source_file != ? AND stem IS NOT NULL", (source_file,))
            for r in cursor.fetchall():
                if r["stem"]:
                    existing_stems.add(normalize_text(r["stem"])[:180])

        total_inserted = 0
        total_images = 0
        skipped_duplicates = 0
        now_iso = datetime.now(timezone.utc).isoformat()

        for q_idx, item in enumerate(package.get("questions", []), start=1):
            q_detail = item.get("detail", {})
            exp_detail = item.get("explanation")
            if not isinstance(exp_detail, dict):
                exp_detail = {"introduction": exp_detail} if isinstance(exp_detail, str) else {}

            raw_stem = q_detail.get("content") or ""
            stem = clean_html_to_markdown(raw_stem)
            if not stem or not stem.strip():
                raise ValueError(
                    f"[DATA INTEGRITY ERROR] Question index {q_idx} in '{source_file}' has an empty statement (stem). "
                    f"Refusing to insert incomplete data."
                )

            # Check deduplication against existing questions in DB
            norm_stem = normalize_text(stem)[:180]
            if deduplicate and norm_stem and norm_stem in existing_stems:
                skipped_duplicates += 1
                continue

            opts = q_detail.get("options", [])
            is_discursive = bool(q_detail.get("question_type") == "d" or len(opts) == 0)
            correct_letter = extract_gabarito(exp_detail, opts, q_detail=q_detail) if not is_discursive else "A"
            golden_exp = format_medway_golden_explanation(
                exp_detail, opts, correct_letter, is_discursive=is_discursive
            )

            # Metadata tags & canonical taxonomy classification
            tags = []
            for t in q_detail.get("tag", []):
                if isinstance(t, dict) and t.get("name"):
                    tags.append(t["name"])
                elif isinstance(t, str) and t.strip():
                    tags.append(t.strip())

            speciality = ""
            spec_raw = q_detail.get("speciality")
            if isinstance(spec_raw, list) and spec_raw:
                first_item = spec_raw[0]
                if isinstance(first_item, dict):
                    speciality = first_item.get("name", "")
                elif isinstance(first_item, str):
                    speciality = first_item
            elif isinstance(spec_raw, dict):
                speciality = spec_raw.get("name", "")
            elif isinstance(spec_raw, str):
                speciality = spec_raw

            area, subtema = self.taxonomy_mapper.map(tags, speciality)
            topic = subtema

            cursor.execute(
                """
                INSERT INTO questions (
                    source_file, source_number, year, institution_code, institution_label,
                    topic, stem, correct_letter, missing_alts, comment_code,
                    area, subtema, editorial_status, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    source_file,
                    q_idx,
                    year,
                    inst_code,
                    inst_label,
                    topic,
                    stem,
                    correct_letter,
                    0,
                    None,
                    area,
                    subtema,
                    editorial_status,
                    "active",
                ),
            )
            new_q_id = cursor.lastrowid
            total_inserted += 1
            if deduplicate and norm_stem:
                existing_stems.add(norm_stem)

            # Alternatives
            if is_discursive:
                cursor.execute(
                    """
                    INSERT INTO alternatives (question_id, letter, text, is_correct)
                    VALUES (?, 'A', 'Questão Dissertativa - Ver Padrão de Resposta no Comentário', 1)
                """,
                    (new_q_id,),
                )
            else:
                for opt in opts:
                    let = opt.get("letter", "").upper()
                    raw_opt_text = opt.get("content") or ""
                    opt_text = clean_html_to_markdown(raw_opt_text)
                    is_corr = 1 if let == correct_letter else 0
                    cursor.execute(
                        """
                        INSERT INTO alternatives (question_id, letter, text, is_correct)
                        VALUES (?, ?, ?, ?)
                    """,
                        (new_q_id, let, opt_text, is_corr),
                    )

            # Golden Explanation
            cursor.execute(
                """
                INSERT INTO explanations (question_id, explanation_text, generated_at, reviewed_at)
                VALUES (?, ?, ?, ?)
            """,
                (new_q_id, golden_exp, now_iso, now_iso),
            )

            # Images strictly from stem and question attachments (NEVER from explanations)
            img_urls = re.findall(r"!\[.*?\]\((https?://[^\)]+)\)", stem)
            img_tags = re.findall(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', raw_stem)

            obj_imgs = []
            for item in q_detail.get("images", []):
                if isinstance(item, dict):
                    u = item.get("image") or item.get("url") or item.get("file")
                    if u:
                        obj_imgs.append(u)
                elif isinstance(item, str) and item.startswith("http"):
                    obj_imgs.append(item)

            opt_imgs = []
            for opt in q_detail.get("options", []):
                if isinstance(opt, dict):
                    u = opt.get("image") or opt.get("image_url")
                    if u:
                        opt_imgs.append(u)

            all_imgs = list(dict.fromkeys(img_urls + img_tags + obj_imgs + opt_imgs))

            for order_idx, img_url in enumerate(all_imgs):
                cursor.execute(
                    """
                    INSERT INTO question_images (question_id, file_path, order_index)
                    VALUES (?, ?, ?)
                """,
                    (new_q_id, img_url, order_idx),
                )
                total_images += 1

        conn.commit()
        conn.close()

        dup_msg = f" ({skipped_duplicates} duplicates skipped)" if skipped_duplicates > 0 else ""
        print(f"[SUCCESS] Ingested {total_inserted} questions into {db_path.name}{dup_msg} with {total_images} images.")
        return total_inserted, total_images, skipped_duplicates



def main() -> None:
    parser = argparse.ArgumentParser(description="Medway Extractor CLI for MedQuest")
    parser.add_argument("--list-exams", action="store_true", help="List available exams in Medway Exam Bank")
    parser.add_argument("--list-simulados", action="store_true", help="List available Aprova Medway Simulados")
    parser.add_argument("--search", type=str, default=None, help="Filter exams by search string (e.g. USP-SP, ENAMED)")
    parser.add_argument("--year", type=int, default=None, help="Filter exams by year (e.g. 2026)")
    parser.add_argument("--limit", type=int, default=25, help="Number of items to list")

    parser.add_argument("--extract-exam", type=int, default=None, help="Extract an exam by its track ID")
    parser.add_argument("--extract-simulados", action="store_true", help="Extract all Aprova Medway simulados")
    parser.add_argument("--extract-search", type=str, default=None, help="Extract all exams matching a search query")
    parser.add_argument(
        "--extract-catalog",
        type=Path,
        nargs="?",
        const=BACKEND_DIR / "data" / "medway_catalog_mapped.json",
        default=None,
        help="Extract exams filtered by the mapped catalog (defaults to app/backend/data/medway_catalog_mapped.json)",
    )
    parser.add_argument("--tier", type=int, default=1, choices=[1, 2], help="Similarity tier to extract (1=Core, 2=Expanded)")
    parser.add_argument("--min-year", type=int, default=2020, help="Minimum exam year")
    parser.add_argument("--max-year", type=int, default=2027, help="Maximum exam year")
    parser.add_argument("--batch-size", type=int, default=None, help="Number of exams to process in this run")
    parser.add_argument("--offset", type=int, default=0, help="Offset index into the filtered catalog")
    parser.add_argument("--institutions", type=str, default=None, help="Comma-separated institution codes to filter (e.g. 'USP-SP,UNICAMP')")
    parser.add_argument("--no-dedup", action="store_true", help="Disable deduplication against existing questions in DB")

    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory to save extracted JSONs")
    parser.add_argument("--import-db", action="store_true", help="Directly ingest extracted questions into medquest.db")
    parser.add_argument("--editorial-status", type=str, default="oficial", choices=["autoral", "oficial"],
                        help="editorial_status to record in DB ('autoral' or 'oficial')")
    parser.add_argument("--delay", type=float, default=0.03, help="Delay between API requests in seconds")
    parser.add_argument("--no-resume", action="store_true", help="Re-download even if already cached locally")

    args = parser.parse_args()
    client = MedwayClient()
    extractor = MedwayExtractor(client=client, output_dir=args.output_dir)

    # 1. List exams
    if args.list_exams:
        print("\n--- Medway Exam Bank Catalog ---")
        res = client.list_exams(search=args.search, year=args.year, limit=args.limit)
        count = res.get("count", 0)
        results = res.get("results", [])
        print(f"Total matching exams: {count} (showing up to {args.limit}):\n")
        for ex in results:
            print(f"  [ID {ex['id']}] {ex.get('name')} | Year: {ex.get('year')} | Qs: {ex.get('question_count')}")
        return

    # 2. List Aprova Medway Simulados
    if args.list_simulados:
        print("\n--- Aprova Medway Simulados Catalog ---")
        mods = client.list_modules(27657)  # Subject 27657 = Aprova Medway
        print(f"Found {len(mods)} Aprova Medway modules:\n")
        for m in mods:
            mod_id = m.get("id")
            mod_detail = client.get_module_detail(mod_id)
            for it in mod_detail.get("module_items", []):
                if it.get("type") == "Trilha":
                    print(f"  [Track ID {it.get('object_id')}] {m.get('name')} -> {it.get('content_identifier')}")
        return

    # 3. Extract Single Exam
    if args.extract_exam:
        pkg = extractor.extract_track(
            track_id=args.extract_exam,
            category_name="exams",
            delay=args.delay,
            resume=not args.no_resume,
        )
        if args.import_db:
            extractor.import_package_to_db(
                pkg,
                editorial_status=args.editorial_status,
                deduplicate=not args.no_dedup,
            )
        return

    # 4. Extract Search Batch
    if args.extract_search:
        print(f"\n--- Batch Extraction for Search Query: '{args.extract_search}' ---")
        res = client.list_exams(search=args.extract_search, year=args.year, limit=args.limit)
        results = res.get("results", [])
        print(f"Found {len(results)} exams to extract.")
        for idx, ex in enumerate(results, start=1):
            print(f"\n[{idx}/{len(results)}] Extracting {ex.get('name')} (ID: {ex['id']})...")
            pkg = extractor.extract_track(
                track_id=ex["id"],
                category_name="exams",
                track_title=ex.get("name"),
                year=ex.get("year"),
                delay=args.delay,
                resume=not args.no_resume,
            )
            if args.import_db:
                extractor.import_package_to_db(
                    pkg,
                    editorial_status=args.editorial_status,
                    deduplicate=not args.no_dedup,
                )
        return

    # 5. Extract Aprova Medway Simulados
    if args.extract_simulados:
        print("\n--- Extracting All Aprova Medway Simulados ---")
        mods = client.list_modules(27657)
        for m in mods:
            mod_detail = client.get_module_detail(m.get("id"))
            for it in mod_detail.get("module_items", []):
                if it.get("type") == "Trilha":
                    tid = it.get("object_id")
                    title = f"{m.get('name')} - {it.get('content_identifier')}"
                    print(f"\nExtracting Simulado: {title} (Track: {tid})...")
                    pkg = extractor.extract_track(
                        track_id=tid,
                        category_name="simulados",
                        track_title=title,
                        delay=args.delay,
                        resume=not args.no_resume,
                    )
                    if args.import_db:
                        extractor.import_package_to_db(
                            pkg,
                            editorial_status="autoral",
                            deduplicate=not args.no_dedup,
                        )
        return

    # 6. Extract Filtered Catalog Batch (Tier 1 / Tier 2)
    if args.extract_catalog:
        cat_file = args.extract_catalog
        if not cat_file.exists():
            print(f"[ERROR] Catalog file {cat_file} not found. Run build_medway_catalog.py first.")
            return

        with open(cat_file, "r", encoding="utf-8") as f:
            catalog = json.load(f)

        filtered = [
            e for e in catalog
            if (e.get("tier") == args.tier)
            and (args.min_year <= (e.get("year") or 0) <= args.max_year)
        ]

        if args.institutions:
            allowed = {i.strip().upper() for i in args.institutions.split(",") if i.strip()}
            filtered = [e for e in filtered if e.get("institution_code", "").upper() in allowed]

        total_matching = len(filtered)
        print("=" * 65)
        print(f"Catalog Extraction Run:")
        print(f"  Tier: {args.tier} | Years: {args.min_year}-{args.max_year}")
        if args.institutions:
            print(f"  Institutions: {args.institutions}")
        print(f"  Total eligible exams: {total_matching}")
        print("=" * 65)

        progress_file = BACKEND_DIR / "data" / f"tier{args.tier}_extraction_progress.json"
        progress_data: Dict[str, Any] = {
            "tier": args.tier,
            "total_eligible": total_matching,
            "completed_tracks": [],
            "failed_tracks": [],
            "total_questions_downloaded": 0,
            "total_ingested": 0,
            "total_duplicates_skipped": 0,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        if progress_file.exists():
            try:
                with open(progress_file, "r", encoding="utf-8") as pf:
                    loaded = json.load(pf)
                    if loaded.get("tier") == args.tier:
                        progress_data = loaded
            except Exception:
                pass

        completed_set = set(progress_data.get("completed_tracks", []))

        start_idx = args.offset
        end_idx = (start_idx + args.batch_size) if args.batch_size else total_matching
        batch = filtered[start_idx:end_idx]

        print(f"Processing batch: exams {start_idx + 1} to {min(end_idx, total_matching)} ({len(batch)} exams)...\n")
        print(f"  Already completed previously: {len(completed_set)} tracks\n")

        total_pkg_questions = progress_data.get("total_questions_downloaded", 0)
        total_ingested = progress_data.get("total_ingested", 0)
        total_duplicates_skipped = progress_data.get("total_duplicates_skipped", 0)

        for b_idx, exam_meta in enumerate(batch, start=1):
            tid = exam_meta["track_id"]
            name = exam_meta["name"]
            yr = exam_meta["year"]
            qc = exam_meta["question_count"]
            inst = exam_meta["institution_code"]

            if tid in completed_set and not args.no_resume:
                print(f"[{b_idx}/{len(batch)}] Track {tid} ({name}) already completed. Skipping.")
                continue

            print(f"\n>>> [{b_idx}/{len(batch)}] {name} (Track {tid} | Year {yr} | ~{qc} Qs | {inst})")

            try:
                pkg = extractor.extract_track(
                    track_id=tid,
                    category_name="exams",
                    track_title=name,
                    year=yr,
                    delay=args.delay,
                    resume=not args.no_resume,
                )

                total_pkg_questions += pkg.get("total_questions", 0)

                if args.import_db:
                    is_sim = "simulado" in name.lower()
                    ed_status = "autoral" if is_sim else args.editorial_status
                    ins, imgs, dups = extractor.import_package_to_db(
                        pkg,
                        editorial_status=ed_status,
                        deduplicate=not args.no_dedup,
                    )
                    total_ingested += ins
                    total_duplicates_skipped += dups

                if tid not in completed_set:
                    progress_data.setdefault("completed_tracks", []).append(tid)
                    completed_set.add(tid)

            except Exception as e:
                print(f"\n[ERROR] Failed processing Track {tid} ({name}): {e}")
                progress_data.setdefault("failed_tracks", []).append({
                    "track_id": tid,
                    "name": name,
                    "error": str(e),
                    "failed_at": datetime.now(timezone.utc).isoformat(),
                })

            # Save state after each track
            progress_data["total_questions_downloaded"] = total_pkg_questions
            progress_data["total_ingested"] = total_ingested
            progress_data["total_duplicates_skipped"] = total_duplicates_skipped
            progress_data["last_updated"] = datetime.now(timezone.utc).isoformat()
            try:
                with open(progress_file, "w", encoding="utf-8") as pf:
                    json.dump(progress_data, pf, ensure_ascii=False, indent=2)
            except Exception:
                pass

        print("\n" + "=" * 65)
        print("Catalog Extraction Batch Finished!")
        print(f"  Exams Processed: {len(batch)}")
        print(f"  Total Tracks Completed So Far: {len(completed_set)} / {total_matching}")
        print(f"  Questions Downloaded: {total_pkg_questions}")
        if args.import_db:
            print(f"  Questions Ingested: {total_ingested}")
            print(f"  Duplicates Skipped: {total_duplicates_skipped}")
        print("=" * 65)
        return

    parser.print_help()


if __name__ == "__main__":
    main()

