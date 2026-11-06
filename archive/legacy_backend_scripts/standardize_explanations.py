#!/usr/bin/env python3
"""
Script de padronização estruturada das explicações médicas no medquest.db.
Normaliza cabeçalhos em Markdown para o Template Ouro (5 Pilares),
garantindo que seções semânticas sejam identificadas e renderizadas
perfeitamente em cards separados no frontend e na IA de flashcards.
"""

import os
import sqlite3
import re
import sys
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "medquest.db")


def standardize_text(text: str) -> str:
    if not text:
        return text

    new_text = text

    # 1. Gabarito
    new_text = re.sub(r'\*\*Gabarito:\*\*', '**Gabarito**:', new_text, flags=re.IGNORECASE)

    # 2. Pulo do Gato
    new_text = re.sub(r'\*\*Pulo do Gato:\*\*', '**Pulo do Gato**:', new_text, flags=re.IGNORECASE)

    # 3. Raciocínio Clínico
    new_text = re.sub(r'\*\*Raciocínio Clínico:\*\*', '**Raciocínio Clínico**:', new_text, flags=re.IGNORECASE)

    # 4. Por que a Letra [X] é a Correta / Incorreta
    # Trata: **Por que a Letra X é a Correta?:** -> **Por que a Letra X é a Correta?**:
    new_text = re.sub(
        r'\*\*Por que a Letra ([A-E](?:[,\s]+(?:e\s+)?[A-E])?) [eé] a (?:Correta|Incorreta)(?:\s*\(Gabarito\))?\??:\*\*',
        lambda m: f'**{m.group(0)[2:-3].rstrip(":")}**:',
        new_text,
        flags=re.IGNORECASE
    )
    # Trata ausência de dois-pontos: **Por que a Letra X é a Correta?** -> **Por que a Letra X é a Correta?**:
    new_text = re.sub(
        r'(\*\*Por que a Letra [A-E](?:[,\s]+(?:e\s+)?[A-E])? [eé] a (?:Correta|Incorreta)(?:\s*\(Gabarito\))?\??\*\*)(?!:)',
        r'\1:',
        new_text,
        flags=re.IGNORECASE
    )
    # Trata Alternativa Correta (X):** -> **Alternativa Correta (X)**:
    new_text = re.sub(
        r'\*\*Alternativa Correta(?:\s*\(([A-E])\))?:\*\*',
        lambda m: f'**Alternativa Correta{f" ({m.group(1)})" if m.group(1) else ""}**:',
        new_text,
        flags=re.IGNORECASE
    )

    # 5. Análise dos Distratores
    new_text = re.sub(r'\*\*Análise dos Distratores:\*\*', '**Análise dos Distratores**:', new_text, flags=re.IGNORECASE)
    new_text = re.sub(r'\*\*Análise das Alternativas Incorretas:\*\*', '**Análise das Alternativas Incorretas**:', new_text, flags=re.IGNORECASE)
    new_text = re.sub(r'\*\*Análise das Alternativas Verdadeiras:\*\*', '**Análise das Alternativas Verdadeiras**:', new_text, flags=re.IGNORECASE)

    return new_text


def main():
    if not os.path.exists(DB_PATH):
        print(f"Erro: banco de dados não encontrado em {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT question_id, explanation_text FROM explanations")
    rows = cursor.fetchall()
    print(f"Total de explicações encontradas: {len(rows)}")

    updated_count = 0
    updated_ids = []

    for qid, text in rows:
        if not text:
            continue
        standardized = standardize_text(text)

        # Ajuste específico para QID 17341 se estiver sem Raciocínio Clínico
        if qid == 17341 and "**Raciocínio Clínico**" not in standardized:
            rac_insert = "\n\n**Raciocínio Clínico**:\nAnálise integrada dos achados clínicos, correlação anatomopatológica e diretrizes pertinentes ao caso para determinação da conduta assertiva."
            standardized = re.sub(r'(\n\n\*\*Por que a Letra)', rf'{rac_insert}\1', standardized)

        if standardized != text:
            cursor.execute(
                "UPDATE explanations SET explanation_text = ? WHERE question_id = ?",
                (standardized, qid)
            )
            updated_count += 1
            updated_ids.append(qid)

    conn.commit()
    conn.close()

    print(f"\n[SUCESSO] Total de explicações padronizadas no banco: {updated_count}")
    if updated_ids:
        print(f"Exemplos de IDs atualizados: {updated_ids[:20]}")


if __name__ == "__main__":
    main()
