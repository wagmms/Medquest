"""Rotas de Curadoria e Taxonomia: taxonomia oficial, reclassificação e exclusão administrativa."""
import json
import os
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request

from .auth import require_curator
from .db import db_transaction, get_db

bp = Blueprint("curation", __name__)


@bp.route("/taxonomy", methods=["GET"])
def get_taxonomy():
    """Retorna a taxonomia canônica oficial dos 170 módulos estruturados por grande área."""
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tax_path = os.path.join(backend_dir, "data", "canonical_taxonomy.json")
    if os.path.exists(tax_path):
        with open(tax_path, "r", encoding="utf-8") as f:
            tax = json.load(f)
            return jsonify(tax)

    # Fallback construído diretamente do banco
    db = get_db()
    rows = db.execute("""
        SELECT area, subtema, subtema_id 
        FROM questions 
        WHERE subtema IS NOT NULL AND subtema != ''
        GROUP BY area, subtema
        ORDER BY area, subtema
    """).fetchall()
    fallback_tax = {}
    for r in rows:
        area, subtema, sid = r["area"], r["subtema"], r["subtema_id"]
        if area not in fallback_tax:
            fallback_tax[area] = {}
        fallback_tax[area][subtema] = sid
    return jsonify(fallback_tax)


@bp.route("/questions/<int:qid>/classification", methods=["PATCH", "PUT"])
@require_curator
def update_question_classification(qid):
    """Atualiza a classificação (área, subtema, tópico) de uma questão. Acesso restrito a curadoria."""
    data = request.get_json(force=True) or {}
    area = (data.get("area") or "").strip()
    subtema = (data.get("subtema") or "").strip()
    topic = (data.get("topic") or subtema).strip()

    if not area or not subtema:
        return jsonify({"error": "Parâmetros 'area' e 'subtema' são obrigatórios"}), 400

    db = get_db()
    q = db.execute("SELECT id FROM questions WHERE id = ?", (qid,)).fetchone()
    if not q:
        return jsonify({"error": "Questão não encontrada"}), 404

    # Resolve subtema_id correspondente a partir da taxonomia canônica
    subtema_id = None
    tax_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "canonical_taxonomy.json")
    if os.path.exists(tax_path):
        try:
            with open(tax_path, "r", encoding="utf-8") as f:
                tax_data = json.load(f)
                if area in tax_data and subtema in tax_data[area]:
                    subtema_id = tax_data[area][subtema]
        except Exception:
            pass

    cols = {r["name"] for r in db.execute("PRAGMA table_info(questions)").fetchall()}
    has_subtema_id = "subtema_id" in cols
    has_subtema_orig = "subtema_orig" in cols

    with db_transaction(db, immediate=True):
        if has_subtema_id and has_subtema_orig:
            db.execute("""
                UPDATE questions
                SET area = ?,
                    subtema = ?,
                    subtema_id = COALESCE(?, subtema_id),
                    topic = ?,
                    subtema_orig = ?
                WHERE id = ?
            """, (area, subtema, subtema_id, topic, subtema, qid))
        elif has_subtema_id:
            db.execute("""
                UPDATE questions
                SET area = ?,
                    subtema = ?,
                    subtema_id = COALESCE(?, subtema_id),
                    topic = ?
                WHERE id = ?
            """, (area, subtema, subtema_id, topic, qid))
        else:
            db.execute("""
                UPDATE questions
                SET area = ?,
                    subtema = ?,
                    topic = ?
                WHERE id = ?
            """, (area, subtema, topic, qid))

    from .questions import invalidate_user_caches, meta_cache
    meta_cache.cache.clear()
    invalidate_user_caches(getattr(g, "user_id", None))

    return jsonify({
        "success": True,
        "question": {
            "id": qid,
            "area": area,
            "subtema": subtema,
            "subtema_id": subtema_id,
            "topic": topic
        }
    })


@bp.route("/questions/<int:qid>", methods=["DELETE"])
@require_curator
def delete_question(qid):
    """Exclui permanentemente uma questão e todas as suas referências associadas.
    Acesso restrito exclusivamente ao curador / administrador configurado.
    """
    user_email = (getattr(g, "user_email", None) or "").strip().lower()

    db = get_db()
    q = db.execute("SELECT id FROM questions WHERE id = ?", (qid,)).fetchone()
    if not q:
        return jsonify({"error": "Questão não encontrada"}), 404

    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

    with db_transaction(db, immediate=True):
        if "alternatives" in tables:
            db.execute("DELETE FROM alternatives WHERE question_id = ?", (qid,))
        if "explanations" in tables:
            db.execute("DELETE FROM explanations WHERE question_id = ?", (qid,))
        if "question_images" in tables:
            db.execute("DELETE FROM question_images WHERE question_id = ?", (qid,))
        if "attempts" in tables:
            db.execute("DELETE FROM attempts WHERE question_id = ?", (qid,))
        if "favorites" in tables:
            db.execute("DELETE FROM favorites WHERE question_id = ?", (qid,))
        if "spaced_repetition" in tables:
            db.execute("DELETE FROM spaced_repetition WHERE question_id = ?", (qid,))
        if "classification_proposals" in tables:
            db.execute("DELETE FROM classification_proposals WHERE question_id = ?", (qid,))
        if "reclassification_audit" in tables:
            db.execute("DELETE FROM reclassification_audit WHERE question_id = ?", (qid,))
        if "flashcards" in tables:
            db.execute("UPDATE flashcards SET question_id = NULL WHERE question_id = ?", (qid,))
        if "questions_fts" in tables:
            try:
                db.execute("DELETE FROM questions_fts WHERE rowid = ?", (qid,))
            except Exception:
                pass
        db.execute("DELETE FROM questions WHERE id = ?", (qid,))

        # Registra tombstone para sincronização bidirecional segura (SQLite <-> Turso)
        db.execute("""
            CREATE TABLE IF NOT EXISTS deleted_questions (
                question_id INTEGER PRIMARY KEY,
                deleted_at TEXT,
                deleted_by TEXT
            )
        """)
        now_iso = datetime.now(timezone.utc).isoformat()
        db.execute(
            "INSERT OR REPLACE INTO deleted_questions (question_id, deleted_at, deleted_by) VALUES (?, ?, ?)",
            (qid, now_iso, user_email),
        )

    from .questions import invalidate_user_caches, meta_cache
    meta_cache.cache.clear()
    invalidate_user_caches(getattr(g, "user_id", None))

    return jsonify({
        "success": True,
        "message": f"Questão #{qid} excluída com sucesso.",
        "id": qid
    })
