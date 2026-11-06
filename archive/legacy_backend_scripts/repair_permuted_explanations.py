#!/usr/bin/env python3
"""
MedQuest - Repair Permuted & Inverted Explanations.
Aligns alternative commentaries in explanations to the actual database alternatives
by semantic text matching against the raw Medway track files.
Synchronizes both local SQLite (medquest.db) and remote Turso Cloud.
"""

from __future__ import annotations

import argparse
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
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from scripts.extract_medway import (
    clean_html_to_markdown,
    normalize_text,
)

DB_PATH = BACKEND_DIR / "medquest.db"
EXAMS_DIR = BACKEND_DIR / "data" / "medway_extracted" / "exams"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("repair_permuted_explanations")


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


def norm_clean(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]", "", s)


def clean_commentary_body(raw_html_or_md: str) -> str:
    cleaned = clean_html_to_markdown(raw_html_or_md)
    # Strip obsolete letter prefix
    cleaned = re.sub(r"^[A-E]\)\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"^(?:[-*•]\s*)?(?:Alternativa|Letra)\s+[A-E](?:\s*\([^)]*\))?\s*:?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"^[A-E]\s*-\s*(?:Correta|Incorreta)\.?\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def extract_section_fallback(pattern: str, text: str, default: str = "") -> str:
    m = re.search(pattern, text, flags=re.IGNORECASE)
    return m.group(1).strip() if m else default


def build_realigned_explanation(
    t_exp: Dict[str, Any],
    db_to_track_opt: Dict[str, Dict[str, Any]],
    correct_letter: str,
    old_explanation: str,
) -> str:
    # 1. Gabarito
    gabarito_header = f"**Gabarito**: Letra {correct_letter}"

    # 2. Pulo do Gato
    conclusion_clean = clean_html_to_markdown(t_exp.get("conclusion") or "")
    if conclusion_clean:
        pulo_gato = f"**Pulo do Gato**:\n{conclusion_clean}"
    else:
        # Fallback to existing Pulo do Gato if present
        existing_pulo = extract_section_fallback(
            r"(\*\*Pulo do Gato\*\*:[\s\S]*?)(?=\n\n\*\*Raciocínio Clínico\*\*|\n\n\*\*Por que a Letra|\Z)",
            old_explanation,
            "**Pulo do Gato**:\nAtenção aos conceitos clínicos essenciais.",
        )
        pulo_gato = existing_pulo

    # 3. Raciocínio Clínico
    intro_clean = clean_html_to_markdown(
        t_exp.get("introduction") or t_exp.get("actual_explanation") or t_exp.get("full_explanation") or ""
    )
    if intro_clean:
        raciocinio = f"**Raciocínio Clínico**:\n{intro_clean}"
    else:
        existing_rac = extract_section_fallback(
            r"(\*\*Raciocínio Clínico\*\*:[\s\S]*?)(?=\n\n\*\*Por que a Letra|\n\n\*\*Análise dos Distratores|\Z)",
            old_explanation,
            "",
        )
        raciocinio = existing_rac

    # 4. Commentary per DB letter
    alt_explanations: Dict[str, str] = {}
    for dl, topt in db_to_track_opt.items():
        t_let = topt["letter"].lower()
        raw_comment = t_exp.get(f"option_{t_let}") or t_exp.get(f"short_option_{t_let}") or ""
        cleaned = clean_commentary_body(raw_comment)
        if not cleaned:
            cleaned = "Alternativa avaliada conforme o raciocínio clínico apresentado."
        alt_explanations[dl] = cleaned

    correct_text = alt_explanations.get(
        correct_letter, "Alternativa correta conforme as diretrizes clínicas."
    )
    por_que_certa = f"**Por que a Letra {correct_letter} é a Correta?**:\n{correct_text}"

    dist_lines = []
    for dl in sorted(alt_explanations.keys()):
        if dl != correct_letter:
            dist_lines.append(f"- **Letra {dl}**: {alt_explanations[dl]}")

    distratores_str = "**Análise dos Distratores**:\n" + "\n".join(dist_lines) if dist_lines else ""

    # 5. References / Bibliography
    bib_clean = clean_html_to_markdown(t_exp.get("bibliography") or "")
    if bib_clean:
        bib_str = f"**Referências Bibliográficas**:\n{bib_clean}"
    else:
        existing_bib = extract_section_fallback(
            r"(\*\*Referências Bibliográficas\*\*:[\s\S]*?)$",
            old_explanation,
            "",
        )
        bib_str = existing_bib

    sections = [gabarito_header, pulo_gato]
    if raciocinio:
        sections.append(raciocinio)
    if por_que_certa:
        sections.append(por_que_certa)
    if distratores_str:
        sections.append(distratores_str)
    if bib_str:
        sections.append(bib_str)

    return "\n\n".join(sections)


