import tempfile
import libsql_experimental

with tempfile.NamedTemporaryFile(suffix='.db') as f:
    conn = libsql_experimental.connect(f.name)
    try:
        print(hasattr(conn, 'batch'))
        print([m for m in dir(conn) if 'batch' in m.lower()])
    except Exception as e:
        print(e)
