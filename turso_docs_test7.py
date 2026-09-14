import urllib.request, json
url = "https://raw.githubusercontent.com/tursodatabase/libsql-python/main/src/libsql/connection.py"
try:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as response:
        content = response.read().decode('utf-8')
        print(content)
except Exception as e:
    pass
