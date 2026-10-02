"""Testes de unidade para o módulo de Data Store e Grounding Médico (knowledge.py)."""

import os
import sqlite3
import pytest

from api.knowledge import (
    get_knowledge_connection,
    init_knowledge_schema,
    retrieve_medical_context,
    format_grounding_block,
    retrieve_jurisprudence_context,
    format_jurisprudence_block,
    _sanitize_fts_query,
)
from api.ai import ask_preceptor_ai


@pytest.fixture
def temp_knowledge_db(tmp_path):
    """Cria um banco de conhecimento temporário isolado para testes."""
    db_file = str(tmp_path / "test_knowledge.db")
    conn = get_knowledge_connection(db_file)
    init_knowledge_schema(conn)

    # Popula com dados de teste
    with conn:
        conn.execute("""
            INSERT INTO knowledge_chunks (
                source_file, source_type, specialty, topic, subtopic, title, content, word_count
            ) VALUES (
                'Ficha Resumo - Insuficiência Cardíaca.pdf',
                'ficha_resumo',
                'Clínica Médica',
                'Cardiologia',
                'Insuficiência Cardíaca',
                'Perfil Hemodinâmico de Stevenson',
                'Perfil B: Quente e Úmido. Mais frequente. Conduta: Furosemida IV e Vasodilatador (Nitroprussiato ou Nitroglicerina). Não fazer morfina rotineira.',
                30
            )
        """)
        conn.execute("""
            INSERT INTO knowledge_chunks (
                source_file, source_type, specialty, topic, subtopic, title, content, word_count
            ) VALUES (
                'Ficha Resumo - Apendicite Aguda.pdf',
                'ficha_resumo',
                'Cirurgia Geral',
                'Abdome Agudo',
                'Apendicite Aguda',
                'Escore de Alvarado e Conduta',
                'Dor em fossa ilíaca direita, sinal de Blumberg positivo. Escore de Alvarado maior que 7 indica intervenção cirúrgica sem necessidade de TC em homens jovens.',
                32
            )
        """)
    conn.close()
    return db_file


def test_sanitize_fts_query():
    """Garante que a query FTS5 seja limpa de caracteres especiais proibidos."""
    assert _sanitize_fts_query("perfil B (quente & úmido)?") == "perfil OR quente OR úmido"
    assert _sanitize_fts_query("a b c") == ""  # ignora palavras com menos de 3 letras


def test_init_and_search_knowledge(temp_knowledge_db):
    """Testa a recuperação via FTS5 por termos clínicos."""
    results = retrieve_medical_context(
        area="Clínica Médica",
        subtema="Cardiologia",
        stem="Paciente com congestão pulmonar e dispneia aos esforços",
        user_question="qual o manejo do perfil B quente e umido?",
        db_path=temp_knowledge_db
    )
    assert len(results) > 0
    assert "Ficha Resumo - Insuficiência Cardíaca.pdf" in results[0]["source_file"]
    assert "Stevenson" in results[0]["title"]


def test_format_grounding_block():
    """Garante que a formatação em Markdown gere o bloco oficial com citações."""
    sample_chunks = [{
        "source_file": "Ficha Resumo - IC.pdf",
        "topic": "Cardiologia",
        "subtopic": "Perfil B",
        "title": "Manejo da Congestão",
        "content": "Diurético de alça é a primeira linha."
    }]
    block = format_grounding_block(sample_chunks)
    assert "### CONTEXTO CLÍNICO OFICIAL ANCORADO (DATA STORE):" in block
    assert "[Fonte: Ficha Resumo - IC.pdf - Cardiologia | Perfil B]" in block
    assert "Diurético de alça é a primeira linha." in block


