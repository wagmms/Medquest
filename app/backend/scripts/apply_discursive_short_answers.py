"""
Script para aplicar as respostas curtas extraídas nas 735 questões discursivas do MedQuest.
Atualiza:
1. explanations.explanation_text -> Insere '**Gabarito**: <resposta curta>' no topo.
2. alternatives.text -> Atualiza a alternativa 'A' com a resposta curta oficial da banca.
Cria backup automático antes de qualquer modificação.
"""

import sys
import json
import shutil
import sqlite3
import re
import argparse
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "medquest.db"
INPUT_PATH = ROOT / "data" / "discursive_short_answers.json"


def clean_existing_gabarito_header(text: str) -> str:
    if not text:
        return ""
    t = text.strip()
    # Remove existing Gabarito header if present (including generic placeholders)
    t = re.sub(r"^\s*\*\*(?:Gabarito|Padrão de Resposta)(?:\s+Oficial)?\*\*:[^\n]*\n+", "", t, flags=re.I).strip()
    return t


def apply_short_answers(apply_changes: bool = False):
    if not DB_PATH.exists():
        print(f"Erro: Banco de dados não encontrado em {DB_PATH}")
        sys.exit(1)

    if not INPUT_PATH.exists():
        print(f"Erro: Arquivo com respostas não encontrado em {INPUT_PATH}")
        sys.exit(1)

    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    valid_answers = {
        int(qid): item["short_answer"].strip()
        for qid, item in data.items()
        if item.get("short_answer", "").strip()
    }

    print(f"Respostas curtas válidas carregadas: {len(valid_answers)}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Verificar questões que existem no banco
    existing_qs = conn.execute("""
        SELECT q.id, q.source_file, q.stem, e.explanation_text, a.text as alt_text
        FROM questions q
        LEFT JOIN explanations e ON e.question_id = q.id
        LEFT JOIN alternatives a ON a.question_id = q.id AND a.letter = 'A'
        WHERE q.id IN ({})
    """.format(",".join(map(str, valid_answers.keys())))).fetchall()

    print(f"Questões encontradas no banco para atualização: {len(existing_qs)}")

    updates_exp = []
    updates_alt = []

    for q in existing_qs:
        qid = q["id"]
        short_ans = valid_answers[qid]

        curr_exp = q["explanation_text"] or ""
        cleaned_exp = clean_existing_gabarito_header(curr_exp)
        new_exp = f"**Gabarito**: {short_ans}\n\n{cleaned_exp}"

        updates_exp.append((new_exp, datetime.now().isoformat(), qid))
        updates_alt.append((short_ans, qid))

    print(f"\nResumo das alterações planejadas:")
    print(f"- Explicações a atualizar (com **Gabarito**: <resposta>): {len(updates_exp)}")
    print(f"- Alternativas a atualizar (letra A): {len(updates_alt)}")

    print("\nExemplo de 3 questões com nova resposta curta:")
    for q in existing_qs[:3]:
        qid = q["id"]
        print(f"--- ID {qid} ({q['source_file']}) ---")
        print(f"Pergunta final: {q['stem'].strip().splitlines()[-1]}")
        print(f"Alternativa anterior: {q['alt_text']}")
        print(f"Nova resposta curta (Gabarito / Alternativa): {valid_answers[qid]}")

    if not apply_changes:
        print("\n[DRY RUN] Nenhuma alteração gravada no banco. Execute com --apply para persistir.")
        conn.close()
        return

    # Backup
    backup_path = DB_PATH.with_name(f"{DB_PATH.name}.before-discursive-answers-{datetime.now():%Y%m%d_%H%M%S}")
    shutil.copy2(DB_PATH, backup_path)
    print(f"\n[BACKUP] Criado com sucesso em: {backup_path}")

    # Aplicar em transação
    with conn:
        conn.executemany(
            "UPDATE explanations SET explanation_text = ?, reviewed_at = ? WHERE question_id = ?",
            updates_exp
        )
        conn.executemany(
            "UPDATE alternatives SET text = ? WHERE question_id = ? AND letter = 'A'",
            updates_alt
        )

    conn.close()
    print(f"\n[SUCESSO] {len(updates_exp)} explicações e {len(updates_alt)} alternativas atualizadas com sucesso no banco!")


def main():
    parser = argparse.ArgumentParser(description="Aplica as respostas curtas da banca nas questões discursivas.")
    parser.add_argument("--apply", action="store_true", help="Persiste as alterações no banco de dados.")
    args = parser.parse_args()

    apply_short_answers(apply_changes=args.apply)


if __name__ == "__main__":
    main()
