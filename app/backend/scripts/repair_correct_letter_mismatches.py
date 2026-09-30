#!/usr/bin/env python3
"""
MedQuest - Sincronização e Correção de Gabaritos Divergentes (SQLite + Turso Cloud)
Corrige 587 questões onde havia discrepância entre questions.correct_letter e alternatives.is_correct,
incluindo a questão QID 23120 (SES-PE 2026: Contracepção no puerpério).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent.parent
DB_PATH = BACKEND_DIR / "medquest.db"
BACKUP_DIR = BACKEND_DIR / "data" / "backups"

sys.path.insert(0, str(BACKEND_DIR))
from scripts.audit.integrity import check_integrity
from scripts.sync_db_turso import execute_turso_pipeline, get_turso_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("repair_gabaritos")

# Questões com gabarito ampliado / múltiplas válidas confirmadas
MULTI_VALID: Dict[int, Set[str]] = {
    10333: {"B", "C"},
    10399: {"B", "D"},
    11024: {"C", "D"},
    11562: {"B", "C"},
}

# Questões onde recurso foi indeferido ou comentário aponta gabarito único
COMMA_TO_SINGLE: Dict[int, str] = {
    8572: "B",
    10540: "B",
    11407: "B",
    12439: "C",
    12558: "C",
    12690: "C",
    12710: "C",
    15777: "A",
}

# Questões onde nenhuma alternativa estava marcada como 1
ZERO_CORRECT_FIX: Dict[int, str] = {
    11266: "A",
}


def backup_database() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_file = BACKUP_DIR / f"medquest-pre-gabarito-fix-{stamp}.db"
    logger.info("Criando backup local do banco em %s...", backup_file)
    shutil.copy2(DB_PATH, backup_file)
    return backup_file


def compute_repairs(conn: sqlite3.Connection) -> Tuple[List[Tuple[str, int]], List[Tuple[int, int, str]]]:
    c = conn.cursor()
    c.execute("SELECT question_id, letter, is_correct FROM alternatives")
    alts_by_q: Dict[int, List[Tuple[str, int]]] = {}
    for aid, let, is_corr in c.fetchall():
        if aid not in alts_by_q:
            alts_by_q[aid] = []
        alts_by_q[aid].append((let, is_corr))

    q_updates: List[Tuple[str, int]] = []  # (new_correct_letter, qid)
    a_updates: List[Tuple[int, int, str]] = []  # (new_is_correct, qid, letter)

    c.execute("SELECT id, correct_letter FROM questions")
    for q in c.fetchall():
        qid = q[0]
        curr_corr = (q[1] or "").strip()
        alts = alts_by_q.get(qid, [])
        if len(alts) <= 1:
            continue

        if qid in MULTI_VALID:
            valid_set = MULTI_VALID[qid]
            canonical_str = ", ".join(sorted(valid_set))
            if curr_corr != canonical_str:
                q_updates.append((canonical_str, qid))
            for let, is_corr in alts:
                expected = 1 if let.upper() in valid_set else 0
                if is_corr != expected:
                    a_updates.append((expected, qid, let))
        elif qid in COMMA_TO_SINGLE:
            target = COMMA_TO_SINGLE[qid]
            if curr_corr != target:
                q_updates.append((target, qid))
            for let, is_corr in alts:
                expected = 1 if let.upper() == target else 0
                if is_corr != expected:
                    a_updates.append((expected, qid, let))
        elif qid in ZERO_CORRECT_FIX:
            target = ZERO_CORRECT_FIX[qid]
            if curr_corr != target:
                q_updates.append((target, qid))
            for let, is_corr in alts:
                expected = 1 if let.upper() == target else 0
                if is_corr != expected:
                    a_updates.append((expected, qid, let))
        else:
            corr_alts = [let.upper() for let, ic in alts if ic == 1]
            if len(corr_alts) == 1:
                target = corr_alts[0]
                if curr_corr != target:
                    q_updates.append((target, qid))

    return q_updates, a_updates


def apply_repairs_local(conn: sqlite3.Connection, q_updates: List[Tuple[str, int]], a_updates: List[Tuple[int, int, str]]) -> None:
    logger.info("Aplicando %d atualizações em questions e %d em alternatives localmente...", len(q_updates), len(a_updates))
    with conn:
        conn.executemany("UPDATE questions SET correct_letter = ? WHERE id = ?", q_updates)
        conn.executemany("UPDATE alternatives SET is_correct = ? WHERE question_id = ? AND letter = ?", a_updates)


def sync_repairs_to_turso(q_updates: List[Tuple[str, int]], a_updates: List[Tuple[int, int, str]]) -> bool:
    url, token = get_turso_config()
    if not url or not token:
        logger.warning("Credenciais do Turso não configuradas. Sincronização remota ignorada.")
        return False

    logger.info("Sincronizando correções com o Turso Cloud (%d questões, %d alternativas)...", len(q_updates), len(a_updates))
    
    # 1. Sync questions updates in batches of 100
    batch_size = 100
    total_q_batches = (len(q_updates) + batch_size - 1) // batch_size
    for idx, i in enumerate(range(0, len(q_updates), batch_size), start=1):
        chunk = q_updates[i:i + batch_size]
        reqs = [{"type": "execute", "stmt": {"sql": "BEGIN"}}]
        for new_letter, qid in chunk:
            reqs.append({
                "type": "execute",
                "stmt": {
                    "sql": "UPDATE questions SET correct_letter = ? WHERE id = ?",
                    "args": [
                        {"type": "text", "value": new_letter},
                        {"type": "integer", "value": str(qid)}
                    ]
                }
            })
        reqs.append({"type": "execute", "stmt": {"sql": "COMMIT"}})
        execute_turso_pipeline(url, token, reqs)
        if idx % 2 == 0 or idx == total_q_batches:
            logger.info("  Turso Cloud: [Questões] %d/%d processadas (%d/%d lotes)", min(i + batch_size, len(q_updates)), len(q_updates), idx, total_q_batches)

    # 2. Sync alternatives updates
    if a_updates:
        reqs = [{"type": "execute", "stmt": {"sql": "BEGIN"}}]
        for is_corr, qid, letter in a_updates:
            reqs.append({
                "type": "execute",
                "stmt": {
                    "sql": "UPDATE alternatives SET is_correct = ? WHERE question_id = ? AND letter = ?",
                    "args": [
                        {"type": "integer", "value": str(is_corr)},
                        {"type": "integer", "value": str(qid)},
                        {"type": "text", "value": letter}
                    ]
                }
            })
        reqs.append({"type": "execute", "stmt": {"sql": "COMMIT"}})
        execute_turso_pipeline(url, token, reqs)
        logger.info("  Turso Cloud: [Alternativas] %d atualizações concluídas", len(a_updates))

    # 3. Verify remotely
    verify_res = execute_turso_pipeline(url, token, [
        {"type": "execute", "stmt": {"sql": """
            SELECT count(*)
            FROM questions q
            JOIN alternatives a ON q.id=a.question_id AND a.is_correct=1
            WHERE q.correct_letter != a.letter AND q.correct_letter NOT LIKE '%,%'
        """}},
        {"type": "execute", "stmt": {"sql": "SELECT correct_letter FROM questions WHERE id = 23120"}}
    ])
    rem_mismatches = int(verify_res["results"][0]["response"]["result"]["rows"][0][0]["value"])
    q23120_corr = verify_res["results"][1]["response"]["result"]["rows"][0][0]["value"]
    logger.info("Verificação Turso Cloud: Divergências simples restantes = %d | Q23120 correct_letter = '%s'", rem_mismatches, q23120_corr)
    return rem_mismatches == 0 and q23120_corr == "A"


def main() -> int:
    backup_file = backup_database()
    logger.info("Conectando ao banco SQLite: %s", DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    
    q_updates, a_updates = compute_repairs(conn)
    logger.info("Calculadas: %d atualizações em questions, %d atualizações em alternatives.", len(q_updates), len(a_updates))
    
    if not q_updates and not a_updates:
        logger.info("Nenhuma divergência encontrada. Banco de dados já está em conformidade.")
        conn.close()
        return 0

    apply_repairs_local(conn, q_updates, a_updates)
    
    # Validação de integridade local
    conn.row_factory = sqlite3.Row
    audit_res = check_integrity(conn)
    mismatches = audit_res["warnings"]["is_correct_mismatches"]
    logger.info("Auditoria pós-correção SQLite: is_correct_mismatches = %d", len(mismatches))
    if len(mismatches) > 0:
        logger.error("Ainda restam divergências locais: %s", mismatches)
        conn.close()
        return 1

    # Checagem específica da questão 23120
    c = conn.cursor()
    c.execute("SELECT correct_letter FROM questions WHERE id = 23120")
    q23120_val = c.fetchone()[0]
    logger.info("QID 23120 correct_letter após correção: '%s'", q23120_val)
    assert q23120_val == "A", f"Esperado 'A', obtido '{q23120_val}'"
    conn.close()

    # Sincronização com o Turso Cloud
    turso_ok = sync_repairs_to_turso(q_updates, a_updates)
    if turso_ok:
        logger.info("Sincronização com Turso Cloud CONCLUÍDA COM SUCESSO!")
    else:
        logger.warning("Sincronização com Turso Cloud pendente ou falhou.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
