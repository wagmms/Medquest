import sqlite3

db_path = 'app/backend/medquest.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Update alternatives
c.execute("UPDATE alternatives SET is_correct = 0 WHERE question_id=48718 AND letter='B'")
c.execute("UPDATE alternatives SET is_correct = 1 WHERE question_id=48718 AND letter='C'")

# Fetch explanation
c.execute("SELECT explanation_text FROM explanations WHERE question_id=48718")
explanation = c.fetchone()[0]

# Fix explanation text
# 1. Gabarito
explanation = explanation.replace("**Gabarito**: Letra B", "**Gabarito**: Letra C")

# Extract B text
b_header = "**Por que a Letra B é a Correta?**:\n"
b_start = explanation.find(b_header) + len(b_header)
b_end = explanation.find("\n\n**Análise dos Distratores**:")
b_text = explanation[b_start:b_end].strip()

# Extract C text
c_header = "- **Letra C**: "
c_start = explanation.find(c_header) + len(c_header)
c_end = explanation.find("\n- **Letra D**:")
c_text = explanation[c_start:c_end].strip()

# Reconstruct explanation
explanation = explanation[:explanation.find("**Por que a Letra B é a Correta?**:")]
explanation += "**Por que a Letra C é a Correta?**:\n"
explanation += c_text + "\n\n"
explanation += "**Análise dos Distratores**:\n"
explanation += "- **Letra A**: " + explanation[explanation.find("- **Letra A**: ")+len("- **Letra A**: "):explanation.find("\n- **Letra C**:")] + "\n"
explanation += "- **Letra B**: " + b_text + "\n"
explanation += "- **Letra D**: " + explanation[explanation.find("- **Letra D**: ")+len("- **Letra D**: "):]

c.execute("UPDATE explanations SET explanation_text = ? WHERE question_id=48718", (explanation,))

conn.commit()
conn.close()
print("Fixed 48718")
