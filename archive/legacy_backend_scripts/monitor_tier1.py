#!/usr/bin/env python3
"""
Interactive Terminal Dashboard for MedQuest Tier 1 Ingestion.
Displays real-time animated progress, database statistics, rate limit health,
and estimated completion time with 1-second auto-refresh.
"""

import os
import sys
import time
import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
LOG_FILE = DATA_DIR / "tier1_daemon.log"
PROGRESS_FILE = DATA_DIR / "tier1_extraction_progress.json"
CATALOG_FILE = DATA_DIR / "medway_catalog_mapped.json"
DB_PATH = BACKEND_DIR / "medquest.db"

SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

def get_daemon_status():
    """Checks if run_tier1_daemon.py is actively running in background."""
    try:
        out = subprocess.check_output(["pgrep", "-f", "run_tier1_daemon.py"]).decode().strip()
        pids = out.splitlines()
        return True, pids[0] if pids else "RUNNING"
    except Exception:
        return False, None

def get_db_stats():
    """Reads real-time stats directly from medquest.db without locking."""
    if not DB_PATH.exists():
        return 0, 0, 0, 0
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        c = conn.cursor()
        c.execute("SELECT count(*) FROM questions")
        total_q = c.fetchone()[0]
        c.execute("SELECT count(*) FROM question_images")
        total_img = c.fetchone()[0]
        c.execute("SELECT count(*) FROM questions WHERE stem IS NULL OR trim(stem) = ''")
        empty_stems = c.fetchone()[0]
        c.execute("SELECT count(DISTINCT source_file) FROM questions")
        distinct_exams = c.fetchone()[0]
        conn.close()
        return total_q, total_img, empty_stems, distinct_exams
    except Exception:
        return 0, 0, 0, 0

def load_progress():
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def get_recent_log_lines(n=8):
    if not LOG_FILE.exists():
        return []
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
            return lines[-n:]
    except Exception:
        return []

def render_progress_bar(current, total, width=40):
    if total <= 0:
        return "[?]"
    pct = min(1.0, current / total)
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {current}/{total} ({pct*100:.1f}%)"

def main():
    tick = 0
    start_time = time.time()
    total_tier1_exams = 676
    
    # Try reading catalog for exact count
    if CATALOG_FILE.exists():
        try:
            with open(CATALOG_FILE, "r") as f:
                cat = json.load(f)
            total_tier1_exams = len([e for e in cat if e.get("tier") == 1])
        except Exception:
            pass

    print("\033[?25l", end="") # hide cursor
    
    try:
        while True:
            spin_char = SPINNER[tick % len(SPINNER)]
            tick += 1
            
            # 1. Fetch info
            is_running, pid = get_daemon_status()
            prog = load_progress()
            completed_tracks = prog.get("completed_tracks", [])
            completed_count = len(completed_tracks)
            total_ingested = prog.get("total_ingested", 0)
            total_dups = prog.get("total_duplicates_skipped", 0)
            total_dl = prog.get("total_questions_downloaded", 0)
            
            db_q, db_img, db_empty, db_exams = get_db_stats()
            log_lines = get_recent_log_lines(10)
            
            # Determine currently running exam from log
            current_exam = "Waiting for next track..."
            for line in reversed(log_lines):
                if "Extracting:" in line:
                    current_exam = line.split("Extracting:")[-1].strip()
                    break

            # Calculate speed and ETA
            elapsed = time.time() - start_time
            q_rate = total_ingested / max(elapsed, 1) # simple estimate
            remaining_exams = max(0, total_tier1_exams - completed_count)
            # Estimate ~22s per exam with current 30ms-50ms pacing
            eta_seconds = remaining_exams * 22
            eta_hours = eta_seconds // 3600
            eta_mins = (eta_seconds % 3600) // 60

            # Clear screen
            os.system("clear")
            
            status_badge = "\033[92m● ACTIVE\033[0m" if is_running else "\033[91m● STOPPED\033[0m"
            stem_badge = "\033[92m✔ 0 EMPTY (100% CLEAN)\033[0m" if db_empty == 0 else f"\033[91m✖ {db_empty} EMPTY\033[0m"

            print("=" * 80)
            print(f" {spin_char}  \033[1mMEDQUEST — TIER 1 BACKGROUND INGESTION MONITOR\033[0m   (Live Refresh: 1s)")
            print("=" * 80)
            print(f" Status:     {status_badge} (PID: {pid or 'N/A'})")
            print(f" Target:     Tier 1 Exams (≥ 2020: USP, UNICAMP, UNIFESP, ENARE, etc.)")
            print(f" Time:       {datetime.now().strftime('%H:%M:%S')} | Elapsed: {int(elapsed//60)}m {int(elapsed%60)}s | ETA: ~{int(eta_hours)}h {int(eta_mins)}m")
            print("-" * 80)
            
            print(f"\033[1mTIER 1 EXAM PROGRESS:\033[0m")
            print(f"  {render_progress_bar(completed_count, total_tier1_exams, width=46)}")
            print(f"  Remaining Exams:  {remaining_exams} of {total_tier1_exams}")
            print("-" * 80)

            print(f"\033[1mLIVE DATABASE METRICS (medquest.db):\033[0m")
            print(f"  Total Questions:   \033[1;36m{db_q:,}\033[0m questions in database")
            print(f"  Images Indexed:    \033[1;33m{db_img:,}\033[0m images (Markdown formatted)")
            print(f"  Distinct Exams:    {db_exams} official source exams")
            print(f"  Data Integrity:    {stem_badge}")
            print(f"  Duplicates Saved:  {total_dups:,} duplicate questions skipped (official tests protected)")
            print("-" * 80)

            print(f"\033[1mCURRENTLY PROCESSING:\033[0m")
            print(f"  \033[94m➔ {current_exam}\033[0m")
            print("-" * 80)

            print(f"\033[1mRECENT DAEMON ACTIVITY (Last Completed Tracks):\033[0m")
            activity_lines = [l for l in log_lines if "Result:" in l or "Extracting:" in l][-4:]
            if activity_lines:
                for l in activity_lines:
                    # Clean timestamp prefix for tighter layout
                    clean_l = l.split("[INFO]")[-1].strip() if "[INFO]" in l else l
                    print(f"  • {clean_l}")
            else:
                print("  • Monitoring active...")
                
            print("=" * 80)
            print(" \033[90mPress Ctrl+C to close monitor (daemon continues running uninterrupted)\033[0m")
            
            time.sleep(1.0)
            
    except KeyboardInterrupt:
        print("\033[?25h") # restore cursor
        print("\n[MONITOR CLOSED] Background daemon is still actively extracting. Goodbye!\n")
    finally:
        print("\033[?25h", end="")

if __name__ == "__main__":
    main()
