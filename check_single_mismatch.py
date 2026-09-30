import sqlite3
import re

db_path = 'app/backend/medquest.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("""
SELECT q.id, e.explanation_text, GROUP_CONCAT(a.letter) 
FROM questions q
JOIN explanations e ON q.id = e.question_id
JOIN alternatives a ON q.id = a.question_id
WHERE a.is_correct = 1
GROUP BY q.id
HAVING COUNT(a.id) = 1
""")
rows = c.fetchall()

for qid, text, correct_letter in rows:
    if not text:
        continue
    
    match_gabarito = re.search(r'\*\*Gabarito\*\*:\s*Letra\s+([A-E])', text, re.IGNORECASE)
    expected_gabarito = match_gabarito.group(1).upper() if match_gabarito else None
    
    if expected_gabarito and expected_gabarito != correct_letter:
        print(f"Question {qid}: DB says {correct_letter}, but text says Gabarito: Letra {expected_gabarito}")