def test_ask_preceptor_ai_grounding_sources_present(monkeypatch, temp_knowledge_db):
    """Garante que ask_preceptor_ai retorne grounding_sources no dicionário de resposta."""
    monkeypatch.setattr("api.knowledge.DEFAULT_KNOWLEDGE_DB", temp_knowledge_db)

    res = ask_preceptor_ai(
        stem="Paciente hipertenso de 68 anos chega ao PS com ortopneia, crepitações bilaterais e PA 170x100.",
        alternatives=[
            {"letter": "A", "text": "Furosemida IV e Nitroglicerina", "is_correct": True},
            {"letter": "B", "text": "Hidratação vigorosa com SF 0,9%", "is_correct": False},
        ],
        correct_letter="A",
        correct_text="Furosemida IV e Nitroglicerina",
        user_letter="B",
        user_question="Por que não hidratar?",
        area="Clínica Médica",
        subtema="Cardiologia"
    )

    assert "answer" in res
    assert "grounding_sources" in res
    assert isinstance(res["grounding_sources"], list)


def test_ask_preceptor_ai_multiturn_and_playbooks(monkeypatch, temp_knowledge_db):
    """Garante que ask_preceptor_ai processe chat_history e comandos especiais (/conduta, /pegadinhas)."""
    monkeypatch.setattr("api.knowledge.DEFAULT_KNOWLEDGE_DB", temp_knowledge_db)

    history = [
        {"role": "user", "content": "O que fazer com esse paciente?"},
        {"role": "assistant", "content": "Ele está no perfil B (quente e úmido)."}
    ]

    # Teste de réplica multi-turn com comando /conduta
    res = ask_preceptor_ai(
        stem="Paciente em perfil B.",
        alternatives=[{"letter": "A", "text": "Furosemida", "is_correct": True}],
        correct_letter="A",
        correct_text="Furosemida",
        user_letter="A",
        user_question="/conduta",
        area="Clínica Médica",
        subtema="Cardiologia",
        chat_history=history
    )

    assert "answer" in res
    assert res["source"] in ("universal", "fallback", "mock_ai")
    assert isinstance(res["grounding_sources"], list)


def test_retrieve_jurisprudence_context(tmp_path):
    """Testa recuperação de questões análogas das bancas via questions_fts."""
    db_file = str(tmp_path / "test_jurisprudence.db")
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    with conn:
        conn.execute("""
            CREATE TABLE questions (
                id INTEGER PRIMARY KEY,
                institution_label TEXT,
                year INTEGER,
                area TEXT,
                subtema TEXT,
                stem TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE explanations (
                question_id INTEGER PRIMARY KEY,
                explanation_text TEXT
            )
        """)
        conn.execute("""
            CREATE VIRTUAL TABLE questions_fts USING fts5(
                stem,
                explanation
            )
        """)
        conn.execute("""
            INSERT INTO questions (id, institution_label, year, area, subtema, stem)
            VALUES (101, 'USP-SP', 2023, 'Clínica Médica', 'Insuficiência Cardíaca', 'Paciente com congestão pulmonar e hipertensão no PS.')
        """)
        conn.execute("""
            INSERT INTO explanations (question_id, explanation_text)
            VALUES (101, 'Gabarito Letra A. Pulo do Gato: No perfil B, a banca sempre exige vasodilatador e diurético.')
        """)
        conn.execute("""
            INSERT INTO questions_fts (rowid, stem, explanation)
            VALUES (101, 'Paciente com congestão pulmonar e hipertensão no PS.', 'Gabarito Letra A. Pulo do Gato: No perfil B, a banca sempre exige vasodilatador e diurético.')
        """)

    results = retrieve_jurisprudence_context(
        db=conn,
        current_question_id=999,
        area="Clínica Médica",
        subtema="Insuficiência Cardíaca",
        stem="Paciente com congestão pulmonar",
        user_question="qual o vasodilatador de escolha?",
        top_k=2
    )

    assert len(results) == 1
    assert results[0]["id"] == 101
    assert results[0]["institution"] == "USP-SP"
    assert "vasodilatador" in results[0]["explanation_excerpt"]

    # Formatação do bloco
    block = format_jurisprudence_block(results)
    assert "JURISPRUDÊNCIA DE BANCAS MÉDICAS" in block
    assert "USP-SP" in block
    assert "Questão #101" in block
    conn.close()


