import sqlite3
import re

db_path = 'app/backend/medquest.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT q.id, e.explanation_text FROM questions q JOIN explanations e ON q.id = e.question_id")
rows = c.fetchall()

for qid, text in rows:
    if not text:
        continue
    
    match_gabarito = re.search(r'\*\*Gabarito\*\*:\s*Letra\s+([A-E])', text, re.IGNORECASE)
    match_porque = re.search(r'\*\*Por que a Letra ([A-E]) é a Correta\?\*\*', text, re.IGNORECASE)
    
    expected_gabarito = match_gabarito.group(1).upper() if match_gabarito else None
    expected_porque = match_porque.group(1).upper() if match_porque else None
    
    if expected_gabarito and expected_porque and expected_gabarito != expected_porque:
        print(f"Question {qid}: Gabarito says {expected_gabarito}, but Por que says {expected_porque}")
