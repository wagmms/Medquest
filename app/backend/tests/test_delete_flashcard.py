"""Testes de exclusão de flashcards restrita ao administrador moraes.wagg@gmail.com."""
from api.db import get_db


def test_delete_flashcard_unauthorized_for_other_users(client, app):
    with app.app_context():
        db = get_db()
        db.execute("""CREATE TABLE IF NOT EXISTS flashcards (
            id INTEGER PRIMARY KEY AUTOINCREMENT, question_id INTEGER, front TEXT, back TEXT,
            created_at TEXT, next_review_date TEXT, fsrs_card TEXT, user_id TEXT DEFAULT '1',
            source_context TEXT, is_ai_generated INTEGER DEFAULT 0, report_status TEXT,
            deck_name TEXT DEFAULT 'Geral', tags TEXT, source_type TEXT DEFAULT 'medquest', anki_nid INTEGER
        )""")
        db.execute("INSERT INTO flashcards(front, back, created_at, user_id) VALUES ('F1', 'B1', '2026-01-01', '1')")
        card_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.commit()

    r = client.delete(f"/api/flashcards/{card_id}", headers={"X-User-Email": "intruder@example.com"})
    assert r.status_code == 403
    data = r.get_json()
    assert "Forbidden" in data["error"]


def test_delete_flashcard_not_found(client):
    r = client.delete("/api/flashcards/999999", headers={"X-User-Email": "moraes.wagg@gmail.com"})
    assert r.status_code == 404
    data = r.get_json()
    assert data["error"] == "Flashcard não encontrado"


def test_delete_flashcard_success(client, app):
    with app.app_context():
        db = get_db()
        db.execute("""CREATE TABLE IF NOT EXISTS flashcards (
            id INTEGER PRIMARY KEY AUTOINCREMENT, question_id INTEGER, front TEXT, back TEXT,
            created_at TEXT, next_review_date TEXT, fsrs_card TEXT, user_id TEXT DEFAULT '1',
            source_context TEXT, is_ai_generated INTEGER DEFAULT 0, report_status TEXT,
            deck_name TEXT DEFAULT 'Geral', tags TEXT, source_type TEXT DEFAULT 'medquest', anki_nid INTEGER
        )""")
        db.execute("INSERT INTO flashcards(front, back, created_at, user_id) VALUES ('Card to delete', 'Back text', '2026-01-01', '1')")
        card_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.commit()

    r = client.delete(f"/api/flashcards/{card_id}", headers={"X-User-Email": "moraes.wagg@gmail.com"})
    assert r.status_code == 200
    res = r.get_json()
    assert res["success"] is True
    assert res["id"] == card_id

    with app.app_context():
        db = get_db()
        assert db.execute("SELECT id FROM flashcards WHERE id = ?", (card_id,)).fetchone() is None
