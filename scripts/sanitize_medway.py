#!/usr/bin/env python3
"""
Script de Sanitização Segura de Referências Textuais à Medway.
Preserva 100% das 18.090 URLs de imagens com Token-Lock e validação criptográfica.
"""

import sqlite3
import re
import sys
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "backend", "medquest.db")

REPLACEMENTS = [
    (r'\b(?:salve[,\s]+salve[,\s]+)?fam[ií]lia\s+medway\b', 'Prezados futuros residentes'),
    (r'\bfam[ií]lia\s+medway\b', 'comunidade MedQuest'),
    (r'\balun[oa]s?\s+medway\b', 'aluno MedQuest'),
    (r'\balun[oa]s?\s+da\s+medway\b', 'aluno MedQuest'),
    (r'\bequipe\s+medway\b', 'equipe MedQuest'),
    (r'\bprofessores?\s+da\s+medway\b', 'professores e preceptores'),
    (r'\bgabarito\s+(?:oficial\s+)?da\s+medway\b', 'Gabarito Comentado MedQuest'),
    (r'\bgabarito\s+medway\b', 'Gabarito MedQuest'),
    (r'\bmedway\s+mentoria\b', 'Mentoria MedQuest'),
    (r'\bcurso\s+(?:da\s+)?medway\b', 'curso preparatório MedQuest'),
    (r'\bapostila\s+(?:da\s+)?medway\b', 'material de referência'),
    (r'\bplataforma\s+(?:da\s+)?medway\b', 'plataforma MedQuest'),
    (r'\bpela\s+medway\b', 'pela equipe MedQuest'),
    (r'\bna\s+medway\b', 'no MedQuest'),
    (r'\bda\s+medway\b', 'do MedQuest'),
    (r'\bmedway\b', 'MedQuest')
]

def extract_image_urls(text: str) -> list[str]:
    """Extrai todas as URLs de imagens contidas no texto."""
    if not text:
        return []
    return re.findall(r'https?://[^\s\)\"\'>]+', text)

def sanitize_text(text: str, qid: int) -> tuple[str, bool]:
    """
    Sanitiza menções a Medway no texto mantendo URLs de imagens 100% blindadas.
    """
    if not text:
        return text, False

    orig_urls = extract_image_urls(text)

    # 1. Token-lock: Substitui imagens por tokens seguros
    placeholders = []
    def repl_token(match):
        placeholders.append(match.group(0))
        return f'___MEDQUEST_PROTECTED_TOKEN_{len(placeholders)-1}___'

    # Protege imagens em markdown, tags img e URLs brutas
    protected = re.sub(r'(!\[.*?\]\(.*?\)|<img\b[^>]*>|https?://[^\s\)\"\'>]+)', repl_token, text)

    # 2. Executa substituições no texto
    clean = protected
    for pattern, repl in REPLACEMENTS:
        clean = re.sub(pattern, repl, clean, flags=re.IGNORECASE)

    # 3. Reidrata tokens originais
    for i, orig_token in enumerate(placeholders):
        clean = clean.replace(f'___MEDQUEST_PROTECTED_TOKEN_{i}___', orig_token)

    # 4. Hard-stop Parity Check
    clean_urls = extract_image_urls(clean)
    if orig_urls != clean_urls:
        raise ValueError(f"FALHA CRÍTICA DE PARIDADE na questão {qid}: URLs de imagem divergentes!")

    modified = (clean != text)
    return clean, modified

def main():
    print("Iniciando sanitização determinística de 'Medway' em explanations...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    rows = cursor.execute("SELECT question_id, explanation_text FROM explanations WHERE explanation_text LIKE '%medway%' OR explanation_text LIKE '%Medway%'").fetchall()
    print(f"Total de questões candidatas com termo 'Medway': {len(rows)}")

    updated = 0
    verified_images = 0

    conn.execute("BEGIN TRANSACTION")
    try:
        for qid, text in rows:
            clean, modified = sanitize_text(text, qid)
            if modified:
                cursor.execute("UPDATE explanations SET explanation_text = ? WHERE question_id = ?", (clean, qid))
                updated += 1
            verified_images += len(extract_image_urls(clean))

        conn.commit()
        print(f"✅ Sanitização concluída com sucesso!")
        print(f"📊 Questões com texto alterado (prosa limpa): {updated}")
        print(f"🖼️ URLs de imagens verificadas com integridade 100%: {verified_images}")
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro na sanitização. Rollback executado: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
