"""Batch loading must scale with questions, not attempt history."""
import pytest

from api.db import get_db
from api.questions import _fetch_batch_data


@pytest.mark.parametrize("use_batch", [False, True])
def test_latest_attempt_is_bounded_and_user_scoped(app, use_batch):
    with app.app_context():
        db = get_db()
        db.executemany(
            "INSERT INTO attempts(question_id, selected_letter, is_correct, user_id) VALUES (1, 'A', 0, 'alice')",
            [()] * 200,
        )
        db.execute("INSERT INTO attempts(question_id, selected_letter, is_correct, user_id) VALUES (1, 'B', 1, 'alice')")
        db.execute("INSERT INTO attempts(question_id, selected_letter, is_correct, user_id) VALUES (1, 'A', 0, 'bob')")
        db.commit()

        row_counts = []

        class Cursor:
            def __init__(self, cursor):
                self.cursor = cursor

            def fetchall(self):
                rows = self.cursor.fetchall()
                row_counts.append(len(rows))
                return rows

        class Connection:
            def execute(self, sql, params):
                return Cursor(db.execute(sql, params))

        connection = Connection()
        if use_batch:
            connection.batch = lambda queries: [connection.execute(sql, params) for sql, params in queries]

        questions, _, _, attempts, wrong, _ = _fetch_batch_data(connection, [1, 2], "alice")
        assert set(questions) == {1, 2}
        assert attempts == {1: {"selected_letter": "B", "is_correct": True}}
        assert wrong == {1: 200}
        assert row_counts[3] == 1
