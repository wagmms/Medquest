"""Motor de Simulação de Prova Prática (OSCE) e 2ª Fase de Residência Médica.

Gerencia o catálogo de estações das bancas oficiais que realizam prova prática
(UNICAMP, UNIFESP, Einstein, Revalida INEP, SCMSP, USP-RP), o ciclo de vida
das sessões de beira-leito, a atuação do paciente virtual e do examinador,
e a auditoria oficial do barema de correção com geração de flashcards de choque.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .db import db_transaction, get_db
from .gemini_pool import generate_content_with_fallback
from .osce_evaluation import (
    _NEGATION_PREFIXES,
    _has_affirmative_mention,
    _normalize_text,
    build_chief_preceptor_review,
    build_medquest_remediation,
    compute_competency_radar_5d,
    evaluate_critical_safety_violations,
    evaluate_osce_red_flags,
    generate_competency_radar,
    generate_timeline_post_mortem,
)
from .osce_prompts import (
    build_examiner_system_prompt,
    build_patient_system_prompt,
    get_hemodynamic_speech_modifier,
)

logger = logging.getLogger(__name__)

from .osce_data import (
    CANONICAL_STATIONS,
    FMRP_USP_TEMPLATES,
    EMERGENCY_DRUGS_CATALOG,
    PROCEDURES_CATALOG,
)

def seed_osce_stations(db, force: bool = False) -> int:
    """Insere ou atualiza o catálogo canônico de estações de prova prática."""
    if not force:
        try:
            row = db.execute("SELECT COUNT(*) AS n FROM osce_stations").fetchone()
            if row and int(row["n"] or 0) >= len(CANONICAL_STATIONS):
                return 0
        except Exception:
            pass

    inserted = 0
    with db_transaction(db, immediate=True):
        for st in CANONICAL_STATIONS:
            existing = db.execute("SELECT id FROM osce_stations WHERE code = ?", (st["code"],)).fetchone()
            door_md = st["scenario_door_markdown"]
            persona_json = json.dumps(st["patient_persona"], ensure_ascii=False)
            exam_json = json.dumps(st["physical_exam"], ensure_ascii=False)
            lab_json = json.dumps(st.get("lab_imaging", {}), ensure_ascii=False)
            barema_json = json.dumps({
                "items": st["checklist_barema"],
                "critical_errors": st.get("critical_errors", [])
            }, ensure_ascii=False)

            if existing:
                db.execute("""
                    UPDATE osce_stations
                    SET title = ?, area = ?, subtema = ?, institution = ?, year = ?,
                        difficulty = ?, duration_seconds = ?, scenario_door_markdown = ?,
                        patient_persona_json = ?, physical_exam_json = ?,
                        lab_imaging_json = ?, checklist_barema_json = ?
                    WHERE code = ?
                """, (
                    st["title"], st["area"], st["subtema"], st["institution"], st["year"],
                    st["difficulty"], st["duration_seconds"], door_md,
                    persona_json, exam_json, lab_json, barema_json,
                    st["code"]
                ))
            else:
                db.execute("""
                    INSERT INTO osce_stations (
                        code, title, area, subtema, institution, year,
                        difficulty, duration_seconds, scenario_door_markdown,
                        patient_persona_json, physical_exam_json,
                        lab_imaging_json, checklist_barema_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    st["code"], st["title"], st["area"], st["subtema"], st["institution"], st["year"],
                    st["difficulty"], st["duration_seconds"], door_md,
                    persona_json, exam_json, lab_json, barema_json
                ))
                inserted += 1
    return inserted


def list_osce_stations(
    db,
    user_id: Optional[str] = None,
    area: Optional[str] = None,
    institution: Optional[str] = None,
    difficulty: Optional[str] = None
) -> list[dict[str, Any]]:
    """Lista as estações práticas disponíveis com histórico de tentativas do usuário."""
    query = """
        SELECT s.id, s.code, s.title, s.area, s.subtema, s.institution, s.year,
               s.difficulty, s.duration_seconds, s.scenario_door_markdown,
               (
                   SELECT MAX(sess.final_score)
                   FROM osce_sessions sess
                   WHERE sess.station_id = s.id AND sess.user_id = ? AND sess.status = 'completed'
               ) as best_score,
               (
                   SELECT COUNT(*)
                   FROM osce_sessions sess
                   WHERE sess.station_id = s.id AND sess.user_id = ? AND sess.status = 'completed'
               ) as completed_attempts
        FROM osce_stations s
        WHERE 1=1
    """
    params: list[Any] = [user_id or "", user_id or ""]

    if area and area != "Todas as Áreas":
        query += " AND s.area = ?"
        params.append(area)
    if institution and institution not in ("Todas as Bancas", "TODAS"):
        query += " AND s.institution = ?"
        params.append(institution)
    if difficulty:
        query += " AND s.difficulty = ?"
        params.append(difficulty)

    query += " ORDER BY s.institution, s.area, s.id"
    rows = db.execute(query, tuple(params)).fetchall()

    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "code": r["code"],
            "title": r["title"],
            "area": r["area"],
            "subtema": r["subtema"],
            "institution": r["institution"],
            "year": r["year"],
            "difficulty": r["difficulty"],
            "duration_seconds": r["duration_seconds"],
            "scenario_door_markdown": r["scenario_door_markdown"],
            "best_score": round(float(r["best_score"]), 1) if r["best_score"] is not None else None,
            "completed_attempts": int(r["completed_attempts"] or 0),
        })
    return result


def _build_physiology_engine(physical_exam: dict[str, Any], subtema: str = "", title: str = "") -> dict[str, Any]:
    """Retorna o motor de fisiologia dinâmica da estação com fallback determinístico sanitizado."""
    if physical_exam.get("physiology_engine"):
        return physical_exam["physiology_engine"]

    vitals = physical_exam.get("vitals", {})
    if not vitals:
        return {
            "initial_state": {
                "hr": 75,
                "sbp": 120,
                "dbp": 80,
                "spo2": 98,
                "rr": 16,
                "temp": 36.5,
                "gcs": 15,
                "rhythm": "NORMAL_SINUS",
                "etco2": 38,
                "perfusion_index": 2.5
            },
            "natural_progression": [],
            "intervention_modifiers": {}
        }

    # Extrai FC
    fc_val = 80
    fc_match = re.search(r"\b(\d{2,3})\b", vitals.get("fc", ""))
    if fc_match:
        fc_val = int(fc_match.group(1))

    # Extrai PA
    sbp_val = 120
    dbp_val = 80
    pa_match = re.search(r"(\d{2,3})\s*[xX/]\s*(\d{2,3})", vitals.get("pa", ""))
    if pa_match:
        sbp_val = int(pa_match.group(1))
        dbp_val = int(pa_match.group(2))

    # Extrai SpO2
    spo2_val = 97
    spo2_match = re.search(r"(\d{2,3})%", vitals.get("sato2", ""))
    if spo2_match:
        spo2_val = int(spo2_match.group(1))

    # Extrai FR
    rr_val = 16
    rr_match = re.search(r"\b(\d{1,2})\b", vitals.get("fr", ""))
    if rr_match:
        rr_val = int(rr_match.group(1))

    # Extrai Temp
    temp_val = 36.5
    temp_match = re.search(r"(\d{2}[.,]\d)", vitals.get("temp", ""))
    if temp_match:
        temp_val = float(temp_match.group(1).replace(",", "."))

    # Determina ritmo basal
    norm_meta = _normalize_text(f"{subtema} {title}")
    if "taquicardia ventricular" in norm_meta or "monomorfica" in norm_meta:
        rhythm = "VENTRICULAR_TACHYCARDIA"
    elif "fibrilacao" in norm_meta:
        rhythm = "AFIB"
    elif "supraventricular" in norm_meta or "tsv" in norm_meta:
        rhythm = "UNSTABLE_SVT"
    elif fc_val >= 100:
        rhythm = "SINUS_TACHYCARDIA"
    elif fc_val < 50:
        rhythm = "SINUS_BRADYCARDIA"
    else:
        rhythm = "NORMAL_SINUS"

    return {
        "initial_state": {
            "hr": fc_val,
            "sbp": sbp_val,
            "dbp": dbp_val,
            "spo2": spo2_val,
            "rr": rr_val,
            "temp": temp_val,
            "gcs": 15 if sbp_val >= 90 else 13,
            "rhythm": rhythm,
            "etco2": 38 if rr_val <= 24 else 28,
            "perfusion_index": 2.2 if sbp_val >= 90 else 0.8
        },
        "natural_progression": [],
        "intervention_modifiers": {}
    }


def _build_auscultation_foci(physical_exam: dict[str, Any], subtema: str = "", title: str = "") -> list[dict[str, Any]]:
    """Gera o mapa de focos anatômicos de ausculta com síntese acústica semiológica procedural."""
    if physical_exam.get("auscultation_foci"):
        return physical_exam["auscultation_foci"]

    findings = physical_exam.get("findings", {})
    resp_text = _normalize_text(findings.get("respiratorio", ""))
    card_text = _normalize_text(findings.get("cardiovascular", ""))
    norm_meta = _normalize_text(f"{subtema} {title}")

    # Determina som cardíaco principal
    if "atrito" in card_text or "pericard" in norm_meta:
        cardiac_sound = "PERICARDIAL_RUB"
    elif "sopro" in card_text or "estenose" in norm_meta or "insuficiencia mitral" in norm_meta:
        cardiac_sound = "SYSTOLIC_MURMUR"
    else:
        cardiac_sound = "NORMAL_HEART"

    # Determina sons pulmonares
    if "sibilo" in resp_text or "bronquio" in norm_meta or "asma" in norm_meta:
        pulm_sound_ant = "EXPIRATORY_WHEEZES"
        pulm_sound_post = "EXPIRATORY_WHEEZES"
    elif "estertor" in resp_text or "crepit" in resp_text or "congestao" in resp_text or "pneumonia" in norm_meta:
        pulm_sound_ant = "NORMAL_VESICULAR"
        pulm_sound_post = "COARSE_CRACKLES"
    else:
        pulm_sound_ant = "NORMAL_VESICULAR"
        pulm_sound_post = "NORMAL_VESICULAR"

    return [
        {"id": "FA", "label": "2º EIC Direito (Foco Aórtico)", "x": 42, "y": 28, "soundType": cardiac_sound if cardiac_sound != "NORMAL_HEART" else "NORMAL_HEART"},
        {"id": "FP", "label": "2º EIC Esquerdo (Foco Pulmonar)", "x": 58, "y": 28, "soundType": "NORMAL_HEART"},
        {"id": "FM", "label": "5º EIC Esquerdo (Foco Mitral)", "x": 64, "y": 48, "soundType": cardiac_sound},
        {"id": "APD", "label": "Terço Inferior Hemitorax Direito", "x": 35, "y": 54, "soundType": pulm_sound_post},
        {"id": "APE", "label": "Terço Médio Hemitorax Esquerdo", "x": 66, "y": 38, "soundType": pulm_sound_ant},
    ]


