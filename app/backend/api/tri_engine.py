"""Motor de Teoria de Resposta ao Item (TRI) e Ranking Preditivo para Grandes Provas.

Implementa o modelo logístico 3PL com estimação EAP (Expected A Posteriori),
cálculo de coerência pedagógica, projeção para escalas de bancas (ENARE, USP-SP, SUS-SP)
e termômetro de probabilidade de corte por especialidade médica de acesso direto.
"""

import math
from typing import Any, Dict, List, Optional, Tuple


def _normal_cdf(x: float) -> float:
    """Função de distribuição acumulada da normal padrão N(0, 1)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _prob_3pl(theta: float, a: float, b: float, c: float = 0.20) -> float:
    """Probabilidade de acerto no modelo 3PL: P(theta) = c + (1 - c) / (1 + exp(-1.7 * a * (theta - b)))."""
    exponent = -1.7 * a * (theta - b)
    # Evitar overflow/underflow
    exponent = max(-30.0, min(30.0, exponent))
    return c + (1.0 - c) / (1.0 + math.exp(exponent))


# Configurações de bancas para escala padronizada
INSTITUTION_TRI_SCALES = {
    "ENARE": {
        "label": "ENARE / Ebserh",
        "mean": 65.0,
        "std": 12.0,
        "max_score": 100.0,
        "cutoffs": {
            "Clínica Médica": 77.5,
            "Cirurgia Geral": 79.0,
            "Pediatria": 71.0,
            "Ginecologia e Obstetrícia": 73.0,
            "Anestesiologia": 81.0,
            "Dermatologia": 85.5,
            "Ortopedia": 74.5,
            "Medicina de Família": 63.0,
        },
    },
    "USP-SP": {
        "label": "USP - São Paulo",
        "mean": 62.0,
        "std": 11.5,
        "max_score": 100.0,
        "cutoffs": {
            "Clínica Médica": 78.0,
            "Cirurgia Geral": 80.5,
            "Pediatria": 72.5,
            "Ginecologia e Obstetrícia": 74.0,
            "Anestesiologia": 82.5,
            "Dermatologia": 87.0,
            "Ortopedia": 76.0,
            "Medicina de Família": 65.0,
        },
    },
    "SUS-SP": {
        "label": "SUS - São Paulo",
        "mean": 66.0,
        "std": 13.0,
        "max_score": 100.0,
        "cutoffs": {
            "Clínica Médica": 76.0,
            "Cirurgia Geral": 78.0,
            "Pediatria": 70.0,
            "Ginecologia e Obstetrícia": 72.0,
            "Anestesiologia": 80.0,
            "Dermatologia": 85.0,
            "Ortopedia": 73.5,
            "Medicina de Família": 62.0,
        },
    },
    "UNIFESP": {
        "label": "Unifesp / EPM",
        "mean": 63.5,
        "std": 11.8,
        "max_score": 100.0,
        "cutoffs": {
            "Clínica Médica": 77.0,
            "Cirurgia Geral": 79.5,
            "Pediatria": 71.5,
            "Ginecologia e Obstetrícia": 73.5,
            "Anestesiologia": 81.5,
            "Dermatologia": 86.0,
            "Ortopedia": 75.0,
            "Medicina de Família": 64.0,
        },
    },
    "UNICAMP": {
        "label": "Unicamp",
        "mean": 63.0,
        "std": 11.8,
        "max_score": 100.0,
        "cutoffs": {
            "Clínica Médica": 77.0,
            "Cirurgia Geral": 79.0,
            "Pediatria": 71.5,
            "Ginecologia e Obstetrícia": 73.0,
            "Anestesiologia": 81.0,
            "Dermatologia": 86.0,
            "Ortopedia": 74.5,
            "Medicina de Família": 63.5,
        },
    },
}

DEFAULT_SCALE = INSTITUTION_TRI_SCALES["ENARE"]


def calibrate_item_parameters(db, question_ids: List[int]) -> Dict[int, Dict[str, float]]:
    """Calibra os parâmetros de discriminação (a), dificuldade (b) e chute (c) para cada questão."""
    if not question_ids:
        return {}

    placeholders = ",".join("?" * len(question_ids))
    # Obter estatísticas empíricas das questões no banco
    rows = db.execute(
        f"""
        SELECT
            q.id,
            q.institution_code,
            COUNT(a.id) AS total_attempts,
            COALESCE(SUM(a.is_correct), 0) AS correct_attempts,
            LENGTH(COALESCE(q.stem, '')) AS stem_len
        FROM questions q
        LEFT JOIN attempts a ON a.question_id = q.id
        WHERE q.id IN ({placeholders})
        GROUP BY q.id
        """,
        question_ids,
    ).fetchall()

    params_map = {}
    for r in rows:
        qid = r["id"]
        total_att = int(r["total_attempts"] or 0)
        correct_att = int(r["correct_attempts"] or 0)
        stem_len = int(r["stem_len"] or 0)

        # Chute (c): 0.20 padrão (5 alternativas)
        c_i = 0.20

        if total_att >= 4:
            acc = correct_att / total_att
            # Mapeamento logístico inverso para b (dificuldade)
            # acerto alto (0.80) -> b negativo (-1.2)
            # acerto baixo (0.30) -> b positivo (+1.4)
            safe_p = max(0.22, min(0.95, acc))
            # Escala centrada
            b_i = -1.0 * math.log((safe_p - 0.20) / (1.0 - safe_p + 0.05))
            b_i = max(-2.5, min(2.5, b_i))
            # Discriminação calibrada
            a_i = 1.25 + min(0.4, (total_att / 50.0) * 0.2)
        else:
            # Questão sem histórico suficiente: usar heurística baseada no tamanho e instituição
            inst = str(r["institution_code"] or "").upper()
            if "USP" in inst or "UNICAMP" in inst or "UNIFESP" in inst:
                base_b = 0.4  # Provas tradicionalmente mais densas e difíceis
            else:
                base_b = 0.0

            if stem_len > 800:
                base_b += 0.2
            elif stem_len < 300:
                base_b -= 0.2

            b_i = max(-2.0, min(2.0, base_b))
            a_i = 1.20

        params_map[qid] = {
            "a": round(a_i, 3),
            "b": round(b_i, 3),
            "c": round(c_i, 3),
        }

    return params_map


def estimate_theta_eap(
    item_params: Dict[int, Dict[str, float]],
    responses: List[Dict[str, Any]],
) -> Tuple[float, float, float]:
    """Estima a proficiência latente (theta), erro padrão (SE) e índice de coerência pedagógica via EAP.
    
    Retorna: (theta, standard_error, pedagogical_coherence_pct)
    """
    if not responses:
        return 0.0, 1.0, 100.0

    # Grid de 31 pontos na faixa [-3.5, +3.5]
    n_points = 31
    theta_min, theta_max = -3.5, 3.5
    step = (theta_max - theta_min) / (n_points - 1)
    nodes = [theta_min + i * step for i in range(n_points)]

    # Pesos da priori N(0, 1)
    prior = [math.exp(-0.5 * th * th) / math.sqrt(2.0 * math.pi) for th in nodes]

    # Log-verossimilhança em cada nó
    log_lik = [0.0] * n_points
    valid_items = []

    for resp in responses:
        qid = resp.get("question_id") or resp.get("id")
        is_corr = bool(resp.get("is_correct"))
        params = item_params.get(qid, {"a": 1.2, "b": 0.0, "c": 0.2})
        valid_items.append((params["a"], params["b"], params["c"], is_corr))

        for j, th in enumerate(nodes):
            p = _prob_3pl(th, params["a"], params["b"], params["c"])
            p = max(1e-7, min(1.0 - 1e-7, p))
            if is_corr:
                log_lik[j] += math.log(p)
            else:
                log_lik[j] += math.log(1.0 - p)

    # Subtrair o máximo para evitar overflow na exponenciação
    max_log = max(log_lik)
    weights = [math.exp(log_lik[j] - max_log) * prior[j] for j in range(n_points)]
    total_weight = sum(weights)

    if total_weight <= 0.0:
        return 0.0, 1.0, 100.0

    # Esperança a posteriori (theta_hat)
    theta_eap = sum(nodes[j] * weights[j] for j in range(n_points)) / total_weight

    # Variância e erro padrão a posteriori
    var_eap = sum(((nodes[j] - theta_eap) ** 2) * weights[j] for j in range(n_points)) / total_weight
    se_eap = math.sqrt(max(0.01, var_eap))

    # Coerência pedagógica: mede quão aderente o padrão de acertos do aluno
    # é à curva característica do item. Padrões onde o aluno erra questões muito fáceis
    # (b < theta - 1.0) e acerta questões muito difíceis (b > theta + 1.2) recebem penalidade de coerência.
    coherence_violations = 0
    total_evaluated = 0

    for a_i, b_i, c_i, is_corr in valid_items:
        p_expected = _prob_3pl(theta_eap, a_i, b_i, c_i)
        # Errou uma questão de alta certeza para o seu nível
        if not is_corr and p_expected >= 0.78:
            coherence_violations += 1
        # Acertou uma questão em que a probabilidade prevista era quase puramente o chute
        elif is_corr and p_expected <= (c_i + 0.08):
            coherence_violations += 0.5
        total_evaluated += 1

    if total_evaluated > 0:
        raw_coherence = 1.0 - (coherence_violations / max(1.0, total_evaluated * 0.35))
        pedagogical_coherence = round(max(40.0, min(100.0, raw_coherence * 100.0)), 1)
    else:
        pedagogical_coherence = 100.0

    return round(theta_eap, 3), round(se_eap, 3), pedagogical_coherence


def evaluate_tri_performance(
    db,
    responses: List[Dict[str, Any]],
    institution_code: Optional[str] = "ENARE",
) -> Dict[str, Any]:
    """Avaliação psicométrica completa da prova ou histórico com projeção de corte por especialidades."""
    if not responses:
        return {
            "theta": 0.0,
            "standard_error": 1.0,
            "pedagogical_coherence_pct": 100.0,
            "coherence_label": "Sem dados",
            "institution_code": institution_code or "ENARE",
            "institution_label": INSTITUTION_TRI_SCALES.get(institution_code or "ENARE", DEFAULT_SCALE)["label"],
            "projected_score": 0.0,
            "raw_score_pct": 0.0,
            "national_percentile": 50.0,
            "specialty_cutoffs": [],
        }

    q_ids = [r.get("question_id") or r.get("id") for r in responses if r.get("question_id") or r.get("id")]
    item_params = calibrate_item_parameters(db, q_ids)

    theta, se, coherence = estimate_theta_eap(item_params, responses)

    # Identificar escala da instituição
    target_code = (institution_code or "ENARE").strip().upper()
    scale_config = INSTITUTION_TRI_SCALES.get(target_code, DEFAULT_SCALE)

    # Projeção de nota TRI na escala da banca (0 a 100)
    raw_projected = scale_config["mean"] + scale_config["std"] * theta
    projected_score = round(max(0.0, min(scale_config["max_score"], raw_projected)), 1)

    # Percentual de acertos brutos
    correct_count = sum(1 for r in responses if r.get("is_correct"))
    raw_score_pct = round((correct_count / len(responses)) * 100.0, 1)

    # Percentil nacional: Phi(theta) * 100
    national_percentile = round(_normal_cdf(theta) * 100.0, 1)

    # Rotular coerência pedagógica
    if coherence >= 85.0:
        coherence_label = "Excelente coerência pedagógica: acertos sólidos em questões compatíveis com o seu nível."
    elif coherence >= 70.0:
        coherence_label = "Boa coerência: distribuição equilibrada de acertos e erros."
    else:
        coherence_label = "Coerência oscilante: ocorrência de erros em questões elementares ou acertos atípicos por eliminação/chute."

    # Termômetro de notas de corte por especialidade médica
    specialty_cutoffs = []
    for spec, cutoff in scale_config["cutoffs"].items():
        diff = round(projected_score - cutoff, 1)
        if diff >= 2.0:
            status = "HIGH_PROBABILITY"
            status_label = "Alta Probabilidade de Aprovação"
        elif diff >= -3.0:
            status = "COMPETITIVE"
            status_label = "Competitivo (Zona de Corte)"
        else:
            status = "NEEDS_IMPROVEMENT"
            status_label = "Abaixo do Corte Esperado"

        specialty_cutoffs.append({
            "specialty": spec,
            "cutoff_score": cutoff,
            "projected_score": projected_score,
            "difference": diff,
            "status": status,
            "status_label": status_label,
        })

    # Ordenar especialidades pelas mais competitivas/próximas da nota do aluno
    specialty_cutoffs.sort(key=lambda s: (s["status"] != "COMPETITIVE", s["cutoff_score"]))

    return {
        "theta": theta,
        "standard_error": se,
        "pedagogical_coherence_pct": coherence,
        "coherence_label": coherence_label,
        "institution_code": target_code,
        "institution_label": scale_config["label"],
        "projected_score": projected_score,
        "raw_score_pct": raw_score_pct,
        "national_percentile": national_percentile,
        "specialty_cutoffs": specialty_cutoffs,
    }
