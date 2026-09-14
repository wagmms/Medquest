import urllib.request
req = urllib.request.Request("https://raw.githubusercontent.com/tursodatabase/libsql-python/main/src/lib.rs")
try:
    with urllib.request.urlopen(req) as response:
        content = response.read().decode('utf-8')
        print("Lines with execute:")
        for line in content.split('\n'):
            if 'execute' in line.lower() or 'batch' in line.lower():
                print(line.strip())
except Exception as e:
    pass
