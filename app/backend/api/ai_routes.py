"""Rotas de IA: Preceptor IA, diagnósticos de provedores, prescrição de estudo e síntese de explicação."""
from datetime import datetime, timezone

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
        db=db,
        question_id=question_id
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

    # Comentários e resoluções de questões foram elaborados por professores de residência.
    # São canônicos e congelados: nunca sobrescrever ou gastar tokens de IA tentando revisá-los.
    if q["explanation_text"] and q["explanation_text"].strip():
        return jsonify({
            "question_id": question_id,
            "explanation_text": q["explanation_text"],
            "source": "canonical_professor_locked"
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

    synthesized_text = (result.get("explanation_text") or "").strip()
    if not synthesized_text or result.get("source") == "fallback":
        return jsonify({
            "error": "Não foi possível sintetizar a explicação no momento.",
            "source": result.get("source", "error")
        }), 503

    now_iso = datetime.now(timezone.utc).isoformat()
    # Persiste na tabela explanations apenas se não houver explicação canônica existente
    with db_transaction(db, immediate=True):
        existing_exp = db.execute(
            "SELECT explanation_text FROM explanations WHERE question_id = ?",
            (question_id,)
        ).fetchone()
        if existing_exp and existing_exp["explanation_text"] and existing_exp["explanation_text"].strip():
            return jsonify({
                "question_id": question_id,
                "explanation_text": existing_exp["explanation_text"],
                "source": "canonical_professor_locked"
            })
        elif existing_exp:
            db.execute("""
                UPDATE explanations
                SET explanation_text = ?, generated_at = ?
                WHERE question_id = ? AND (explanation_text IS NULL OR TRIM(explanation_text) = '')
            """, (synthesized_text, now_iso, question_id))
        else:
            db.execute("""
                INSERT INTO explanations (question_id, explanation_text, generated_at)
                VALUES (?, ?, ?)
            """, (question_id, synthesized_text, now_iso))

    from .questions import invalidate_user_caches
    invalidate_user_caches(getattr(g, "user_id", None))

    return jsonify({
        "question_id": question_id,
        "explanation_text": result.get("explanation_text"),
        "source": "ai_synthesized",
        "model": result.get("model")
    })


@bp.route("/ai/analyze-image", methods=["POST"])
def analyze_medical_image():
    """
    Endpoint para análise multimodal de exames de imagem médica (ECG, RX, TC, Dermato, Lab).
    Suporta upload multipart/form-data ('image') ou JSON com 'image_base64'.
    """
    from .medical_vision import analisar_exame_imagem

    image_bytes = None
    mime_type = "image/jpeg"
    modality = "auto"
    clinical_context = None

    # 1. Verifica se veio via multipart/form-data
    if "image" in request.files:
        uploaded_file = request.files["image"]
        image_bytes = uploaded_file.read()
        mime_type = uploaded_file.content_type or "image/jpeg"
        modality = request.form.get("modality", "auto")
        clinical_context = request.form.get("clinical_context")
    else:
        # 2. Verifica se veio via JSON
        body = request.get_json(silent=True) or {}
        b64_data = body.get("image_base64")
        if b64_data:
            import base64
            # Remove data URL prefix se presente
            if "," in b64_data:
                b64_data = b64_data.split(",", 1)[1]
            try:
                image_bytes = base64.b64decode(b64_data)
            except Exception:
                return jsonify({"error": "Base64 de imagem inválido.", "code": "INVALID_IMAGE_BASE64"}), 400
        mime_type = body.get("mime_type", "image/jpeg")
        modality = body.get("modality", "auto")
        clinical_context = body.get("clinical_context")

    if not image_bytes or len(image_bytes) == 0:
        return jsonify({
            "error": "Nenhuma imagem foi fornecida para análise.",
            "code": "MISSING_IMAGE"
        }), 400

    resultado = analisar_exame_imagem(
        dados_bytes=image_bytes,
        mime_type=mime_type,
        modalidade=modality,
        contexto_clinico=clinical_context,
    )

    return jsonify(resultado), 200

