"""User-owned activity progress, separate from learning-performance metrics."""
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request

from .db import db_transaction, get_db
from .services.taxonomy import find_area_for_subtema

bp = Blueprint("themes", __name__)


def _theme_state(db, subtema):
    row = db.execute(
        "SELECT theory_completed, study_path, updated_at FROM theme_progress WHERE user_id=? AND subtema=?",
        (g.user_id, subtema),
    ).fetchone()
    cards = db.execute(
        """SELECT COUNT(*) AS total,
                  COALESCE(SUM(CASE WHEN f.next_review_date <= ? THEN 1 ELSE 0 END), 0) AS due
           FROM flashcards f JOIN questions q ON q.id=f.question_id
           WHERE f.user_id=? AND q.subtema=?
             AND (f.report_status IS NULL OR TRIM(f.report_status)='')""",
        (datetime.now(timezone.utc).isoformat(), g.user_id, subtema),
    ).fetchone()
    return {
        "subtema": subtema,
        "theory_completed": bool(row["theory_completed"]) if row else False,
        "study_path": row["study_path"] if row else "essential",
        "updated_at": row["updated_at"] if row else None,
        "flashcards_total": cards["total"],
        "flashcards_due": cards["due"],
    }


@bp.route("/themes/progress", methods=["GET", "PUT"])
def theme_progress():
    subtema = request.args.get("subtema", "")
    if not find_area_for_subtema(subtema):
        return jsonify({"error": "Tema não encontrado no catálogo."}), 404
    db = get_db()
    if request.method == "PUT":
        payload = request.get_json(silent=True)
        if (not isinstance(payload, dict)
                or set(payload) != {"theory_completed", "study_path"}
                or type(payload.get("theory_completed")) is not bool
                or payload.get("study_path") not in ("essential", "complete")):
            return jsonify({"error": "Informe theory_completed (booleano) e study_path (essential ou complete)."}), 400
        with db_transaction(db):
            db.execute(
                """INSERT INTO theme_progress (user_id, subtema, theory_completed, study_path, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(user_id, subtema) DO UPDATE SET
                     theory_completed=excluded.theory_completed,
                     study_path=excluded.study_path, updated_at=excluded.updated_at""",
                (g.user_id, subtema, int(payload["theory_completed"]), payload["study_path"],
                 datetime.now(timezone.utc).isoformat()),
            )
    return jsonify(_theme_state(db, subtema))
