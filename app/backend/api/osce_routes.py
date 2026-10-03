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

    if not station_id:
        return jsonify({"error": "station_id é obrigatório"}), 400

    try:
        session = osce.start_osce_session(
            db=db,
            station_id=int(station_id),
            user_id=user_id,
            circuit_session_id=circuit_session_id
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

