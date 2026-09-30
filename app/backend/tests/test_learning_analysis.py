from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from api.db import get_db
from api.services.learning_analysis import build_learning_analysis

NOW = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)


def attempt(db, qid, correct, stamp, user='1'):
    db.execute('INSERT INTO attempts (question_id, is_correct, answered_at, user_id) VALUES (?, ?, ?, ?)', (qid, correct, stamp, user))


def report(db, **kwargs):
    return build_learning_analysis(db, '1', now=NOW, days=14, **kwargs)


def test_first_exposure_precedes_window_and_repeats_do_not_inflate(app):
    with app.app_context():
        db = get_db()
        attempt(db, 1, 0, '2026-08-01T12:00:00Z')
        for hour in range(10):
            attempt(db, 1, 1, f'2026-09-29T{hour:02}:00:00Z')
        attempt(db, 2, 0, '2026-09-28T12:00:00Z')
        attempt(db, 2, 1, '2026-09-28T12:01:00Z')
        data = report(db)
        assert data['summary']['new_questions'] == {'correct': 0, 'total': 1, 'accuracy': 0}
        assert data['summary']['delayed_reviews'] == {'correct': 1, 'total': 1, 'accuracy': 1}
        assert data['summary']['corrected'] == 2
        assert data['summary']['pending_checks'] == 1
        assert data['summary']['retained_corrections'] == 1
        assert sum(w['new_questions']['total'] for w in data['weeks']) == 1
        assert sum(w['delayed_reviews']['total'] for w in data['weeks']) == 1


def test_retention_uses_previous_exposure_and_last_eligible_outcome(app):
    with app.app_context():
        db = get_db()
        attempt(db, 1, 0, '2026-09-20T12:00:00Z')
        attempt(db, 1, 1, '2026-09-20T12:01:00Z')
        assert report(db)['summary']['pending_checks'] == 1
        attempt(db, 1, 1, '2026-09-21T12:00:00Z')
        assert report(db)['summary']['delayed_reviews']['total'] == 0
        attempt(db, 1, 1, '2026-09-22T12:00:00Z')
        assert report(db)['summary']['retained_corrections'] == 1
        attempt(db, 1, 0, '2026-09-25T12:00:00Z')
        result = report(db)['summary']
        assert result['delayed_reviews'] == {'correct': 0, 'total': 1, 'accuracy': 0}
        assert result['retained_corrections'] == 0
        assert result['unresolved'] == result['recurring'] == 1
        attempt(db, 1, 1, '2026-09-25T12:01:00Z')
        assert report(db)['summary']['pending_checks'] == 1


def test_scope_isolation_and_real_study_queue(app, client):
    with app.app_context():
        db = get_db()
        attempt(db, 1, 0, '2026-09-25T12:00:00Z')
        attempt(db, 2, 0, '2026-09-25T12:00:00Z')
        attempt(db, 1, 1, '2026-09-26T12:00:00Z', 'another-user')
        db.commit()
        data = report(db, institution='USP-SP', area='Clínica Médica', subtema='Hipertensão Arterial Sistêmica')
        assert data['summary']['unresolved'] == 1
        assert len(data['topics']) == 1
        link = data['priorities'][0]['actions']['errors']
        qs = parse_qs(urlparse(link).query)
        assert qs['institution'] == ['USP-SP']
        assert qs['area'] == ['Clínica Médica']
        assert qs['subtema'] == ['Hipertensão Arterial Sistêmica']
        assert qs['status'] == ['wrong']
    response = client.get('/api/questions?' + urlparse(link).query)
    assert [q['id'] for q in response.get_json()] == [1]
    response = client.get('/api/stats/learning-analysis', headers={'X-Guest-ID': 'another-empty-user'})
    assert response.status_code == 200
    assert response.get_json()['summary']['answered'] == 0


def test_timezone_boundaries_and_future_rows(app):
    with app.app_context():
        db = get_db()
        attempt(db, 1, 0, '2026-09-17T02:59:59Z')
        attempt(db, 2, 1, '2026-09-17T00:00:00-03:00')
        attempt(db, 3, 1, '2026-10-01T12:00:00Z')
        data = report(db)
        assert data['scope']['start'] == '2026-09-17'
        assert data['scope']['previous_end'] == '2026-09-16'
        assert data['summary']['new_questions']['correct'] == 1
        assert data['summary']['new_questions']['total'] == 1
        assert data['summary']['previous_new_questions']['total'] == 1


def test_undated_history_is_not_a_new_first_attempt(app):
    with app.app_context():
        db = get_db()
        attempt(db, 1, 0, None)
        attempt(db, 1, 1, '2026-09-29T12:00:00Z')
        result = report(db)['summary']
        assert result['new_questions']['total'] == 0
        assert result['delayed_reviews']['total'] == 0
        assert result['pending_checks'] == 1


