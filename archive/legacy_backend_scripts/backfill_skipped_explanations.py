"""
Backfills and upgrades explanations for previously existing questions that were skipped during Medway ingestion.
Iterates over all extracted exam packages, matches skipped questions to existing questions in medquest.db,
and updates their explanation in the explanations table with Medway's 5-Pillar Golden Template.
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from scripts.extract_medway import (
    clean_html_to_markdown,
    extract_gabarito,
    format_medway_golden_explanation,
    normalize_text,
)

DB_PATH = BACKEND_DIR / "medquest.db"
EXAMS_DIR = BACKEND_DIR / "data" / "medway_extracted" / "exams"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backfill_explanations")


def get_db_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=60.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 60000")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def backfill_explanations(
    db_path: Path = DB_PATH,
    exams_dir: Path = EXAMS_DIR,
    dry_run: bool = False,
    override_all: bool = True,
) -> Dict[str, int]:
    """Scans all extracted exam packages and copies golden explanations to matching skipped questions in DB."""
    if not exams_dir.exists():
        logger.error("Exams directory does not exist: %s", exams_dir)
        return {"updated": 0, "images_added": 0, "skipped_same_source": 0}

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # 1. Build fast lookup index of existing questions: norm_stem[:180] -> (qid, source_file, correct_letter)
    logger.info("Indexing existing questions in %s...", db_path.name)
    cursor.execute("SELECT id, stem, source_file, correct_letter FROM questions WHERE stem IS NOT NULL")
    stem_to_qmeta: Dict[str, Tuple[int, str, str]] = {}
    for r in cursor.fetchall():
        st = r["stem"]
        if st and st.strip():
            n = normalize_text(st)[:180]
            if n:
                stem_to_qmeta[n] = (r["id"], r["source_file"] or "", (r["correct_letter"] or "").strip().upper())

    logger.info("Loaded %d distinct normalized question stems from DB.", len(stem_to_qmeta))

    # Pre-fetch existing images to prevent duplication: (question_id, file_path)
    cursor.execute("SELECT question_id, file_path FROM question_images")
    existing_images: Set[Tuple[int, str]] = {(r["question_id"], r["file_path"]) for r in cursor.fetchall()}

    track_files = sorted(glob.glob(str(exams_dir / "track_*.json")))
    logger.info("Found %d extracted track packages to inspect for explanation backfill.", len(track_files))

    updated_explanations = 0
    images_added = 0
    skipped_same_source = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    for idx, fpath in enumerate(track_files, start=1):
        try:
            with open(fpath, "r", encoding="utf-8") as fp:
                package = json.load(fp)
        except Exception as e:
            logger.warning("Failed to read %s: %s", fpath, e)
            continue

        track_name = package.get("name", f"Track_{package.get('track_id')}")
        track_id = package.get("track_id", 0)
        source_file_label = f"{track_name} [{track_id}]"

        for item in package.get("questions", []):
            q_detail = item.get("detail", {})
            raw_stem = q_detail.get("content") or ""
            stem = clean_html_to_markdown(raw_stem)
            if not stem or not stem.strip():
                continue

            norm = normalize_text(stem)[:180]
            if not norm or norm not in stem_to_qmeta:
                continue

            target_qid, target_source, target_correct = stem_to_qmeta[norm]

            # If this question was inserted directly by this exact track, skip backfill
            if target_source == source_file_label:
                skipped_same_source += 1
                continue

            exp_detail = item.get("explanation")
            if not exp_detail:
                continue

            opts = q_detail.get("options", [])
            is_discursive = bool(q_detail.get("question_type") == "d" or len(opts) == 0)
            if not is_discursive and target_correct and target_correct in "ABCDE":
                correct_letter = target_correct
            else:
                correct_letter = extract_gabarito(exp_detail, opts, q_detail=q_detail) if not is_discursive else "A"
            golden_exp = format_medway_golden_explanation(
                exp_detail, opts, correct_letter, is_discursive=is_discursive
            )

            if not golden_exp or not golden_exp.strip():
                continue

            if not dry_run:
                # Update/Replace explanation with rich Medway Golden Explanation
                cursor.execute(
                    """
                    INSERT INTO explanations (question_id, explanation_text, generated_at, reviewed_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(question_id) DO UPDATE SET
                        explanation_text = excluded.explanation_text,
                        generated_at = excluded.generated_at,
                        reviewed_at = excluded.reviewed_at
                """,
                    (target_qid, golden_exp, now_iso, now_iso),
                )
                updated_explanations += 1

                # Extract and associate images strictly from question stem or question attachments (NEVER from explanation)
                img_urls = re.findall(r"!\[.*?\]\((https?://[^\)]+)\)", stem)
                img_tags = re.findall(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', raw_stem)

                obj_imgs = []
                for it in q_detail.get("images", []):
                    if isinstance(it, dict):
                        u = it.get("image") or it.get("url") or it.get("file")
                        if u:
                            obj_imgs.append(u)
                    elif isinstance(it, str) and it.startswith("http"):
                        obj_imgs.append(it)

                all_imgs = list(dict.fromkeys(img_urls + img_tags + obj_imgs))

                for order_idx, img_url in enumerate(all_imgs):
                    if (target_qid, img_url) not in existing_images:
                        cursor.execute(
                            "INSERT INTO question_images (question_id, file_path, order_index) VALUES (?, ?, ?)",
                            (target_qid, img_url, order_idx),
                        )
                        existing_images.add((target_qid, img_url))
                        images_added += 1
            else:
                updated_explanations += 1

        if idx % 25 == 0 and not dry_run:
            conn.commit()
            logger.info(
                "[%d/%d packages processed] Updated %d explanations, added %d images so far.",
                idx, len(track_files), updated_explanations, images_added
            )

    if not dry_run:
        conn.commit()

    conn.close()

    logger.info("=" * 65)
    logger.info("EXPLANATION BACKFILL COMPLETED SUCCESSFULLY!")
    logger.info("Total Explanations Upgraded: %d", updated_explanations)
    logger.info("Total Images Linked: %d", images_added)
    logger.info("Skipped Same Source: %d", skipped_same_source)
    logger.info("=" * 65)

    return {
        "updated": updated_explanations,
        "images_added": images_added,
        "skipped_same_source": skipped_same_source,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill explanations for skipped questions.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    args = parser.parse_args()
    backfill_explanations(dry_run=args.dry_run)
