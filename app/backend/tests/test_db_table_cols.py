import sqlite3
import pytest
from unittest.mock import MagicMock

from api.db import _table_cols, TursoConnection


def test_table_cols_sqlite_valid():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT, created_at TEXT)")
    cols = _table_cols(conn, "test_table")
    assert cols == ["id", "name", "created_at"]


def test_table_cols_turso_valid():
    mock_client = MagicMock()
    # Simulate Turso query result for "SELECT name FROM pragma_table_info(?)"
    mock_cursor = MagicMock()
    mock_cursor.description = [("name", None, None, None, None, None, None)]
    mock_cursor.fetchall.return_value = [("id",), ("title",), ("status",)]
    mock_client.execute.return_value = mock_cursor

    turso_conn = TursoConnection(client=mock_client)
    cols = _table_cols(turso_conn, "planner_config")

    assert cols == ["id", "title", "status"]
    mock_client.execute.assert_called_once_with(
        "SELECT name FROM pragma_table_info(?)", ["planner_config"]
    )


@pytest.mark.parametrize(
    "invalid_table",
    [
        "questions; DROP TABLE questions;--",
        "questions--",
        "table with spaces",
        "table'quote",
        'table"quote',
        "table`quote",
        "table-with-dash",
        "",
        123,
        None,
        ["questions"],
    ],
)
def test_table_cols_invalid_table_name_raises_value_error(invalid_table):
    conn = sqlite3.connect(":memory:")
    with pytest.raises(ValueError, match="Invalid table name"):
        _table_cols(conn, invalid_table)
