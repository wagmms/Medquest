"""Testes de exclusão de questões restrita ao administrador moraes.wagg@gmail.com."""
import sqlite3
from api.db import get_db


def test_delete_question_unauthorized_for_other_users(client):
    r = client.delete("/api/questions/1", headers={"X-User-Email": "intruder@example.com"})
    assert r.status_code == 403
    data = r.get_json()
    assert "Forbidden" in data["error"]


def test_delete_question_not_found(client):
    r = client.delete("/api/questions/999999", headers={"X-User-Email": "moraes.wagg@gmail.com"})
    assert r.status_code == 404
    data = r.get_json()
    assert data["error"] == "Questão não encontrada"


def test_delete_question_cascading_success(client, app):
    with app.app_context():
        db = get_db()
        # Seed related data for question 1
        db.execute("INSERT OR REPLACE INTO attempts(id, question_id, selected_letter, is_correct, user_id) VALUES (10, 1, 'B', 1, 1)")
        db.execute("CREATE TABLE IF NOT EXISTS favorites (question_id INTEGER, user_id TEXT DEFAULT '1', PRIMARY KEY (question_id, user_id))")
        db.execute("INSERT OR REPLACE INTO favorites(question_id, user_id) VALUES (1, '1')")
        db.execute("""CREATE TABLE IF NOT EXISTS flashcards (
            id INTEGER PRIMARY KEY AUTOINCREMENT, question_id INTEGER, front TEXT, back TEXT,
            created_at TEXT, next_review_date TEXT, fsrs_card TEXT, user_id TEXT DEFAULT '1',
            source_context TEXT, is_ai_generated INTEGER DEFAULT 0, report_status TEXT,
            deck_name TEXT DEFAULT 'Geral', tags TEXT, source_type TEXT DEFAULT 'medquest', anki_nid INTEGER
        )""")
        db.execute("INSERT INTO flashcards(question_id, front, back, created_at, user_id) VALUES (1, 'Front text', 'Back text', '2026-01-01', '1')")
        card_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.commit()

    # Perform deletion as moraes.wagg@gmail.com
    r = client.delete("/api/questions/1", headers={"X-User-Email": "moraes.wagg@gmail.com"})
    assert r.status_code == 200
    res = r.get_json()
    assert res["success"] is True
    assert res["id"] == 1

    # Verify cascading cleanup in database
    with app.app_context():
        db = get_db()
        assert db.execute("SELECT id FROM questions WHERE id = 1").fetchone() is None
        assert db.execute("SELECT id FROM alternatives WHERE question_id = 1").fetchone() is None
        assert db.execute("SELECT question_id FROM explanations WHERE question_id = 1").fetchone() is None
        assert db.execute("SELECT id FROM attempts WHERE question_id = 1").fetchone() is None
        assert db.execute("SELECT question_id FROM favorites WHERE question_id = 1").fetchone() is None
        # Flashcard must be preserved with unlinked question_id (NULL)
        card = db.execute("SELECT id, question_id FROM flashcards WHERE id = ?", (card_id,)).fetchone()
        assert card is not None
        assert card[1] is None
