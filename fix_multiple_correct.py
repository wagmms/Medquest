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

fixed_count = 0
for qid, text, correct_letters in rows:
    if not text:
        continue
    
    match_gabarito = re.search(r'\*\*Gabarito\*\*:\s*Letra\s+([A-E])', text, re.IGNORECASE)
    expected_gabarito = match_gabarito.group(1).upper() if match_gabarito else None
    
    # If the DB has multiple correct answers, and we found a single expected gabarito
    if expected_gabarito and len(correct_letters.split(',')) > 1:
        c.execute("UPDATE alternatives SET is_correct = 0 WHERE question_id = ?", (qid,))
        c.execute("UPDATE alternatives SET is_correct = 1 WHERE question_id = ? AND letter = ?", (qid, expected_gabarito))
        fixed_count += 1

conn.commit()
conn.close()
print(f"Fixed {fixed_count} questions with multiple correct alternatives.")
