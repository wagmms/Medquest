"""Rotas de API para o Simulador de Prova Prática (OSCE) e 2ª Fase."""
from __future__ import annotations

import logging
from flask import Blueprint, g, jsonify, request

from . import osce
from .db import get_db, db_transaction

logger = logging.getLogger(__name__)

bp = Blueprint("osce", __name__)


def _resolve_user_id() -> str:
    user_id = getattr(g, "user_id", None)
    if not user_id:
        guest_id = request.headers.get("X-Guest-ID") or request.headers.get("x-internal-guest-id")
        if guest_id:
            user_id = f"guest:{guest_id.lower()}"
        else:
            user_id = "guest:anonymous"
    return user_id


@bp.route("/osce/stations", methods=["GET"])
def list_stations():
    db = get_db()
    user_id = _resolve_user_id()

    # Garante que as estações canônicas estejam inicializadas
    osce.seed_osce_stations(db)

    area = request.args.get("area")
    institution = request.args.get("institution")
    difficulty = request.args.get("difficulty")

    stations = osce.list_osce_stations(
        db=db,
        user_id=user_id,
        area=area,
        institution=institution,
        difficulty=difficulty
    )
    return jsonify({"stations": stations, "count": len(stations)})


@bp.route("/osce/stations/<int:station_id>", methods=["GET"])
def get_station_details(station_id: int):
    db = get_db()
    station = osce.get_osce_station(db, station_id, include_barema=False)
    if not station:
        return jsonify({"error": "Estação prática não encontrada"}), 404
    return jsonify(station)


@bp.route("/osce/sessions/start", methods=["POST"])
def start_session():
    db = get_db()
    user_id = _resolve_user_id()
    body = request.get_json(silent=True) or {}

    station_id = body.get("station_id")
    circuit_session_id = body.get("circuit_session_id")
    mode = body.get("mode", "blind")

    if not station_id:
        return jsonify({"error": "station_id é obrigatório"}), 400

    try:
        session = osce.start_osce_session(
            db=db,
            station_id=int(station_id),
            user_id=user_id,
            circuit_session_id=circuit_session_id,
            mode=mode
        )
        return jsonify(session), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@bp.route("/osce/sessions/<session_id>/interact", methods=["POST"])
