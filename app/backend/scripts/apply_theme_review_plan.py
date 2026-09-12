"""Apply a complete manual review of one canonical theme.

The plan lists every question initially assigned to the source theme and only
the questions that must move.  Questions not in ``moves`` are audited as
explicitly retained.  The command is dry-run by default.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
from pathlib import Path
from uuid import uuid4

from apply_theme_review_batch import (
    BACKUPS,
    DATABASE,
    REPORTS,
    apply_batch,
    canonical_destinations,
)


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PLAN = ROOT / "docs" / "audits" / "theme_abdome_agudo_inflamatorio_review_plan.json"


def load_plan(path: Path) -> dict:
    plan = json.loads(path.read_text(encoding="utf-8"))
    source = plan.get("source") or {}
    if not all(isinstance(source.get(key), str) and source[key].strip() for key in ("area", "subtema")):
        raise ValueError("Plano precisa informar a área e o tema-fonte.")
    ids = plan.get("reviewed_question_ids")
    if not isinstance(ids, list) or not ids or any(not isinstance(qid, int) for qid in ids) or len(set(ids)) != len(ids):
        raise ValueError("reviewed_question_ids deve conter IDs inteiros únicos.")
    moves = plan.get("moves") or []
    move_ids = [item.get("question_id") for item in moves]
    if any(not isinstance(qid, int) for qid in move_ids) or len(set(move_ids)) != len(move_ids) or not set(move_ids) <= set(ids):
        raise ValueError("Movimentações inválidas no plano.")
    return plan


def decisions_for_plan(connection: sqlite3.Connection, plan: dict) -> list[dict[str, str | int]]:
    source = plan["source"]
    rows = connection.execute(
        "SELECT id, area, subtema FROM questions WHERE area = ? AND subtema = ? ORDER BY id",
        (source["area"], source["subtema"]),
    ).fetchall()
    actual_ids = {row[0] for row in rows}
    expected_ids = set(plan["reviewed_question_ids"])
    if actual_ids != expected_ids:
        raise ValueError(
            "A composição do tema mudou desde a revisão. "
            f"Faltam no banco: {sorted(expected_ids - actual_ids)}; não previstos: {sorted(actual_ids - expected_ids)}"
        )

    destinations, _ = canonical_destinations()
    move_by_id = {item["question_id"]: item for item in plan.get("moves", [])}
    decisions = []
    for question_id, area, subtema in rows:
        move = move_by_id.get(question_id)
        if move:
            target_area, target_subtema, rationale = move["area"], move["subtema"], move["rationale"]
        else:
            target_area, target_subtema = area, subtema
            rationale = "Revisão manual: enunciado e alternativas confirmam o tema atual."
        if (target_area, target_subtema) not in destinations:
            raise ValueError(f"Destino não canônico para questão {question_id}: {(target_area, target_subtema)}")
        decisions.append({
            "question_id": question_id,
            "area": target_area,
            "subtema": target_subtema,
            "rationale": rationale,
        })
    return decisions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--apply", action="store_true", help="Aplica após backup e validações.")
    args = parser.parse_args()

    plan_path = args.plan.resolve()
    plan = load_plan(plan_path)
    with sqlite3.connect(DATABASE) as connection:
        decisions = decisions_for_plan(connection, plan)
        if not args.apply:
            print(json.dumps({"mode": "dry-run", "questions_reviewed": len(decisions), "moves": len(plan.get("moves", [])), "status": "validated"}, ensure_ascii=False))
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
        "plan": str(plan_path.relative_to(ROOT)),
        "backup": str(backup.relative_to(ROOT)),
        "questions_reviewed": len(decisions),
        "questions_reclassified": len(plan.get("moves", [])),
    }
    output = REPORTS / f"human-theme-review-{timestamp}.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**report, "report": str(output.relative_to(ROOT))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
