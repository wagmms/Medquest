"""Fixtures de teste: cada teste recebe um banco SQLite temporário próprio (isolado)."""
import os
import sqlite3

import pytest

from api import create_app

collect_ignore: list[str] = []

SCHEMA_AND_SEED = """
CREATE TABLE questions(
    id INTEGER PRIMARY KEY, source_file TEXT, source_number INTEGER, year INTEGER,
    institution_code TEXT, institution_label TEXT, topic TEXT, stem TEXT,
    correct_letter TEXT, missing_alts INTEGER DEFAULT 0, area TEXT, subtema TEXT,
    subtema_id TEXT, subtema_orig TEXT, editorial_status TEXT, status TEXT DEFAULT 'active');
CREATE TABLE alternatives(id INTEGER PRIMARY KEY, question_id INTEGER, letter TEXT,
    text TEXT, is_correct INTEGER);
CREATE TABLE explanations(question_id INTEGER PRIMARY KEY, explanation_text TEXT, generated_at TEXT);
CREATE TABLE question_images(id INTEGER PRIMARY KEY, question_id INTEGER, file_path TEXT, order_index INTEGER);
CREATE TABLE attempts(id INTEGER PRIMARY KEY, question_id INTEGER, selected_letter TEXT,
    is_correct INTEGER, answered_at TEXT, confidence TEXT, user_id INTEGER DEFAULT 1, time_spent_ms INTEGER);
INSERT INTO questions(id,area,subtema,stem,correct_letter,missing_alts,year,institution_code,institution_label)
  VALUES (1,'Clínica Médica','Hipertensão Arterial Sistêmica','Q1?','B',0,2025,'USP-SP','USP'),
         (2,'Pediatria','Imunização (PNI)','Q2?','A',0,2025,'USP-RP','USP RP'),
         (3,'Pediatria','Vitaminas','Q3 Discursiva?','A',0,2021,'UNICAMP','UNICAMP');
INSERT INTO alternatives(question_id,letter,text,is_correct) VALUES
  (1,'A','a',0),(1,'B','b',1),(2,'A','a',1),(2,'B','b',0),(3,'A','Anote sua hipótese',1);
INSERT INTO explanations VALUES (1,'explicação da 1','now'), (3,'**Gabarito**: DISSERTATIVA\n**Pulo do Gato**: Raquitismo carencial\n**Raciocínio Clínico**: Deficiência de vitamina D','now');
"""


@pytest.fixture()
def app(tmp_path):
    dbfile = tmp_path / "medquest_test.db"
    con = sqlite3.connect(dbfile)
    con.executescript(SCHEMA_AND_SEED)
    con.commit()
    con.close()
    os.environ["MEDQUEST_DB"] = str(dbfile)
    try:
        from api.questions import count_cache, meta_cache
        from api.stats import overview_cache
        meta_cache.cache.clear()
        count_cache.cache.clear()
        overview_cache.cache.clear()
        app = create_app(testing=True)
        yield app
    finally:
        os.environ.pop("MEDQUEST_DB", None)


@pytest.fixture()
def client(app):
    return app.test_client()



@pytest.fixture(autouse=True)
def mock_ai_providers_hermetic(monkeypatch):
    """Garante que a suíte de testes seja 100% hermética, rápida e offline por padrão."""
    if os.environ.get("RUN_LIVE_AI") == "1":
        return

    from api import ai, gemini_pool, osce

    def fake_generate_content_with_fallback(prompt, system_instruction=None, json_mode=False, **kwargs):
        if gemini_pool.gemini_pool.total_keys == 0:
            raise RuntimeError("Todos os provedores de IA falharam (simulando indisponibilidade).")

        if json_mode:
            return {
                "text": '{"terms": ["hipertensao", "has", "pressao alta"]}',
                "source": "mock_ai",
                "model": "mock-flash"
            }
        return {
            "text": "A conduta padrão-ouro é iniciar tratamento adequado.\n\n**Gabarito**: Alternativa B.\n**Pulo do Gato**: Em pacientes de alto risco, iniciar monoterapia ou combinação conforme diretriz.",
            "source": "mock_ai",
            "model": "mock-flash"
        }

    monkeypatch.setattr(gemini_pool, "generate_content_with_fallback", fake_generate_content_with_fallback)
    monkeypatch.setattr(ai, "generate_content_with_fallback", fake_generate_content_with_fallback)
    monkeypatch.setattr(
        osce,
        "generate_content_with_fallback",
        lambda *args, **kwargs: {"text": "", "source": "mock_osce_fallback", "model": "mock-flash"},
    )



