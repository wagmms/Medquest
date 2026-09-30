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

c.execute("SELECT question_id, explanation_text, generated_at, reviewed_at FROM explanations WHERE explanation_text IS NOT NULL")
exps = c.fetchall()

print(f"Pushing ALL {len(exps)} explanations to Turso to guarantee consistency...")

batch_size = 100
for i in range(0, len(exps), batch_size):
    chunk = exps[i:i+batch_size]
    reqs = [{"type": "execute", "stmt": {"sql": "BEGIN"}}]
    for qid, text, gen, rev in chunk:
        reqs.append({
            "type": "execute",
            "stmt": {
                "sql": "INSERT INTO explanations (question_id, explanation_text, generated_at, reviewed_at) VALUES (?, ?, ?, ?) ON CONFLICT(question_id) DO UPDATE SET explanation_text = excluded.explanation_text, reviewed_at = excluded.reviewed_at",
                "args": [
                    {"type": "integer", "value": str(qid)},
                    {"type": "text", "value": text},
                    {"type": "text", "value": gen or ""},
                    {"type": "text", "value": rev or ""}
                ]
            }
        })
    reqs.append({"type": "execute", "stmt": {"sql": "COMMIT"}})
    execute_turso_pipeline(url, token, reqs)
    if (i // batch_size) % 10 == 0:
        print(f"Synced batch {i//batch_size + 1}")

print("Done syncing all explanations.")
