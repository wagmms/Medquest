#!/usr/bin/env python3
"""
MedQuest - Targeted Repair Script for Mismatched Explanations.
Restores the authentic 5-Pillar Golden Explanations for questions where
an extraction heuristic inverted or mismatched the correct answer letter.
Synchronizes both local SQLite (medquest.db) and remote Turso Cloud.
"""

from __future__ import annotations

import glob
import json
import logging
import os
import re
import sqlite3
import sys
import time
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from scripts.extract_medway import (
    clean_html_to_markdown,
    format_medway_golden_explanation,
    normalize_text,
)

DB_PATH = BACKEND_DIR / "medquest.db"
EXAMS_DIR = BACKEND_DIR / "data" / "medway_extracted" / "exams"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("repair_mismatches")


def load_env() -> None:
    env_paths = [ROOT_DIR / ".env", BACKEND_DIR / ".env"]
    for env_path in env_paths:
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def get_turso_config() -> Tuple[Optional[str], Optional[str]]:
    load_env()
    raw_url = os.environ.get("TURSO_DATABASE_URL", "")
    token = os.environ.get("TURSO_AUTH_TOKEN", "")
    if not raw_url or not token:
        return None, None
    url = raw_url.replace("libsql://", "https://").replace("wss://", "https://") + "/v2/pipeline"
    return url, token


def execute_turso_pipeline(
    url: str, token: str, requests_list: list, timeout: int = 60, retries: int = 4
) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = json.dumps({"requests": requests_list}).encode("utf-8")
    last_err = None
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(attempt * 2)
            else:
                raise last_err
    return {}


