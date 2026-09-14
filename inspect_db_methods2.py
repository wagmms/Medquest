import tempfile
import libsql

with tempfile.NamedTemporaryFile(suffix='.db') as f:
    client = libsql.connect(f.name)
    print("execute_batch exists?", hasattr(client, 'execute_batch'))

    # Is it available on the rust sync connection somehow but hidden in python?
    try:
        client.execute_batch("SELECT 1; SELECT 2;")
    except Exception as e:
        print(e)
