import tempfile
import libsql

# Let's inspect again if we can just do: client.execute_batch
# Oh! Wait, did I look for `executescript`?
# Maybe Turso's actual batch method in python is on the cursor?
with tempfile.NamedTemporaryFile(suffix='.db') as f:
    conn = libsql.connect(f.name)
    print(hasattr(conn.cursor(), 'execute_batch'))
