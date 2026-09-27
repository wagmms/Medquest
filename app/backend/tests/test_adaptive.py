import json

from api.adaptive import fsrs_metrics, topic_priority
from api.srs import review


def test_fsrs_metrics_are_real_and_corrupt_state_is_safe():
    card_json, _ = review(None, True, "duvida")
    metrics = fsrs_metrics(card_json)
    assert 0 <= metrics["retrievability"] <= 1
    assert metrics["stability"] > 0
    assert fsrs_metrics("not-json")["retrievability"] is None


def test_topic_priority_uses_evidence_memory_and_coverage():
    weak, confidence = topic_priority(10, 2, retrievability=0.5, coverage=0.1)
    strong, _ = topic_priority(10, 9, retrievability=0.95, coverage=0.8)
    assert confidence > 0.8
    assert weak > strong


def test_learning_profile_exposes_goal_and_transparent_method(client):
    response = client.get("/api/stats/learning-profile")
    assert response.status_code == 200
    body = response.get_json()
    assert body["goal"]["configured_daily_questions"] == 30
    assert body["method"]["deterministic"] is True
    assert body["topics"]
    assert "priority_score" in body["topics"][0]


def test_adaptive_queue_is_deterministic_and_prioritizes_recent_error(client):
    attempt = client.post(
        "/api/questions/1/attempt",
        json={"selected_letter": "A", "confidence": "certeza", "time_spent_ms": 1000},
    )
    assert attempt.status_code == 200
    first = client.get("/api/questions?mode=adaptive&limit=2").get_json()
    second = client.get("/api/questions?mode=adaptive&limit=2").get_json()
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first[0]["id"] == 1
    assert "latest_attempt_wrong" in first[0]["adaptive_reasons"]


def test_learning_profile_filters_exact_topic_and_counts_distinct_answers(client):
    for _ in range(2):
        response = client.post('/api/questions/1/attempt', json={
            'selected_letter': 'B', 'confidence': 'certeza', 'time_spent_ms': 1000,
        })
        assert response.status_code == 200
    response = client.get('/api/stats/learning-profile', query_string={
        'subtema': 'Hipertensão Arterial Sistêmica',
    })
    topics = response.get_json()['topics']
    assert len(topics) == 1
    assert topics[0]['topic'] == 'Hipertensão Arterial Sistêmica'
    assert topics[0]['available'] == 1
    assert topics[0]['answered'] == 1
    assert topics[0]['attempts'] == 2
    other = client.get('/api/stats/learning-profile', query_string={
        'subtema': 'Hipertensão Arterial Sistêmica',
    }, headers={'X-User-ID': 'other-user'}).get_json()['topics'][0]
    assert other['answered'] == 0
    assert other['attempts'] == 0
    assert other['due_count'] == 0


def test_learning_profile_unknown_topic_does_not_return_other_topics(client):
    response = client.get('/api/stats/learning-profile', query_string={'subtema': 'unknown'})
    assert response.status_code == 200
    assert response.get_json()['topics'] == []


def test_learning_profile_preserves_topics_with_same_legacy_topic(client):
    body = client.get('/api/stats/learning-profile').get_json()
    assert {topic['topic'] for topic in body['topics']} == {
        'Hipertensão Arterial Sistêmica', 'Imunização (PNI)', 'Vitaminas',
    }
    assert all(topic['available'] == 1 for topic in body['topics'])