def get_osce_station(db, station_id: int, include_barema: bool = False) -> Optional[dict[str, Any]]:
    """Carrega detalhes de uma estação, mantendo o barema oculto durante a prova."""
    row = db.execute("""
        SELECT id, code, title, area, subtema, institution, year,
               difficulty, duration_seconds, scenario_door_markdown,
               patient_persona_json, physical_exam_json, lab_imaging_json,
               checklist_barema_json
        FROM osce_stations
        WHERE id = ?
    """, (station_id,)).fetchone()
    if not row:
        return None

    physical_exam = json.loads(row["physical_exam_json"] or "{}")
    lab_imaging = json.loads(row["lab_imaging_json"] or "{}")
    patient_persona = json.loads(row["patient_persona_json"] or "{}")

    station = {
        "id": row["id"],
        "code": row["code"],
        "title": row["title"],
        "area": row["area"],
        "subtema": row["subtema"],
        "institution": row["institution"],
        "year": row["year"],
        "difficulty": row["difficulty"],
        "duration_seconds": row["duration_seconds"],
        "scenario_door_markdown": row["scenario_door_markdown"],
        "patient_persona": {
            "name": patient_persona.get("name"),
            "age": patient_persona.get("age"),
            "gender": patient_persona.get("gender"),
            "chief_complaint": patient_persona.get("chief_complaint"),
        },
        "physical_exam_categories": list(physical_exam.get("findings", {}).keys()),
        "vitals_available": bool(physical_exam.get("vitals")),
        "lab_imaging_catalog": [
            {"key": k, "title": v.get("title", k)}
            for k, v in lab_imaging.items()
        ],
        "physiology_engine": _build_physiology_engine(physical_exam, row["subtema"], row["title"]),
        "auscultation_foci": _build_auscultation_foci(physical_exam, row["subtema"], row["title"])
    }

    if include_barema:
        barema = json.loads(row["checklist_barema_json"] or "{}")
        station["checklist_barema"] = barema.get("items", [])
        station["critical_errors"] = barema.get("critical_errors", [])
        station["patient_persona_full"] = patient_persona
        station["physical_exam_full"] = physical_exam
        station["lab_imaging_full"] = lab_imaging

    return station


# =========================================================================
# VETOR 5: MOTOR DE ESTAÇÕES INÉDITAS INFINITAS (IA DA FMRP-USP)
# =========================================================================




# =========================================================================
def generate_osce_station(
    db,
    user_id: str,
    area: Optional[str] = None,
    subtema: Optional[str] = None,
    difficulty: str = "hard",
    adaptative: bool = False
) -> dict[str, Any]:
    """
    Motor de Geração de Estações Inéditas Infinitas com o padrão da FMRP-USP (Ribeirão Preto).
    - Se adaptative=True ou area=='adaptativo': analisa o histórico do aluno (erros teóricos em attempts ou notas baixas em osce_sessions)
      para priorizar a fraqueza clínica real.
    - Constrói cenários de alta complexidade médica nos ambientes reais do complexo FMRP-USP
      (HC-UE, HC-Criança, Mater, CSE Sumarezinho, UCO).
    - Persiste a estação na tabela osce_stations com código USP-RP-AI-<hash>.
    - Retorna os dados completos da estação criada pronta para execução na Arena OSCE.
    """
    import random
    target_area = area
    target_subtema = subtema

    # 1. Raciocínio Adaptativo: Localiza fraquezas reais do aluno
    if adaptative or not target_area or target_area.lower() in ["adaptativo", "fraquezas", "auto"]:
        # Tenta identificar histórico recente de reprovação em OSCE
        try:
            low_osce = db.execute("""
                SELECT st.area, st.subtema, AVG(s.final_score) as avg_score
                FROM osce_sessions s
                JOIN osce_stations st ON s.station_id = st.id
                WHERE s.user_id = ? AND s.status = 'completed'
                GROUP BY st.area, st.subtema
                HAVING avg_score < 7.0
                ORDER BY avg_score ASC
                LIMIT 1
            """, (user_id,)).fetchone()
            if low_osce:
                target_area = low_osce["area"]
                target_subtema = low_osce["subtema"]
        except Exception:
            pass

        # Se não achou no OSCE, verifica erros na 1ª fase (questões de prova teórica)
        if not target_area or target_area.lower() in ["adaptativo", "fraquezas", "auto"]:
            try:
                worst_topic = db.execute("""
                    SELECT q.area, q.subtema, COUNT(*) as err_count
                    FROM attempts a
                    JOIN questions q ON a.question_id = q.id
                    WHERE a.is_correct = 0 AND (a.user_id = ? OR a.user_id = 1)
                    GROUP BY q.area, q.subtema
                    ORDER BY err_count DESC
                    LIMIT 1
                """, (user_id,)).fetchone()
                if worst_topic:
                    target_area = worst_topic["area"]
                    target_subtema = worst_topic["subtema"]
            except Exception:
                pass

        # Fallback de seleção aleatória entre as grandes áreas
        if not target_area or target_area.lower() in ["adaptativo", "fraquezas", "auto"]:
            areas_catalog = ["Clínica Médica", "Cirurgia Geral", "Pediatria", "Ginecologia e Obstetrícia", "Medicina Preventiva"]
            target_area = random.choice(areas_catalog)

    # 2. Filtra modelos disponíveis da FMRP-USP
    matched_templates = [
        t for t in FMRP_USP_TEMPLATES
        if _normalize_text(t["area"]) == _normalize_text(target_area)
    ]
    if target_subtema:
        sub_norm = _normalize_text(target_subtema)
        specific_templates = [t for t in matched_templates if sub_norm in _normalize_text(t["subtema"])]
        if specific_templates:
            matched_templates = specific_templates

    if not matched_templates:
        matched_templates = FMRP_USP_TEMPLATES

    chosen_template = random.choice(matched_templates)

    # 3. Parametrização Dinâmica do Caso (Variações Inéditas de Paciente)
    patient_name = random.choice(chosen_template["patient_names"])
    patient_age = random.randint(chosen_template["age_range"][0], chosen_template["age_range"][1])
    unique_hash = uuid.uuid4().hex[:8].upper()
    station_code = f"USP-RP-AI-{unique_hash}"

    # Monta cartaz na porta da estação
    door_md = (
        f"### ESTAÇÃO: {chosen_template['hospital_unit']}\n\n"
        f"**Candidato(a)**:\n"
        f"Você é o médico de plantão no complexo hospitalar da Faculdade de Medicina de Ribeirão Preto (FMRP-USP).\n\n"
        f"**Cenário de Atendimento**:\n"
        f"- Paciente: {patient_name}, {patient_age} anos, {chosen_template['gender']}.\n"
        f"- Queixa de Admissão: \"{chosen_template['chief_complaint']}\"\n\n"
        f"**Sua Tarefa Obrigatória**:\n"
        f"1. Conduza o atendimento beira-leito imediato, realize a anamnese direcionada e acolha o paciente.\n"
        f"2. Solicite e interprete o exame físico segmentar e os exames complementares disponíveis.\n"
        f"3. Estabeleça o diagnóstico diferencial ou etiológico principal.\n"
        f"4. Prescreva o plano terapêutico inicial e verbalize a conduta de encerramento da estação.\n\n"
        f"*Tempo de prova: 8 minutos (Cronômetro Oficial FMRP-USP/FAEPA).*"
    )

    persona_payload = {
        "name": patient_name,
        "age": patient_age,
        "gender": chosen_template["gender"],
        "chief_complaint": chosen_template["chief_complaint"],
        "past_medical_history": chosen_template["history"],
        "allergies": "Nenhuma alergia conhecida."
    }

    physical_payload = {
        "vitals": chosen_template["vitals"],
        "findings": chosen_template["findings"]
    }

    labs_payload = chosen_template.get("lab_imaging", {})
    barema_payload = {
        "items": chosen_template["barema_items"],
        "critical_errors": chosen_template.get("critical_errors", [])
    }

    # 4. Salva a nova estação inédita no banco
    with db_transaction(db, immediate=True):
        cursor = db.execute("""
            INSERT INTO osce_stations (
                code, title, area, subtema, institution, year,
                difficulty, duration_seconds, scenario_door_markdown,
                patient_persona_json, physical_exam_json,
                lab_imaging_json, checklist_barema_json
            ) VALUES (?, ?, ?, ?, 'USP-RP', 2026, ?, 480, ?, ?, ?, ?, ?)
        """, (
            station_code,
            chosen_template["title_template"],
            chosen_template["area"],
            chosen_template["subtema"],
            difficulty,
            door_md,
            json.dumps(persona_payload, ensure_ascii=False),
            json.dumps(physical_payload, ensure_ascii=False),
            json.dumps(labs_payload, ensure_ascii=False),
            json.dumps(barema_payload, ensure_ascii=False)
        ))
        new_station_id = getattr(cursor, "lastrowid", None)
        if not new_station_id:
            row_st = db.execute("SELECT id FROM osce_stations WHERE code = ?", (station_code,)).fetchone()
            new_station_id = row_st["id"] if row_st else None

    return {
        "success": True,
        "station_id": new_station_id,
        "code": station_code,
        "title": chosen_template["title_template"],
        "area": chosen_template["area"],
        "subtema": chosen_template["subtema"],
        "institution": "USP-RP",
        "difficulty": difficulty,
        "message": f"Estação inédita FMRP-USP sintetizada com sucesso para {chosen_template['area']} ({chosen_template['subtema']})."
    }


def evaluate_live_barema_progress(
    checklist_items: list[dict[str, Any]],
    transcript: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    elapsed_seconds: int = 0
) -> dict[str, Any]:
    """Avalia o progresso em tempo real do barema para o Modo Treino com Preceptor Fantasma."""
    candidate_texts = [
        t.get("message", "").lower() for t in transcript if t.get("sender") == "candidato"
    ]
    actions_texts = [
        f"{a.get('action_type', '')} {a.get('action_target', '')} {a.get('findings', '')}".lower() for a in actions
    ]
    for a in actions:
        if a.get("action_type") == "prescription":
            for p in a.get("prescription_items", []):
                actions_texts.append(f"{p.get('drug_name', '')} {p.get('dose', '')} {p.get('unit', '')} {p.get('route', '')} {p.get('notes', '')}".lower())

    all_evidence = " ".join(candidate_texts + actions_texts)
    norm_evidence = _normalize_text(all_evidence)

    items_status = []
    total_earned = 0.0
    total_weight = 0.0

    for item in checklist_items:
        weight = float(item.get("weight", 1.0))
        total_weight += weight
        keywords = item.get("keywords", [])
        matches = [kw for kw in keywords if _normalize_text(kw) in norm_evidence]
        match_ratio = len(matches) / max(1, len(keywords))

        is_completed = match_ratio >= 0.4 or len(matches) >= 2
        is_partial = not is_completed and (match_ratio > 0.15 or len(matches) == 1)

        score_earned = weight if is_completed else (round(weight * 0.5, 2) if is_partial else 0.0)
        total_earned += score_earned

        items_status.append({
            "id": item.get("id"),
            "title": item.get("title"),
            "category": item.get("category"),
            "weight": weight,
            "score_earned": score_earned,
            "completed": is_completed or is_partial,
            "status": "cumprido_total" if is_completed else ("cumprido_parcial" if is_partial else "nao_cumprido"),
            "matched_keywords": matches[:3]
        })

    # Dicas e Alertas Proativos do Preceptor Fantasma baseados no tempo e itens pendentes
    proactive_hints = []
    uncompleted_categories = set(i["category"] for i in items_status if not i["completed"])

    if elapsed_seconds >= 180 and "exame_fisico" in uncompleted_categories:
        proactive_hints.append("⚠️ Preceptor Fantasma: Já se passaram 3 minutos! Não se esqueça de checar os sinais vitais e o exame físico segmentar.")
    if elapsed_seconds >= 240 and "exames_complementares" in uncompleted_categories:
        proactive_hints.append("⚠️ Preceptor Fantasma: Metade da estação decorrida! Lembre-se de solicitar o exame complementar essencial (ECG, Labs ou Imagem).")
    if elapsed_seconds >= 300 and ("conduta_tratamento" in uncompleted_categories or "tratamento" in uncompleted_categories):
        proactive_hints.append("🚨 Preceptor Fantasma: Faltam 3 minutos! Inicie a prescrição de urgência na prancheta ou verbalize as medidas terapêuticas imediatas.")

    normalized_score = round(min(10.0, (total_earned / max(1.0, total_weight)) * 10.0), 1)

    return {
        "mode": "guided",
        "current_score": normalized_score,
        "max_score": 10.0,
        "raw_earned": round(total_earned, 2),
        "raw_weight": round(total_weight, 2),
        "percentage": round((total_earned / max(1.0, total_weight)) * 100),
        "items_status": items_status,
        "proactive_hints": proactive_hints
    }


