"""Theme progress and flashcard review must remain scoped to theme and owner."""
import pytest

THEME = 'Hipertensão Arterial Sistêmica e Crises Hipertensivas'
OTHER = 'Calendário Vacinal do PNI e Imunizações Especiais'


@pytest.fixture(autouse=True)
def canonical_seed(app):
    from api.db import get_db, db_transaction
    with app.app_context():
        db = get_db()
        with db_transaction(db):
            db.execute('UPDATE questions SET subtema=? WHERE id=1', (THEME,))
            db.execute('UPDATE questions SET subtema=? WHERE id=2', (OTHER,))


def test_theme_progress_persists_without_changing_learning_metrics(client):
    url = '/api/themes/progress'
    before = client.get('/api/stats/learning-profile', query_string={'subtema': THEME}).get_json()['topics']
    initial = client.get(url, query_string={'subtema': THEME}).get_json()
    assert initial['theory_completed'] is False
    assert initial['study_path'] == 'essential'
    saved = client.put(url, query_string={'subtema': THEME}, json={
        'theory_completed': True, 'study_path': 'complete',
    })
    assert saved.status_code == 200
    reloaded = client.get(url, query_string={'subtema': THEME}).get_json()
    assert reloaded['theory_completed'] is True
    assert reloaded['study_path'] == 'complete'
    assert reloaded['updated_at']
    other = client.get(url, query_string={'subtema': THEME}, headers={'X-User-ID': 'another'}).get_json()
    assert other['theory_completed'] is False
    assert other['updated_at'] is None
    assert client.get(url, query_string={'subtema': OTHER}).get_json()['theory_completed'] is False
    after = client.get('/api/stats/learning-profile', query_string={'subtema': THEME}).get_json()['topics']
    assert before == after
    client.put(url, query_string={'subtema': THEME}, json={'theory_completed': False, 'study_path': 'essential'})
    assert client.get(url, query_string={'subtema': THEME}).get_json()['theory_completed'] is False


def test_theme_validation_and_versioned_route(client):
    assert client.get('/api/themes/progress?subtema=unknown').status_code == 404
    assert client.get('/api/v1/themes/progress', query_string={'subtema': THEME}).status_code == 200
    for payload in [None, [], {}, {'theory_completed': 'false', 'study_path': 'complete'},
                    {'theory_completed': True, 'study_path': 'invalid'},
                    {'theory_completed': True, 'study_path': 'complete', 'user_id': 'another'}]:
        response = client.put('/api/themes/progress', query_string={'subtema': THEME}, json=payload)
        assert response.status_code == 400


def test_flashcard_theme_filter_scopes_due_upcoming_all_and_counts(client):
    first = client.post('/api/flashcards/save', json={'question_id': 1, 'front': 'Front 1', 'back': 'Back 1'})
    second = client.post('/api/flashcards/save', json={'question_id': 2, 'front': 'Front 2', 'back': 'Back 2'})
    assert first.status_code in (200, 201)
    assert second.status_code in (200, 201)
    fid = first.get_json()['id']
    query = {'subtema': THEME}
    due = client.get('/api/flashcards/review', query_string=query).get_json()
    assert [card['id'] for card in due] == [fid]
    state = client.get('/api/themes/progress', query_string=query).get_json()
    assert state['flashcards_total'] == state['flashcards_due'] == 1
    assert client.get('/api/flashcards/review', query_string=query, headers={'X-User-ID': 'another'}).get_json() == []
    client.post(f'/api/flashcards/{fid}/review', json={'confidence': 'certeza'})
    assert client.get('/api/flashcards/review', query_string=query).get_json() == []
    upcoming = client.get('/api/flashcards/review', query_string={**query, 'scope': 'upcoming'}).get_json()
    assert [card['id'] for card in upcoming] == [fid]
    all_cards = client.get('/api/flashcards/review', query_string={**query, 'all': 'true'}).get_json()
    assert [card['id'] for card in all_cards] == [fid]
    assert client.get('/api/flashcards/review', query_string={**query, 'all': 'true', 'deck': 'nonexistent'}).get_json() == []
    assert client.get('/api/themes/progress', query_string=query).get_json()['flashcards_due'] == 0
    client.post(f'/api/flashcards/{fid}/report', json={'reason': 'Conteúdo incorreto'})
    assert client.get('/api/themes/progress', query_string=query).get_json()['flashcards_total'] == 0


def test_reset_clears_theme_progress(client):
    client.put('/api/themes/progress', query_string={'subtema': THEME}, json={'theory_completed': True, 'study_path': 'complete'})
    response = client.delete('/api/stats/reset')
    assert response.status_code == 200
    assert client.get('/api/themes/progress', query_string={'subtema': THEME}).get_json()['theory_completed'] is False
