import urllib.request
req = urllib.request.Request("https://raw.githubusercontent.com/tursodatabase/libsql-python/main/src/connection.rs")
try:
    with urllib.request.urlopen(req) as response:
        content = response.read().decode('utf-8')
        for i, line in enumerate(content.split('\n')):
            if 'execute_batch' in line.lower() or 'batch' in line.lower() or 'executemany' in line.lower():
                print(f"L{i}: {line.strip()}")
except Exception as e:
    pass
