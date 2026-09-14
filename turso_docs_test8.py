import tempfile
import libsql

with tempfile.NamedTemporaryFile(suffix='.db') as f:
    conn = libsql.connect(f.name)
    try:
        conn.batch(["SELECT 1"])
        print("batch works")
    except Exception as e:
        print(e)
