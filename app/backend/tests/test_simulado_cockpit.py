"""Testes para o novo Cockpit de Simulados (provas oficiais, histórico de sessões e construtor)."""
import json


def test_official_exams_retorna_bancas_sp(client):
    r = client.get("/api/simulado/official-exams")
    assert r.status_code == 200
    data = r.get_json()
    assert "exams" in data
    inst_codes = [exam["institution_code"] for exam in data["exams"]]
    # As 5 bancas alvo devem estar presentes
    assert "USP-SP" in inst_codes
    assert "USP-RP" in inst_codes
    assert "UNICAMP" in inst_codes
    assert "UNIFESP" in inst_codes
    assert "SUS-SP" in inst_codes


def test_simulado_sessions_crud(client):
    # Inicialmente lista vazia
    r = client.get("/api/simulado/sessions")
    assert r.status_code == 200
    assert r.get_json()["sessions"] == []

    # Salva uma sessão
    session_payload = {
        "client_session_id": "test-session-12345",
        "planned_duration_seconds": 18000,
        "elapsed_seconds": 12000,
        "total_questions": 100,
        "answered_count": 100,
        "correct_count": 82,
        "filters": {"institutions": ["USP-SP"], "years": ["2024"]},
        "area_results": [
            {"area": "Clínica Médica", "correct": 18, "total": 20},
            {"area": "Cirurgia", "correct": 16, "total": 20},
        ],
    }
    post_r = client.post("/api/simulado/sessions", json=session_payload)
    assert post_r.status_code == 200
    assert post_r.get_json()["success"] is True

    # Consulta histórico
    list_r = client.get("/api/simulado/sessions")
    assert list_r.status_code == 200
    sessions = list_r.get_json()["sessions"]
    assert len(sessions) == 1
    s = sessions[0]
    assert s["client_session_id"] == "test-session-12345"
    assert s["total_questions"] == 100
    assert s["correct_count"] == 82
    assert s["accuracy_percent"] == 82.0
    assert s["filters"]["institutions"] == ["USP-SP"]
    assert len(s["area_results"]) == 2

    # Remove a sessão
    del_r = client.delete("/api/simulado/sessions/test-session-12345")
    assert del_r.status_code == 200
    assert del_r.get_json()["deleted"] is True

    # Confirma que foi excluída
    list_r2 = client.get("/api/simulado/sessions")
    assert list_r2.status_code == 200
    assert len(list_r2.get_json()["sessions"]) == 0


def test_simulado_custom_expande_aliases(client):
    r = client.post("/api/simulado/custom", json={
        "institutions": ["USP-SP"],
        "years": [],
        "questions_per_area": 5
    })
    assert r.status_code == 200
    # Na fixture de teste temos poucas questões cadastradas, mas o endpoint não deve falhar
    assert isinstance(r.get_json(), list)