def repair_explanations() -> None:
    logger.info("Connecting to local SQLite: %s", DB_PATH)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Identify all mismatched questions
    cursor.execute("""
        SELECT q.id, q.stem, q.correct_letter, e.explanation_text
        FROM questions q
        JOIN explanations e ON q.id = e.question_id
        WHERE q.correct_letter IS NOT NULL AND length(trim(q.correct_letter)) = 1
        AND e.explanation_text LIKE '%**Gabarito**: Letra %'
        AND substr(trim(q.correct_letter), 1, 1) != (
            SELECT upper(substr(trim(substr(e.explanation_text, instr(e.explanation_text, "**Gabarito**: Letra ") + 20, 2)), 1, 1))
        )
    """)
    mismatches = cursor.fetchall()
    logger.info("Found %d mismatched questions in local database.", len(mismatches))

    if not mismatches:
        logger.info("No mismatches found. Database is already clean.")
        return

    # 2. Fix Q9867 special case if present
    # In Q9867 (USP-SP 2026 AUTORAL), the question's true clinical answer is D, but questions table had A.
    q9867 = next((m for m in mismatches if m["id"] == 9867), None)
    turso_extra_updates: List[Dict[str, Any]] = []
    if q9867:
        logger.info("Fixing Q9867: Updating questions.correct_letter to 'D' and setting alternative D as correct.")
        cursor.execute("UPDATE questions SET correct_letter = 'D' WHERE id = 9867")
        cursor.execute("UPDATE alternatives SET is_correct = 1 WHERE question_id = 9867 AND letter = 'D'")
        cursor.execute("UPDATE alternatives SET is_correct = 0 WHERE question_id = 9867 AND letter != 'D'")
        conn.commit()

        turso_extra_updates.extend([
            {"type": "execute", "stmt": {"sql": "UPDATE questions SET correct_letter = 'D' WHERE id = 9867"}},
            {"type": "execute", "stmt": {"sql": "UPDATE alternatives SET is_correct = 1 WHERE question_id = 9867 AND letter = 'D'"}},
            {"type": "execute", "stmt": {"sql": "UPDATE alternatives SET is_correct = 0 WHERE question_id = 9867 AND letter != 'D'"}},
        ])
        mismatches = [m for m in mismatches if m["id"] != 9867]

    # 3. Index raw track packages by normalized stem
    logger.info("Indexing track packages from %s...", EXAMS_DIR)
    stem_to_track_item: Dict[str, Tuple[Dict[str, Any], List[Dict[str, Any]]]] = {}
    track_files = sorted(glob.glob(str(EXAMS_DIR / "track_*.json")))
    for tf in track_files:
        try:
            with open(tf, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            for q in data.get("questions", []):
                raw_c = q.get("detail", {}).get("content", "")
                if raw_c:
                    norm = normalize_text(raw_c)[:180]
                    if norm and norm not in stem_to_track_item:
                        opts = q.get("detail", {}).get("options", [])
                        exp = q.get("explanation", {})
                        stem_to_track_item[norm] = (exp, opts)
        except Exception as e:
            logger.warning("Error reading track file %s: %s", tf, e)

    logger.info("Loaded %d questions from track packages.", len(stem_to_track_item))

    # 4. Rebuild explanations for all remaining mismatched questions
    now_iso = datetime.now(timezone.utc).isoformat()
    repaired_records: List[Tuple[int, str, str]] = []  # (qid, new_exp, reviewed_at)
    repaired_from_track = 0
    repaired_via_fallback = 0

    for m in mismatches:
        qid = m["id"]
        stem = m["stem"] or ""
        target_let = m["correct_letter"].strip().upper()
        old_exp = m["explanation_text"] or ""
        norm = normalize_text(stem)[:180]

        new_golden = None
        if norm in stem_to_track_item:
            exp_detail, opts = stem_to_track_item[norm]
            new_golden = format_medway_golden_explanation(
                exp_detail, opts, target_let, is_discursive=False
            )
            repaired_from_track += 1
        else:
            # Fallback: rearrange existing markdown sections
            # Extract Pulo do Gato, Raciocínio Clínico, and all alternative texts
            pulo_m = re.search(r"(\*\*Pulo do Gato\*\*:[\s\S]*?)(?=\n\n\*\*Raciocínio Clínico\*\*|\n\n\*\*Por que a Letra|\Z)", old_exp)
            rac_m = re.search(r"(\*\*Raciocínio Clínico\*\*:[\s\S]*?)(?=\n\n\*\*Por que a Letra|\n\n\*\*Análise dos Distratores|\Z)", old_exp)
            por_m = re.search(r"\*\*Por que a Letra\s*([A-E])\s*é a Correta\?\*\*:\s*([\s\S]*?)(?=\n\n\*\*Análise dos Distratores|\Z)", old_exp)
            dist_m = re.search(r"\*\*Análise dos Distratores\*\*:\s*([\s\S]*?)(?=\n\n\*\*Referências Bibliográficas|\Z)", old_exp)

            pulo_text = pulo_m.group(1).strip() if pulo_m else "**Pulo do Gato**:\nAtenção aos conceitos clínicos essenciais."
            rac_text = rac_m.group(1).strip() if rac_m else ""

            # Map existing options
            option_texts: Dict[str, str] = {}
            if por_m:
                option_texts[por_m.group(1).upper()] = por_m.group(2).strip()
            if dist_m:
                dist_body = dist_m.group(1)
                for line in dist_body.split("\n- "):
                    lm = re.match(r"(?:- )?\*\*Letra\s*([A-E])\*\*:\s*([\s\S]*)", line.strip())
                    if lm:
                        option_texts[lm.group(1).upper()] = lm.group(2).strip()

            target_correct_text = option_texts.get(target_let, "Alternativa correta conforme as diretrizes clínicas.")
            dist_lines = []
            for l in sorted(option_texts.keys()):
                if l != target_let:
                    dist_lines.append(f"- **Letra {l}**: {option_texts[l]}")

            parts = [
                f"**Gabarito**: Letra {target_let}",
                pulo_text,
            ]
            if rac_text:
                parts.append(rac_text)
            parts.append(f"**Por que a Letra {target_let} é a Correta?**:\n{target_correct_text}")
            if dist_lines:
                parts.append("**Análise dos Distratores**:\n" + "\n".join(dist_lines))

            new_golden = "\n\n".join(parts)
            repaired_via_fallback += 1

        cursor.execute(
            "UPDATE explanations SET explanation_text = ?, reviewed_at = ? WHERE question_id = ?",
            (new_golden, now_iso, qid),
        )
        repaired_records.append((qid, new_golden, now_iso))

    conn.commit()
    logger.info(
        "Successfully updated %d explanations in local SQLite (from tracks: %d, fallback: %d).",
        len(repaired_records),
        repaired_from_track,
        repaired_via_fallback,
    )

    # 5. Synchronize repaired records to Turso Cloud
    url, token = get_turso_config()
    if not url or not token:
        logger.warning("TURSO_DATABASE_URL or TURSO_AUTH_TOKEN missing. Skipping remote sync.")
        conn.close()
        return

    logger.info("Synchronizing updates to Turso Cloud via Pipeline v2...")

    # Execute extra updates (Q9867 if any)
    if turso_extra_updates:
        logger.info("Applying Q9867 updates to Turso...")
        execute_turso_pipeline(url, token, turso_extra_updates)

    # Batch update explanations to Turso
    batch_size = 100
    total_batches = (len(repaired_records) + batch_size - 1) // batch_size
    upsert_sql = """
        INSERT INTO explanations (question_id, explanation_text, generated_at, reviewed_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(question_id) DO UPDATE SET
            explanation_text = excluded.explanation_text,
            reviewed_at = excluded.reviewed_at
    """

    for batch_idx, i in enumerate(range(0, len(repaired_records), batch_size), start=1):
        chunk = repaired_records[i : i + batch_size]
        reqs = [{"type": "execute", "stmt": {"sql": "BEGIN"}}]
        for qid, text, rev in chunk:
            reqs.append({
                "type": "execute",
                "stmt": {
                    "sql": upsert_sql,
                    "args": [
                        {"type": "integer", "value": str(qid)},
                        {"type": "text", "value": text},
                        {"type": "text", "value": rev},
                        {"type": "text", "value": rev},
                    ],
                },
            })
        reqs.append({"type": "execute", "stmt": {"sql": "COMMIT"}})
        execute_turso_pipeline(url, token, reqs)
        if batch_idx % 5 == 0 or batch_idx == total_batches:
            logger.info("Turso sync progress: %d/%d batches completed.", batch_idx, total_batches)

    logger.info("Turso Cloud synchronization finished successfully.")
    conn.close()


if __name__ == "__main__":
    repair_explanations()