def get_session_mode(actions: list[dict[str, Any]]) -> str:
    """Extrai o modo da sessão (blind ou guided) a partir do histórico de ações."""
    for a in actions:
        if a.get("action_type") == "session_init" and a.get("mode"):
            return str(a.get("mode"))
    return "blind"


def start_osce_session(
    db,
    station_id: int,
    user_id: str,
    circuit_session_id: Optional[str] = None,
    mode: str = "blind"
) -> dict[str, Any]:
    """Inicia uma sessão cronometrada de prova prática no Modo Prova Cega ou Treino Guiado."""
    station = db.execute("SELECT id, code, title, institution, duration_seconds, scenario_door_markdown, checklist_barema_json FROM osce_stations WHERE id = ?", (station_id,)).fetchone()
    if not station:
        raise ValueError(f"Estação {station_id} não encontrada.")

    session_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    session_mode = "guided" if mode == "guided" else "blind"

    initial_transcript = [
        {
            "sender": "examinador",
            "message": "Candidato(a), você pode entrar na sala de exame. O tempo de prova começou.",
            "timestamp": now_iso
        }
    ]

    initial_actions = [
        {
            "action_type": "session_init",
            "mode": session_mode,
            "timestamp": now_iso
        }
    ]

    with db_transaction(db, immediate=True):
        db.execute("""
            INSERT INTO osce_sessions (
                id, station_id, user_id, circuit_session_id,
                status, start_time, elapsed_seconds,
                transcript_json, actions_taken_json
            ) VALUES (?, ?, ?, ?, 'in_progress', ?, 0, ?, ?)
        """, (
            session_id, station_id, user_id, circuit_session_id,
            now_iso, json.dumps(initial_transcript, ensure_ascii=False),
            json.dumps(initial_actions, ensure_ascii=False)
        ))

    barema_raw = json.loads(station["checklist_barema_json"] or "{}")
    checklist_items = barema_raw.get("items", []) if isinstance(barema_raw, dict) else (barema_raw if isinstance(barema_raw, list) else [])

    guided_feedback = None
    if session_mode == "guided":
        guided_feedback = evaluate_live_barema_progress(checklist_items, initial_transcript, initial_actions, 0)

    return {
        "session_id": session_id,
        "station_id": station_id,
        "code": station["code"],
        "title": station["title"],
        "institution": station["institution"],
        "duration_seconds": station["duration_seconds"],
        "start_time": now_iso,
        "transcript": initial_transcript,
        "mode": session_mode,
        "guided_feedback": guided_feedback
    }


def get_osce_live_feedback(db, session_id: str, user_id: str, elapsed_seconds: int = 0) -> dict[str, Any]:
    """Retorna o progresso em tempo real do barema para o Modo Treino com Preceptor Fantasma."""
    sess = db.execute("""
        SELECT s.id, s.station_id, s.status, s.actions_taken_json, s.transcript_json,
               st.checklist_barema_json
        FROM osce_sessions s
        JOIN osce_stations st ON s.station_id = st.id
        WHERE s.id = ?
    """, (session_id,)).fetchone()

    if not sess:
        raise ValueError("Sessão não encontrada.")

    actions = json.loads(sess["actions_taken_json"] or "[]")
    transcript = json.loads(sess["transcript_json"] or "[]")
    barema_raw = json.loads(sess["checklist_barema_json"] or "{}")
    checklist_items = barema_raw.get("items", []) if isinstance(barema_raw, dict) else (barema_raw if isinstance(barema_raw, list) else [])

    mode = get_session_mode(actions)
    feedback = evaluate_live_barema_progress(checklist_items, transcript, actions, elapsed_seconds)
    feedback["mode"] = mode
    return feedback


