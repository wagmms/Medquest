"""
Testes unitários e de integração para o script de auto-reparo de flashcards (auto_heal_cards.py).
"""
import json
import sqlite3
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

import sys
backend_dir = Path(__file__).resolve().parent.parent
root_dir = backend_dir.parent.parent
if str(root_dir / "scripts") not in sys.path:
    sys.path.insert(0, str(root_dir / "scripts"))

from auto_heal_cards import DatabaseManager, CardHealer, process_single_card, run_pipeline


@pytest.fixture
def mock_db(tmp_path):
    """Cria um banco SQLite temporário com esquema MedQuest completo para testes."""
    db_file = tmp_path / "test_medquest.db"
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row

    conn.execute("""
        CREATE TABLE flashcards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER,
            front TEXT NOT NULL,
            back TEXT,
            created_at TEXT NOT NULL,
            next_review_date TEXT,
            fsrs_card TEXT,
            user_id TEXT DEFAULT '1',
            source_context TEXT,
            is_ai_generated INTEGER DEFAULT 0,
            report_status TEXT,
            deck_name TEXT DEFAULT 'Geral',
            tags TEXT,
            source_type TEXT DEFAULT 'medquest'
        )
    """)

    conn.execute("""
        CREATE TABLE questions (
            id INTEGER PRIMARY KEY,
            stem TEXT,
            correct_letter TEXT,
            area TEXT,
            subtema TEXT,
            topic TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE alternatives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER,
            letter TEXT,
            text TEXT,
            is_correct INTEGER
        )
    """)

    conn.execute("""
        CREATE TABLE explanations (
            question_id INTEGER PRIMARY KEY,
            explanation_text TEXT
        )
    """)

    # Insere dados de teste:
    # 1. Questão 100
    conn.execute(
        "INSERT INTO questions (id, stem, correct_letter, area, subtema) VALUES (?, ?, ?, ?, ?)",
        (100, "Paciente com febre e tosse produtiva.", "A", "Clínica Médica", "Pneumologia")
    )
    conn.execute(
        "INSERT INTO alternatives (question_id, letter, text, is_correct) VALUES (?, ?, ?, ?)",
        (100, "A", "Amoxicilina", 1)
    )
    conn.execute(
        "INSERT INTO alternatives (question_id, letter, text, is_correct) VALUES (?, ?, ?, ?)",
        (100, "B", "Ciprofloxacino", 0)
    )
    conn.execute(
        "INSERT INTO explanations (question_id, explanation_text) VALUES (?, ?)",
        (100, "**Gabarito**: A. **Pulo do Gato**: PAC sem comorbidades trata-se com Amoxicilina.")
    )

    # 2. Flashcard 1 (Reportado)
    conn.execute("""
        INSERT INTO flashcards (id, question_id, front, back, created_at, report_status)
        VALUES (1, 100, '[Pneumologia] Paciente com tosse.\\n\\n👉 Conduta: {{c1::Amoxicilina}}',
                '💡 Pulo do Gato:\\nTratamento ambulatorial padrão.', '2026-09-01', 'Mal formatado')
    """)

    # 3. Flashcard 2 (Não reportado / Normal)
    conn.execute("""
        INSERT INTO flashcards (id, question_id, front, back, created_at, report_status)
        VALUES (2, 100, '[Pneumologia] Card normal.\\n\\n👉 Conduta: {{c1::Amox}}',
                '💡 Pulo do Gato:\\nOk', '2026-09-01', NULL)
    """)

    conn.commit()
    conn.close()
    return db_file


def test_fetch_reported_cards(mock_db, monkeypatch):
    """Verifica se apenas cards com report_status ativo são detectados."""
    monkeypatch.setenv("MEDQUEST_DB", str(mock_db))
    db_mgr = DatabaseManager(target="local")

    cards = db_mgr.fetch_reported_cards()
    assert len(cards) == 1
    assert cards[0]["id"] == 1
    assert cards[0]["report_status"] == "Mal formatado"


def test_fetch_question_context(mock_db, monkeypatch):
    """Verifica se o contexto médico completo da questão é recuperado."""
    monkeypatch.setenv("MEDQUEST_DB", str(mock_db))
    db_mgr = DatabaseManager(target="local")

    ctx = db_mgr.fetch_question_context(100)
    assert ctx is not None
    assert ctx["question_id"] == 100
    assert ctx["correct_letter"] == "A"
    assert ctx["area"] == "Clínica Médica"
    assert len(ctx["alternatives"]) == 2
    assert "Amoxicilina" in ctx["explanation"]


