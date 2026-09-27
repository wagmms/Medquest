#!/usr/bin/env python3
"""Regenerate all AI-generated flashcards using the improved algorithm.

Reads each flashcard's linked question from the database, re-generates the
front/back/context using the enhanced prompt + fallback, and updates the card
in-place (preserving FSRS scheduling state, report status, etc.).

Usage:
    cd app/backend
    .venv/bin/python ../../scripts/regenerate_cards.py [--dry-run] [--turso]
"""
import argparse
import json
import os
import sys
import time

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "backend"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "app", "backend", ".env"))

import sqlite3
from api.ai import generate_cloze_flashcard, _extract_medical_cloze_fallback


def get_local_db():
    db_path = os.path.join(os.path.dirname(__file__), "..", "app", "backend", "medquest.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_turso_client():
    """Create a Turso HTTP client for remote updates."""
    import libsql_client
    url = os.environ.get("TURSO_DATABASE_URL", "").replace("libsql://", "https://")
    token = os.environ.get("TURSO_AUTH_TOKEN", "")
    if not url or not token:
        return None
    return libsql_client.create_client_sync(url=url, auth_token=token)


def fetch_cards_to_regenerate(db):
    """Fetch all AI-generated flashcards with their question context."""
    return db.execute("""
        SELECT f.id, f.question_id, f.front AS old_front, f.back AS old_back,
               f.source_context AS old_context, f.user_id,
               q.stem, q.correct_letter, q.area, q.subtema, q.topic,
               e.explanation_text
        FROM flashcards f
        JOIN questions q ON f.question_id = q.id
        LEFT JOIN explanations e ON e.question_id = q.id
        WHERE f.is_ai_generated = 1 AND f.question_id IS NOT NULL
        ORDER BY f.id
    """).fetchall()


def fetch_alternatives(db, question_id, correct_letter):
    """Fetch correct and wrong alternative texts."""
    corr_letters = [c.strip().upper() for c in (correct_letter or "").split(",") if c.strip()]
    first_letter = corr_letters[0] if corr_letters else ""

    correct_alt = db.execute(
        "SELECT text, letter FROM alternatives WHERE question_id = ? AND (is_correct = 1 OR letter = ? OR letter = ?) "
        "ORDER BY is_correct DESC, letter ASC LIMIT 1",
        (question_id, correct_letter, first_letter)
    ).fetchone()

    # Try to find the wrong letter from the original card context or attempts
    wrong_alt = None
    attempt = db.execute(
        "SELECT selected_letter FROM attempts WHERE question_id = ? AND is_correct = 0 ORDER BY id DESC LIMIT 1",
        (question_id,)
    ).fetchone()
    wrong_letter = attempt["selected_letter"] if attempt else ""

    if wrong_letter:
        wrong_alt = db.execute(
            "SELECT text FROM alternatives WHERE question_id = ? AND letter = ?",
            (question_id, wrong_letter.strip().upper())
        ).fetchone()

    return correct_alt, wrong_alt, wrong_letter


def regenerate_card(row, db, use_ai=True):
    """Regenerate a single card, returning the new card data."""
    correct_alt, wrong_alt, wrong_letter = fetch_alternatives(
        db, row["question_id"], row["correct_letter"]
    )

    if not correct_alt:
        return None

    gen_func = generate_cloze_flashcard if use_ai else _extract_medical_cloze_fallback

    try:
        card_data = gen_func(
            stem=row["stem"],
            correct_text=correct_alt["text"],
            wrong_text=wrong_alt["text"] if wrong_alt else "",
            explanation=row["explanation_text"] or "",
            area=row["area"] or "",
            subtema=row["subtema"] or "",
            topic=row["topic"] or "",
            correct_letter=row["correct_letter"] or "",
            wrong_letter=wrong_letter or "",
        )
        return card_data
    except Exception as e:
        print(f"  ⚠️  Error generating card for question {row['question_id']}: {e}")
        # Fallback to deterministic
        try:
            card_data = _extract_medical_cloze_fallback(
                stem=row["stem"],
                correct_text=correct_alt["text"],
                wrong_text=wrong_alt["text"] if wrong_alt else "",
                explanation=row["explanation_text"] or "",
                area=row["area"] or "",
                subtema=row["subtema"] or "",
                topic=row["topic"] or "",
                correct_letter=row["correct_letter"] or "",
                wrong_letter=wrong_letter or "",
            )
            return card_data
        except Exception as e2:
            print(f"  ❌ Fallback also failed: {e2}")
            return None


def main():
    parser = argparse.ArgumentParser(description="Regenerate AI flashcards with improved algorithm")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without applying them")
    parser.add_argument("--turso", action="store_true", help="Also update Turso cloud database")
    parser.add_argument("--no-ai", action="store_true", help="Use only deterministic fallback (no AI calls)")
    args = parser.parse_args()

    db = get_local_db()
    cards = fetch_cards_to_regenerate(db)
    print(f"Found {len(cards)} AI-generated cards to regenerate.\n")

    if not cards:
        print("Nothing to do.")
        return

    updated = []
    for i, row in enumerate(cards, 1):
        print(f"[{i}/{len(cards)}] Card #{row['id']} (Question #{row['question_id']})")
        card_data = regenerate_card(row, db, use_ai=not args.no_ai)
        if not card_data:
            print("  ⏭️  Skipped (no correct alternative found)")
            continue

        new_front = card_data.get("front", "")
        new_back = card_data.get("back", "")
        new_context = card_data.get("context", "")

        # Show diff
        if new_front != row["old_front"]:
            print(f"  📝 Front changed: {len(row['old_front'])} → {len(new_front)} chars")
        if new_back != row["old_back"]:
            print(f"  📝 Back changed: {len(row['old_back'] or '')} → {len(new_back)} chars")

        updated.append((new_front, new_back, new_context, row["id"], row["user_id"]))

        if not args.no_ai:
            time.sleep(0.5)  # Rate limit for AI calls

    print(f"\n{'=' * 60}")
    print(f"Total: {len(updated)} cards to update out of {len(cards)}")

    if args.dry_run:
        print("DRY RUN — no changes applied.")
        return

    # Apply to local SQLite
    print("\nUpdating local SQLite...")
    for front, back, context, card_id, user_id in updated:
        db.execute("""
            UPDATE flashcards
            SET front = ?, back = ?, source_context = ?
            WHERE id = ? AND user_id = ?
        """, (front, back, context, card_id, user_id))
    db.commit()
    print(f"  ✅ {len(updated)} cards updated in local DB.")

    # Apply to Turso
    if args.turso:
        print("\nUpdating Turso cloud...")
        try:
            turso = get_turso_client()
            if turso:
                for front, back, context, card_id, user_id in updated:
                    turso.execute(
                        "UPDATE flashcards SET front = ?, back = ?, source_context = ? WHERE id = ? AND user_id = ?",
                        [front, back, context, card_id, user_id]
                    )
                print(f"  ✅ {len(updated)} cards updated in Turso.")
            else:
                print("  ⚠️  Turso credentials not found, skipping remote update.")
        except Exception as e:
            print(f"  ❌ Turso update failed: {e}")

    db.close()
    print("\nDone! 🎉")


if __name__ == "__main__":
    main()
