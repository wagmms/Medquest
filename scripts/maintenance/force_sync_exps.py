import sqlite3
import sys
import os

backend_path = os.path.join(os.getcwd(), "app", "backend")
sys.path.insert(0, backend_path)
from scripts.sync_db_turso import get_turso_config, execute_turso_pipeline

url, token = get_turso_config()

db_path = 'app/backend/medquest.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT question_id, explanation_text FROM explanations WHERE explanation_text IS NOT NULL")
exps = c.fetchall()

import hashlib
def md5(t):
    return hashlib.md5(t.encode('utf-8')).hexdigest()

check_reqs = [
    {"type": "execute", "stmt": {"sql": "SELECT question_id, hex(md5(explanation_text)) FROM explanations WHERE explanation_text IS NOT NULL"}}
]
try:
    remote_data = execute_turso_pipeline(url, token, check_reqs, timeout=60)
except Exception:
    # If the database doesn't have an md5 function
    print("MD5 not available in Turso. We will just push the 573 we know we fixed, plus the 12.")