def test_card_healer_validation():
    """Valida o parser e sanitizador de respostas da IA."""
    healer = CardHealer()

    valid_json = json.dumps({
        "fixed_front": "[Pneumo] Caso clínico...\\n\\n👉 Diagnóstico: {{c1::Pneumonia bacteriana}}",
        "fixed_back": "💡 **Pulo do Gato:**\\nRegra de ouro clínica.",
        "fix_summary": "Correção ortográfica e de cloze.",
        "changes_made": ["Ajustado cloze {{c1::...}}"]
    })

    card = {"id": 1, "front": "{{c1::Antigo}}"}
    parsed = healer._parse_and_validate_response(valid_json, card)
    assert parsed is not None
    assert parsed["fixed_front"].startswith("[Pneumo]")
    assert "💡 **Pulo do Gato:**" in parsed["fixed_back"]
    assert len(parsed["changes_made"]) == 1

    # Resposta sem cloze quando o original tinha cloze deve ser rejeitada
    invalid_no_cloze = json.dumps({
        "fixed_front": "[Pneumo] Pergunta sem cloze",
        "fixed_back": "💡 Pulo do Gato:",
        "fix_summary": "Erro",
        "changes_made": []
    })
    assert healer._parse_and_validate_response(invalid_no_cloze, card) is None


def test_apply_repair_and_bring_online(mock_db, monkeypatch):
    """Verifica se apply_repair atualiza o card, limpa o report_status (online) e gera log."""
    monkeypatch.setenv("MEDQUEST_DB", str(mock_db))
    db_mgr = DatabaseManager(target="local")

    success = db_mgr.apply_repair(
        card_id=1,
        fixed_front="[Pneumologia] Nova frente {{c1::Amoxicilina}}",
        fixed_back="💡 **Pulo do Gato:**\\nNovo verso perfeito.",
        report_reason="Mal formatado",
        original_front="Frente antiga",
        original_back="Verso antigo",
        fix_summary="Reformatado",
        changes_made=["Ajustado cloze"],
        model_used="gemini-3.5-flash-lite",
    )
    assert success is True

    # Verifica no banco se o card agora está ONLINE (report_status IS NULL)
    conn = sqlite3.connect(str(mock_db))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT front, back, report_status FROM flashcards WHERE id = 1").fetchone()
    assert row["report_status"] is None  # Card está online novamente!
    assert "Nova frente" in row["front"]
    assert "Novo verso" in row["back"]

    # Verifica se o log de auditoria foi inserido
    log_row = conn.execute("SELECT * FROM flashcard_repair_logs WHERE flashcard_id = 1").fetchone()
    assert log_row is not None
    assert log_row["report_reason"] == "Mal formatado"
    assert log_row["model_used"] == "gemini-3.5-flash-lite"
    assert log_row["target_db"] == "local"
    conn.close()


def test_run_pipeline_end_to_end(mock_db, monkeypatch):
    """Executa a pipeline de ponta a ponta com mock do provedor de IA."""
    monkeypatch.setenv("MEDQUEST_DB", str(mock_db))
    db_mgr = DatabaseManager(target="local")
    healer = CardHealer()

    mock_ai_response = {
        "text": json.dumps({
            "fixed_front": "[Pneumologia] Caso...\\n\\n👉 Conduta: {{c1::Amoxicilina}}",
            "fixed_back": "💡 **Pulo do Gato:**\\nDiretriz 2026.",
            "fix_summary": "Padronização de formatação.",
            "changes_made": ["Formatado"]
        }),
        "model": "gemini-3.5-flash-lite"
    }

    with patch("auto_heal_cards.gemini_pool.generate_content", return_value=mock_ai_response):
        total, ok, fail = run_pipeline(db_mgr, healer)
        assert total == 1
        assert ok == 1
        assert fail == 0

    # Segunda execução não deve achar mais nenhum card pendente (já corrigido e online)
    total2, ok2, fail2 = run_pipeline(db_mgr, healer)
    assert total2 == 0
