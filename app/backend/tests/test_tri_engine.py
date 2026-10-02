"""Testes unitários e de integração para o motor de Teoria de Resposta ao Item (TRI)."""
import math
from api.tri_engine import _normal_cdf, _prob_3pl, estimate_theta_eap, evaluate_tri_performance


def test_normal_cdf_values():
    assert round(_normal_cdf(0.0), 3) == 0.5
    assert round(_normal_cdf(1.96), 3) == 0.975
    assert round(_normal_cdf(-1.96), 3) == 0.025


def test_prob_3pl_behavior():
    # Para theta muito baixo, a probabilidade tende ao chute c (0.20)
    p_low = _prob_3pl(-4.0, a=1.2, b=0.0, c=0.20)
    assert 0.19 <= p_low <= 0.22

    # Para theta == b, p(theta) = c + (1-c)/2 = 0.20 + 0.40 = 0.60
    p_mid = _prob_3pl(0.0, a=1.2, b=0.0, c=0.20)
    assert round(p_mid, 2) == 0.60

    # Para theta muito alto, p(theta) tende a 1.0
    p_high = _prob_3pl(4.0, a=1.2, b=0.0, c=0.20)
    assert p_high >= 0.98


def test_eap_coherence_rewards_consistent_pattern():
    # Item params: 3 fáceis, 3 médias, 3 difíceis
    item_params = {
        1: {"a": 1.2, "b": -1.5, "c": 0.2},
        2: {"a": 1.2, "b": -1.2, "c": 0.2},
        3: {"a": 1.2, "b": -1.0, "c": 0.2},
        4: {"a": 1.3, "b": 0.0, "c": 0.2},
        5: {"a": 1.3, "b": 0.2, "c": 0.2},
        6: {"a": 1.3, "b": 0.4, "c": 0.2},
        7: {"a": 1.4, "b": 1.2, "c": 0.2},
        8: {"a": 1.4, "b": 1.5, "c": 0.2},
        9: {"a": 1.4, "b": 1.8, "c": 0.2},
    }

    # Padrão consistente (acerta as 6 primeiras - fáceis e médias, erra as 3 difíceis)
    resp_consistent = [
        {"question_id": i, "is_correct": i <= 6} for i in range(1, 10)
    ]
    theta_cons, se_cons, coher_cons = estimate_theta_eap(item_params, resp_consistent)

    # Padrão errático/chute (erra as 3 fáceis, acerta as 3 difíceis)
    resp_erratic = [
        {"question_id": 1, "is_correct": False},
        {"question_id": 2, "is_correct": False},
        {"question_id": 3, "is_correct": False},
        {"question_id": 4, "is_correct": True},
        {"question_id": 5, "is_correct": True},
        {"question_id": 6, "is_correct": True},
        {"question_id": 7, "is_correct": True},
        {"question_id": 8, "is_correct": True},
        {"question_id": 9, "is_correct": False},
    ]
    theta_err, se_err, coher_err = estimate_theta_eap(item_params, resp_erratic)

    # O padrão consistente deve ter maior coerência pedagógica
    assert coher_cons >= 85.0
    assert coher_cons > coher_err


def test_simulado_tri_evaluation_endpoint(client):
    payload = {
        "institution": "ENARE",
        "attempts": [
            {"question_id": 1, "is_correct": True, "selected_letter": "B"},
            {"question_id": 2, "is_correct": True, "selected_letter": "A"},
            {"question_id": 3, "is_correct": False, "selected_letter": "C"},
        ],
    }
    res = client.post("/api/simulado/tri-evaluation", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert "theta" in data
    assert "standard_error" in data
    assert "pedagogical_coherence_pct" in data
    assert "coherence_label" in data
    assert "projected_score" in data
    assert "national_percentile" in data
    assert "specialty_cutoffs" in data
    assert data["institution_code"] == "ENARE"
    assert len(data["specialty_cutoffs"]) >= 5

    # Verifica se os status de corte estão bem formatados
    first_spec = data["specialty_cutoffs"][0]
    assert "specialty" in first_spec
    assert "cutoff_score" in first_spec
    assert "status" in first_spec
    assert first_spec["status"] in ("HIGH_PROBABILITY", "COMPETITIVE", "NEEDS_IMPROVEMENT")


def test_stats_tri_readiness_endpoint(client):
    # Envia uma tentativa
    client.post(
        "/api/questions/1/attempt",
        json={"selected_letter": "B", "confidence": "certeza", "time_spent_ms": 1200},
    )

    res = client.get("/api/stats/tri-readiness?institution=USP-SP")
    assert res.status_code == 200
    data = res.get_json()
    assert data["institution_code"] == "USP-SP"
    assert "projected_score" in data
    assert "national_percentile" in data
    assert "specialty_cutoffs" in data
