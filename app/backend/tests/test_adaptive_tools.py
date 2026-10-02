"""Testes de unidade para a Tool get_student_weak_topics e diagnósticos adaptativos."""

import sqlite3
import pytest
from datetime import datetime, timezone

from api.adaptive_tools import (
    get_student_weak_topics,
    format_student_diagnostic_block,
)
from api.ai import ask_preceptor_ai


@pytest.fixture
def mock_db():
    """Cria um banco SQLite em memória com dados de tentativas e repetição espaçada para teste."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    with conn:
        conn.execute("""
            CREATE TABLE questions (
                id INTEGER PRIMARY KEY,
                stem TEXT,
                area TEXT,
                subtema TEXT,
                topic TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER,
                selected_letter TEXT,
                is_correct INTEGER,
                answered_at TEXT,
                confidence TEXT,
                user_id TEXT,
                time_spent_ms INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE spaced_repetition (
                question_id INTEGER,
                efactor REAL,
                interval INTEGER,
                next_review_date TEXT,
                user_id TEXT,
                fsrs_card TEXT
            )
        """)

        # Questões de exemplo
        conn.execute("INSERT INTO questions VALUES (1, 'IC questão', 'Clínica Médica', 'Insuficiência Cardíaca', 'Cardiologia')")
        conn.execute("INSERT INTO questions VALUES (2, 'Arritmia questão', 'Clínica Médica', 'Arritmias', 'Cardiologia')")
        conn.execute("INSERT INTO questions VALUES (3, 'Trauma questão', 'Cirurgia Geral', 'Trauma Abdominal', 'Cirurgia')")

        # Tentativas do aluno 'user_123':
        # Insuficiência Cardíaca: 3 tentativas, 1 acerto (33.3% acurácia)
        conn.execute("INSERT INTO attempts (question_id, is_correct, user_id) VALUES (1, 1, 'user_123')")
        conn.execute("INSERT INTO attempts (question_id, is_correct, user_id) VALUES (1, 0, 'user_123')")
        conn.execute("INSERT INTO attempts (question_id, is_correct, user_id) VALUES (1, 0, 'user_123')")

        # Arritmias: 2 tentativas, 2 acertos (100% acurácia)
        conn.execute("INSERT INTO attempts (question_id, is_correct, user_id) VALUES (2, 1, 'user_123')")
        conn.execute("INSERT INTO attempts (question_id, is_correct, user_id) VALUES (2, 1, 'user_123')")

        # FSRS: 1 revisão vencida no passado
        past_date = "2026-01-01T00:00:00+00:00"
        conn.execute("INSERT INTO spaced_repetition (question_id, next_review_date, user_id) VALUES (1, ?, 'user_123')", (past_date,))

    yield conn
    conn.close()


def test_get_student_weak_topics(mock_db):
    """Testa a extração dos pontos fracos e itens SRS do aluno."""
    res = get_student_weak_topics(mock_db, "user_123")

    assert res["status"] == "success"
    assert res["has_data"] is True
    assert res["total_attempts"] == 5
    assert res["overall_accuracy_pct"] == 60.0
    assert res["srs_due_count"] == 1
    assert len(res["weak_topics"]) >= 1

    # O tema mais fraco deve ser Insuficiência Cardíaca com 33.3% de acerto
    weakest = res["weak_topics"][0]
    assert weakest["topic"] == "Insuficiência Cardíaca"
    assert weakest["accuracy_pct"] == 33.3
    assert weakest["wrong"] == 2


def test_format_student_diagnostic_block(mock_db):
    """Testa a formatação em Markdown para injeção no prompt do Preceptor."""
    res = get_student_weak_topics(mock_db, "user_123")
    block = format_student_diagnostic_block(res)

    assert "### DADOS DIAGNÓSTICOS EM TEMPO REAL DO ALUNO" in block
    assert "Insuficiência Cardíaca" in block
    assert "33.3%" in block
    assert "1 questões prontas para revisão imediata" in block


def test_ask_preceptor_ai_tool_calling_trigger(mock_db, monkeypatch):
    """Garante que o Preceptor acione a Tool e retorne tool_call ao receber dúvida sobre foco/fraquezas."""
    res = ask_preceptor_ai(
        stem="Paciente de 60 anos.",
        alternatives=[{"letter": "A", "text": "Opção A", "is_correct": True}],
        correct_letter="A",
        correct_text="Opção A",
        user_letter="A",
        user_question="Em que devo focar hoje nos meus estudos?",
        area="Clínica Médica",
        subtema="Cardiologia",
        user_id="user_123",
        db=mock_db
    )

    assert "answer" in res
    assert "tool_call" in res
    assert res["tool_call"] is not None
    assert res["tool_call"]["name"] == "get_student_weak_topics"
    assert res["tool_call"]["data"]["has_data"] is True
    assert res["tool_call"]["data"]["weak_topics"][0]["topic"] == "Insuficiência Cardíaca"
