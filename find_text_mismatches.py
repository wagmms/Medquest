import sqlite3
import re

db_path = 'app/backend/medquest.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT q.id, e.explanation_text FROM questions q JOIN explanations e ON q.id = e.question_id")
rows = c.fetchall()

mismatches = []

for qid, text in rows:
    if not text:
        continue
    
    match_gabarito = re.search(r'\*\*Gabarito\*\*:\s*Letra\s+([A-E])', text, re.IGNORECASE)
    expected_gabarito = match_gabarito.group(1).upper() if match_gabarito else None
    
    if not expected_gabarito:
        continue
    
    # Check if there is any distractor analysis that says it's correct
    distratores_idx = text.find('**Análise dos Distratores**:')
    if distratores_idx == -1:
        continue
        
    distratores_text = text[distratores_idx:]
    
    # We parse each letter in the distratores
    letter_matches = re.finditer(r'- \*\*Letra ([A-E])\*\*: (.*?)(?=(?:\n- \*\*Letra [A-E]\*\*:)|\Z)', distratores_text, re.DOTALL)
    
    for match in letter_matches:
        dist_letter = match.group(1).upper()
        dist_content = match.group(2)
        
        # If this is the expected gabarito, skip (it shouldn't be in distratores anyway, but let's be safe)
        if dist_letter == expected_gabarito:
            continue
            
        # Check if the text says it is the correct answer
        if re.search(r'(?i)(esta é a alternativa correta|esta é a nossa resposta|esta é nossa resposta correta|gabarito da questão|a alternativa correta é a letra)', dist_content):
            mismatches.append((qid, expected_gabarito, dist_letter))
            break # Found a mismatch for this question

print(f"Found {len(mismatches)} internal mismatches where a distractor is claimed to be correct.")
for m in mismatches[:20]:
    print(f"Question {m[0]}: Gabarito says {m[1]}, but distractor {m[2]} claims to be correct.")

