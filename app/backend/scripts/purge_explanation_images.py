#!/usr/bin/env python3
"""
MedQuest - Purge Explanation Images from question_images

Deletes explanation/resolution images that were mistakenly inserted into
the question_images table during historical ingestion passes.
Preserves genuine question images (clinical photos, ECGs, CTs, radiographs).
"""

import os
import sqlite3
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BACKEND_DIR, "medquest.db")


def purge_explanation_images(db_path=DB_PATH):
    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. Total count before
    cur.execute("SELECT COUNT(*) FROM question_images")
    total_before = cur.fetchone()[0]
    print(f"Total question_images before purge: {total_before}")

    # 2. Delete question_explanation_images
    cur.execute("DELETE FROM question_images WHERE file_path LIKE '%question_explanation_images%'")
    medway_exp_deleted = cur.rowcount
    print(f"Deleted medway explanation images: {medway_exp_deleted}")

    # 3. Delete non-medway images that appear in explanation_text (and NOT in question stem)
    cur.execute("""
        DELETE FROM question_images
        WHERE id IN (
            SELECT qi.id
            FROM question_images qi
            JOIN explanations e ON e.question_id = qi.question_id
            WHERE e.explanation_text LIKE '%' || qi.file_path || '%'
              AND NOT EXISTS (
                  SELECT 1 FROM questions q 
                  WHERE q.id = qi.question_id 
                    AND q.stem LIKE '%' || qi.file_path || '%'
              )
        )
    """)
    other_exp_deleted = cur.rowcount
    print(f"Deleted other external explanation images: {other_exp_deleted}")

    # 4. Question 10218 cleanup (USP-RP 2025 #8):
    # Ensure stem uses the official Medway CDN question image instead of temporary Google doc URL,
    # and remove duplicate Q63 attachment
    cdn_q8_url = "https://cdn.medway.com.br/media/question_images/ID162522_2025_institution-object-26_Q8/question.png"
    cur.execute("SELECT stem FROM questions WHERE id = 10218")
    row = cur.fetchone()
    if row and "googleusercontent" in row[0]:
        import re
        new_stem = re.sub(r'https://lh7-rt\.googleusercontent\.com/[^\)\s]+', cdn_q8_url, row[0])
        cur.execute("UPDATE questions SET stem = ? WHERE id = 10218", (new_stem,))
        print("Updated Q10218 stem to use Medway CDN question image.")

    # Remove duplicate Q63 image and googleusercontent from question_images for 10218
    cur.execute("""
        DELETE FROM question_images 
        WHERE question_id = 10218 
          AND (file_path LIKE '%ID205004%' OR file_path LIKE '%googleusercontent%')
    """)
    print(f"Cleaned redundant duplicate attachments for Q10218: {cur.rowcount} deleted.")

    conn.commit()

    # 5. Total count after
    cur.execute("SELECT COUNT(*) FROM question_images")
    total_after = cur.fetchone()[0]
    print(f"Total question_images after purge: {total_after} (deleted {total_before - total_after})")

    # Verification: check questions 10218 and 14286
    cur.execute("SELECT id, file_path FROM question_images WHERE question_id = 10218")
    print("Q10218 remaining question_images:", cur.fetchall())

    cur.execute("SELECT id, file_path FROM question_images WHERE question_id = 14286")
    print("Q14286 remaining question_images:", cur.fetchall())

    conn.close()
    return total_before - total_after


if __name__ == "__main__":
    purge_explanation_images()