def interact_session(session_id: str):
    db = get_db()
    user_id = _resolve_user_id()
    body = request.get_json(silent=True) or {}

    message = body.get("message", "").strip()
    elapsed_seconds = int(body.get("elapsed_seconds", 0))

    if not message:
        return jsonify({"error": "Mensagem não pode ser vazia"}), 400

    try:
        result = osce.interact_osce_session(
            db=db,
            session_id=session_id,
            user_id=user_id,
            message=message,
            elapsed_seconds=elapsed_seconds
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@bp.route("/osce/sessions/<session_id>/dispatch_speech", methods=["POST"])
def dispatch_speech(session_id: str):
    """Dispatcher unificado de voz para modo Hands-Free de alta fidelidade."""
    db = get_db()
    user_id = _resolve_user_id()
    body = request.get_json(silent=True) or {}

    message = body.get("message", "").strip()
    elapsed_seconds = int(body.get("elapsed_seconds", 0))

    if not message:
        return jsonify({"error": "Mensagem transcrita não pode ser vazia"}), 400

    try:
        result = osce.dispatch_osce_speech(
            db=db,
            session_id=session_id,
            user_id=user_id,
            message=message,
            elapsed_seconds=elapsed_seconds
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404



@bp.route("/osce/sessions/<session_id>/action", methods=["POST"])
def execute_action(session_id: str):
    db = get_db()
    user_id = _resolve_user_id()
    body = request.get_json(silent=True) or {}

    action_type = body.get("action_type", "").strip()
    action_target = body.get("action_target", "").strip()
    elapsed_seconds = int(body.get("elapsed_seconds", 0))

    if not action_type or not action_target:
        return jsonify({"error": "action_type e action_target são obrigatórios"}), 400

    try:
        result = osce.execute_osce_action(
            db=db,
            session_id=session_id,
            user_id=user_id,
            action_type=action_type,
            action_target=action_target,
            elapsed_seconds=elapsed_seconds
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@bp.route("/osce/sessions/<session_id>/finish", methods=["POST"])
def finish_session(session_id: str):
    db = get_db()
    user_id = _resolve_user_id()
    body = request.get_json(silent=True) or {}

    conduct_notes = body.get("conduct_notes")

    try:
        result = osce.finish_osce_session(
            db=db,
            session_id=session_id,
            user_id=user_id,
            conduct_notes=conduct_notes
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@bp.route("/osce/sessions/<session_id>/report", methods=["GET"])
def get_report(session_id: str):
    db = get_db()
    user_id = _resolve_user_id()

    report = osce.get_osce_session_report(db, session_id, user_id)
    if not report:
        return jsonify({"error": "Relatório de sessão não encontrado"}), 404
    return jsonify(report)


@bp.route("/osce/sessions/<session_id>/export_cards", methods=["POST"])
def export_shock_cards(session_id: str):
    """Exporta os Flashcards de Choque do barema diretamente para a tabela de flashcards do MedQuest."""
    db = get_db()
    user_id = _resolve_user_id()

    try:
        res = osce.export_osce_flashcards(db, session_id, user_id)
        return jsonify(res)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@bp.route("/osce/drugs", methods=["GET"])
def get_emergency_drugs():
    """Retorna o catálogo oficial de medicamentos de emergência para autocompletion na prescrição."""
    drugs = osce.get_emergency_drugs_catalog()
    return jsonify({"drugs": drugs, "count": len(drugs)})


@bp.route("/osce/procedures", methods=["GET"])
def get_procedures():
    """Retorna o catálogo de procedimentos beira-leito e janelas E-FAST para o manequim 2D."""
    procedures = osce.get_procedures_catalog()
    return jsonify({"procedures": procedures, "count": len(procedures)})


@bp.route("/osce/sessions/<session_id>/prescribe", methods=["POST"])
def prescribe_drugs(session_id: str):
    """Assina e processa uma prescrição médica estruturada na sala de emergência."""
    db = get_db()
    user_id = _resolve_user_id()
    body = request.get_json(silent=True) or {}

    prescription_items = body.get("prescription", [])
    elapsed_seconds = int(body.get("elapsed_seconds", 0))

    if not isinstance(prescription_items, list) or not prescription_items:
        return jsonify({"error": "prescription deve ser uma lista com ao menos 1 item."}), 400

    try:
        result = osce.prescribe_osce_drugs(
            db=db,
            session_id=session_id,
            user_id=user_id,
            prescription_items=prescription_items,
            elapsed_seconds=elapsed_seconds
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@bp.route("/osce/sessions/<session_id>/procedure", methods=["POST"])
def perform_procedure(session_id: str):
    """Executa um procedimento invasivo ou varredura ultrassonográfica E-FAST no manequim 2D."""
    db = get_db()
    user_id = _resolve_user_id()
    body = request.get_json(silent=True) or {}

    procedure_type = body.get("procedure_type", "").strip()
    anatomical_site = body.get("anatomical_site", "").strip()
    elapsed_seconds = int(body.get("elapsed_seconds", 0))

    if not procedure_type or not anatomical_site:
        return jsonify({"error": "procedure_type e anatomical_site são obrigatórios."}), 400

    try:
        result = osce.perform_osce_procedure(
            db=db,
            session_id=session_id,
            user_id=user_id,
            procedure_type=procedure_type,
            anatomical_site=anatomical_site,
            elapsed_seconds=elapsed_seconds
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@bp.route("/osce/sessions/<session_id>/live_feedback", methods=["GET"])
def get_session_live_feedback(session_id: str):
    """Consulta o progresso em tempo real do barema para o Modo Treino com Preceptor Fantasma."""
    db = get_db()
    user_id = _resolve_user_id()
    elapsed_seconds = int(request.args.get("elapsed_seconds", 0))

    try:
        feedback = osce.get_osce_live_feedback(
            db=db,
            session_id=session_id,
            user_id=user_id,
            elapsed_seconds=elapsed_seconds
        )
        return jsonify(feedback)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@bp.route("/osce/stations/generate", methods=["POST"])
def generate_station():
    """Gera uma estação inédita infinita no padrão FMRP-USP com parametrização dinâmica e IA adaptativa."""
    db = get_db()
    user_id = _resolve_user_id()
    body = request.get_json(silent=True) or {}

    area = body.get("area")
    subtema = body.get("subtema")
    difficulty = body.get("difficulty", "hard")
    adaptative = bool(body.get("adaptative", False))

    try:
        result = osce.generate_osce_station(
            db=db,
            user_id=user_id,
            area=area,
            subtema=subtema,
            difficulty=difficulty,
            adaptative=adaptative
        )
        return jsonify(result), 201
    except Exception as e:
        logger.exception("Erro ao gerar estação inédita FMRP-USP: %s", e)
        return jsonify({"error": f"Falha ao sintetizar estação inédita: {str(e)}"}), 500
