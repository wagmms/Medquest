import sqlite3
import re

db_path = 'app/backend/medquest.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("""
SELECT q.id, e.explanation_text, a.letter 
FROM questions q
JOIN explanations e ON q.id = e.question_id
JOIN alternatives a ON q.id = a.question_id
WHERE a.is_correct = 1
""")
rows = c.fetchall()

mismatches = []
for qid, text, correct_letter in rows:
    if not text:
        continue
    
    # Check gabarito
    match_gabarito = re.search(r'\*\*Gabarito\*\*:\s*Letra\s+([A-E])', text, re.IGNORECASE)
    match_porque = re.search(r'\*\*Por que a Letra ([A-E]) é a Correta\?\*\*', text, re.IGNORECASE)
    
    expected_gabarito = match_gabarito.group(1).upper() if match_gabarito else None
    expected_porque = match_porque.group(1).upper() if match_porque else None
    
    if expected_gabarito and expected_gabarito != correct_letter:
        mismatches.append(f"Question {qid}: DB says {correct_letter}, but text says Gabarito: Letra {expected_gabarito}")
        continue
        
    if expected_porque and expected_porque != correct_letter:
        mismatches.append(f"Question {qid}: DB says {correct_letter}, but text says Por que a Letra {expected_porque} é a Correta")

print(f"Found {len(mismatches)} mismatches")
for m in mismatches[:20]:
    print(m)
