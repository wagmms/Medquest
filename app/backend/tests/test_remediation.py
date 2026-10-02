"""Testes para o Radar de Pontos Cegos e Fila de Treino de Recuperação (Remediation)."""
import json
from api.db import get_db


def test_blindspots_diagnoses_errors_and_tracks_healing(client):
    # 1. Sem tentativas
    res = client.get("/api/stats/blindspots")
    assert res.status_code == 200
    data = res.get_json()
    assert "summary" in data
    assert "blindspots" in data
    assert data["summary"]["unresolved_errors_count"] == 0
    assert data["summary"]["healed_count"] == 0

    # 2. Erra a questão 1 (gabarito é B)
    # Supondo que resposta A seja erro
    att1 = client.post(
        "/api/questions/1/attempt",
        json={"selected_letter": "A", "confidence": "certeza", "time_spent_ms": 1500},
    )
    assert att1.status_code == 200
    assert att1.get_json()["is_correct"] is False

    res_after_error = client.get("/api/stats/blindspots")
    assert res_after_error.status_code == 200
    data_err = res_after_error.get_json()
    assert data_err["summary"]["unresolved_errors_count"] >= 1
    assert data_err["summary"]["healed_count"] == 0
    assert len(data_err["blindspots"]) >= 1

    first_bs = data_err["blindspots"][0]
    assert first_bs["unresolved_count"] >= 1
    assert first_bs["severity"] in ("CRITICAL", "HIGH", "MODERATE")
    assert "clinical_insight" in first_bs
    assert "workout_url" in first_bs

    # 3. Retifica a questão 1 acertando (gabarito B)
    att2 = client.post(
        "/api/questions/1/attempt",
        json={"selected_letter": "B", "confidence": "certeza", "time_spent_ms": 1200},
    )
    assert att2.status_code == 200
    assert att2.get_json()["is_correct"] is True

    res_after_heal = client.get("/api/stats/blindspots")
    assert res_after_heal.status_code == 200
    data_heal = res_after_heal.get_json()
    # A questão 1 foi superada/curada!
    assert data_heal["summary"]["healed_count"] >= 1
    assert data_heal["summary"]["healing_rate_pct"] > 0


def test_remediation_queue_endpoint_and_mode(client):
    # Erra a questão 1
    client.post(
        "/api/questions/1/attempt",
        json={"selected_letter": "A", "confidence": "certeza", "time_spent_ms": 1500},
    )

    # 1. Rota dedicada /api/questions/remediation
    res1 = client.get("/api/questions/remediation?limit=5")
    assert res1.status_code == 200
    queue1 = res1.get_json()
    assert isinstance(queue1, list)
    assert len(queue1) >= 1
    # Questão 1 deve estar na lista como erro não resolvido
    q1_entry = next((q for q in queue1 if q["id"] == 1), None)
    assert q1_entry is not None
    assert q1_entry["remediation_reason"] == "unresolved_error"

    # 2. Rota geral com mode=remediation /api/questions?mode=remediation
    res2 = client.get("/api/questions?mode=remediation&limit=5")
    assert res2.status_code == 200
    queue2 = res2.get_json()
    assert isinstance(queue2, list)
    assert len(queue2) >= 1
    assert any(q["id"] == 1 for q in queue2)


def test_remediation_user_isolation(client):
    # Usuário padrão erra questão 1
    client.post(
        "/api/questions/1/attempt",
        json={"selected_letter": "A", "confidence": "certeza", "time_spent_ms": 1500},
    )
    res_user1 = client.get("/api/stats/blindspots").get_json()
    assert res_user1["summary"]["unresolved_errors_count"] >= 1

    # Outro usuário com cabeçalho de autenticação diferente
    headers_user2 = {"X-User-ID": "user_isolated_test_uuid"}
    res_user2 = client.get("/api/stats/blindspots", headers=headers_user2).get_json()
    assert res_user2["summary"]["unresolved_errors_count"] == 0
    assert len(res_user2["blindspots"]) == 0
