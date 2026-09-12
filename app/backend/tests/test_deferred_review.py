from datetime import datetime, timedelta, timezone

import pytest

from api.db import get_db


@pytest.mark.parametrize("batch", [False, True])
@pytest.mark.parametrize("days_until_due", [-1, 7])
def test_unrated_answer_defers_due_review_without_advancing_fsrs(client, app, batch, days_until_due):
    client.post("/api/questions/1/attempt", json={"selected_letter": "B", "confidence": "certeza"})
    original_due = (datetime.now(timezone.utc) + timedelta(days=days_until_due)).isoformat()
    with app.app_context():
        db = get_db()
        db.execute("UPDATE spaced_repetition SET next_review_date = ?", (original_due,))
        db.commit()
        original_card = db.execute("SELECT fsrs_card FROM spaced_repetition").fetchone()["fsrs_card"]

    before = datetime.now(timezone.utc)
    payload = {"selected_letter": "B", "confidence": "defer"}
    if batch:
        response = client.post("/api/attempt/batch", json={"attempts": [{"question_id": 1, **payload}]})
        result = response.get_json()["results"][0]
    else:
        response = client.post("/api/questions/1/attempt", json=payload)
        result = response.get_json()
    assert response.status_code == 200
    assert result["next_review_date"] is None  # Still allow an explicit rating in the UI.
    assert client.get("/api/questions?status=srs_due").get_json() == []
    with app.app_context():
        row = get_db().execute("SELECT fsrs_card, next_review_date FROM spaced_repetition").fetchone()
        assert row["fsrs_card"] == original_card
        if days_until_due > 1:
            assert row["next_review_date"] == original_due
        else:
            assert datetime.fromisoformat(row["next_review_date"]) >= before + timedelta(days=1)

    rated = client.post("/api/questions/1/review", json={"confidence": "duvida"})
    assert rated.status_code == 200
    assert rated.get_json()["next_review_date"]
    with app.app_context():
        assert get_db().execute("SELECT fsrs_card FROM spaced_repetition").fetchone()["fsrs_card"] != original_card


@pytest.mark.parametrize("batch", [False, True])
def test_unrated_new_question_does_not_create_fsrs_card(client, app, batch):
    payload = {"selected_letter": "B", "confidence": "defer"}
    if batch:
        response = client.post("/api/attempt/batch", json={"attempts": [{"question_id": 1, **payload}]})
    else:
        response = client.post("/api/questions/1/attempt", json=payload)
    assert response.status_code == 200
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) AS n FROM spaced_repetition").fetchone()["n"] == 0
        assert get_db().execute("SELECT COUNT(*) AS n FROM attempts").fetchone()["n"] == 1
