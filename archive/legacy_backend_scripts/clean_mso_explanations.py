#!/usr/bin/env python3
"""
Script to clean Microsoft Word CSS style definitions and XML metadata
artifacts from question explanations in MedQuest SQLite and Turso Cloud.
"""

import os
import re
import sys
import sqlite3

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DB_PATH = os.path.join(ROOT_DIR, "app", "backend", "medquest.db")


def clean_explanation_text(text: str) -> str:
    if not text:
        return text
    raw = text

    # 1. Remove raw styles, scripts, xml, HTML comments, Word tags
    raw = re.sub(r"<style\b[^>]*>[\s\S]*?</style>", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"<xml\b[^>]*>[\s\S]*?</xml>", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"<!--[\s\S]*?-->", "", raw)
    raw = re.sub(r"</?(?:o|w|m|v):[a-z0-9_-]+[^>]*>", "", raw, flags=re.IGNORECASE)

    # 2. Remove leaked Word CSS style definitions
    raw = re.sub(r"/\*\s*Style Definitions\s*\*\/[\s\S]*?(?:mso-fareast-language:[^}]+;\}|\})", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"table\.MsoNormalTable\s*\{[\s\S]*?\}", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\b(?:mso-style-[^;]+;|mso-tstyle-[^;]+;|mso-[a-z-]+:[^;]+;)", "", raw, flags=re.IGNORECASE)

    # 3. Remove leaked Word document properties dumps
    raw = re.sub(
        r"Normal\s*\n+\s*0\s*\n+(?:false\s*\n+)?(?:\d+\s*\n+)?(?:false\s*\n+)+[A-Z]{2}-[A-Z]{2}\s*\n+X-NONE\s*\n+X-NONE",
        "",
        raw,
        flags=re.IGNORECASE,
    )
    raw = re.sub(r"\b(?:PT-BR|EN-US)\s*\n+X-NONE\s*\n+X-NONE\b", "", raw, flags=re.IGNORECASE)

    # 4. Fix spacing after distractor headers if the removal left a newline gap
    raw = re.sub(r"(- \*\*Letra [A-E]\*\*):?\s*\n+", r"\1: ", raw)

    # 5. Collapse excessive blank lines
    raw = re.sub(r"\n{3,}", "\n\n", raw).strip()
    return raw


def has_mso_artifact(text: str) -> bool:
    if not text:
        return False
    return (
        "MsoNormalTable" in text
        or "/* Style Definitions */" in text
        or "X-NONE" in text
        or bool(re.search(r"Normal\s+0\s+(?:false\s+)?21", text))
        or "mso-fareast-language" in text
    )


def run_clean(sync_turso: bool = True):
    print(f"[1/3] Conectando ao banco SQLite: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT question_id, explanation_text FROM explanations")
    rows = cur.fetchall()

    affected = []
    for r in rows:
        qid = r["question_id"]
        exp = r["explanation_text"]
        if has_mso_artifact(exp):
            affected.append((qid, exp))

    print(f"  Encontradas {len(affected)} explicações com artefatos MSO no banco local.")
    if not affected:
        print("  Nenhuma explicação precisa de limpeza.")
        return

    print(f"[2/3] Limpando {len(affected)} explicações no banco local...")
    updates = []
    for qid, exp in affected:
        cleaned = clean_explanation_text(exp)
        updates.append((cleaned, qid))

    cur.executemany("UPDATE explanations SET explanation_text = ? WHERE question_id = ?", updates)
    conn.commit()

    # Verificar que todas foram limpas
    cur.execute("SELECT count(*) FROM explanations WHERE explanation_text LIKE '%MsoNormalTable%' OR explanation_text LIKE '%X-NONE%'")
    remaining = cur.fetchone()[0]
    print(f"  [OK] Limpeza local concluída! Restantes no SQLite local: {remaining}")

    if sync_turso:
        print("[3/3] Sincronizando alterações com o Turso Cloud...")
        backend_scripts = os.path.dirname(os.path.abspath(__file__))
        if backend_scripts not in sys.path:
            sys.path.insert(0, backend_scripts)
        from sync_db_turso import sync_database
        sync_ok = sync_database(verbose=True)
        if sync_ok:
            print("  [OK] Sincronização com o Turso Cloud finalizada com sucesso!")
        else:
            print("  [AVISO] Sincronização com o Turso Cloud finalizada com avisos.")


if __name__ == "__main__":
    sync = "--no-sync" not in sys.argv
    run_clean(sync_turso=sync)
