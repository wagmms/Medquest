import os
import urllib.request
req = urllib.request.Request("https://raw.githubusercontent.com/tursodatabase/libsql-python/main/src/lib.rs")
try:
    with urllib.request.urlopen(req) as response:
        content = response.read().decode('utf-8')
        print(content[:500])
except Exception as e:
    pass
