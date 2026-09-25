from datetime import date, timedelta

from api.services.planner import generate_annual_plan, build_plan_from_schedule


def test_intensive_plan_uses_high_yield_catalog():
    rows = [
        {"area": "Clínica Médica", "subtema": "Hipertensão Arterial Sistêmica e Crises Hipertensivas", "q_count": 12},
        {"area": "Clínica Médica", "subtema": "Tema sem prioridade cadastrada", "q_count": 12},
    ]
    start = date.today()
    result = generate_annual_plan(
        rows,
        start.isoformat(),
        (start + timedelta(weeks=8)).isoformat(),
        hours_per_week=10,
        intensive=True,
    )

    topics = [topic for week in result["plan"] for topic in week["topics"]]
    topic_names = {topic["subtema"] for topic in topics}
    assert "Hipertensão Arterial Sistêmica e Crises Hipertensivas" in topic_names
    assert "Tema sem prioridade cadastrada" not in topic_names


def test_plan_uses_curriculum_theory_duration_and_two_hour_practice_block():
    rows = [
        {"area": "Clínica Médica", "subtema": "Hipertensão Arterial Sistêmica e Crises Hipertensivas", "q_count": 12},
    ]
    start = date.today()

    result = generate_annual_plan(
        rows,
        start.isoformat(),
        (start + timedelta(weeks=8)).isoformat(),
        hours_per_week=10,
    )

    topics = [topic for week in result["plan"] for topic in week["topics"]]
    topic = next(topic for topic in topics if topic["subtema"] == "Hipertensão Arterial Sistêmica e Crises Hipertensivas")
    assert topic["estimated_theory_hours"] == 2.81
    assert topic["estimated_practice_hours"] == 2.0
    assert topic["estimated_hours"] == 4.81
    assert topic["theory_source"] == "curriculum"
    assert topic["course_module"] == "Hipertensão Arterial Sistêmica e Crises Hipertensivas"


def test_plan_ignores_topics_outside_the_canonical_catalog():
    rows = [
        {"area": "Clínica Médica", "subtema": "Tema sem prioridade cadastrada", "q_count": 12},
    ]
    start = date.today()

    result = generate_annual_plan(
        rows,
        start.isoformat(),
        (start + timedelta(weeks=8)).isoformat(),
        hours_per_week=10,
    )

    topics = [topic for week in result["plan"] for topic in week["topics"]]
    assert topics
    assert result["total_required_hours"] == 610


def test_go_focos_usp_are_high_yield():
    rows = []
    start = date.today()
    result = generate_annual_plan(
        rows,
        start.isoformat(),
        (start + timedelta(weeks=20)).isoformat(),
        hours_per_week=20,
        intensive=True,
    )
    topics = [topic for week in result["plan"] for topic in week["topics"]]
    go_topics = [t for t in topics if t["area"] == "Ginecologia e Obstetrícia"]
    go_names = {t["subtema"] for t in go_topics}

    # Verify key GO Foco USP topics are present in intensive plan
    assert "Síndromes Hipertensivas na Gravidez (Pré-eclâmpsia e Eclâmpsia)" in go_names
    assert "Investigação das Amenorreias e Síndrome dos Ovários Policísticos (SOP)" in go_names
    assert "Assistência Pré-Natal de Baixo e Alto Risco" in go_names
    assert "Rastreamento Citopatológico e Conduta em Lesões Cervicais (HPV)" in go_names
    assert "Diabetes Gestacional e Pré-Gestacional" in go_names
    assert "Métodos Contraceptivos: Hormonais, DIU e Cirúrgicos" in go_names
    assert "Climatério, Menopausa e Terapia de Reposição Hormonal (TRH)" in go_names
    assert "Uroginecologia: Incontinência Urinária e Prolapso Genital" in go_names
    assert len(go_names) == 14


