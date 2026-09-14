import tempfile
import libsql
from app.backend.api.db import TursoConnection

def run_test():
    with tempfile.NamedTemporaryFile(suffix='.db') as f:
        client = libsql.connect(f.name)
        turso_conn = TursoConnection(client, persistent=False)
        try:
            print("Trying turso_conn.client.batch...")
            # Wait, TursoConnection's client doesn't have batch, but wait, DOES the turso client library that they import have one?
            # They import libsql, not libsql_client.
            turso_conn.client.batch([])
        except Exception as e:
            print("Failed:", e)
run_test()
