import libsql
import os
from dotenv import load_dotenv
load_dotenv("app/backend/.env")
url = os.environ.get("TURSO_DATABASE_URL", "http://dummy.com")
print("connecting to", url)
client = libsql.connect(url)
print(dir(client))
try:
    print(hasattr(client, 'batch'))
except Exception as e:
    print(e)
