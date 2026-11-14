"""Rotas de IA: Preceptor IA e diagnósticos operacionais do provedor Gemini."""
from urllib.parse import quote

from flask import Blueprint, g, jsonify, request

from . import ai
from .auth import require_auth
from .db import get_db
from .gemini_pool import provider_status

bp = Blueprint("ai_routes", __name__)


@bp.route("/questions/<int:question_id>/ask_ai", methods=["POST"])
@require_auth
def ask_question_ai(question_id):
    db = get_db()
    q = db.execute("""
        SELECT q.id, q.stem, q.area, q.subtema, q.topic,
               e.explanation_text
        FROM questions q
        LEFT JOIN explanations e ON q.id = e.question_id
        WHERE q.id = ?
    """, (question_id,)).fetchone()

    if not q:
        return jsonify({"error": "Questão não encontrada"}), 404

    alts = db.execute("""
        SELECT letter, text, is_correct
        FROM alternatives
        WHERE question_id = ?
        ORDER BY letter
    """, (question_id,)).fetchall()

    alts_list = [{"letter": a["letter"], "text": a["text"], "is_correct": bool(a["is_correct"])} for a in alts]
    correct_alt = next((a for a in alts_list if a["is_correct"]), None)
    correct_letter = correct_alt["letter"] if correct_alt else ""
    correct_text = correct_alt["text"] if correct_alt else ""

    body = request.get_json(silent=True) or {}
    user_question = body.get("user_question", "")
    user_letter = body.get("user_letter", "")
    chat_history = body.get("chat_history", [])

    user_id = getattr(g, "user_id", "1")
    result = ai.ask_preceptor_ai(
        stem=q["stem"],
        alternatives=alts_list,
        correct_letter=correct_letter,
        correct_text=correct_text,
        user_letter=user_letter,
        user_question=user_question,
        explanation=q["explanation_text"] or "",
        area=q["area"] or "",
        subtema=q["subtema"] or q["topic"] or "",
        chat_history=chat_history if isinstance(chat_history, list) else None,
        user_id=user_id,
        db=db,
        question_id=question_id
    )

    if result.get("source") == "fallback":
        return jsonify({
            "error": "Preceptor IA temporariamente indisponível. Tente novamente em instantes.",
            "source": "fallback"
        }), 503

    return jsonify(result)


@bp.route("/ai/health", methods=["GET"])
@require_auth
def ai_health():
    status = provider_status()
    gemini = status["providers"]["gemini"]
    status["model"] = gemini["models"][0] if gemini["models"] else None
    status["total_keys"] = gemini["keys"]
    return jsonify(status)


@bp.route("/ai/preceptor_focus", methods=["GET", "POST"])
@require_auth
def preceptor_dashboard_focus():
    """
    Retorna o diagnóstico adaptativo e o plano de ataque do Preceptor IA
    para o Dashboard do estudante. Suporta modo rápido (apenas métricas) e
    modo com parecer clínico de IA.
    """
    db = get_db()
    user_id = getattr(g, "user_id", "1")

    body = request.get_json(silent=True) or {}
    generate_ai = body.get("generate_ai", True)
    if request.method == "GET":
        ai_arg = request.args.get("ai", "1")
        generate_ai = ai_arg in ("1", "true", "True")

    if not generate_ai:
        from .adaptive_tools import get_student_weak_topics
        diag_data = get_student_weak_topics(db, user_id, limit=5)
        weak_list = diag_data.get("weak_topics", [])
        if weak_list:
            top_weak = weak_list[0]
            rec_subtema = top_weak.get("topic", "Clínica Médica")
            rec_area = top_weak.get("area", "")
            rec_url = f"/estudar?subtema={quote(rec_subtema)}&limit=15"
        else:
            rec_subtema = "Síndromes Coronarianas Agudas"
            rec_area = "Clínica Médica"
            rec_url = "/estudar?area=Clinica%20Medica&limit=15"

        return jsonify({
            "diagnostic_data": diag_data,
            "recommended_topic": {
                "subtema": rec_subtema,
                "area": rec_area,
                "practice_url": rec_url,
            },
            "source": "database_snapshot"
        })

    result = ai.generate_preceptor_dashboard_focus(db, user_id)
    return jsonify(result)