def interact_osce_session(
    db,
    session_id: str,
    user_id: str,
    message: str,
    elapsed_seconds: int = 0,
    target: str = "PATIENT",
    current_vitals: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    """Processa fala/pergunta do aluno roteada para o Paciente Virtual ou para a Banca Examinadora."""
    sess = db.execute("""
        SELECT s.id, s.station_id, s.user_id, s.status, s.transcript_json, s.actions_taken_json,
               st.title, st.area, st.subtema, st.institution, st.patient_persona_json, st.scenario_door_markdown,
               st.physical_exam_json, st.checklist_barema_json
        FROM osce_sessions s
        JOIN osce_stations st ON s.station_id = st.id
        WHERE s.id = ?
    """, (session_id,)).fetchone()

    if not sess:
        raise ValueError(f"Sessão {session_id} não encontrada.")
    if sess["status"] != "in_progress":
        return {"error": "Sessão já finalizada.", "status": sess["status"]}

    transcript = json.loads(sess["transcript_json"] or "[]")
    persona = json.loads(sess["patient_persona_json"] or "{}")
    physical_exam = json.loads(sess["physical_exam_json"] or "{}")

    now_iso = datetime.now(timezone.utc).isoformat()
    clean_msg = message.strip()
    norm_target = str(target or "PATIENT").upper().strip()
    is_examiner = norm_target in ("EXAMINER", "EXAMINADOR", "BANCA")

    # Adiciona a mensagem do aluno ao transcript
    transcript.append({
        "sender": "candidato",
        "target": "examinador" if is_examiner else "paciente",
        "message": clean_msg,
        "timestamp": now_iso,
        "elapsed_seconds": elapsed_seconds
    })

    # Decisão de resposta via Roteador Dual-Agent
    station_meta = {
        "title": sess["title"],
        "area": sess["area"],
        "subtema": sess["subtema"],
        "institution": sess["institution"]
    }

    if is_examiner:
        system_prompt = build_examiner_system_prompt(station_meta, physical_exam, current_vitals)
        user_prompt = f"O candidato se dirige à banca examinadora:\n\"{clean_msg}\"\n\nResponda como o examinador oficial:"
    else:
        system_prompt = build_patient_system_prompt(persona, current_vitals)
        history_str = "\n".join([
            f"{t['sender'].upper()}: {t['message']}"
            for t in transcript[-4:]
        ])
        user_prompt = f"Diálogo recente na sala:\n{history_str}\n\nO candidato diz ao paciente:\n\"{clean_msg}\"\n\nResponda como o paciente {persona.get('name', '')}:"

    reply_text = ""
    try:
        resp = generate_content_with_fallback(
            prompt=user_prompt,
            system_instruction=system_prompt,
            timeout=12,
            temperature=0.2 if is_examiner else 0.5
        )
        reply_text = resp.get("text", "").strip()
    except Exception as e:
        logger.warning(f"OSCE LLM fallback ativado para {norm_target}: {e}")

    if not reply_text:
        # Fallback determinístico médico de alta fidelidade
        msg_lower = _normalize_text(clean_msg)
        if is_examiner:
            if any(w in msg_lower for w in ["ausculta", "auscultar", "estetoscopio"]):
                reply_text = "Utilize o estetoscópio interativo diretamente no manequim à sua frente. O áudio está disponível nos focos."
            elif any(w in msg_lower for w in ["exame fisico", "examinar o paciente", "vou examinar", "fazer exame"]):
                reply_text = "Seja específico. Qual manobra ou tempo semiológico deseja realizar e em qual topografia?"
            elif any(w in msg_lower for w in ["blumberg", "descompressao", "periton"]):
                reply_text = physical_exam.get("findings", {}).get("abdome", "Descompressão brusca indolor.")
            elif any(w in msg_lower for w in ["prescrevo", "administro", "faco", "iniciar"]):
                reply_text = "Conduta considerada."
            else:
                reply_text = "Examinador registra sua solicitação. Prossiga com o atendimento."
        else:
            gcs = int(current_vitals.get("gcs", 15) or 15) if current_vitals else 15
            spo2 = int(current_vitals.get("spo2", 98) or 98) if current_vitals else 98
            rr = int(current_vitals.get("rr", 16) or 16) if current_vitals else 16

            if gcs <= 8:
                reply_text = "Uhn... ahh... [geme fracamente]"
            else:
                if any(w in msg_lower for w in ["dor", "onde dói", "sente", "queima", "aperta"]):
                    base_reply = persona.get("pain_characteristics") or persona.get("chief_complaint", "Dói muito aqui no peito, doutor.")
                elif any(w in msg_lower for w in ["quando", "começou", "tempo", "horas", "minutos"]):
                    base_reply = f"Começou de repente faz pouco tempo, doutor. {persona.get('chief_complaint', '')}"
                elif any(w in msg_lower for w in ["fuma", "cigarro", "bebe", "álcool", "remédio", "pressão", "diabete", "histórico"]):
                    base_reply = persona.get("past_medical_history") or persona.get("past_history", "Não tomo nenhum remédio doutor.")
                elif any(w in msg_lower for w in ["falta de ar", "suor", "suando", "enjoo", "náusea", "vomit"]):
                    base_reply = persona.get("associated_symptoms", "Tô sentindo uma náusea forte e um suor frio.")
                elif any(w in msg_lower for w in ["viagra", "sildenafila", "ereção"]):
                    base_reply = persona.get("sildenafil_use", "Não tomei nada disso não, doutor.")
                elif any(w in msg_lower for w in ["olá", "bom dia", "boa tarde", "nome", "sou o médico", "vamos cuidar"]):
                    base_reply = f"Doutor, por favor me ajuda, tá doendo demais! {persona.get('chief_complaint', '')}"
                else:
                    base_reply = "Entendi, doutor. O que o senhor vai fazer pra me ajudar?"

                if spo2 < 88 or rr > 30:
                    reply_text = f"Doutor... [arfa]... {base_reply[:40]}... [puxa o ar]"
                else:
                    reply_text = base_reply

    sender_label = "examinador" if is_examiner else "paciente"
    transcript.append({
        "sender": sender_label,
        "target": "candidato",
        "message": reply_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": elapsed_seconds
    })

    with db_transaction(db, immediate=True):
        db.execute("""
            UPDATE osce_sessions
            SET transcript_json = ?, elapsed_seconds = ?
            WHERE id = ?
        """, (json.dumps(transcript, ensure_ascii=False), elapsed_seconds, session_id))

    res_payload: dict[str, Any] = {
        "reply": reply_text,
        "sender": sender_label,
        "target": norm_target,
        "elapsed_seconds": elapsed_seconds,
        "transcript_count": len(transcript)
    }

    actions = json.loads(sess["actions_taken_json"] or "[]")
    if get_session_mode(actions) == "guided":
        barema_raw = json.loads(sess["checklist_barema_json"] or "{}")
        checklist_items = barema_raw.get("items", []) if isinstance(barema_raw, dict) else (barema_raw if isinstance(barema_raw, list) else [])
        res_payload["guided_feedback"] = evaluate_live_barema_progress(checklist_items, transcript, actions, elapsed_seconds)

    return res_payload


def execute_osce_action(
    db,
    session_id: str,
    user_id: str,
    action_type: str,
    action_target: str,
    elapsed_seconds: int = 0
) -> dict[str, Any]:
    """
    Executa uma ação clínica beira-leito:
    - action_type = 'physical_exam': inspeciona segmento ou ausculta com estetoscópio virtual.
    - action_type = 'vitals': solicita sinais vitais imediatos.
    - action_type = 'lab_imaging': solicita exame complementar (ECG, RX, TC, labs).
    """
    sess = db.execute("""
        SELECT s.id, s.station_id, s.status, s.actions_taken_json, s.transcript_json,
               st.physical_exam_json, st.lab_imaging_json, st.checklist_barema_json
        FROM osce_sessions s
        JOIN osce_stations st ON s.station_id = st.id
        WHERE s.id = ?
    """, (session_id,)).fetchone()

    if not sess:
        raise ValueError("Sessão não encontrada.")
    if sess["status"] != "in_progress":
        return {"error": "Sessão finalizada."}

    actions = json.loads(sess["actions_taken_json"] or "[]")
    transcript = json.loads(sess["transcript_json"] or "[]")
    exam = json.loads(sess["physical_exam_json"] or "{}")
    labs = json.loads(sess["lab_imaging_json"] or "{}")

    now_iso = datetime.now(timezone.utc).isoformat()
    target_clean = action_target.strip().lower()

    action_record = {
        "action_type": action_type,
        "action_target": action_target,
        "elapsed_seconds": elapsed_seconds,
        "timestamp": now_iso
    }

    examiner_message = ""
    result_payload: dict[str, Any] = {}

    if action_type == "vitals":
        vitals = exam.get("vitals", {})
        examiner_message = (
            f"Sinais Vitais: PA {vitals.get('pa', '120x80')}, FC {vitals.get('fc', '80 bpm')}, "
            f"FR {vitals.get('fr', '16 irpm')}, SatO2 {vitals.get('sato2', '98%')}, "
            f"Temp {vitals.get('temp', '36.5 °C')}"
        )
        if "hgt" in vitals:
            examiner_message += f", Glicemia {vitals.get('hgt')}"
        result_payload = {"vitals": vitals}

    elif action_type == "physical_exam":
        findings = exam.get("findings", {})
        norm_target = _normalize_text(action_target)
        finding_text = None
        for k, v in findings.items():
            norm_k = _normalize_text(k)
            if norm_target in norm_k or norm_k in norm_target:
                finding_text = v
                break

        if not finding_text:
            finding_text = "Sem anormalidades detectáveis nesta área."

        audio_key = exam.get("auscultation_audio", {}).get(target_clean)
        examiner_message = f"Exame Físico ({action_target}): {finding_text}"
        result_payload = {
            "finding": finding_text,
            "target": action_target,
            "audio_key": audio_key
        }

    elif action_type == "lab_imaging":
        lab_item = None
        norm_target = _normalize_text(action_target)
        for k, v in labs.items():
            norm_k = _normalize_text(k)
            norm_title = _normalize_text(v.get("title", ""))
            if norm_target in norm_k or norm_k in norm_target or norm_target in norm_title or norm_title in norm_target:
                lab_item = v
                break

        if lab_item and lab_item.get("available", True):
            examiner_message = f"Examinador entrega: {lab_item.get('title', action_target)}. Resultado: {lab_item.get('result_text')}"
            result_payload = {
                "title": lab_item.get("title", action_target),
                "result_text": lab_item.get("result_text"),
                "image_url": lab_item.get("image_url")
            }
        else:
            examiner_message = f"Examinador informa: O exame '{action_target}' não está disponível de imediato ou não foi fornecido pela banca nesta estação."
            result_payload = {"available": False, "title": action_target}

    # Registra ação e intervenção do examinador
    actions.append(action_record)
    transcript.append({
        "sender": "examinador",
        "message": examiner_message,
        "timestamp": now_iso,
        "elapsed_seconds": elapsed_seconds,
        "action_payload": result_payload
    })

    with db_transaction(db, immediate=True):
        db.execute("""
            UPDATE osce_sessions
            SET actions_taken_json = ?, transcript_json = ?, elapsed_seconds = ?
            WHERE id = ?
        """, (
            json.dumps(actions, ensure_ascii=False),
            json.dumps(transcript, ensure_ascii=False),
            elapsed_seconds,
            session_id
        ))

    res_payload: dict[str, Any] = {
        "action_type": action_type,
        "target": action_target,
        "examiner_message": examiner_message,
        "payload": result_payload,
        "elapsed_seconds": elapsed_seconds
    }

    if get_session_mode(actions) == "guided":
        barema_raw = json.loads(sess["checklist_barema_json"] or "{}")
        checklist_items = barema_raw.get("items", []) if isinstance(barema_raw, dict) else (barema_raw if isinstance(barema_raw, list) else [])
        res_payload["guided_feedback"] = evaluate_live_barema_progress(checklist_items, transcript, actions, elapsed_seconds)

    return res_payload


def dispatch_osce_speech(
    db,
    session_id: str,
    user_id: str,
    message: str,
    elapsed_seconds: int = 0
) -> dict[str, Any]:
    """
    Dispatcher de voz Hands-Free de alta performance para a sala prática do OSCE.
    Analisa a fala natural do candidato e classifica/executa em tempo real:
    1. Comandos ao Examinador (sinais vitais, exames complementares, exame físico, conduta verbalizada).
    2. Diálogo com o Paciente Simulado (anamnese, perguntas clínicas, acolhimento).
    3. Fila de áudio falado (spoken_queue) para execução de áudio encadeado.
    """
    sess = db.execute("""
        SELECT s.id, s.station_id, s.user_id, s.status, s.actions_taken_json, s.transcript_json,
               st.title, st.area, st.subtema, st.patient_persona_json, st.physical_exam_json, st.lab_imaging_json
        FROM osce_sessions s
        JOIN osce_stations st ON s.station_id = st.id
        WHERE s.id = ?
    """, (session_id,)).fetchone()

    if not sess:
        raise ValueError(f"Sessão {session_id} não encontrada.")
    if sess["status"] != "in_progress":
        return {"error": "Sessão já finalizada.", "status": sess["status"]}

    clean_msg = message.strip()
    norm_msg = _normalize_text(clean_msg)
    if not clean_msg:
        return {"error": "Mensagem vazia."}

    exam = json.loads(sess["physical_exam_json"] or "{}")
    labs = json.loads(sess["lab_imaging_json"] or "{}")
    persona = json.loads(sess["patient_persona_json"] or "{}")

    actions_executed = []
    spoken_queue = []
    is_conduct_verbalized = False

    # 1. Detecta Conduta Verbalizada
    conduct_triggers = [
        "minha conduta", "prescrevo", "prescrever", "iniciar tratamento", "vou iniciar",
        "encaminho para", "solicito vaga", "indico cirurgia", "indico laparotomia",
        "passo o caso", "diagnostico e conduta", "administro"
    ]
    if any(trigger in norm_msg for trigger in conduct_triggers):
        is_conduct_verbalized = True

    # 2. Detecta Solicitação de Sinais Vitais
    vitals_triggers = [
        "sinais vitais", "vitais completos", "dados vitais", "aferir pa", "pressao arterial",
        "frequencia cardiaca", "saturacao de o2", "temperatura axilar", "hgt", "glicemia capilar"
    ]
    if any(trigger in norm_msg for trigger in vitals_triggers):
        act_res = execute_osce_action(db, session_id, user_id, "vitals", "vitals", elapsed_seconds)
        actions_executed.append(act_res)
        spoken_queue.append({
            "speaker": "examinador",
            "text": act_res["examiner_message"]
        })

    # 3. Detecta Solicitação de Exames Complementares (Labs e Imagens)
    for k, v in labs.items():
        norm_k = _normalize_text(k)
        norm_title = _normalize_text(v.get("title", ""))
        triggers = [norm_k, norm_title]

        if "ecg" in norm_k or "eletro" in norm_k or "eletrocardiograma" in norm_title:
            triggers.extend(["ecg", "eletro", "eletrocardiograma", "tracado"])
        if "gasometria" in norm_k or "gaso" in norm_title:
            triggers.extend(["gasometria", "gaso", "eletrolitos", "potassio", "sodio", "gaso arterial"])
        if "rx" in norm_k or "raio" in norm_k or "radiografia" in norm_title:
            triggers.extend(["raio x", "rx", "radiografia", "rx torax", "rx de torax"])
        if "tomografia" in norm_k or "tc" in norm_title:
            triggers.extend(["tomografia", "tc", "tc de torax", "tc de abdome", "angiotomografia"])
        if "fast" in norm_k or "ultrassom" in norm_title or "efast" in norm_k:
            triggers.extend(["fast", "e-fast", "efast", "ultrassom", "ultrasonografia", "ultrassonografia beira leito"])
        if "troponina" in norm_k or "enzimas" in norm_title:
            triggers.extend(["troponina", "enzimas cardiacas", "curva de troponina"])
        if "hemograma" in norm_k or "leucocitos" in norm_title:
            triggers.extend(["hemograma", "leucograma", "plaquetas"])

        if any(trig in norm_msg for trig in triggers):
            if not any(a.get("target") == k for a in actions_executed):
                act_res = execute_osce_action(db, session_id, user_id, "lab_imaging", k, elapsed_seconds)
                actions_executed.append(act_res)
                spoken_queue.append({
                    "speaker": "examinador",
                    "text": act_res["examiner_message"]
                })

    # 4. Detecta Exame Físico / Ausculta
    findings = exam.get("findings", {})
    for segment, desc in findings.items():
        norm_seg = _normalize_text(segment)
        seg_triggers = [norm_seg]
        if norm_seg == "cardiovascular":
            seg_triggers.extend(["ausculta cardiaca", "coracao", "bulhas", "sopros"])
        elif norm_seg == "respiratorio":
            seg_triggers.extend(["ausculta pulmonar", "pulmao", "murmurio", "respiracao", "estertores", "sibilos"])
        elif norm_seg == "abdome":
            seg_triggers.extend(["palpacao do abdome", "palpar abdome", "exame do abdome", "descompressao", "blumberg", "ruidos hidroaereos"])
        elif norm_seg == "geral":
            seg_triggers.extend(["exame geral", "estado geral", "aspecto geral", "hidratacao", "mucosas"])

        if any(trig in norm_msg for trig in seg_triggers):
            if not any(a.get("target") == segment for a in actions_executed):
                act_res = execute_osce_action(db, session_id, user_id, "physical_exam", segment, elapsed_seconds)
                actions_executed.append(act_res)
                spoken_queue.append({
                    "speaker": "examinador",
                    "text": act_res["examiner_message"]
                })

        # 4.5 Detecta Procedimentos Beira-Leito e Manequim por Voz
    proc_triggers = [
        ("puncture", "thoracocentesis", ["puncao de alivio", "toracocentese", "descompressao toracica", "descomprimir torax", "segundo espaco"]),
        ("drainage", "chest_tube", ["dreno de torax", "drenagem toracica", "selo d'agua", "dreno tubular", "quinto espaco"]),
        ("maneuver", "hamilton", ["manobra de hamilton", "massagem bimanual", "compressao bimanual", "compressao uterina"]),
        ("cardioversion", "cardioversion", ["cardioversao", "cardioverter", "choque sincronizado", "cardioversao eletrica"]),
        ("vascular", "intraosseous", ["puncao intraossea", "acesso intraosseo", "via intraossea"]),
        ("vascular", "central_vein", ["acesso venoso central", "puncao de subclavia", "puncao de jugular"]),
        ("efast", "morrison", ["janela hepatorrenal", "espaco de morrison", "janela de morrison"]),
        ("efast", "splenorenal", ["janela esplenorrenal", "recesso de koller"]),
        ("efast", "pelvic", ["janela pelvica", "janela suprapubica", "fundo de saco posterior"]),
        ("efast", "pericardial", ["janela pericardica", "janela subxifoide", "subxifoidea"]),
        ("efast", "pleural_right", ["fast pleural", "ultrassom pulmonar", "deslizamento pleural", "lung sliding"]),
    ]
    for p_type, p_site, p_keywords in proc_triggers:
        if any(kw in norm_msg for kw in p_keywords):
            if not any(a.get("action_type") == "procedure" and a.get("target") == p_site for a in actions_executed):
                act_proc = perform_osce_procedure(db, session_id, user_id, p_type, p_site, elapsed_seconds)
                actions_executed.append({
                    "action_type": "procedure",
                    "target": p_site,
                    "examiner_message": act_proc["examiner_message"],
                    "payload": act_proc,
                    "elapsed_seconds": elapsed_seconds
                })
                spoken_queue.extend(act_proc.get("spoken_queue", []))

    # 4.6 Detecta Prescrição Farmacológica Verbalizada
    if any(kw in norm_msg for kw in ["prescrevo", "prescrever", "administro", "administrar", "infundir", "faco"]) or (is_conduct_verbalized and any(drg["id"] in norm_msg for drg in EMERGENCY_DRUGS_CATALOG)):
        found_drugs = []
        for drug in EMERGENCY_DRUGS_CATALOG:
            d_name = drug["name"]
            d_id = drug["id"]
            d_norm = _normalize_text(d_name)
            drug_kws = [d_id, _normalize_text(d_name.split("(")[0])]
            if d_id == "adrenalina":
                drug_kws.extend(["adrenalina", "epinefrina"])
            elif d_id == "sf09":
                drug_kws.extend(["soro fisiologico", "sf 0,9", "sf 0.9", "cloreto de sodio"])
            elif d_id == "ringers_lactate":
                drug_kws.extend(["ringer lactato", "ringer"])
            elif d_id == "tranexamico":
                drug_kws.extend(["acido tranexamico", "transamin", "tranexamico"])
            elif d_id == "aas":
                drug_kws.extend(["aas", "aspirina", "acido acetilsalicilico"])
            elif d_id == "noradrenalina":
                drug_kws.extend(["noradrenalina", "nora"])
            elif d_id == "gluconato_calcio":
                drug_kws.extend(["gluconato de calcio", "gluconato"])
            elif d_id == "insulina_regular":
                drug_kws.extend(["insulina regular", "insulina"])
            elif d_id == "sg50":
                drug_kws.extend(["glicose 50", "sg 50", "glicoinsulina"])
            elif d_id == "kcl":
                drug_kws.extend(["cloreto de potassio", "kcl"])
            elif d_id == "sulfato_magnesio":
                drug_kws.extend(["sulfato de magnesio", "sulfato"])
            elif d_id == "atropina":
                drug_kws.extend(["atropina"])

            if any(dkw in norm_msg for dkw in drug_kws):
                route = drug.get("routes", ["EV"])[0]
                if "intramuscular" in norm_msg or " im " in f" {norm_msg} ":
                    route = "IM"
                elif "endovenos" in norm_msg or " ev " in f" {norm_msg} " or " iv " in f" {norm_msg} ":
                    route = "EV"
                elif "subcutan" in norm_msg or " sc " in f" {norm_msg} ":
                    route = "SC"
                elif "oral" in norm_msg or " vo " in f" {norm_msg} " or "mastigad" in norm_msg:
                    route = "VO"

                found_drugs.append({
                    "drug_name": d_name.split("(")[0].strip(),
                    "dose": drug.get("default_dose", "1"),
                    "unit": drug.get("default_unit", "ampola"),
                    "route": route,
                    "notes": "Prescrito por comando de voz viva-voz beira-leito"
                })

        if found_drugs and not any(a.get("action_type") == "prescription" for a in actions_executed):
            act_presc = prescribe_osce_drugs(db, session_id, user_id, found_drugs, elapsed_seconds)
            actions_executed.append({
                "action_type": "prescription",
                "target": "voice_prescription",
                "examiner_message": act_presc["examiner_message"],
                "payload": act_presc,
                "elapsed_seconds": elapsed_seconds
            })
            spoken_queue.extend(act_presc.get("spoken_queue", []))

    # 5. Se houver conduta verbalizada, adiciona confirmação do examinador
    if is_conduct_verbalized:
        examiner_confirm = "Examinador registra: Conduta verbalizada pelo candidato anotada no barema."
        spoken_queue.append({
            "speaker": "examinador",
            "text": examiner_confirm
        })

    # 6. Avalia se a fala também contém interação com o Paciente
    patient_dialogue_triggers = [
        "dona", "senhor", "senhora", "voce", "vc", "como vai", "ola", "bom dia", "boa tarde",
        "boa noite", "onde doi", "qual e a dor", "quando comecou", "falta de ar", "remedio",
        "toma algum", "alergia", "fuma", "bebe", "antecedentes", "familia", "febre", "vomito",
        "vomitou", "sente", "o que aconteceu", "me conta", "calma", "estou aqui", "vamos cuidar"
    ]
    is_patient_dialogue = (
        len(actions_executed) == 0 and not is_conduct_verbalized
    ) or any(trig in norm_msg for trig in patient_dialogue_triggers)

    patient_reply_text = ""
    if is_patient_dialogue:
        interact_res = interact_osce_session(db, session_id, user_id, clean_msg, elapsed_seconds)
        patient_reply_text = interact_res.get("reply", "")
        if patient_reply_text:
            spoken_queue.append({
                "speaker": "paciente",
                "text": patient_reply_text
            })

    # Recupera o transcript e ações atualizados
    updated_sess = db.execute("""
        SELECT s.transcript_json, s.actions_taken_json, st.checklist_barema_json
        FROM osce_sessions s
        JOIN osce_stations st ON s.station_id = st.id
        WHERE s.id = ?
    """, (session_id,)).fetchone()
    current_transcript = json.loads(updated_sess["transcript_json"] or "[]")
    current_actions = json.loads(updated_sess["actions_taken_json"] or "[]")

    res_dispatch: dict[str, Any] = {
        "transcription": clean_msg,
        "actions_executed": actions_executed,
        "is_patient_dialogue": is_patient_dialogue,
        "patient_reply": patient_reply_text,
        "spoken_queue": spoken_queue,
        "transcript": current_transcript,
        "elapsed_seconds": elapsed_seconds
    }

    if get_session_mode(current_actions) == "guided":
        barema_raw = json.loads(updated_sess["checklist_barema_json"] or "{}")
        checklist_items = barema_raw.get("items", []) if isinstance(barema_raw, dict) else (barema_raw if isinstance(barema_raw, list) else [])
        res_dispatch["guided_feedback"] = evaluate_live_barema_progress(checklist_items, current_transcript, current_actions, elapsed_seconds)

    return res_dispatch


def finish_osce_session(
    db,
    session_id: str,
    user_id: str,
    conduct_notes: Optional[str] = None
) -> dict[str, Any]:
    """
    Finaliza a estação de prova prática e executa a auditoria completa do Barema Oficial (Etapa 4):
    - Motor Determinístico de Red Flags (Iatrogenias, ABCDE, Farmacologia e Choque)
    - Cálculo de Nota Bruta, Deduções e Travas de Teto de Segurança (caps_station_at)
    - Emissão do Veredito Oficial da Banca (APROVADO COM DISTINÇÃO, LIMITE, REPROVADO, ELIMINADO)
    - Radar de 5 Competências Médicas Fundamentais
    - Parecer do Preceptor Chefe com Conduta Canônica Padrão-Ouro
    - Prescrição de Remediação no MedQuest e Flashcards de Choque
    """
    sess = db.execute("""
        SELECT s.id, s.station_id, s.user_id, s.start_time, s.elapsed_seconds,
               s.transcript_json, s.actions_taken_json,
               st.title, st.area, st.subtema, st.institution, st.year,
               st.checklist_barema_json
        FROM osce_sessions s
        JOIN osce_stations st ON s.station_id = st.id
        WHERE s.id = ?
    """, (session_id,)).fetchone()

    if not sess:
        raise ValueError("Sessão não encontrada.")

    transcript = json.loads(sess["transcript_json"] or "[]")
    actions = json.loads(sess["actions_taken_json"] or "[]")
    barema_raw = json.loads(sess["checklist_barema_json"] or "{}")
    checklist_items = barema_raw.get("items", []) if isinstance(barema_raw, dict) else (barema_raw if isinstance(barema_raw, list) else [])
    critical_errors = barema_raw.get("critical_errors", []) if isinstance(barema_raw, dict) else []

    if conduct_notes and conduct_notes.strip():
        transcript.append({
            "sender": "candidato",
            "message": f"Conduta e Prescrição Verbalizada: {conduct_notes.strip()}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": int(sess["elapsed_seconds"] or 0)
        })

    # Reúne todo o texto produzido pelo aluno e ações realizadas
    candidate_texts = [
        str(t.get("message") or "").lower() for t in transcript if t.get("sender") == "candidato"
    ]
    actions_texts = [
        f"{a.get('action_type', '')} {a.get('action_target', '')} {a.get('anatomical_site', '')} {a.get('findings', '')}".lower()
        for a in actions
    ]
    all_evidence_corpus = " ".join(candidate_texts + actions_texts)
    norm_evidence_corpus = _normalize_text(all_evidence_corpus)

    total_score = 0.0
    max_score = 0.0
    evaluated_items = []
    shock_cards = []

    for item in checklist_items:
        weight = float(item.get("weight", 1.0))
        max_score += weight
        keywords = item.get("keywords", [])

        matches = [kw for kw in keywords if _normalize_text(kw) in norm_evidence_corpus]
        match_ratio = len(matches) / max(1, len(keywords))

        if match_ratio >= 0.4 or len(matches) >= 2:
            earned = weight
            status = "cumprido_total"
            evidence = f"Identificado na conduta do candidato: termos [{', '.join(matches[:4])}]."
        elif match_ratio > 0.15 or len(matches) == 1:
            earned = round(weight * 0.5, 2)
            status = "cumprido_parcial"
            evidence = f"Cumprimento parcial identificado com o termo [{matches[0]}]."
        else:
            earned = 0.0
            status = "nao_cumprido"
            evidence = "Critério não contemplado nas falas ou ações do candidato durante o tempo de prova."

        total_score += earned
        evaluated_items.append({
            "id": item.get("id"),
            "criterion_id": str(item.get("id", "")),
            "code": str(item.get("code", item.get("id", "ITEM"))),
            "title": item.get("title"),
            "description": item.get("description", item.get("title", "")),
            "category": item.get("category", "Geral"),
            "weight": weight,
            "max_score": weight,
            "score_earned": earned,
            "awarded_score": earned,
            "status": "FULL" if status == "cumprido_total" else ("PARTIAL" if status == "cumprido_parcial" else "NONE"),
            "timestamp_achieved_sec": int(sess["elapsed_seconds"] or 0) if status != "nao_cumprido" else None,
            "evidence": evidence,
            "evidence_citation": evidence
        })

        if status != "cumprido_total":
            shock_cards.append({
                "station_code": sess["subtema"],
                "front": f"🚨 [OSCE {sess['institution']} - {sess['area']}]\nQual é a conduta obrigatória segundo o barema oficial para:\n👉 **{item.get('title')}**?",
                "back": f"💡 **Critério de Avaliação da Banca**:\n{item.get('description', '')}\n\n⚠️ **Palavras-chave de aprovação**: {', '.join(item.get('keywords', []))}",
                "category": item.get("category"),
                "weight": weight
            })

    raw_score_normalized = round(min(10.0, (total_score / max(1.0, max_score)) * 10.0), 1)

    # 1. Auditoria Avançada de Red Flags (Etapa 4)
    red_flags = evaluate_osce_red_flags(
        actions=actions,
        transcript=transcript,
        station_meta=dict(sess),
        checklist_items=checklist_items
    )

    # Auditoria Legada de Segurança Clínica
    critical_warnings = evaluate_critical_safety_violations(
        critical_errors=critical_errors,
        evidence_text=all_evidence_corpus,
        actions=actions,
        station_meta=dict(sess)
    )
    for warn in critical_warnings:
        if not any(rf["title"] == warn for rf in red_flags):
            red_flags.append({
                "code": "RF_CLINICAL_SAFETY",
                "title": "Violação de Segurança Clínica",
                "description": warn,
                "timestamp_sec": 0,
                "score_deduction": 1.5,
                "clinical_consequence": "Quebra de diretriz de segurança estabelecida no barema."
            })

    # 2. Cálculo da Nota Final com Dedução e Travas de Teto (Caps)
    total_penalty = round(sum(rf.get("score_deduction", 0.0) for rf in red_flags), 1)
    computed_final = max(0.0, raw_score_normalized - total_penalty)

    # Aplica trava de teto máximo de segurança (Fatal Flaw)
    min_cap = min([rf["caps_station_at"] for rf in red_flags if "caps_station_at" in rf], default=None)
    if min_cap is not None:
        computed_final = min(computed_final, min_cap)
    final_score_normalized = round(computed_final, 1)

    # 3. Determinação do Veredito Oficial da Banca
    if any(rf.get("caps_station_at", 10.0) <= 4.0 for rf in red_flags):
        headline_verdict = "ELIMINADO POR IATROGENIA"
    elif final_score_normalized < 7.0:
        headline_verdict = "REPROVADO POR TÉCNICA"
    elif final_score_normalized < 8.5:
        headline_verdict = "APROVADO NO LIMITE"
    else:
        headline_verdict = "APROVADO COM DISTINÇÃO"

    # Gera Flashcards de Choque específicos para contraindicações graves violadas
    for warn in critical_warnings:
        shock_cards.append({
            "station_code": sess["subtema"],
            "front": (
                f"🚨 [ERRO CRÍTICO / CONTRAINDICAÇÃO - {sess['institution']}]\n"
                f"Qual é a regra de segurança clínica violada em:\n"
                f"👉 **{sess['title']}**?"
            ),
            "back": (
                f"⛔ **Falta Grave / Conduta de Risco**:\n{warn}\n\n"
                "⚠️ Em prova prática, esta conduta acarreta perda severa de barema ou eliminação imediata."
            ),
            "category": "seguranca_farmacologica",
            "weight": 2.0
        })

    # Gera Flashcards de Choque específicos para Red Flags anatômicas / cirúrgicas
    for rf in red_flags:
        if rf.get("code") != "RF_CLINICAL_SAFETY":
            shock_cards.append({
                "station_code": sess["subtema"],
                "front": (
                    f"🚨 [ERRO CRÍTICO / CONTRAINDICAÇÃO - {sess['institution']}]\n"
                    f"Qual é o risco fatal de:\n"
                    f"👉 **{rf['title']}**?"
                ),
                "back": (
                    f"⛔ **Consequência Clínica**:\n{rf['clinical_consequence']}\n\n"
                    f"⚠️ **Descrição da Falha**: {rf['description']}\n\n"
                    "Em prova de 2ª fase presencial, esta falha acarreta eliminação imediata ou corte severo de nota."
                ),
                "category": "seguranca_paciente",
                "weight": 2.5
            })

    # 4. Computa Timeline Post-Mortem e Radar de Competências em 5D
    timeline_data = generate_timeline_post_mortem(
        station_meta=dict(sess),
        transcript=transcript,
        actions=actions,
        evaluated_items=evaluated_items,
        elapsed_seconds=sess["elapsed_seconds"]
    )

    radar_5d = compute_competency_radar_5d(
        station_meta=dict(sess),
        evaluated_items=evaluated_items,
        actions=actions,
        transcript=transcript,
        elapsed_seconds=sess["elapsed_seconds"],
        red_flags=red_flags
    )

    radar_data = generate_competency_radar(
        station_meta=dict(sess),
        evaluated_items=evaluated_items,
        actions=actions,
        transcript=transcript,
        elapsed_seconds=sess["elapsed_seconds"],
        critical_warnings=[rf["description"] for rf in red_flags]
    )

    chief_review = build_chief_preceptor_review(
        station_meta=dict(sess),
        evaluated_items=evaluated_items,
        red_flags=red_flags,
        final_score=final_score_normalized
    )

    medquest_remediation = build_medquest_remediation(
        station_meta=dict(sess),
        weaknesses=radar_data.get("weaknesses", [])
    )

    preceptor_feedback = {
        "headline_verdict": headline_verdict,
        "raw_score": raw_score_normalized,
        "penalty_deduction": total_penalty,
        "final_score": final_score_normalized,
        "cutoff_score": 7.0,
        "max_score": 10.0,
        "approved": final_score_normalized >= 7.0 and headline_verdict != "ELIMINADO POR IATROGENIA",
        "station_title": sess["title"],
        "institution": sess["institution"],
        "summary": chief_review["executive_summary"],
        "competency_radar_5d": radar_5d,
        "competency_radar": radar_data,
        "evaluated_items": evaluated_items,
        "red_flags_triggered": red_flags,
        "critical_warnings": [rf["description"] for rf in red_flags],
        "chief_preceptor_review": chief_review,
        "medquest_remediation": medquest_remediation,
        "shock_cards_count": len(shock_cards),
        "timeline_post_mortem": timeline_data
    }

    now_iso = datetime.now(timezone.utc).isoformat()
    with db_transaction(db, immediate=True):
        db.execute("""
            UPDATE osce_sessions
            SET status = 'completed',
                end_time = ?,
                final_score = ?,
                checklist_evaluation_json = ?,
                preceptor_feedback_json = ?,
                transcript_json = ?
            WHERE id = ?
        """, (
            now_iso,
            final_score_normalized,
            json.dumps({"items": evaluated_items, "critical_warnings": [rf["description"] for rf in red_flags], "red_flags": red_flags}, ensure_ascii=False),
            json.dumps(preceptor_feedback, ensure_ascii=False),
            json.dumps(transcript, ensure_ascii=False),
            session_id
        ))

    return {
        "session_id": session_id,
        "final_score": final_score_normalized,
        "raw_score": raw_score_normalized,
        "penalty_deduction": total_penalty,
        "headline_verdict": headline_verdict,
        "approved": preceptor_feedback["approved"],
        "status": "completed",
        "evaluated_items": evaluated_items,
        "red_flags_triggered": red_flags,
        "preceptor_feedback": preceptor_feedback,
        "chief_preceptor_review": chief_review,
        "competency_radar_5d": radar_5d,
        "medquest_remediation": medquest_remediation,
        "shock_cards": shock_cards,
        "elapsed_seconds": sess["elapsed_seconds"],
        "timeline_post_mortem": timeline_data,
        "competency_radar": radar_data
    }


def get_osce_session_report(db, session_id: str, user_id: str) -> Optional[dict[str, Any]]:
    """Recupera o espelho oficial de prova e relatório detalhado pós-sessão com Timeline e Radar."""
    row = db.execute("""
        SELECT s.id, s.station_id, s.user_id, s.status, s.start_time, s.end_time,
               s.elapsed_seconds, s.final_score, s.transcript_json, s.actions_taken_json,
               s.checklist_evaluation_json, s.preceptor_feedback_json,
               st.code, st.title, st.area, st.subtema, st.institution, st.year,
               st.duration_seconds, st.scenario_door_markdown
        FROM osce_sessions s
        JOIN osce_stations st ON s.station_id = st.id
        WHERE s.id = ?
    """, (session_id,)).fetchone()

    if not row:
        return None

    evaluation = json.loads(row["checklist_evaluation_json"] or "{}")
    feedback = json.loads(row["preceptor_feedback_json"] or "{}")
    transcript = json.loads(row["transcript_json"] or "[]")
    actions = json.loads(row["actions_taken_json"] or "[]")

    timeline_data = feedback.get("timeline_post_mortem")
    radar_data = feedback.get("competency_radar")

    if not timeline_data or not radar_data:
        timeline_data = generate_timeline_post_mortem(
            station_meta=dict(row),
            transcript=transcript,
            actions=actions,
            evaluated_items=evaluation.get("items", []),
            elapsed_seconds=row["elapsed_seconds"]
        )
        radar_data = generate_competency_radar(
            station_meta=dict(row),
            evaluated_items=evaluation.get("items", []),
            actions=actions,
            transcript=transcript,
            elapsed_seconds=row["elapsed_seconds"],
            critical_warnings=evaluation.get("critical_warnings", [])
        )

    return {
        "session_id": row["id"],
        "station_id": row["station_id"],
        "code": row["code"],
        "title": row["title"],
        "area": row["area"],
        "subtema": row["subtema"],
        "institution": row["institution"],
        "year": row["year"],
        "status": row["status"],
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "elapsed_seconds": row["elapsed_seconds"],
        "duration_seconds": row["duration_seconds"],
        "final_score": row["final_score"],
        "scenario_door_markdown": row["scenario_door_markdown"],
        "checklist_evaluation": evaluation.get("items", []),
        "critical_warnings": evaluation.get("critical_warnings", []),
        "preceptor_feedback": feedback,
        "transcript": transcript,
        "timeline_post_mortem": timeline_data,
        "competency_radar": radar_data
    }


# =========================================================================
# VETOR 2: CATÁLOGOS E MOTORES DE PRESCRIÇÃO E MANEQUIM INTERATIVO
# =========================================================================



def get_emergency_drugs_catalog() -> list[dict[str, Any]]:
    """Retorna o catálogo completo de medicamentos da sala de emergência do OSCE."""
    return EMERGENCY_DRUGS_CATALOG


def get_procedures_catalog() -> list[dict[str, Any]]:
    """Retorna o catálogo de procedimentos beira-leito e janelas E-FAST para o manequim 2D."""
    return PROCEDURES_CATALOG


def prescribe_osce_drugs(
    db,
    session_id: str,
    user_id: str,
    prescription_items: list[dict[str, Any]],
    elapsed_seconds: int = 0
) -> dict[str, Any]:
    """
    Processa a assinatura de uma prescrição médica estruturada na Sala Vermelha / Emergência:
    - Analisa os fármacos e doses prescritos contra o checklist e regras clínicas da estação.
    - Notifica a intervenção da equipe de enfermagem da banca.
    - Enfileira fala do examinador para TTS imediato.
    """
    sess = db.execute("""
        SELECT s.id, s.station_id, s.status, s.actions_taken_json, s.transcript_json,
               st.code, st.title, st.checklist_barema_json, st.scenario_door_markdown
        FROM osce_sessions s
        JOIN osce_stations st ON s.station_id = st.id
        WHERE s.id = ?
    """, (session_id,)).fetchone()

    if not sess:
        raise ValueError("Sessão não encontrada.")
    if sess["status"] != "in_progress":
        return {"error": "Sessão finalizada."}

    actions = json.loads(sess["actions_taken_json"] or "[]")
    transcript = json.loads(sess["transcript_json"] or "[]")
    barema_raw = json.loads(sess["checklist_barema_json"] or "{}")
    barema_items = barema_raw.get("items", []) if isinstance(barema_raw, dict) else (barema_raw if isinstance(barema_raw, list) else [])
    now_iso = datetime.now(timezone.utc).isoformat()

    if not prescription_items:
        return {"error": "Nenhum medicamento informado na prescrição."}

    # Monta a descrição legível e busca correspondências no barema
    drug_summaries: list[str] = []
    matched_checklist_titles: list[str] = []

    for item in prescription_items:
        name = item.get("drug_name", "Medicamento").strip()
        dose = item.get("dose", "").strip()
        unit = item.get("unit", "").strip()
        route = item.get("route", "").strip()
        notes = item.get("notes", "").strip()

        desc_parts = [name]
        if dose:
            desc_parts.append(f"{dose} {unit}".strip())
        if route:
            desc_parts.append(f"via {route}")
        if notes:
            desc_parts.append(f"({notes})")

        drug_summaries.append(" ".join(desc_parts))

        # Checa pertinência com os itens de tratamento do barema da estação
        norm_item = _normalize_text(f"{name} {dose} {unit} {route} {notes}")
        for crit in barema_items:
            if isinstance(crit, dict) and crit.get("category") in ("conduta_tratamento", "tratamento", "conduta"):
                for kw in crit.get("keywords", []):
                    if _normalize_text(kw) in norm_item:
                        if crit.get("title") not in matched_checklist_titles:
                            matched_checklist_titles.append(crit.get("title", ""))

    prescription_text = "; ".join(drug_summaries)
    examiner_message = (
        f"Prescrição da Sala de Emergência recebida pela equipe de enfermagem: {prescription_text}. "
        "Fármacos checados e administrados conforme prescrito. Sinais vitais em monitorização contínua."
    )

    action_record = {
        "action_type": "prescription",
        "action_target": "emergency_prescription",
        "prescription_items": prescription_items,
        "matched_criteria": matched_checklist_titles,
        "elapsed_seconds": elapsed_seconds,
        "timestamp": now_iso
    }

    spoken_queue: list[dict[str, str]] = [
        {"speaker": "examinador", "text": f"Prescrição recebida e administrada pela enfermagem beira-leito: {prescription_text}."}
    ]

    actions.append(action_record)
    transcript.append({
        "sender": "examinador",
        "message": examiner_message,
        "timestamp": now_iso,
        "elapsed_seconds": elapsed_seconds,
        "action_payload": {
            "type": "prescription",
            "items": prescription_items,
            "matched_criteria": matched_checklist_titles
        }
    })

    with db_transaction(db, immediate=True):
        db.execute("""
            UPDATE osce_sessions
            SET actions_taken_json = ?, transcript_json = ?, elapsed_seconds = ?
            WHERE id = ?
        """, (
            json.dumps(actions, ensure_ascii=False),
            json.dumps(transcript, ensure_ascii=False),
            elapsed_seconds,
            session_id
        ))

    res_presc: dict[str, Any] = {
        "success": True,
        "prescription_text": prescription_text,
        "examiner_message": examiner_message,
        "matched_criteria": matched_checklist_titles,
        "spoken_queue": spoken_queue,
        "elapsed_seconds": elapsed_seconds
    }

    if get_session_mode(actions) == "guided":
        res_presc["guided_feedback"] = evaluate_live_barema_progress(barema_items, transcript, actions, elapsed_seconds)

    return res_presc


def perform_osce_procedure(
    db,
    session_id: str,
    user_id: str,
    procedure_type: str,
    anatomical_site: str,
    elapsed_seconds: int = 0
) -> dict[str, Any]:
    """
    Executa um procedimento invasivo ou varredura ultrassonográfica (E-FAST) no manequim 2D beira-leito.
    """
    sess = db.execute("""
        SELECT s.id, s.station_id, s.status, s.actions_taken_json, s.transcript_json,
               st.code, st.title, st.physical_exam_json, st.lab_imaging_json, st.checklist_barema_json
        FROM osce_sessions s
        JOIN osce_stations st ON s.station_id = st.id
        WHERE s.id = ?
    """, (session_id,)).fetchone()

    if not sess:
        raise ValueError("Sessão não encontrada.")
    if sess["status"] != "in_progress":
        return {"error": "Sessão finalizada."}

    actions = json.loads(sess["actions_taken_json"] or "[]")
    transcript = json.loads(sess["transcript_json"] or "[]")
    station_code = sess["code"]
    labs = json.loads(sess["lab_imaging_json"] or "{}")
    now_iso = datetime.now(timezone.utc).isoformat()

    site_clean = anatomical_site.strip().lower()
    proc_type_clean = procedure_type.strip().lower()

    examiner_message = ""
    findings_desc = ""
    is_positive_finding = False
    image_url: Optional[str] = None

    # 1. VARREDURA ULTRASSONOGRÁFICA E-FAST (POCUS)
    if proc_type_clean in ("efast", "efast_probe", "fast") or site_clean in (
        "morrison", "splenorenal", "pelvic", "pericardial", "pleural_right", "pleural_left",
        "efast_ruq_morrison", "efast_morrison_ruq", "efast_luq_splenorenal", "efast_splenorenal_luq",
        "efast_subxiphoid_pericardial", "efast_suprapubic_pelvic"
    ):
        is_trauma_fast = "FAST" in station_code or "trauma" in sess["title"].lower() or "politrauma" in sess["title"].lower()

        if site_clean in ("morrison", "efast_ruq_morrison", "efast_morrison_ruq"):
            if is_trauma_fast:
                findings_desc = (
                    "Janela Hepatorrenal (Morrison): Presença de lâmina fina de líquido livre anecoico "
                    "no recesso entre o lobo hepático direito e o córtex renal anterior. Espaço de Morrison POSITIVO para líquido livre."
                )
                is_positive_finding = True
            else:
                findings_desc = "Janela Hepatorrenal (Morrison): Interface hepatorrenal nítida sem acúmulo de líquido anecoico."
        elif site_clean in ("splenorenal", "efast_luq_splenorenal", "efast_splenorenal_luq"):
            if is_trauma_fast:
                findings_desc = (
                    "Janela Esplenorrenal (Recesso de Koller): Presença de volumosa quantidade de líquido livre anecoico "
                    "circundando o polo inferior e hilo do baço, com irregularidade cortical compatível com laceração esplênica ativa. FAST POSITIVO."
                )
                is_positive_finding = True
            else:
                findings_desc = "Janela Esplenorrenal: Recesso de Koller sem coleções ou líquido livre visível."
        elif site_clean in ("pelvic", "efast_suprapubic_pelvic"):
            if is_trauma_fast:
                findings_desc = (
                    "Janela Pélvica / Suprapúbica: Presença de líquido livre anecoico acumulado no fundo de saco peritoneal posterior. FAST POSITIVO."
                )
                is_positive_finding = True
            else:
                findings_desc = "Janela Pélvica: Bexiga fisiologicamente preenchida, sem líquido livre em escavação pélvica."
        elif site_clean in ("pericardial", "efast_subxiphoid_pericardial"):
            findings_desc = (
                "Janela Subxifoide / Pericárdica: Espaço pericárdico virtual preservado, sem lâmina anecoica ou "
                "sinais de tamponamento cardíaco. Contratilidade ventricular preservada."
            )
        elif site_clean in ("pleural_right", "pleural_left"):
            is_right = "right" in site_clean
            findings_desc = (
                f"E-FAST Pleuropulmonar {'Direito' if is_right else 'Esquerdo'}: Deslizamento pleural ('lung sliding') presente, "
                "com linhas A fisiológicas e sinal da praia no Modo M. Ausência de pneumotórax neste hemitórax."
            )
        else:
            findings_desc = f"Varredura ultrassonográfica no sítio {anatomical_site}: Estruturas anatômicas avaliadas sem coleções agudas adicionais."

        examiner_message = f"Examinador entrega imagem do E-FAST: {findings_desc}"

    # 2. TORACOCENTESE DE ALÍVIO COM AGULHA & IATROGENIA DE BORDA DE COSTELA
    elif proc_type_clean in ("puncture", "thoracocentesis", "thoracocentesis_relief") or "thoracocentesis" in site_clean:
        if "inferior_border" in site_clean or "iatrogenic" in site_clean:
            findings_desc = (
                "IATROGENIA GRAVE: Agulha introduzida rente à BORDA INFERIOR da costela superior, "
                "lacerando a artéria intercostal! Observa-se saída de sangue vivo em jato pulsátil e piora hemodinâmica imediata (Hemotórax Iatrogênico)!"
            )
            is_positive_finding = False
        else:
            findings_desc = (
                "Descompressão torácica com Jelco calibroso na borda superior da costela! "
                "Ocorre escape audível e vigoroso de ar sob alta pressão (\"HISS\" audível)! "
                "A turgência jugular atenua e a expansão torácica melhora expressivamente."
            )
            is_positive_finding = True
        examiner_message = f"Procedimento de Toracocentese de Alívio: {findings_desc}"

    # 3. DRENAGEM TORÁCICA TUBULAR EM SELO D'ÁGUA
    elif proc_type_clean in ("drainage", "chest_tube", "chest_tube_insertion") or "chest_tube" in site_clean:
        findings_desc = (
            "Dreno torácico tubular 32 Fr introduzido no 5º EIC na linha axilar média (triângulo de segurança) "
            "e conectado a selo d'água. Dreno posicionado com sucesso e fixado com bailarina. "
            "Observa-se oscilação adequada da coluna d'água e drenagem gasosa/serossanguinolenta imediata."
        )
        examiner_message = f"Drenagem Torácica Fechada: {findings_desc}"
        is_positive_finding = True

    # 4. VIA AÉREA CIRÚRGICA / CRICOTIREOIDOSTOMIA
    elif proc_type_clean in ("cricothyroidotomy", "surgical_cricothyroidotomy") or "cricoid" in site_clean or "thyroid" in site_clean:
        if "thyroid_gland" in site_clean or "iatrogenic" in site_clean:
            findings_desc = (
                "IATROGENIA CRÍTICA: Incisão cirúrgica realizada ABAIXO da cartilagem cricoide sobre o istmo da tireoide! "
                "Hemorragia cervical maciça imediata inundando o campo cirúrgico e a traqueia!"
            )
            is_positive_finding = False
        else:
            findings_desc = (
                "Cricotireoidostomia cirúrgica de emergência executada com perfeição: incisão horizontal na membrana cricotireoidea, "
                "dilatação com pinça hemostática, introdução de tubo traqueal nº 6.0 e balonete insuflado. "
                "Ventilação mecânica restabelecida com expansão torácica bilateral simétrica!"
            )
            is_positive_finding = True
        examiner_message = f"Via Aérea Cirúrgica de Emergência: {findings_desc}"

    # 5. MANOBRA DE HAMILTON (COMPRESSÃO BIMANUAL UTERINA)
    elif proc_type_clean in ("maneuver", "hamilton") or "hamilton" in site_clean:
        is_hpp = "HPP" in station_code or "hemorragia" in sess["title"].lower() or "atonia" in sess["title"].lower()
        if is_hpp:
            findings_desc = (
                "Manobra de compressão bimanual de Hamilton iniciada imediatamente: punho cerrado no fundo de saco anterior "
                "da vagina contra a parede anterior uterina e mão abdominal tracionando o fundo para frente. "
                "O útero contrai parcialmente sob a compressão com redução do sangramento vaginal em jato."
            )
            is_positive_finding = True
        else:
            findings_desc = "Manobra executada conforme a técnica obstétrica padrão."
        examiner_message = f"Manobra Obstétrica Beira-Leito: {findings_desc}"

    # 6. CARDIOVERSÃO ELÉTRICA SINCRONIZADA
    elif proc_type_clean in ("cardioversion",) or "cardioversion" in site_clean:
        is_tv = "TV" in station_code or "taquicardia" in sess["title"].lower()
        if is_tv:
            findings_desc = (
                "Pás de desfibrilador posicionadas com gel (infraclavicular direita e ápice cardíaco). "
                "Modo sincronizado ATIVADO, flag nas ondas R confirmado. Sedação rápida administrada. "
                "A equipe afasta-se e o choque de 100 Joules é disparado! O monitor acusa reversão imediata para Ritmo Sinusal, "
                "FC 84 bpm, pulsos amplos e PA normalizada em 115x75 mmHg!"
            )
            is_positive_finding = True
        else:
            findings_desc = "Cardioversão sincronizada realizada com choque disparado na onda R."
        examiner_message = f"Cardioversão Elétrica Sincronizada: {findings_desc}"

    # 7. ACESSO VENOSO PROFUNDO / INTRAÓSSEO
    elif proc_type_clean in ("vascular", "intraosseous", "intraosseous_access", "central_line_insertion") or "intraosseous" in site_clean or "central_vein" in site_clean or "seldinger" in site_clean or "tibia" in site_clean:
        if "intraosseous" in site_clean or "tibia" in site_clean or proc_type_clean in ("intraosseous", "intraosseous_access"):
            findings_desc = (
                "Punção intraóssea realizada na tíbia proximal (2 cm abaixo e medial à tuberosidade tibial). "
                "Aspiração de medula óssea positiva e infusão livre de soro sem extravasamento. Via de emergência garantida."
            )
        else:
            findings_desc = (
                "Acesso venoso central obtido por punção de veia jugular interna direita sob técnica de Seldinger. "
                "Refluxo venoso escuro livre e infusão em fluxo rápido confirmada."
            )
        examiner_message = f"Acesso Vascular de Urgência: {findings_desc}"
        is_positive_finding = True

    # OUTROS PROCEDIMENTOS
    else:
        findings_desc = f"Procedimento ({procedure_type} no sítio {anatomical_site}) realizado com sucesso pela técnica asséptica beira-leito."
        examiner_message = f"Procedimento Beira-Leito Realizado: {findings_desc}"

    action_record = {
        "action_type": "procedure",
        "procedure_type": procedure_type,
        "anatomical_site": anatomical_site,
        "findings": findings_desc,
        "is_positive": is_positive_finding,
        "elapsed_seconds": elapsed_seconds,
        "timestamp": now_iso
    }

    spoken_queue: list[dict[str, str]] = [
        {"speaker": "examinador", "text": examiner_message}
    ]

    actions.append(action_record)
    transcript.append({
        "sender": "examinador",
        "message": examiner_message,
        "timestamp": now_iso,
        "elapsed_seconds": elapsed_seconds,
        "action_payload": {
            "type": "procedure",
            "procedure_type": procedure_type,
            "anatomical_site": anatomical_site,
            "findings": findings_desc,
            "image_url": image_url
        }
    })

    with db_transaction(db, immediate=True):
        db.execute("""
            UPDATE osce_sessions
            SET actions_taken_json = ?, transcript_json = ?, elapsed_seconds = ?
            WHERE id = ?
        """, (
            json.dumps(actions, ensure_ascii=False),
            json.dumps(transcript, ensure_ascii=False),
            elapsed_seconds,
            session_id
        ))

    res_proc: dict[str, Any] = {
        "success": True,
        "procedure_type": procedure_type,
        "anatomical_site": anatomical_site,
        "findings": findings_desc,
        "is_positive": is_positive_finding,
        "examiner_message": examiner_message,
        "spoken_queue": spoken_queue,
        "elapsed_seconds": elapsed_seconds
    }

    if get_session_mode(actions) == "guided":
        barema_raw = json.loads(sess["checklist_barema_json"] or "{}")
        c_items = barema_raw.get("items", []) if isinstance(barema_raw, dict) else (barema_raw if isinstance(barema_raw, list) else [])
        res_proc["guided_feedback"] = evaluate_live_barema_progress(c_items, transcript, actions, elapsed_seconds)

    return res_proc


def get_circuit_plan(db, institution: Optional[str] = "USP-RP") -> dict[str, Any]:
    """
    Monta o Circuito Oficial de 2ª Fase com 5 estações cobrindo as 5 especialidades nucleares:
    1. Clínica Médica
    2. Cirurgia Geral
    3. Pediatria
    4. Ginecologia e Obstetrícia
    5. Medicina Preventiva
    """
    areas_order = [
        "Clínica Médica",
        "Cirurgia Geral",
        "Pediatria",
        "Ginecologia e Obstetrícia",
        "Medicina Preventiva"
    ]
    circuit_id = f"circuit-{uuid.uuid4().hex[:10]}"
    stations_selected = []

    for step_idx, area in enumerate(areas_order, 1):
        row = None
        if institution and institution != "Todas as Bancas":
            row = db.execute("""
                SELECT id, code, title, area, subtema, institution, duration_seconds
                FROM osce_stations
                WHERE area = ? AND institution = ?
                ORDER BY year DESC, id ASC
                LIMIT 1
            """, (area, institution)).fetchone()

        if not row:
            row = db.execute("""
                SELECT id, code, title, area, subtema, institution, duration_seconds
                FROM osce_stations
                WHERE area = ?
                ORDER BY year DESC, id ASC
                LIMIT 1
            """, (area,)).fetchone()

        if row:
            stations_selected.append({
                "step": step_idx,
                "station_id": row["id"],
                "code": row["code"],
                "area": row["area"],
                "subtema": row["subtema"],
                "title": row["title"],
                "institution": row["institution"],
                "duration_seconds": row["duration_seconds"]
            })

    return {
        "circuit_id": circuit_id,
        "institution": institution or "USP-RP",
        "total_steps": len(stations_selected),
        "stations": stations_selected
    }


def get_circuit_summary(db, circuit_id: str, user_id: str) -> dict[str, Any]:
    """
    Consolida as notas e avaliações do Circuito de 2ª Fase de 5 estações (escala 0.0 a 50.0).
    """
    sessions = db.execute("""
        SELECT s.id, s.station_id, s.status, s.final_score, s.elapsed_seconds,
               s.checklist_evaluation_json, s.preceptor_feedback_json,
               st.code, st.title, st.area, st.institution
        FROM osce_sessions s
        JOIN osce_stations st ON s.station_id = st.id
        WHERE s.circuit_session_id = ? AND s.user_id = ?
        ORDER BY s.start_time ASC
    """, (circuit_id, user_id)).fetchall()

    station_summaries = []
    total_score = 0.0
    total_completed = 0
    total_critical_errors = 0

    for idx, sess in enumerate(sessions, 1):
        score = float(sess["final_score"] or 0.0)
        is_completed = sess["status"] == "completed"
        if is_completed:
            total_completed += 1
            total_score += score

        fb = json.loads(sess["preceptor_feedback_json"] or "{}")
        crit_warns = fb.get("critical_warnings", [])
        total_critical_errors += len(crit_warns)

        station_summaries.append({
            "step": idx,
            "session_id": sess["id"],
            "station_id": sess["station_id"],
            "code": sess["code"],
            "area": sess["area"],
            "title": sess["title"],
            "institution": sess["institution"],
            "final_score": round(score, 1),
            "approved": score >= 7.0,
            "status": sess["status"],
            "critical_warnings": crit_warns
        })

    max_score = 50.0
    avg_score = round(total_score / max(1, total_completed), 1) if total_completed > 0 else 0.0
    percentage = round((total_score / max_score) * 100, 1)
    approved = total_completed >= 5 and total_score >= 35.0

    if approved:
        board_feedback = (
            f"Parabéns! Desempenho aprovado no Circuito Oficial de 2ª Fase com {total_score:.1f}/50.0 pontos ({percentage}%). "
            "Atendimento beira-leito seguro, comunicação empática consistente e raciocínio clínico maduro nas 5 grandes áreas da residência."
        )
    elif total_completed < 5:
        board_feedback = f"Circuito em andamento: {total_completed} de 5 estações concluídas. Total acumulado: {total_score:.1f}/50.0 pontos."
    else:
        board_feedback = (
            f"Pontuação de {total_score:.1f}/50.0 pontos ({percentage}%) insuficiente para aprovação na 2ª Fase (nota de corte: 35.0/50.0). "
            f"Identificamos {total_critical_errors} falta(s) crítica(s) de segurança clínica. Revise os flashcards de choque gerados."
        )

    return {
        "circuit_id": circuit_id,
        "user_id": user_id,
        "total_score": round(total_score, 1),
        "max_score": max_score,
        "average_score": avg_score,
        "percentage": percentage,
        "approved": approved,
        "stations_completed": total_completed,
        "total_stations": 5,
        "critical_errors_count": total_critical_errors,
        "stations": station_summaries,
        "board_feedback": board_feedback
    }


