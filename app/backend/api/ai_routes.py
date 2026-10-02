"""Rotas de IA: Preceptor IA, diagnósticos de provedores, prescrição de estudo e síntese de explicação."""
from flask import Blueprint, g, jsonify, request

from . import ai
from .db import db_transaction, get_db
from .schemas import (
    PrescribeStudyIn,
    SynthesizeExplanationIn,
    ValidationError,
    validation_errors,
)
from .universal_pool import provider_status

bp = Blueprint("ai_routes", __name__)


@bp.route("/questions/<int:question_id>/ask_ai", methods=["POST"])
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

    user_id = getattr(g, "user_id", None)
    if not user_id:
        guest_id = request.headers.get("X-Guest-ID") or request.headers.get("x-internal-guest-id")
        if guest_id:
            user_id = f"guest:{guest_id.lower()}"
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
        db=db
    )

    # A resposta determinística é útil internamente como último recurso, mas
    # não é uma resposta do Preceptor. Retornar sucesso nesse caso fazia a UI
    # apresentar o texto genérico como se tivesse sido gerado pela IA.
    if result.get("source") == "fallback":
        return jsonify({
            "error": "Preceptor IA temporariamente indisponível. Tente novamente em instantes.",
            "source": "fallback"
        }), 503

    return jsonify(result)


@bp.route("/ai/health", methods=["GET"])
def ai_health():
    status = provider_status()
    # Mantém os campos legados consumidos por clientes anteriores sem gastar
    # quota fazendo pings reais em todas as chaves.
    gemini = status["providers"]["gemini"]
    status["model"] = gemini["models"][0] if gemini["models"] else None
    status["total_keys"] = gemini["keys"]
    return jsonify(status)


@bp.route("/ai/preceptor_focus", methods=["GET", "POST"])
def preceptor_dashboard_focus():
    """
    Retorna o diagnóstico adaptativo e o plano de ataque do Preceptor IA
    para o Dashboard do estudante. Suporta modo rápido (apenas métricas) e
    modo com parecer clínico de IA.
    """
    db = get_db()
    user_id = getattr(g, "user_id", None)
    if not user_id:
        guest_id = request.headers.get("X-Guest-ID") or request.headers.get("x-internal-guest-id")
        if guest_id:
            user_id = f"guest:{guest_id.lower()}"

    body = request.get_json(silent=True) or {}
    generate_ai = body.get("generate_ai", True)
    if request.method == "GET":
        ai_arg = request.args.get("ai", "1")
        generate_ai = ai_arg in ("1", "true", "True")

    if not generate_ai:
        from .adaptive_tools import get_student_weak_topics
        from urllib.parse import quote
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



@bp.route("/ai/prescribe_study", methods=["POST"])
def prescribe_study():
    try:
        data = PrescribeStudyIn.model_validate(request.get_json(force=True) or {})
    except ValidationError as e:
        return jsonify({"error": "invalid input", "details": validation_errors(e)}), 400

    result = ai.generate_study_prescription(
        weak_topics=data.weak_topics,
        distractors=data.distractors,
        at_risk_topics=data.at_risk_topics,
        target_institution=data.target_institution
    )
    return jsonify(result)


@bp.route("/questions/<int:question_id>/synthesize_explanation", methods=["POST"])
def synthesize_explanation(question_id):
    try:
        data = SynthesizeExplanationIn.model_validate(request.get_json(force=True) or {})
    except ValidationError as e:
        return jsonify({"error": "invalid input", "details": validation_errors(e)}), 400

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

    # Se já possui explicação e não é para forçar regeneração, retorna a existente
    if q["explanation_text"] and not data.force_regenerate:
        return jsonify({
            "question_id": question_id,
            "explanation_text": q["explanation_text"],
            "source": "cached_db"
        })

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

    result = ai.synthesize_question_explanation(
        stem=q["stem"],
        alternatives=alts_list,
        correct_letter=correct_letter,
        correct_text=correct_text,
        area=q["area"] or "",
        subtema=q["subtema"] or q["topic"] or ""
    )

    # Persiste na tabela explanations se sintetizado com sucesso
    with db_transaction(db, immediate=True):
        existing_exp = db.execute("SELECT question_id FROM explanations WHERE question_id = ?", (question_id,)).fetchone()
        if existing_exp:
            db.execute("""
                UPDATE explanations
                SET explanation_text = ?
                WHERE question_id = ?
            """, (result.get("explanation_text", ""), question_id))
        else:
            db.execute("""
                INSERT INTO explanations (question_id, explanation_text)
                VALUES (?, ?)
            """, (question_id, result.get("explanation_text", "")))

    from .questions import invalidate_user_caches
    invalidate_user_caches(getattr(g, "user_id", None))

    return jsonify({
        "question_id": question_id,
        "explanation_text": result.get("explanation_text"),
        "source": result.get("source"),
        "model": result.get("model")
    })
