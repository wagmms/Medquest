import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

url = 'http://127.0.0.1:5050/api/questions/5/ask_ai'
data = json.dumps({'user_question': 'O que e ritmo juncional?'}).encode('utf-8')
req = Request(url, data=data, headers={'Content-Type': 'application/json'})

try:
    with urlopen(req) as resp:
        print(resp.read().decode('utf-8'))
except HTTPError as e:
    print(f"Error {e.code}: {e.read().decode('utf-8')}")