def test_proportional_distribution_avoids_end_concentration():
    rows = []
    start = date.today()
    result = generate_annual_plan(
        rows,
        start.isoformat(),
        (start + timedelta(weeks=26)).isoformat(),
        hours_per_week=24,
        intensive=False,
    )
    plan = result["plan"]
    assert len(plan) >= 20

    # Ensure GO is well distributed across the schedule, not only at the end
    first_half_weeks = plan[:len(plan)//2]
    second_half_weeks = plan[len(plan)//2:]

    go_first_half = sum(1 for w in first_half_weeks for t in w["topics"] if t["area"] == "Ginecologia e Obstetrícia")
    go_second_half = sum(1 for w in second_half_weeks for t in w["topics"] if t["area"] == "Ginecologia e Obstetrícia")

    assert go_first_half >= 10
    assert go_second_half >= 10

    # In the final 3 weeks, no single area should occupy > 60% of total topics
    for w in plan[-3:]:
        total_w = len(w["topics"])
        for area in ["Clínica Médica", "Cirurgia", "Ginecologia e Obstetrícia", "Pediatria", "Preventiva"]:
            area_count = sum(1 for t in w["topics"] if t["area"] == area)
            assert area_count <= max(3, int(total_w * 0.65))


def test_planner_topic_progress_and_reset(client):
    # Test marking a topic as completed
    r = client.post("/api/planner/1/topic", json={"subtema": "Taquiarritmias", "completed": True})
    assert r.status_code == 200
    assert r.get_json()["completed"] is True

    # Test getting topic progress
    r = client.get("/api/planner/topics")
    assert r.status_code == 200
    assert r.get_json().get("1:Taquiarritmias") is True

    # Test stats reset clears topic progress
    r = client.delete("/api/stats/reset")
    assert r.status_code == 200

    r = client.get("/api/planner/topics")
    assert r.status_code == 200
    assert r.get_json().get("1:Taquiarritmias") is None


def test_planner_without_history_preserves_prior_behavior():
    start = date.today()
    result = generate_annual_plan(
        [],
        start.isoformat(),
        (start + timedelta(weeks=12)).isoformat(),
        hours_per_week=20,
        adaptive_signals={},
    )
    topics = [t for week in result["plan"] for t in week["topics"]]
    assert len(topics) > 0
    for t in topics:
        assert t["priority_reasons"] == []
        if t["priority"] >= 100:
            assert t["priority"] in (101.5, 102.0, 103.0)


def test_planner_adaptive_priority_boosts_theme_with_difficulty():
    start = date.today()
    theme_normal = "Hipertensão Arterial Sistêmica e Crises Hipertensivas"
    theme_struggling = "Síndromes Coronarianas Agudas (Com e Sem Supra de ST)"

    adaptive_signals = {
        theme_struggling: {
            "topic": theme_struggling,
            "attempts": 8,
            "correct": 1,
            "accuracy": 0.125,
            "priority_score": 0.75,
            "reasons": ["low_accuracy"],
            "due_count": 0,
            "retrievability": None,
        }
    }

    result = generate_annual_plan(
        [],
        start.isoformat(),
        (start + timedelta(weeks=12)).isoformat(),
        hours_per_week=20,
        adaptive_signals=adaptive_signals,
    )
    topics = [t for week in result["plan"] for t in week["topics"]]
    t_normal = next(t for t in topics if t["subtema"] == theme_normal)
    t_struggling = next(t for t in topics if t["subtema"] == theme_struggling)

    assert "low_accuracy" in t_struggling["priority_reasons"]
    assert t_normal["priority_reasons"] == []
    assert t_struggling["priority"] > t_normal["priority"]

    struggling_idx = topics.index(t_struggling)
    normal_idx = topics.index(t_normal)
    assert struggling_idx < normal_idx


def test_planner_user_isolation(client, app):
    from api.db import get_db
    with app.app_context():
        db = get_db()
        db.execute(
            """INSERT INTO questions(id, area, subtema, stem, correct_letter, missing_alts, year, institution_code, institution_label)
               VALUES (101, 'Clínica Médica', 'Hipertensão Arterial Sistêmica e Crises Hipertensivas', 'Stem HAS', 'B', 0, 2025, 'USP', 'USP'),
                      (102, 'Clínica Médica', 'Síndromes Coronarianas Agudas (Com e Sem Supra de ST)', 'Stem SCA', 'A', 0, 2025, 'USP', 'USP')"""
        )
        for _ in range(5):
            db.execute(
                """INSERT INTO attempts(question_id, selected_letter, is_correct, answered_at, user_id)
                   VALUES (101, 'A', 0, '2026-09-20T10:00:00Z', ?)""",
                ("user_alpha",)
            )
        db.commit()

    start = date.today()
    exam = (start + timedelta(weeks=12)).isoformat()
    payload = {"start_date": start.isoformat(), "exam_date": exam, "hours_per_week": 20}

    resp_alpha = client.post("/api/generate_plan", json=payload, headers={"X-User-ID": "user_alpha"})
    assert resp_alpha.status_code == 200
    topics_alpha = [t for w in resp_alpha.get_json()["plan"] for t in w["topics"]]
    has_alpha = next(t for t in topics_alpha if t["subtema"] == "Hipertensão Arterial Sistêmica e Crises Hipertensivas")
    assert "low_accuracy" in has_alpha["priority_reasons"]
    assert has_alpha["priority"] > 103.0

    resp_beta = client.post("/api/generate_plan", json=payload, headers={"X-User-ID": "user_beta"})
    assert resp_beta.status_code == 200
    topics_beta = [t for w in resp_beta.get_json()["plan"] for t in w["topics"]]
    has_beta = next(t for t in topics_beta if t["subtema"] == "Hipertensão Arterial Sistêmica e Crises Hipertensivas")
    assert has_beta["priority_reasons"] == []
    assert has_beta["priority"] == 103.0


def test_planner_supports_topic_outside_top_15(client, app):
    import json
    from api.adaptive import build_learning_profile
    from api.db import get_db
    from api.services.planner import _resolve_data_path

    with open(_resolve_data_path("plannerData.json"), "r", encoding="utf-8") as f:
        meta = json.load(f)
    canonical_subtemas = []
    for area in meta:
        for macro in area.get("macroThemes", []):
            for s in macro.get("dbSubtemas", []):
                if s not in canonical_subtemas:
                    canonical_subtemas.append(s)
                if len(canonical_subtemas) >= 20:
                    break
            if len(canonical_subtemas) >= 20:
                break
        if len(canonical_subtemas) >= 20:
            break

    assert len(canonical_subtemas) == 20

    user_id = "user_top15_test"
    with app.app_context():
        db = get_db()
        for idx, subtema in enumerate(canonical_subtemas):
            qid = 200 + idx
            db.execute(
                """INSERT INTO questions(id, area, subtema, stem, correct_letter, missing_alts, year, institution_code, institution_label)
                   VALUES (?, 'Clínica Médica', ?, 'Stem', 'B', 0, 2025, 'USP', 'USP')""",
                (qid, subtema)
            )
            attempts_count = 25 - idx
            for _ in range(attempts_count):
                db.execute(
                    """INSERT INTO attempts(question_id, selected_letter, is_correct, answered_at, user_id)
                       VALUES (?, 'A', 0, '2026-09-20T10:00:00Z', ?)""",
                    (qid, user_id)
                )
        db.commit()

        profile = build_learning_profile(db, user_id)
        top15_topics = {t["topic"] for t in profile["topics"]}
        assert len(top15_topics) == 15

        outside_topic = canonical_subtemas[19]
        assert outside_topic not in top15_topics

    start = date.today()
    exam = (start + timedelta(weeks=12)).isoformat()
    payload = {"start_date": start.isoformat(), "exam_date": exam, "hours_per_week": 20}

    resp = client.post("/api/generate_plan", json=payload, headers={"X-User-ID": user_id})
    assert resp.status_code == 200
    plan_topics = [t for w in resp.get_json()["plan"] for t in w["topics"]]
    outside_item = next(t for t in plan_topics if t["subtema"] == outside_topic)

    assert "low_accuracy" in outside_item["priority_reasons"]
    assert outside_item["priority"] > 100.0





def test_empty_adaptive_history_matches_legacy_plan_exactly():
    start = date.today()
    kwargs = dict(rows=[], start_date_str=start.isoformat(),
                  exam_date_str=(start + timedelta(weeks=52)).isoformat(), hours_per_week=40)
    assert generate_annual_plan(**kwargs, adaptive_signals={}) == generate_annual_plan(**kwargs)


def test_adaptive_signals_preserve_catalog_and_intensive_filter():
    start = date.today()
    kwargs = dict(rows=[], start_date_str=start.isoformat(),
                  exam_date_str=(start + timedelta(weeks=52)).isoformat(), hours_per_week=40)
    def topics(plan):
        return {topic['subtema']: topic for week in plan['plan'] for topic in week['topics']}
    baseline = topics(generate_annual_plan(**kwargs))
    signals = {name: {'priority_score': 0.8, 'reasons': ['memory_at_risk']} for name in baseline}
    adaptive = topics(generate_annual_plan(**kwargs, adaptive_signals=signals))
    assert len(baseline) == len(adaptive) == 170
    for name, previous in baseline.items():
        for key in ('estimated_theory_hours', 'estimated_practice_hours', 'estimated_hours'):
            assert adaptive[name][key] == previous[key]
    intensive_before = topics(generate_annual_plan(**kwargs, intensive=True))
    intensive_after = topics(generate_annual_plan(**kwargs, intensive=True, adaptive_signals=signals))
    assert intensive_before.keys() == intensive_after.keys()


def test_planner_schedule_persisted_and_frozen_across_calls(client, app):
    from api.db import get_db

    user_id = "user_freeze_test"
    start = date.today()
    exam = (start + timedelta(weeks=20)).isoformat()
    payload = {"start_date": start.isoformat(), "exam_date": exam, "hours_per_week": 20}

    # First call generates and persists
    resp1 = client.post("/api/generate_plan", json=payload, headers={"X-User-ID": user_id})
    assert resp1.status_code == 200
    plan1 = resp1.get_json()["plan"]
    weeks_order_1 = [(w["week"], [t["subtema"] for t in w["topics"]]) for w in plan1]

    # Verify rows were persisted in planner_schedule
    with app.app_context():
        db = get_db()
        count = db.execute("SELECT COUNT(*) FROM planner_schedule WHERE user_id = ?", (user_id,)).fetchone()[0]
        assert count > 0

    # Simulate answering questions with many errors in a topic that is scheduled for a later week
    later_topic = plan1[5]["topics"][0]["subtema"]
    with app.app_context():
        db = get_db()
        db.execute(
            """INSERT INTO questions(id, area, subtema, stem, correct_letter, missing_alts, year, institution_code, institution_label)
               VALUES (99901, 'Clínica Médica', ?, 'Stem Error', 'B', 0, 2025, 'USP', 'USP')""",
            (later_topic,)
        )
        for _ in range(8):
            db.execute(
                """INSERT INTO attempts(question_id, selected_letter, is_correct, answered_at, user_id)
                   VALUES (99901, 'A', 0, '2026-09-20T10:00:00Z', ?)""",
                (user_id,)
            )
        db.commit()

    # Second call must return the EXACT same weeks and topic order
    resp2 = client.post("/api/generate_plan", json=payload, headers={"X-User-ID": user_id})
    assert resp2.status_code == 200
    plan2 = resp2.get_json()["plan"]
    weeks_order_2 = [(w["week"], [t["subtema"] for t in w["topics"]]) for w in plan2]

    assert weeks_order_1 == weeks_order_2

    # But the topic itself should now reflect live adaptive signals
    topic_in_plan2 = next(t for w in plan2 for t in w["topics"] if t["subtema"] == later_topic)
    assert "low_accuracy" in topic_in_plan2["priority_reasons"]


def test_planner_schedule_cleared_on_reset_and_regenerate(client, app):
    from api.db import get_db

    user_id = "user_reset_test"
    start = date.today()
    exam = (start + timedelta(weeks=20)).isoformat()
    payload = {"start_date": start.isoformat(), "exam_date": exam, "hours_per_week": 20}

    # Generate
    resp = client.post("/api/generate_plan", json=payload, headers={"X-User-ID": user_id})
    assert resp.status_code == 200

    with app.app_context():
        db = get_db()
        assert db.execute("SELECT COUNT(*) FROM planner_schedule WHERE user_id = ?", (user_id,)).fetchone()[0] > 0

    # Reset
    resp_reset = client.post("/api/planner/config/reset", headers={"X-User-ID": user_id})
    assert resp_reset.status_code == 200

    with app.app_context():
        db = get_db()
        assert db.execute("SELECT COUNT(*) FROM planner_schedule WHERE user_id = ?", (user_id,)).fetchone()[0] == 0

    # Force regenerate via flag
    resp_gen = client.post("/api/generate_plan", json={**payload, "regenerate": True}, headers={"X-User-ID": user_id})
    assert resp_gen.status_code == 200
    with app.app_context():
        db = get_db()
        assert db.execute("SELECT COUNT(*) FROM planner_schedule WHERE user_id = ?", (user_id,)).fetchone()[0] > 0


def test_planner_topics_endpoint_returns_subtema_and_week_composite(client):
    user_id = "user_topic_progress_test"
    headers = {"X-User-ID": user_id}

    # Mark topic completed
    resp = client.post("/api/planner/3/topic", json={"subtema": "Hipertensão", "completed": True}, headers=headers)
    assert resp.status_code == 200

    # Get topics
    resp_get = client.get("/api/planner/topics", headers=headers)
    assert resp_get.status_code == 200
    data = resp_get.get_json()
    assert data.get("3:Hipertensão") is True
    assert data.get("Hipertensão") is True


def test_invalid_start_date_format_returns_error():
    result = generate_annual_plan(
        rows=[],
        start_date_str="invalid-start-date",
        exam_date_str="2025-12-31",
        hours_per_week=20,
    )
    assert result == {"error": "Formato de data inválido."}


def test_invalid_exam_date_format_returns_error():
    result = generate_annual_plan(
        rows=[],
        start_date_str="2025-01-01",
        exam_date_str="2025-13-45",
        hours_per_week=20,
    )
    assert result == {"error": "Formato de data inválido."}


def test_invalid_date_formats_api_endpoint(client):
    resp = client.post(
        "/api/generate_plan",
        json={
            "start_date": "not-a-valid-date",
            "exam_date": "2025-12-31",
            "hours_per_week": 20,
        },
    )
    assert resp.status_code == 200
    assert resp.get_json() == {"error": "Formato de data inválido."}

    resp_exam = client.post(
        "/api/generate_plan",
        json={
            "start_date": "2025-01-01",
            "exam_date": "invalid-exam-date",
            "hours_per_week": 20,
        },
    )
    assert resp_exam.status_code == 200
    assert resp_exam.get_json() == {"error": "Formato de data inválido."}


def test_no_warning_when_all_topics_fit_or_weeks_sufficient():
    start = date(2026, 9, 7)
    exam = date(2027, 11, 15)  # 62 weeks away
    # With 12 hours/week, 62 * 12 = 744 hours, curriculum needs ~610 hours (50 weeks)
    res = generate_annual_plan([], start.isoformat(), exam.isoformat(), hours_per_week=12)
    assert res.get("warning") is None
    assert len(res["plan"]) > 0

    # Simulate frozen schedule rows
    schedule_rows = []
    for w in res["plan"]:
        for order, t in enumerate(w["topics"]):
            schedule_rows.append({"week": w["week"], "subtema": t["subtema"], "display_order": order})

    # Reloading with exam_date_str must also not yield a warning
    reloaded = build_plan_from_schedule(
        schedule_rows,
        start.isoformat(),
        hours_per_week=12,
        exam_date_str=exam.isoformat(),
    )
    assert reloaded is not None
    assert reloaded.get("warning") is None
    assert reloaded.get("total_available_hours") is None


def test_warning_when_insufficient_time_and_schedule_reloaded():
    start = date(2026, 9, 7)
    exam = date(2026, 11, 16)  # 10 weeks away
    # 10 weeks * 12h = 120h, curriculum needs ~610h -> genuine deficit
    res = generate_annual_plan([], start.isoformat(), exam.isoformat(), hours_per_week=12)
    assert res.get("warning") is not None
    assert "120 horas disponíveis" in res["warning"]
    assert res.get("total_available_hours") == 120
    assert res.get("total_required_hours") == 610

    # Build schedule rows for the 10 weeks that could be planned
    schedule_rows = []
    for w in res["plan"]:
        for order, t in enumerate(w["topics"]):
            schedule_rows.append({"week": w["week"], "subtema": t["subtema"], "display_order": order})

    reloaded = build_plan_from_schedule(
        schedule_rows,
        start.isoformat(),
        hours_per_week=12,
        exam_date_str=exam.isoformat(),
    )
    assert reloaded is not None
    assert reloaded.get("warning") is not None
    assert "120 horas disponíveis" in reloaded["warning"]
    assert reloaded.get("total_available_hours") == 120
    assert reloaded.get("total_required_hours") == 610


def test_generate_plan_api_no_warning_on_reload_when_time_sufficient(client):
    user_id = "user_sufficient_time_test"
    start = date(2026, 9, 7)
    exam = date(2027, 11, 15)
    payload = {
        "start_date": start.isoformat(),
        "exam_date": exam.isoformat(),
        "hours_per_week": 12,
    }

    # First call generates and persists
    resp1 = client.post("/api/generate_plan", json=payload, headers={"X-User-ID": user_id})
    assert resp1.status_code == 200
    data1 = resp1.get_json()
    assert data1.get("warning") is None

    # Second call uses frozen schedule in database
    resp2 = client.post("/api/generate_plan", json=payload, headers={"X-User-ID": user_id})
    assert resp2.status_code == 200
    data2 = resp2.get_json()
    assert data2.get("warning") is None



