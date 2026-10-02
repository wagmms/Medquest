import pytest
from unittest.mock import MagicMock
from api.ai import generate_preceptor_dashboard_focus


def test_generate_preceptor_dashboard_focus_empty_user(monkeypatch):
    """Valida foco quando o usuário ainda não possui histórico de tentativas."""
    mock_db = MagicMock()
    # Mock do retorno de get_student_weak_topics para usuário sem dados
    monkeypatch.setattr(
        "api.ai.get_student_weak_topics",
        lambda db, uid, limit=5: {
            "status": "empty",
            "has_data": False,
            "overall_accuracy_pct": 0.0,
            "total_attempts": 0,
            "srs_due_count": 0,
            "weak_topics": [],
        }
    )

    captured_prompts = []
    def mock_generate_content(prompt, system_instruction=None, **kwargs):
        captured_prompts.append((prompt, system_instruction))
        return {
            "text": "📊 **Raio-X de Desempenho**\nCalibração inicial...\n🎯 **Plano de Ataque Prático do Dia**\nResolva 15 questões.",
            "source": "mock_ai",
            "model": "mock-flash"
        }
    monkeypatch.setattr("api.ai.generate_content_with_fallback", mock_generate_content)

    res = generate_preceptor_dashboard_focus(mock_db, "user_novato")
    assert res["diagnostic_data"]["has_data"] is False
    assert "Raio-X de Desempenho" in res["analysis_markdown"]
    assert "Plano de Ataque Prático do Dia" in res["analysis_markdown"]
    assert res["recommended_topic"]["subtema"] == "Síndromes Coronarianas Agudas"
    assert len(captured_prompts) == 1


def test_generate_preceptor_dashboard_focus_with_weak_topics(monkeypatch):
    """Valida foco quando o aluno possui temas vulneráveis e revisões pendentes."""
    mock_db = MagicMock()
    monkeypatch.setattr(
        "api.ai.get_student_weak_topics",
        lambda db, uid, limit=5: {
            "status": "success",
            "has_data": True,
            "overall_accuracy_pct": 65.0,
            "total_attempts": 50,
            "srs_due_count": 7,
            "weak_topics": [
                {
                    "topic": "Diverticulite Aguda",
                    "area": "Cirurgia Geral",
                    "attempts": 6,
                    "accuracy_pct": 33.3,
                    "wrong": 4,
                }
            ],
        }
    )

    def mock_generate_content(prompt, system_instruction=None, **kwargs):
        assert "Diverticulite Aguda" in prompt
        assert "Cirurgia Geral" in prompt
        return {
            "text": "📊 **Raio-X de Desempenho**\n65% de acerto.\n🚨 **Subtemas Vulneráveis**\nDiverticulite Aguda.\n🎯 **Plano de Ataque**\n15 questões.",
            "source": "mock_ai",
            "model": "mock-flash"
        }
    monkeypatch.setattr("api.ai.generate_content_with_fallback", mock_generate_content)

    res = generate_preceptor_dashboard_focus(mock_db, "user_experiente")
    assert res["diagnostic_data"]["has_data"] is True
    assert res["recommended_topic"]["subtema"] == "Diverticulite Aguda"
    assert res["recommended_topic"]["area"] == "Cirurgia Geral"
    assert "Diverticulite%20Aguda" in res["recommended_topic"]["practice_url"]


def test_preceptor_focus_route_api(client, monkeypatch):
    """Testa endpoint HTTP /api/ai/preceptor_focus com fast snapshot (generate_ai=False) e com IA."""
    monkeypatch.setattr(
        "api.ai.generate_preceptor_dashboard_focus",
        lambda db, uid: {
            "diagnostic_data": {"has_data": True, "overall_accuracy_pct": 80.0},
            "analysis_markdown": "Plano de ataque pronto.",
            "recommended_topic": {"subtema": "Trauma", "area": "Cirurgia", "practice_url": "/estudar"},
            "source": "mock"
        }
    )

    # 1. Teste com generate_ai=True (padrão)
    resp = client.post("/api/ai/preceptor_focus", json={"generate_ai": True}, headers={"X-Guest-ID": "guest-123"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["source"] == "mock"
    assert data["recommended_topic"]["subtema"] == "Trauma"

    # 2. Teste rápido com generate_ai=False
    monkeypatch.setattr(
        "api.adaptive_tools.get_student_weak_topics",
        lambda db, uid, limit=5: {
            "status": "success",
            "has_data": True,
            "overall_accuracy_pct": 80.0,
            "weak_topics": [{"topic": "Trauma", "area": "Cirurgia", "attempts": 5, "accuracy_pct": 20.0}]
        }
    )
    resp_fast = client.get("/api/ai/preceptor_focus?ai=0", headers={"X-Guest-ID": "guest-123"})
    assert resp_fast.status_code == 200
    data_fast = resp_fast.get_json()
    assert data_fast["source"] == "database_snapshot"
    assert data_fast["recommended_topic"]["subtema"] == "Trauma"
