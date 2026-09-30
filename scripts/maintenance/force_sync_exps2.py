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

print("Fetching remote explanations to compare...")
check_reqs = [
    {"type": "execute", "stmt": {"sql": "SELECT question_id, explanation_text FROM explanations WHERE explanation_text IS NOT NULL"}}
]
remote_data = execute_turso_pipeline(url, token, check_reqs, timeout=120)
remote_rows = remote_data["results"][0]["response"]["result"]["rows"]

remote_exps = {}
for r in remote_rows:
    if r and r[1]["value"] is not None:
        remote_exps[int(r[0]["value"])] = r[1]["value"]

to_update = []
for qid, text in exps:
    if qid in remote_exps and remote_exps[qid] != text:
        to_update.append((qid, text))

print(f"Found {len(to_update)} explanations to update in Turso.")

if to_update:
    batch_size = 50
    for i in range(0, len(to_update), batch_size):
        chunk = to_update[i:i+batch_size]
        reqs = [{"type": "execute", "stmt": {"sql": "BEGIN"}}]
        for qid, text in chunk:
            reqs.append({
                "type": "execute",
                "stmt": {
                    "sql": "UPDATE explanations SET explanation_text = ? WHERE question_id = ?",
                    "args": [
                        {"type": "text", "value": text},
                        {"type": "integer", "value": str(qid)}
                    ]
                }
            })
        reqs.append({"type": "execute", "stmt": {"sql": "COMMIT"}})
        execute_turso_pipeline(url, token, reqs)
        print(f"Synced batch {i//batch_size + 1}")

print("Done syncing explanations.")
