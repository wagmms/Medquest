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
""")
rows = c.fetchall()

mismatches = []
for qid, text, correct_letters in rows:
    if not text:
        continue
    
    match_gabarito = re.search(r'\*\*Gabarito\*\*:\s*Letra\s+([A-E])', text, re.IGNORECASE)
    expected_gabarito = match_gabarito.group(1).upper() if match_gabarito else None
    
    if expected_gabarito and expected_gabarito != correct_letters:
        mismatches.append((qid, correct_letters, expected_gabarito))

print("Found mismatches:")
for qid, db_ans, exp_ans in mismatches:
    print(f"Question {qid}: DB={db_ans}, Exp={exp_ans}")