def test_risk_counts_only_items_below_threshold(app, client, monkeypatch):
    metric = lambda value, now=None: {'retrievability': float(value) if value else None}
    monkeypatch.setattr('api.services.learning_analysis.fsrs_metrics', metric)
    monkeypatch.setattr('api.stats.fsrs_metrics', metric)
    with app.app_context():
        db = get_db()
        db.execute("UPDATE questions SET area='Clínica Médica', subtema='Mesmo tema'")
        for qid in range(1, 4):
            db.execute('INSERT INTO spaced_repetition(question_id, fsrs_card, next_review_date, user_id) VALUES (?, ?, ?, ?)', (qid, '0.6' if qid == 1 else '0.95', '2026-09-29T12:00:00Z', '1'))
        db.commit()
        data = report(db)
        assert data['summary']['tracked'] == 3
        assert data['summary']['at_risk'] == 1
        assert data['summary']['due'] == 3
        assert data['topics'][0]['min_retrievability'] == .6
    assert client.get('/api/stats/at-risk').get_json()[0]['items_count'] == 1


def test_empty_and_unassessed_scopes_are_not_weaknesses(app):
    with app.app_context():
        db = get_db()
        data = report(db)
        assert data['summary']['new_questions']['accuracy'] is None
        assert data['summary']['tracked'] == 0
        assert all(t['reason'] == 'needs_assessment' for t in data['priorities'])
        assert all(t['follow_up'] == 'needs_assessment' for t in data['topics'])
        assert all(t['actions']['new'] for t in data['topics'])
        empty = report(db, institution='does-not-exist')
        assert empty['summary']['available'] == 0
        assert empty['priorities'] == []


def test_same_topic_in_different_areas_stays_separate(app):
    with app.app_context():
        db = get_db()
        db.execute("UPDATE questions SET subtema='Compartilhado'")
        data = report(db)
        assert len(data['topics']) == 2
        assert {t['area'] for t in data['topics']} == {'Clínica Médica', 'Pediatria'}


def test_goal_respects_time_capacity(app, client):
    with app.app_context():
        db = get_db()
        db.execute("INSERT OR REPLACE INTO planner_config(user_id, hours_per_day, questions_per_day) VALUES ('1', 1, 200)")
        db.commit()
        assert report(db)['goal']['questions'] <= 20
    assert client.get('/api/stats/learning-profile').get_json()['goal']['questions_today'] <= 20


def test_readiness_unique_first_answers_and_scoped_actions(app, client):
    with app.app_context():
        db = get_db()
        attempt(db, 1, 0, '2026-09-20T12:00:00Z')
        for _ in range(30):
            attempt(db, 1, 1, '2026-09-21T12:00:00Z')
        db.commit()
    data = client.get('/api/stats/exam-readiness?institution=USP-SP').get_json()
    area = next(a for a in data['areas'] if a['area'] == 'Clínica Médica')
    assert area['attempts'] == 1
    assert area['correct'] == 0
    assert data['evidence_status'] == 'insufficient'
    assert all('institution=USP-SP' in a['action'] for a in data['areas'])
    assert all('institution=USP-SP' in f['action_url'] for f in data['key_factors'])


@pytest.mark.parametrize('query', ['days=0', 'days=hello', 'days=365', 'tz_offset=9999', 'tz_offset=nan'])
def test_invalid_filters(client, query):
    assert client.get('/api/stats/learning-analysis?' + query).status_code == 400


def test_same_timestamp_immediate_retry_does_not_replace_delayed_failure(app):
    with app.app_context():
        db = get_db()
        attempt(db, 1, 1, '2026-09-20T12:00:00Z')
        attempt(db, 1, 0, '2026-09-22T12:00:00Z')
        attempt(db, 1, 1, '2026-09-22T12:00:00Z')
        data = report(db)
        assert data['summary']['delayed_reviews'] == {'correct': 0, 'total': 1, 'accuracy': 0}
        assert data['summary']['pending_checks'] == 1


def test_older_offline_upload_does_not_become_first_exposure(app):
    with app.app_context():
        db = get_db()
        attempt(db, 1, 1, '2026-09-29T12:00:00Z')
        attempt(db, 1, 0, '2026-08-20T12:00:00Z')
        assert report(db)['summary']['new_questions']['total'] == 0


def test_due_review_action_uses_scoped_queue(app, client):
    with app.app_context():
        db = get_db()
        db.execute("INSERT INTO spaced_repetition(question_id, next_review_date, user_id) VALUES (1, '2020-01-01T00:00:00Z', '1')")
        db.execute("INSERT INTO spaced_repetition(question_id, next_review_date, user_id) VALUES (2, '2020-01-01T00:00:00Z', '1')")
        db.commit()
        data = report(db, institution='USP-SP')
        assert data['summary']['due'] == 1
        link = data['topics'][0]['actions']['reviews']
    response = client.get('/api/questions?' + urlparse(link).query)
    assert [q['id'] for q in response.get_json()] == [1]
