"""Durability and full-download regressions from the September audit."""
import uuid

from api.db import get_db


def test_flashcard_save_and_review_are_idempotent(client, app):
    headers = {"X-Idempotency-Key": str(uuid.uuid4())}
    payload = {"question_id": 1, "front": "Question", "back": "Answer", "context": "Test"}
    first = client.post('/api/flashcards/save', json=payload, headers=headers)
    assert first.status_code == 200
    assert client.post('/api/flashcards/save', json=payload, headers=headers).json == first.json
    card_id = first.json['id']
    headers = {"X-Idempotency-Key": str(uuid.uuid4())}
    first_review = client.post(f'/api/flashcards/{card_id}/review', json={"confidence": "certeza"}, headers=headers)
    assert first_review.status_code == 200
    with app.app_context():
        state = get_db().execute('SELECT fsrs_card FROM flashcards WHERE id = ?', (card_id,)).fetchone()[0]
    second_review = client.post(f'/api/flashcards/{card_id}/review', json={"confidence": "certeza"}, headers=headers)
    assert second_review.json == first_review.json
    with app.app_context():
        assert get_db().execute('SELECT fsrs_card FROM flashcards WHERE id = ?', (card_id,)).fetchone()[0] == state


def test_flashcard_effects_rollback_if_idempotency_completion_fails(client, app, monkeypatch):
    from api import flashcards
    monkeypatch.setattr(flashcards, 'complete_idempotency', lambda *args: (_ for _ in ()).throw(RuntimeError('lost lease')))
    response = client.post('/api/flashcards/save', json={"question_id": 1, "front": "Test"},
                           headers={"X-Idempotency-Key": str(uuid.uuid4())})
    assert response.status_code == 500
    with app.app_context():
        assert get_db().execute('SELECT count(*) FROM flashcards').fetchone()[0] == 0


def test_flashcard_download_cursor_returns_all_cards_and_is_owner_scoped(client, app):
    with app.app_context():
        db = get_db()
        db.executemany("INSERT INTO flashcards(question_id, front, created_at, next_review_date, user_id) VALUES (1, 'Test', '2026-01-01', '2026-01-01', ?)", [('1',)] * 125 + [('other',)])
        db.commit()
    first = client.get('/api/flashcards/review?all=true&limit=100').json
    assert len(first) == 100
    second = client.get(f'/api/flashcards/review?all=true&limit=100&after_id={first[-1]["id"]}').json
    assert len(second) == 25
    assert len({c['id'] for c in first + second}) == 125


def test_delete_default_deck_removes_legacy_null_names_but_not_other_owners(client, app):
    with app.app_context():
        db = get_db()
        db.executemany("INSERT INTO flashcards(question_id, front, created_at, user_id, deck_name) VALUES (1, 'Test', '2026-01-01', ?, ?)", [('1', None), ('1', ''), ('other', None)])
        db.commit()
    response = client.delete('/api/flashcards/deck', json={'deck_name': 'Geral'})
    assert response.status_code == 200
    assert response.json['deleted_count'] == 2
    with app.app_context():
        assert get_db().execute('SELECT user_id FROM flashcards').fetchone()[0] == 'other'


def test_cleanup_command_is_registered_and_validates_retention(app):
    runner = app.test_cli_runner()
    assert runner.invoke(args=['cleanup-idempotency', '--max-age-days', '0']).exit_code != 0
    assert runner.invoke(args=['cleanup-idempotency']).exit_code == 0