def test_twin_question_selection_and_dual_fsrs_update(client, app):
    from api.db import get_db
    with app.app_context():
        db = get_db()
        # Seed an unseen twin question Q4 with same subtema as Q1 (UNICAMP vs USP-SP)
        db.execute("""
            INSERT INTO questions(id, area, subtema, stem, correct_letter, missing_alts, year, institution_code, institution_label)
            VALUES (4, 'Clínica Médica', 'Hipertensão Arterial Sistêmica', 'Q4 HAS Twin?', 'A', 0, 2024, 'UNICAMP', 'UNICAMP')
        """)
        db.execute("INSERT INTO alternatives(question_id, letter, text, is_correct) VALUES (4, 'A', 'correct alt', 1)")
        db.commit()

    # 1. Answer Q1 correctly with certeza
    ans = client.post('/api/questions/1/attempt', json={
        'selected_letter': 'B', 'confidence': 'certeza', 'time_spent_ms': 1200,
    })
    assert ans.status_code == 200
    assert ans.get_json()['is_correct'] is True

    # 2. Make Q1 due by setting next_review_date in the past
    with app.app_context():
        db = get_db()
        db.execute("UPDATE spaced_repetition SET next_review_date = '2020-01-01T00:00:00+00:00' WHERE question_id = 1")
        db.commit()

    # 3. Request adaptive queue in balanced mode
    queue = client.get('/api/questions?mode=adaptive&adaptive_focus=balanced&limit=5').get_json()
    assert len(queue) > 0

    # The twin question (Q4) should be ranked at the top acting as twin for Q1
    twin_item = next((q for q in queue if q['id'] == 4), None)
    assert twin_item is not None
    assert twin_item['is_twin'] is True
    assert twin_item['twin_for_question_id'] == 1
    assert twin_item['twin_origin_institution'] == 'USP-SP'
    assert 'twin_concept_review' in twin_item['adaptive_reasons']
    # Q1 was replaced by twin in this session
    assert not any(q['id'] == 1 for q in queue)

    # 4. Answer the twin question Q4 with twin_for_question_id=1
    twin_ans = client.post('/api/questions/4/attempt', json={
        'selected_letter': 'A',
        'confidence': 'certeza',
        'time_spent_ms': 1500,
        'twin_for_question_id': 1,
    })
    assert twin_ans.status_code == 200
    assert twin_ans.get_json()['is_correct'] is True

    # 5. Verify that Q1's FSRS record in spaced_repetition has been pushed into the future
    with app.app_context():
        db = get_db()
        sr1 = db.execute("SELECT next_review_date FROM spaced_repetition WHERE question_id = 1").fetchone()
        assert sr1 is not None
        # It should no longer be in the past (2020)
        assert sr1['next_review_date'] > '2025-01-01'


def test_adaptive_focus_coverage_vs_retention(client, app):
    from api.db import get_db
    with app.app_context():
        db = get_db()
        # Seed an unseen question
        db.execute("""
            INSERT INTO questions(id, area, subtema, stem, correct_letter, missing_alts, year, institution_code, institution_label)
            VALUES (10, 'Cirurgia', 'Apendicite Aguda', 'Q10 Unseen?', 'A', 0, 2025, 'SUS-SP', 'SUS')
        """)
        db.execute("INSERT INTO alternatives(question_id, letter, text, is_correct) VALUES (10, 'A', 'alt', 1)")
        # Insert a due review for Q2
        db.execute("INSERT OR REPLACE INTO spaced_repetition(question_id, next_review_date, user_id) VALUES (2, '2020-01-01T00:00:00+00:00', '1')")
        db.commit()

    # In coverage mode, coverage gap has heavy weight (+80)
    cov_queue = client.get('/api/questions?mode=adaptive&adaptive_focus=coverage&limit=10').get_json()
    assert any(q['id'] == 10 for q in cov_queue)
    q10_cov = next(q for q in cov_queue if q['id'] == 10)
    assert 'coverage_gap' in q10_cov['adaptive_reasons']

    # In retention mode, review_due has much higher weight (+110)
    ret_queue = client.get('/api/questions?mode=adaptive&adaptive_focus=retention&limit=10').get_json()
    assert len(ret_queue) > 0
    # First item in retention queue should have review_due or twin_concept_review
    reasons = ret_queue[0]['adaptive_reasons']
    assert any(r in reasons for r in ('review_due', 'twin_concept_review', 'latest_attempt_wrong'))
