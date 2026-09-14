import urllib.request, json
url = "https://raw.githubusercontent.com/tursodatabase/libsql-python/main/src/connection.rs"
try:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as response:
        content = response.read().decode('utf-8')
        for i, line in enumerate(content.split('\n')):
            if 'execute_batch' in line:
                print(f"L{i}: {line.strip()}")
except Exception as e:
    print(e)
