#!/usr/bin/env python3
"""
Rebuild / Backfill SQLite FTS5 index for MedQuest questions and explanations.
Garante que todas as 42.828+ questões estejam 100% indexadas no FTS5 para busca clínica de alta velocidade.
"""

import argparse
import logging
import os
import sqlite3
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("rebuild_fts")

BACKEND_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BACKEND_DIR / "medquest.db"


def rebuild_local_fts(db_path: Path, full: bool = False):
    if not db_path.exists():
        logger.error(f"Banco de dados local não encontrado em: {db_path}")
        return False

    conn = sqlite3.connect(str(db_path), timeout=60.0)
    cur = conn.cursor()

    try:
        cur.execute("PRAGMA busy_timeout = 30000;")
        cur.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS questions_fts USING fts5(
                stem,
                explanation
            )
        """)

        total_questions = cur.execute("SELECT count(*) FROM questions").fetchone()[0]
        indexed_before = cur.execute("SELECT count(*) FROM questions_fts").fetchone()[0]

        logger.info(f"Questões no banco: {total_questions} | Já indexadas no FTS5: {indexed_before}")

        if full:
            logger.info("Executando recriação completa (--full)...")
            t0 = time.time()
            cur.execute("BEGIN IMMEDIATE;")
            cur.execute("DELETE FROM questions_fts;")
            cur.execute("""
                INSERT INTO questions_fts(rowid, stem, explanation)
                SELECT q.id, q.stem, COALESCE(e.explanation_text, '')
                FROM questions q
                LEFT JOIN explanations e ON q.id = e.question_id;
            """)
            conn.commit()
            elapsed = time.time() - t0
            indexed_after = cur.execute("SELECT count(*) FROM questions_fts").fetchone()[0]
            logger.info(f"Reconstrução completa finalizada em {elapsed:.2f}s! Total indexado: {indexed_after}")
            return True

        # Backfill incremental (apenas questões ausentes)
        missing_count = cur.execute("""
            SELECT count(*) FROM questions q
            WHERE NOT EXISTS (SELECT 1 FROM questions_fts f WHERE f.rowid = q.id)
        """).fetchone()[0]

        if missing_count == 0:
            logger.info("Todas as questões já estão indexadas no FTS5! Nenhuma ação necessária.")
            return True

        logger.info(f"Indexando {missing_count} questões faltantes...")
        t0 = time.time()
        cur.execute("BEGIN IMMEDIATE;")
        cur.execute("""
            INSERT INTO questions_fts(rowid, stem, explanation)
            SELECT q.id, q.stem, COALESCE(e.explanation_text, '')
            FROM questions q
            LEFT JOIN explanations e ON q.id = e.question_id
            WHERE NOT EXISTS (SELECT 1 FROM questions_fts f WHERE f.rowid = q.id);
        """)
        conn.commit()
        elapsed = time.time() - t0
        indexed_after = cur.execute("SELECT count(*) FROM questions_fts").fetchone()[0]
        logger.info(f"Backfill finalizado com sucesso em {elapsed:.2f}s! Total indexado: {indexed_after}/{total_questions}")
        return True

    except Exception as e:
        logger.error(f"Erro durante a reindexação do FTS5: {e}", exc_info=True)
        conn.rollback()
        return False
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Rebuild or backfill MedQuest FTS5 index")
    parser.add_argument("--full", action="store_true", help="Limpa e reconstrói todo o índice do zero")
    parser.add_argument("--db", type=str, default=str(DB_PATH), help="Caminho do arquivo SQLite")
    args = parser.parse_args()

    success = rebuild_local_fts(Path(args.db), full=args.full)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
