import sqlite3
import pytest
from flask import g
from api.filters import get_user_target_institutions, TARGET_INSTITUTION_RATIO
from api.questions import _sample_prioritized_ids


def test_get_user_target_institutions_empty_and_todas(app):
    with app.app_context():
        from api.db import get_db
        db = get_db()
        # Sem registro no planner_config
        assert get_user_target_institutions(db, "user_inexistente") == set()

        # Com TODAS AS BANCAS
        db.execute(
            "INSERT INTO planner_config (user_id, exam_date, start_date, days_per_week, questions_per_day, target_institution) VALUES (?, '2026-11-15', '2026-01-01', 6, 30, 'Todas as Bancas')",
            ("user_todas",)
        )
        assert get_user_target_institutions(db, "user_todas") == set()


def test_get_user_target_institutions_expansion(app):
    with app.app_context():
        from api.db import get_db
        db = get_db()
        db.execute(
            "INSERT INTO planner_config (user_id, exam_date, start_date, days_per_week, questions_per_day, target_institution) VALUES (?, '2026-11-15', '2026-01-01', 6, 30, 'USP-SP, UNICAMP, SCMSP')",
            ("user_alvo",)
        )
        targets = get_user_target_institutions(db, "user_alvo")
        assert "USP-SP" in targets
        assert "USP SP" in targets
        assert "UNICAMP" in targets
        assert "SCMSP" in targets
        assert "SCM" in targets


def test_sample_prioritized_ids_blending(app):
    with app.app_context():
        from api.db import get_db
        db = get_db()
        # Seed 10 questões: 5 USP-SP e 5 OUTRAS
        for i in range(10, 15):
            db.execute("INSERT INTO questions (id, area, subtema, stem, correct_letter, missing_alts, year, institution_code) VALUES (?, 'Cirurgia', 'Apendicite', 'Stem', 'A', 0, 2024, 'USP-SP')", (i,))
        for i in range(15, 20):
            db.execute("INSERT INTO questions (id, area, subtema, stem, correct_letter, missing_alts, year, institution_code) VALUES (?, 'Cirurgia', 'Apendicite', 'Stem', 'A', 0, 2024, 'UNIFESP')", (i,))

        target_insts = {"USP-SP"}
        where_clause = "q.missing_alts = 0 AND q.area = ?"
        params = ("Cirurgia",)

        # Solicita 5 questões: 40% = 2 de USP-SP e 60% = 3 de UNIFESP
        sampled_ids = _sample_prioritized_ids(db, where_clause, params, limit=5, target_insts=target_insts, has_explicit_inst_filter=False)
        assert len(sampled_ids) == 5
        
        # Verifica a contagem de cada banca nos IDs sorteados
        ph = ",".join("?" * len(sampled_ids))
        rows = db.execute(f"SELECT institution_code FROM questions WHERE id IN ({ph})", sampled_ids).fetchall()
        usp_count = sum(1 for r in rows if r["institution_code"] == "USP-SP")
        other_count = sum(1 for r in rows if r["institution_code"] == "UNIFESP")

        # Cota de 40% de 5 = 2 USP-SP e 3 outras
        assert usp_count == 2
        assert other_count == 3


def test_sample_prioritized_ids_fallback_when_short(app):
    with app.app_context():
        from api.db import get_db
        db = get_db()
        # Tema com apenas 1 questão da banca alvo e 5 de outras
        for i in range(30, 31):
            db.execute("INSERT INTO questions (id, area, subtema, stem, correct_letter, missing_alts, year, institution_code) VALUES (?, 'Pediatria', 'Asma Infantil', 'Stem', 'A', 0, 2024, 'USP-SP')", (i,))
        for i in range(31, 36):
            db.execute("INSERT INTO questions (id, area, subtema, stem, correct_letter, missing_alts, year, institution_code) VALUES (?, 'Pediatria', 'Asma Infantil', 'Stem', 'A', 0, 2024, 'AMRIGS')", (i,))

        target_insts = {"USP-SP"}
        where_clause = "q.missing_alts = 0 AND q.subtema = ?"
        params = ("Asma Infantil",)

        # Solicita 4 questões: meta seria 2 USP-SP, mas só existe 1. Deve completar com AMRIGS sem falhar!
        sampled_ids = _sample_prioritized_ids(db, where_clause, params, limit=4, target_insts=target_insts, has_explicit_inst_filter=False)
        assert len(sampled_ids) == 4
        assert 30 in sampled_ids  # A única questão alvo deve estar presente


def test_api_questions_study_queue_with_target_institution(client, app):
    # Configura planner_config para o usuário de teste
    with app.app_context():
        from api.db import get_db, db_transaction
        db = get_db()
        with db_transaction(db, immediate=True):
            db.execute(
                "INSERT OR REPLACE INTO planner_config (user_id, exam_date, start_date, days_per_week, questions_per_day, target_institution) VALUES (?, '2026-11-15', '2026-01-01', 6, 30, 'USP-SP')",
                ("user-1",)
            )

    # 1. GET /api/questions (modo normal)
    res = client.get("/api/questions?limit=10", headers={"X-User-ID": "user-1"})
    assert res.status_code == 200
    data = res.get_json()
    assert len(data) > 0
    # Verifica a presença da flag is_target_institution
    for q in data:
        assert "is_target_institution" in q
        if q["institution_code"] in ("USP-SP", "USP SP"):
            assert q["is_target_institution"] is True

    # 2. GET /api/questions/<id>
    q_usp = next((q for q in data if q["institution_code"] == "USP-SP"), None)
    if q_usp:
        res_detail = client.get(f"/api/questions/{q_usp['id']}", headers={"X-User-ID": "user-1"})
        assert res_detail.status_code == 200
        assert res_detail.get_json()["is_target_institution"] is True

    # 3. POST /api/questions/batch
    res_batch = client.post("/api/questions/batch", json={"ids": [d["id"] for d in data[:3]]}, headers={"X-User-ID": "user-1"})
    assert res_batch.status_code == 200
    batch_qs = res_batch.get_json()["questions"]
    assert len(batch_qs) > 0
    for bq in batch_qs:
        assert "is_target_institution" in bq

    # 4. GET /api/meta
    res_meta = client.get("/api/meta", headers={"X-User-ID": "user-1"})
    assert res_meta.status_code == 200
    meta_json = res_meta.get_json()
    assert "target_institutions" in meta_json
    assert any("USP-SP" in t for t in meta_json["target_institutions"])


def test_api_questions_adaptive_mode_target_boost(client, app):
    with app.app_context():
        from api.db import get_db, db_transaction
        db = get_db()
        with db_transaction(db, immediate=True):
            db.execute(
                "INSERT OR REPLACE INTO planner_config (user_id, exam_date, start_date, days_per_week, questions_per_day, target_institution) VALUES (?, '2026-11-15', '2026-01-01', 6, 30, 'USP-SP')",
                ("user-adaptive",)
            )

    res = client.get("/api/questions?mode=adaptive&limit=10", headers={"X-User-ID": "user-adaptive"})
    assert res.status_code == 200
    data = res.get_json()
    assert len(data) > 0
    usp_items = [q for q in data if q.get("institution_code") == "USP-SP"]
    if usp_items:
        assert usp_items[0]["is_target_institution"] is True
        assert "target_institution_focus" in usp_items[0]["adaptive_reasons"]
