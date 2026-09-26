#!/usr/bin/env python3
"""
Automated Tier 1 Background Ingestion Daemon for MedQuest.
Continuously iterates through all Tier 1 exams in medway_catalog_mapped.json (years 2027 down to 2020),
extracts questions with structured explanations, normalizes images to Markdown ![imagem](url),
deduplicates against all existing medquest.db questions, and records progress in real time.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Paths
BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
CATALOG_PATH = DATA_DIR / "medway_catalog_mapped.json"
PROGRESS_FILE = DATA_DIR / "tier1_extraction_progress.json"
LOG_FILE = DATA_DIR / "tier1_daemon.log"

sys.path.insert(0, str(BACKEND_DIR / "scripts"))
from extract_medway import MedwayExtractor, MedwayClient

# Configure logging to both console and file
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("tier1_daemon")


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Could not read progress file: %s", e)
    return {
        "tier": 1,
        "completed_tracks": [],
        "failed_tracks": [],
        "total_questions_downloaded": 0,
        "total_ingested": 0,
        "total_duplicates_skipped": 0,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


def save_progress(progress: dict) -> None:
    progress["last_updated"] = datetime.now(timezone.utc).isoformat()
    try:
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Failed to save progress: %s", e)


def run_daemon() -> None:
    logger.info("=" * 65)
    logger.info("Starting Medway Tier 1 Background Ingestion Daemon")
    logger.info("=" * 65)

    if not CATALOG_PATH.exists():
        logger.error("Catalog %s not found. Build catalog first.", CATALOG_PATH)
        return

    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    # Filter Tier 1 (ordered by year DESC, question count DESC)
    tier1_exams = [e for e in catalog if e.get("tier") == 1]
    total_exams = len(tier1_exams)
    logger.info("Total Tier 1 exams in catalog: %d", total_exams)

    progress = load_progress()
    completed_set = set(progress.get("completed_tracks", []))
    logger.info("Already completed previously: %d tracks", len(completed_set))

    client = MedwayClient()
    extractor = MedwayExtractor(client=client)

    for idx, exam in enumerate(tier1_exams, start=1):
        tid = exam["track_id"]
        name = exam["name"]
        year = exam["year"]
        qc = exam.get("question_count", 0)
        inst = exam.get("institution_code", "UNKNOWN")

        if tid in completed_set:
            continue

        pct = (len(completed_set) / total_exams) * 100
        logger.info(
            "[%d/%d (%.1f%%)] Extracting: %s | Track: %s | Year: %s | ~%s Qs | %s",
            idx, total_exams, pct, name, tid, year, qc, inst
        )

        try:
            # 1. Download / load from cache
            pkg = extractor.extract_track(
                track_id=tid,
                category_name="exams",
                track_title=name,
                year=year,
                delay=0.0,
                resume=True,
                workers=2,
            )

            q_count = pkg.get("total_questions", 0)
            progress["total_questions_downloaded"] = progress.get("total_questions_downloaded", 0) + q_count

            # 2. Ingest into medquest.db with strict deduplication
            is_sim = "simulado" in name.lower()
            ed_status = "autoral" if is_sim else "oficial"
            ins, imgs, dups = extractor.import_package_to_db(
                pkg,
                editorial_status=ed_status,
                deduplicate=True,
            )

            progress["total_ingested"] = progress.get("total_ingested", 0) + ins
            progress["total_duplicates_skipped"] = progress.get("total_duplicates_skipped", 0) + dups

            completed_set.add(tid)
            progress.setdefault("completed_tracks", []).append(tid)

            logger.info(
                "  --> Result: %d ingested, %d duplicates skipped, %d images. (Total ingested so far: %d)",
                ins, dups, imgs, progress["total_ingested"]
            )

        except Exception as e:
            logger.error("  --> [FAIL] Error extracting Track %s (%s): %s", tid, name, e)
            progress.setdefault("failed_tracks", []).append({
                "track_id": tid,
                "name": name,
                "error": str(e),
                "failed_at": datetime.now(timezone.utc).isoformat(),
            })

        save_progress(progress)
        # Polite breathing delay between exams
        time.sleep(1.5)

    logger.info("=" * 65)
    logger.info("ALL TIER 1 EXAMS HAVE BEEN PROCESSED!")
    logger.info("Total Tracks Completed: %d / %d", len(completed_set), total_exams)
    logger.info("Total Questions Ingested: %d", progress.get("total_ingested", 0))
    logger.info("Total Duplicates Skipped: %d", progress.get("total_duplicates_skipped", 0))
    logger.info("=" * 65)

    # Automatically upgrade explanations on all skipped questions
    logger.info("Triggering post-ingestion explanation upgrade on skipped questions...")
    try:
        from scripts.backfill_skipped_explanations import backfill_explanations
        stats = backfill_explanations(dry_run=False)
        logger.info(
            "Backfilled explanations: %d updated, %d images linked.",
            stats.get("updated", 0), stats.get("images_added", 0)
        )
    except Exception as e:
        logger.error("Failed to backfill explanations on skipped questions: %s", e)


if __name__ == "__main__":
    run_daemon()
