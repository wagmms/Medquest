import tempfile
import libsql

with tempfile.NamedTemporaryFile(suffix='.db') as f:
    conn = libsql.connect(f.name)
    # Testing whether `libsql.connect` returns an object that supports ANY batch command under a different name
    print([m for m in dir(conn) if 'exec' in m.lower()])
