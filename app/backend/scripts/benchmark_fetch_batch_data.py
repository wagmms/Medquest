import time
import sqlite3
import os
import json
import sys

# Ensure backend module can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.questions import _fetch_batch_data

class CountingSqliteConnection:
    """Wrapper around sqlite3.Connection that tracks execute vs batch calls and simulates latency."""
    def __init__(self, conn, simulated_latency_ms=0):
        self.conn = conn
        self.execute_count = 0
        self.batch_count = 0
        self.simulated_latency_ms = simulated_latency_ms

    def execute(self, sql, parameters=()):
        self.execute_count += 1
        if self.simulated_latency_ms > 0:
            time.sleep(self.simulated_latency_ms / 1000.0)
        return self.conn.execute(sql, parameters)

    def fetchall(self):
        return self.conn.fetchall()

    def batch(self, queries):
        self.batch_count += 1
        if self.simulated_latency_ms > 0:
            time.sleep(self.simulated_latency_ms / 1000.0)
        results = []
        for sql, params in queries:
            results.append(self.conn.execute(sql, params))
        return results

def setup_benchmark_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE questions(
            id INTEGER PRIMARY KEY, source_file TEXT, source_number INTEGER, year INTEGER,
            institution_code TEXT, institution_label TEXT, topic TEXT, stem TEXT,
            correct_letter TEXT, missing_alts INTEGER DEFAULT 0, area TEXT, subtema TEXT,
            editorial_status TEXT, status TEXT DEFAULT 'active'
        )
    """)
    conn.execute("""
        CREATE TABLE alternatives(
            id INTEGER PRIMARY KEY, question_id INTEGER, letter TEXT, text TEXT, is_correct INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE question_images(
            id INTEGER PRIMARY KEY, question_id INTEGER, file_path TEXT, order_index INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE attempts(
            id INTEGER PRIMARY KEY, question_id INTEGER, selected_letter TEXT,
            is_correct INTEGER, answered_at TEXT, confidence TEXT, user_id TEXT DEFAULT '1', time_spent_ms INTEGER
        )
    """)
    conn.execute("CREATE TABLE favorites (question_id INTEGER, user_id TEXT DEFAULT '1', PRIMARY KEY (question_id, user_id))")

    for i in range(1, 1001):
        conn.execute("INSERT INTO questions (id, stem, correct_letter) VALUES (?, ?, 'A')", (i, f"Stem {i}"))
        for letter in ['A', 'B', 'C', 'D', 'E']:
            conn.execute("INSERT INTO alternatives (question_id, letter, text, is_correct) VALUES (?, ?, ?, ?)",
                         (i, letter, f"Option {letter}", 1 if letter == 'A' else 0))
        conn.execute("INSERT INTO question_images (question_id, file_path, order_index) VALUES (?, ?, 0)", (i, f"/img/{i}.png"))
        conn.execute("INSERT INTO attempts (question_id, selected_letter, is_correct, user_id) VALUES (?, 'A', 1, 'user1')", (i,))
        if i % 2 == 0:
            conn.execute("INSERT INTO favorites (question_id, user_id) VALUES (?, 'user1')", (i,))

    conn.commit()
    return conn

def run_benchmark():
    conn = setup_benchmark_db()

    ids_100 = list(range(1, 101))
    ids_600 = list(range(1, 601))

    # Benchmark local DB without latency
    wrapper_local = CountingSqliteConnection(conn, simulated_latency_ms=0)
    iterations = 50

    wrapper_local.execute_count = 0
    wrapper_local.batch_count = 0
    t0 = time.perf_counter()
    for _ in range(iterations):
        _fetch_batch_data(wrapper_local, ids_100, "user1")
    t1 = time.perf_counter()
    local_100_ms = ((t1 - t0) / iterations) * 1000

    wrapper_local.execute_count = 0
    wrapper_local.batch_count = 0
    t0 = time.perf_counter()
    for _ in range(iterations):
        _fetch_batch_data(wrapper_local, ids_600, "user1")
    t1 = time.perf_counter()
    local_600_ms = ((t1 - t0) / iterations) * 1000

    # Benchmark with 2ms simulated latency (like Turso/remote DB)
    wrapper_remote = CountingSqliteConnection(conn, simulated_latency_ms=2)
    wrapper_remote.execute_count = 0
    wrapper_remote.batch_count = 0
    t0 = time.perf_counter()
    for _ in range(5):
        _fetch_batch_data(wrapper_remote, ids_600, "user1")
    t1 = time.perf_counter()
    remote_600_ms = ((t1 - t0) / 5) * 1000
    exec_600 = wrapper_remote.execute_count / 5
    batch_600 = wrapper_remote.batch_count / 5

    print(json.dumps({
        "local_100_ids_ms": round(local_100_ms, 3),
        "local_600_ids_ms": round(local_600_ms, 3),
        "remote_600_ids_ms": round(remote_600_ms, 3),
        "remote_exec_calls": exec_600,
        "remote_batch_calls": batch_600,
    }, indent=2))

if __name__ == "__main__":
    run_benchmark()
