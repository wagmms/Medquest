"""Apply a manually reviewed classification batch with a SQLite audit trail.

The command is dry-run by default.  ``--apply`` backs up the database, checks
that the decision file covers precisely the current out-of-catalogue questions,
then updates classifications and writes an adjudication record per question.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sqlite3
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[3]
DATABASE = ROOT / "app" / "backend" / "medquest.db"
TAXONOMY = ROOT / "canonical_taxonomy_170.json"
CANONICAL_MAP = ROOT / "app" / "backend" / "data" / "canonical_taxonomy.json"
MIGRATION = ROOT / "app" / "backend" / "migrations" / "006_classification_review.sql"
DECISIONS = ROOT / "docs" / "audits" / "noncanonical_urology_review_decisions.json"
BACKUPS = ROOT / "backups" / "taxonomy-reclassification"
REPORTS = ROOT / "docs" / "audits"


def load_decisions(path: Path) -> list[dict[str, str | int]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    decisions = raw.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        raise ValueError("Arquivo de decisões não contém uma lista não vazia.")
    ids = [item.get("question_id") for item in decisions]
    if any(not isinstance(value, int) for value in ids) or len(set(ids)) != len(ids):
        raise ValueError("Cada decisão deve ter um question_id inteiro único.")
    for item in decisions:
        if not all(isinstance(item.get(key), str) and item[key].strip() for key in ("area", "subtema", "rationale")):
            raise ValueError(f"Decisão inválida para questão {item['question_id']}.")
    return decisions


def canonical_destinations() -> tuple[set[tuple[str, str]], dict[str, dict[str, str]]]:
    taxonomy = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    destinations = {(area, subtema) for area, subtemas in taxonomy.items() for subtema in subtemas}
    if len(destinations) != 170:
        raise ValueError(f"Taxonomia canônica inválida: {len(destinations)} temas.")
    canonical_map = json.loads(CANONICAL_MAP.read_text(encoding="utf-8"))
    map_destinations = {(area, subtema) for area, subtemas in canonical_map.items() for subtema in subtemas}
    if map_destinations != destinations:
        raise ValueError("canonical_taxonomy.json não está sincronizado com a taxonomia de 170 temas.")
    return destinations, canonical_map


def validate_batch(connection: sqlite3.Connection, decisions: list[dict[str, str | int]]) -> None:
    destinations, _ = canonical_destinations()
    invalid = [(item["area"], item["subtema"]) for item in decisions if (item["area"], item["subtema"]) not in destinations]
    if invalid:
        raise ValueError(f"Destinos fora da taxonomia canônica: {invalid}")

    decision_ids = {item["question_id"] for item in decisions}
    placeholders = ",".join("?" for _ in decision_ids)
    found = {row[0] for row in connection.execute(f"SELECT id FROM questions WHERE id IN ({placeholders})", tuple(decision_ids))}
    if found != decision_ids:
        raise ValueError(f"Questões ausentes: {sorted(decision_ids - found)}")

    rows = connection.execute("SELECT id, area, subtema FROM questions").fetchall()
    current_outside = {row[0] for row in rows if (row[1], row[2]) not in destinations}
    if current_outside != decision_ids:
        raise ValueError(
            "O lote não cobre exatamente as questões fora do catálogo. "
            f"Faltam: {sorted(current_outside - decision_ids)}; extras: {sorted(decision_ids - current_outside)}"
        )


def apply_batch(connection: sqlite3.Connection, decisions: list[dict[str, str | int]], run_id: str) -> None:
    _, canonical_map = canonical_destinations()
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    input_hash = hashlib.sha256(json.dumps(decisions, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    connection.executescript(MIGRATION.read_text(encoding="utf-8"))
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            """INSERT INTO classification_runs
               (id, taxonomy_version, pipeline_version, input_hash, status, created_at, notes)
               VALUES (?, 'canonical_taxonomy_170.json', 'human-theme-review-v1', ?, 'completed', ?, ?)""",
            (run_id, input_hash, now, "Revisão manual das questões fora do catálogo canônico."),
        )
        for item in decisions:
            question_id = item["question_id"]
            area = item["area"]
            subtema = item["subtema"]
            rationale = item["rationale"]
            old = connection.execute("SELECT area, subtema FROM questions WHERE id = ?", (question_id,)).fetchone()
            proposal = connection.execute(
                """INSERT INTO classification_proposals
                   (run_id, question_id, reviewer_role, decision, proposed_area, proposed_subtema,
                    confidence, evidence, alternatives_json, status, created_at)
                   VALUES (?, ?, 'adjudicator', 'classify', ?, ?, 1.0, ?, '[]', 'accepted', ?)""",
                (run_id, question_id, area, subtema, rationale, now),
            )
            connection.execute(
                """INSERT INTO classification_reviews
                   (proposal_id, reviewer, decision, final_area, final_subtema, rationale, reviewed_at)
                   VALUES (?, 'codex-theme-review', 'override', ?, ?, ?, ?)""",
                (proposal.lastrowid, area, subtema, rationale, now),
            )
            connection.execute(
                "UPDATE questions SET area = ?, subtema = ?, subtema_id = ? WHERE id = ?",
                (area, subtema, canonical_map[area][subtema], question_id),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Aplica o lote após backup e validações.")
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    args = parser.parse_args()

    decisions = load_decisions(args.decisions)
    with sqlite3.connect(DATABASE) as connection:
        validate_batch(connection, decisions)
        if not args.apply:
            print(json.dumps({"mode": "dry-run", "questions": len(decisions), "status": "validated"}, ensure_ascii=False))
            return 0

        timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        BACKUPS.mkdir(parents=True, exist_ok=True)
        backup = BACKUPS / f"medquest-pre-theme-review-{timestamp}.db"
        with sqlite3.connect(backup) as destination:
            connection.backup(destination)
        if not backup.exists() or backup.stat().st_size == 0:
            raise RuntimeError("Backup SQLite não foi criado corretamente.")

        run_id = f"human-theme-review-{timestamp}-{uuid4().hex[:8]}"
        apply_batch(connection, decisions, run_id)
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"Falha de integridade após a aplicação: {integrity}")

    REPORTS.mkdir(parents=True, exist_ok=True)
    report = {
        "run_id": run_id,
        "backup": str(backup.relative_to(ROOT)),
        "questions_reclassified": len(decisions),
        "decision_file": str(args.decisions.relative_to(ROOT)),
    }
    path = REPORTS / f"human-theme-review-{timestamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**report, "report": str(path.relative_to(ROOT))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