def repair_permuted_explanations(dry_run: bool = False, sync_turso: bool = True) -> int:
    logger.info("Connecting to local SQLite: %s", DB_PATH)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Load all DB alternatives
    cursor.execute("SELECT question_id, letter, text, is_correct FROM alternatives ORDER BY question_id, letter")
    db_alts: Dict[int, Dict[str, Tuple[str, int]]] = {}
    for row in cursor.fetchall():
        qid = row["question_id"]
        if qid not in db_alts:
            db_alts[qid] = {}
        db_alts[qid][row["letter"].upper()] = (row["text"] or "", row["is_correct"] or 0)

    # Load all DB questions with explanations
    cursor.execute("""
        SELECT q.id, q.source_file, q.source_number, q.stem, q.correct_letter, e.explanation_text
        FROM questions q
        JOIN explanations e ON q.id = e.question_id
        WHERE q.correct_letter IS NOT NULL AND length(trim(q.correct_letter)) = 1
    """)
    db_questions = cursor.fetchall()
    logger.info("Loaded %d questions with explanations from local database.", len(db_questions))

    # Index raw track packages by normalized stem
    logger.info("Indexing track packages from %s...", EXAMS_DIR)
    stem_to_track_item: Dict[str, Dict[str, Any]] = {}
    track_files = sorted(glob.glob(str(EXAMS_DIR / "track_*.json")))
    for tf in track_files:
        try:
            with open(tf, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            for q in data.get("questions", []):
                raw_c = q.get("detail", {}).get("content", "")
                if raw_c:
                    norm = norm_clean(raw_c)[:120]
                    if norm and norm not in stem_to_track_item:
                        stem_to_track_item[norm] = q
        except Exception as e:
            logger.warning("Error reading track file %s: %s", tf, e)

    logger.info("Loaded %d questions from track packages.", len(stem_to_track_item))

    repaired_records: List[Tuple[int, str, str]] = []  # (qid, new_exp, reviewed_at)
    now_iso = datetime.now(timezone.utc).isoformat()

    for row in db_questions:
        qid = row["id"]
        stem = row["stem"] or ""
        correct_let = row["correct_letter"].strip().upper()
        old_exp = row["explanation_text"] or ""
        d_opts = db_alts.get(qid, {})

        if not d_opts or len(d_opts) < 2:
            continue

        norm = norm_clean(stem)[:120]
        if norm not in stem_to_track_item:
            continue

        t_q = stem_to_track_item[norm]
        t_opts = t_q.get("detail", {}).get("options", [])
        t_exp = t_q.get("explanation")
        if not t_opts or not isinstance(t_exp, dict):
            continue

        t_map = {o["letter"].upper(): (norm_clean(o.get("content", "")), o) for o in t_opts if o.get("letter")}
        d_map = {l.upper(): (norm_clean(t[0]), t[0]) for l, t in d_opts.items()}

        db_to_track_opt: Dict[str, Dict[str, Any]] = {}
        for dl, (dt_norm, dt_raw) in d_map.items():
            if not dt_norm:
                continue
            best_opt = None
            best_score = 0.0
            for tl, (tt_norm, topt) in t_map.items():
                if not tt_norm:
                    continue
                if dt_norm[:30] in tt_norm or tt_norm[:30] in dt_norm:
                    score = 1.0
                else:
                    score = SequenceMatcher(None, dt_norm[:50], tt_norm[:50]).ratio()
                if score > best_score:
                    best_score = score
                    best_opt = topt
            if best_score > 0.55 and best_opt:
                db_to_track_opt[dl] = best_opt

        # Check if bijection: every DB alternative matched a distinct track option
        matched_track_letters = [opt["letter"] for opt in db_to_track_opt.values()]
        if len(db_to_track_opt) == len(d_map) and len(set(matched_track_letters)) == len(d_map):
            # Check if any letter differs
            is_permuted = any(dl != opt["letter"] for dl, opt in db_to_track_opt.items())
            if is_permuted:
                new_golden = build_realigned_explanation(t_exp, db_to_track_opt, correct_let, old_exp)
                repaired_records.append((qid, new_golden, now_iso))

    logger.info("Identified %d permuted questions requiring explanation repair.", len(repaired_records))

    if not repaired_records:
        logger.info("No permuted explanations found. Database is completely aligned.")
        conn.close()
        return 0

    if dry_run:
        logger.info("[DRY RUN] Would update %d explanations in local SQLite.", len(repaired_records))
        for qid, exp, _ in repaired_records[:3]:
            logger.info("--- Preview for QID %d ---", qid)
            print(exp[:400] + "\n...")
        conn.close()
        return len(repaired_records)

    # 1. Update local SQLite
    logger.info("Applying updates to %d records in local SQLite...", len(repaired_records))
    cursor.executemany(
        "UPDATE explanations SET explanation_text = ?, reviewed_at = ? WHERE question_id = ?",
        [(text, rev, qid) for qid, text, rev in repaired_records],
    )
    conn.commit()
    logger.info("Local SQLite updated successfully.")

    # 2. Synchronize to Turso Cloud
    if sync_turso:
        url, token = get_turso_config()
        if not url or not token:
            logger.warning("TURSO_DATABASE_URL or TURSO_AUTH_TOKEN missing. Skipping remote sync.")
            conn.close()
            return len(repaired_records)

        logger.info("Synchronizing %d updates to Turso Cloud via Pipeline v2...", len(repaired_records))
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
            if batch_idx % 2 == 0 or batch_idx == total_batches:
                logger.info("Turso sync progress: %d/%d batches completed.", batch_idx, total_batches)

        logger.info("Turso Cloud synchronization finished successfully.")

    conn.close()
    return len(repaired_records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Repair permuted explanations in MedQuest.")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without modifying databases.")
    parser.add_argument("--no-turso", action="store_true", help="Skip remote Turso sync.")
    args = parser.parse_args()

    repair_permuted_explanations(dry_run=args.dry_run, sync_turso=not args.no_turso)
