import sqlite3
import re

db_path = 'app/backend/medquest.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT q.id, e.explanation_text FROM questions q JOIN explanations e ON q.id = e.question_id")
rows = c.fetchall()

fixed_count = 0

for qid, text in rows:
    if not text:
        continue
    
    match_gabarito = re.search(r'\*\*Gabarito\*\*:\s*Letra\s+([A-E])', text, re.IGNORECASE)
    old_correct = match_gabarito.group(1).upper() if match_gabarito else None
    
    if not old_correct:
        continue
        
    distratores_idx = text.find('**Análise dos Distratores**:')
    if distratores_idx == -1:
        continue
        
    distratores_text = text[distratores_idx:]
    
    letter_matches = list(re.finditer(r'- \*\*Letra ([A-E])\*\*: (.*?)(?=(?:\n- \*\*Letra [A-E]\*\*:)|\Z)', distratores_text, re.DOTALL))
    
    new_correct = None
    new_correct_text = None
    
    for match in letter_matches:
        dist_letter = match.group(1).upper()
        dist_content = match.group(2).strip()
        
        if dist_letter == old_correct:
            continue
            
        if re.search(r'(?i)(esta é a alternativa correta|esta é a nossa resposta|esta é nossa resposta correta|gabarito da questão|a alternativa correta é a letra)', dist_content):
            new_correct = dist_letter
            new_correct_text = dist_content
            break
            
    if new_correct:
        # We need to swap old_correct and new_correct in the explanation text
        
        # 1. Replace Gabarito
        new_text = re.sub(r'\*\*Gabarito\*\*:\s*Letra\s+' + old_correct, f'**Gabarito**: Letra {new_correct}', text, count=1, flags=re.IGNORECASE)
        
        # 2. Extract old "Por que" block
        old_porque_match = re.search(r'\*\*Por que a Letra ' + old_correct + r' é a Correta\?\*\*:(.*?)\n\*\*Análise dos Distratores\*\*:', new_text, re.DOTALL | re.IGNORECASE)
        if not old_porque_match:
            print(f"Warning: Could not find old por que for {qid}")
            continue
            
        old_porque_text = old_porque_match.group(1).strip()
        
        # 3. Replace the header for the "Por que" section
        new_text = re.sub(r'\*\*Por que a Letra ' + old_correct + r' é a Correta\?\*\*', f'**Por que a Letra {new_correct} é a Correta?**', new_text, count=1, flags=re.IGNORECASE)
        
        # 4. In new_text, replace the old_porque_text with new_correct_text
        new_text = new_text.replace(old_porque_text, new_correct_text, 1)
        
        # 5. In Análise dos Distratores, replace new_correct_text with old_porque_text
        # And we must also rename the bullet points if needed. Actually we just need to replace the content of new_correct with old_porque_text,
        # and change the bullet point letter of new_correct to old_correct.
        
        # Wait, the distractor list should remain alphabetically ordered!
        # Let's extract all distractor contents.
        distractor_dict = {}
        for match in letter_matches:
            distractor_dict[match.group(1).upper()] = match.group(2).strip()
            
        # The new distractor dict should contain old_correct with old_porque_text
        # And should NOT contain new_correct.
        distractor_dict[old_correct] = old_porque_text
        if new_correct in distractor_dict:
            del distractor_dict[new_correct]
            
        # Rebuild Análise dos Distratores
        new_distratores = "**Análise dos Distratores**:\n"
        for letter in sorted(distractor_dict.keys()):
            new_distratores += f"- **Letra {letter}**: {distractor_dict[letter]}\n"
            
        # Replace the whole Análise dos Distratores block in new_text
        new_text = new_text[:new_text.find('**Análise dos Distratores**:')] + new_distratores.strip()
        
        # Update DB
        c.execute("UPDATE alternatives SET is_correct = 0 WHERE question_id = ?", (qid,))
        c.execute("UPDATE alternatives SET is_correct = 1 WHERE question_id = ? AND letter = ?", (qid, new_correct))
        c.execute("UPDATE explanations SET explanation_text = ? WHERE question_id = ?", (new_text, qid))
        fixed_count += 1

conn.commit()
conn.close()
print(f"Successfully fixed {fixed_count} questions.")
