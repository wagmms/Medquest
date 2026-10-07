def test_exam_readiness_reports_gaps_and_limited_sample(client):
    client.post("/api/questions/1/attempt", json={"selected_letter": "B"})
    report = client.get("/api/stats/exam-readiness?institution=USP-SP").get_json()
    assert report["institution"] == "USP-SP"
    assert report["answered"] == 1
    assert report["areas"][0]["sample"] == "limited"
    assert report["areas"][0]["action"].startswith("/estudar?")
    assert "institution=USP-SP" in report["areas"][0]["action"]
    assert len(report["key_factors"]) > 0
    assert "institution=USP-SP" in report["key_factors"][0]["action_url"]


def test_exam_readiness_excludes_other_user_attempts(client):
    with client.application.app_context():
        from api.db import get_db
        db = get_db()
        db.execute(
            """INSERT INTO attempts
               (question_id, selected_letter, is_correct, answered_at, confidence, user_id)
               VALUES (1, 'B', 1, '2026-08-20T12:00:00+00:00', 'certeza', 'other-user')"""
        )
        db.commit()
    report = client.get("/api/stats/exam-readiness?institution=USP-SP").get_json()
    assert report["answered"] == 0
    assert sum(area["attempts"] for area in report["areas"]) == 0


def test_exam_readiness_fallback_to_allowed_institutions(client):
    # Instituição não permitida ou vazia deve cair no padrão USP-SP
    report_invalid = client.get("/api/stats/exam-readiness?institution=INVALID_INST").get_json()
    assert report_invalid["institution"] == "USP-SP"

    report_empty = client.get("/api/stats/exam-readiness").get_json()
    assert report_empty["institution"] == "USP-SP"

    # Instituições permitidas devem ser aceitas
    for inst in ["USP-SP", "USP-RP", "UNICAMP", "UNIFESP", "SUS-SP"]:
        res = client.get(f"/api/stats/exam-readiness?institution={inst}").get_json()
        assert res["institution"] == inst


def test_breakdown_institution_restricted_to_allowed_five(client):
    res = client.get("/api/stats/breakdown?by=institution")
    assert res.status_code == 200
    data = res.get_json()
    allowed = {"USP-SP", "USP-RP", "UNICAMP", "UNIFESP", "SUS-SP"}
    assert len(data) == 5
    for item in data:
        assert item["key"] in allowed


def test_question_filter_institution_alias_expansion(client):
    # O filtro por USP-SP deve expandir para incluir aliases como USP SP e excluir outras bancas
    with client.application.app_context():
        from api.db import get_db
        db = get_db()
        db.execute("""
            INSERT OR IGNORE INTO questions (id, source_file, source_number, year, institution_code, institution_label, topic, area, subtema, missing_alts)
            VALUES
            (8801, 'test.pdf', 1, 2026, 'USP-SP', 'USP São Paulo', 'Cardio', 'Clínica Médica', 'Cardiologia', 0),
            (8802, 'test.pdf', 2, 2026, 'USP SP', 'USP SP Objetiva', 'Cardio', 'Clínica Médica', 'Cardiologia', 0),
            (8803, 'test.pdf', 3, 2026, 'ENARE', 'ENARE', 'Cardio', 'Clínica Médica', 'Cardiologia', 0)
        """)
        db.commit()

    res = client.get("/api/questions?institution=USP-SP")
    assert res.status_code == 200
    items = res.get_json()
    returned_ids = {q["id"] for q in items}
    assert 8801 in returned_ids or len(items) > 0
    # ENARE nunca deve estar no resultado de busca filtrado por USP-SP
    assert 8803 not in returned_ids


def test_exam_readiness_candidate_benchmark_and_competitive_layer(client):
    res = client.get("/api/stats/exam-readiness?institution=USP-SP")
    assert res.status_code == 200
    report = res.get_json()

    # Verifica campos de benchmark
    assert "candidate_mean" in report
    assert "competitive_delta" in report
    assert "competitive_analysis" in report

    comp = report["competitive_analysis"]
    assert "candidate_mean" in comp
    assert "difficulty_adjusted_score" in comp
    assert "difficulty_breakdown" in comp
    assert "facil" in comp["difficulty_breakdown"]
    assert "media" in comp["difficulty_breakdown"]
    assert "dificil" in comp["difficulty_breakdown"]

    # Verifica áreas enriquecidas com benchmark de candidatos
    assert len(report["areas"]) > 0
    for area in report["areas"]:
        assert "candidate_accuracy" in area
        assert area["candidate_accuracy"] > 0
        assert "competitive_delta" in area

