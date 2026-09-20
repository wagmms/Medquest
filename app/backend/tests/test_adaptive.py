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
