"""
MedQuest - Módulo de Benchmarks de Candidatos e Avaliação Competitiva por Banca.

Carrega e provê métricas de desempenho real dos candidatos (taxas empíricas de acerto
por questão, por grande área e por banca) extraídas dos exames oficiais de residência médica.
Adiciona a camada analítica de comparação competitiva e calibração bayesiana empírica.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("candidate_benchmarks")

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "institution_candidate_benchmarks.json"

_BENCHMARKS_CACHE: Optional[Dict[str, Any]] = None


def _load_benchmarks() -> Dict[str, Any]:
    global _BENCHMARKS_CACHE
    if _BENCHMARKS_CACHE is not None:
        return _BENCHMARKS_CACHE

    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                _BENCHMARKS_CACHE = json.load(f)
                return _BENCHMARKS_CACHE
        except Exception as e:
            logger.error("Erro ao carregar %s: %s", DATA_FILE, e)

    _BENCHMARKS_CACHE = {
        "institutions": {},
        "question_benchmarks": {}
    }
    return _BENCHMARKS_CACHE


def get_institution_benchmark(institution_code: Optional[str]) -> Dict[str, Any]:
    """Retorna o benchmark oficial dos candidatos para a instituição especificada."""
    data = _load_benchmarks()
    insts = data.get("institutions", {})

    code = (institution_code or "GERAL").strip().upper()
    if code in insts:
        return insts[code]

    # Fallback para GERAL ou valores padrão
    if "GERAL" in insts:
        return insts["GERAL"]

    return {
        "institution_code": code,
        "overall_candidate_accuracy": 0.695,
        "total_questions": 0,
        "difficulty_distribution": {"facil": 0.45, "media": 0.38, "dificil": 0.17},
        "areas": {
            "Clínica Médica": {"candidate_accuracy": 0.698, "question_count": 0},
            "Cirurgia": {"candidate_accuracy": 0.691, "question_count": 0},
            "Ginecologia e Obstetrícia": {"candidate_accuracy": 0.717, "question_count": 0},
            "Pediatria": {"candidate_accuracy": 0.692, "question_count": 0},
            "Medicina Preventiva": {"candidate_accuracy": 0.745, "question_count": 0},
        }
    }


def get_question_benchmark(question_id: int) -> Tuple[float, str]:
    """Retorna (candidate_accuracy, difficulty_tier) para a questão informada."""
    data = _load_benchmarks()
    q_map = data.get("question_benchmarks", {})
    qid_str = str(question_id)
    if qid_str in q_map:
        item = q_map[qid_str]
        return float(item.get("p", 0.70)), str(item.get("tier", "media"))
    return 0.70, "media"


def calculate_competitive_analysis(
    attempts_records: List[Dict[str, Any]],
    institution_code: Optional[str],
) -> Dict[str, Any]:
    """
    Calcula a camada avançada de comparação competitiva:
    - Delta Competitivo sobre a concorrência
    - Desempenho ponderado pela dificuldade dos itens (IRT-like weighting)
    - Estratificação de acertos por faixa de dificuldade (Fácil, Média, Difícil)
    """
    bench = get_institution_benchmark(institution_code)
    bench_overall = bench.get("overall_candidate_accuracy", 0.695)

    if not attempts_records:
        return {
            "candidate_mean": round(bench_overall, 4),
            "competitive_delta": None,
            "competitive_ratio": None,
            "difficulty_adjusted_score": None,
            "difficulty_breakdown": {
                "facil": {"user_accuracy": None, "candidate_accuracy": 0.85, "attempts": 0},
                "media": {"user_accuracy": None, "candidate_accuracy": 0.65, "attempts": 0},
                "dificil": {"user_accuracy": None, "candidate_accuracy": 0.38, "attempts": 0},
            }
        }

    tier_stats = {
        "facil": {"correct": 0, "attempts": 0, "cand_sum": 0.0},
        "media": {"correct": 0, "attempts": 0, "cand_sum": 0.0},
        "dificil": {"correct": 0, "attempts": 0, "cand_sum": 0.0},
    }

    weighted_user_score = 0.0
    sum_weights = 0.0
    cand_expected_sum = 0.0

    for att in attempts_records:
        qid = att.get("question_id")
        is_cor = 1 if att.get("is_correct") else 0
        p_cand, tier = get_question_benchmark(qid) if qid else (0.70, "media")

        # Ponderação por discriminação e dificuldade:
        # Acertar item difícil (p=0.30) tem peso 1.40; errar item fácil (p=0.85) penaliza mais.
        w_item = max(0.5, 1.0 + (0.70 - p_cand))
        weighted_user_score += is_cor * w_item
        sum_weights += w_item
        cand_expected_sum += p_cand

        tier_stats[tier]["attempts"] += 1
        tier_stats[tier]["correct"] += is_cor
        tier_stats[tier]["cand_sum"] += p_cand

    n_tot = len(attempts_records)
    user_raw_acc = sum(1 for a in attempts_records if a.get("is_correct")) / n_tot
    cand_mean = cand_expected_sum / n_tot if n_tot > 0 else bench_overall
    delta = round(user_raw_acc - cand_mean, 4)
    ratio = round(user_raw_acc / cand_mean, 4) if cand_mean > 0 else 1.0
    adj_score = round(weighted_user_score / sum_weights, 4) if sum_weights > 0 else user_raw_acc

    breakdown = {}
    for t in ["facil", "media", "dificil"]:
        t_att = tier_stats[t]["attempts"]
        t_cor = tier_stats[t]["correct"]
        t_user_acc = round(t_cor / t_att, 4) if t_att > 0 else None
        default_cand_acc = 0.85 if t == "facil" else (0.65 if t == "media" else 0.38)
        t_cand_acc = round(tier_stats[t]["cand_sum"] / t_att, 4) if t_att > 0 else default_cand_acc

        breakdown[t] = {
            "user_accuracy": t_user_acc,
            "candidate_accuracy": t_cand_acc,
            "attempts": t_att,
            "delta": round(t_user_acc - t_cand_acc, 4) if t_user_acc is not None else None
        }

    return {
        "candidate_mean": round(cand_mean, 4),
        "competitive_delta": delta,
        "competitive_ratio": ratio,
        "difficulty_adjusted_score": adj_score,
        "difficulty_breakdown": breakdown,
    }
