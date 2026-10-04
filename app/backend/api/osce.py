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
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .db import db_transaction, get_db
from .universal_pool import generate_content_with_fallback

logger = logging.getLogger(__name__)


def _normalize_text(text: str) -> str:
    """Normaliza texto removendo acentos e espaços extras para matching tolerante a grafia."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()

from .osce_data import (
    CANONICAL_STATIONS,
    FMRP_USP_TEMPLATES,
    EMERGENCY_DRUGS_CATALOG,
    PROCEDURES_CATALOG,
)

def seed_osce_stations(db) -> int:
    """Insere ou atualiza o catálogo canônico de estações de prova prática."""
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
        ]
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
# VETOR DE SEGURANÇA CLÍNICA BEIRA-LEITO (ClinicalSafetyGuard)
# =========================================================================

def evaluate_critical_safety_violations(
    critical_errors: list[str],
    evidence_text: str,
    actions: list[dict[str, Any]],
    station_meta: dict[str, Any]
) -> list[str]:
    """
    Motor de Auditoria de Segurança Clínica Beira-Leito (ClinicalSafetyGuard).
    Cruza contraindicações formais das bancas com falas, prescrições e procedimentos do candidato.
    """
    norm_evidence = _normalize_text(evidence_text)
    prescriptions: list[dict[str, Any]] = []
    procedures: list[dict[str, Any]] = []

    for a in actions:
        if a.get("action_type") == "prescription":
            prescriptions.extend(a.get("prescription_items", []))
        elif a.get("action_type") == "procedure":
            procedures.append(a)

    all_prescribed_drugs = " ".join([
        _normalize_text(f"{p.get('drug_name', '')} {p.get('dose', '')} {p.get('route', '')} {p.get('notes', '')}")
        for p in prescriptions
    ])
    full_corpus = f"{norm_evidence} {all_prescribed_drugs}"

    station_subtema = _normalize_text(station_meta.get("subtema", ""))
    detected_violations: list[str] = []

    for err in critical_errors:
        err_norm = _normalize_text(err)
        flagged = False

        # 1. Bicarbonato em Cetoacidose Diabética (pH > 6.9)
        if "bicarbonato" in err_norm:
            if any(term in full_corpus for term in ["bicarbonato", "nahco3", "bicarb"]):
                flagged = True

        # 2. Insulina sem dosar/checar Potássio
        elif "potassio" in err_norm and "insulina" in err_norm:
            has_insulin = any(term in full_corpus for term in ["insulina", "bic de insulina", "insulina regular"])
            checked_k = any(term in full_corpus for term in ["potassio", "k+", "gasometria", "eletrolitos", "kcl"])
            if has_insulin and not checked_k:
                flagged = True

        # 3. Suspender insulina precocemente ao atingir 250 mg/dL na CAD
        elif "suspender" in err_norm and "insulina" in err_norm:
            if any(phrase in full_corpus for phrase in ["suspender insulina", "desligo a insulina", "parar a insulina"]):
                flagged = True

        # 4. Fibrinolítico / Trombolítico em SCA sem supra
        elif "trombolitico" in err_norm or "fibrinolitico" in err_norm:
            if any(term in full_corpus for term in ["trombolise", "alteplase", "tenecteplase", "estreptoquinase", "metalyse", "actilyse"]):
                flagged = True

        # 5. Nitrato em suspeita de infarto de VD ou uso de sildenafila
        elif "nitrato" in err_norm:
            has_nitrate = any(term in full_corpus for term in ["nitrato", "isordil", "mononitrato", "dinitrato", "tridil", "nitroglicerina"])
            checked_contra = any(term in full_corpus for term in ["sildenafila", "viagra", "tadalafila", "erecao", "ventriculo direito", "vd"])
            if has_nitrate and not checked_contra:
                flagged = True

        # 6. Oxigenioterapia de rotina sem hipoxemia (SatO2 normal)
        elif "oxigenioterapia" in err_norm:
            if any(term in full_corpus for term in ["cateter de o2", "oxigenio a", "o2 a", "mascara de o2", "o2 2l", "o2 3l"]):
                flagged = True

        # 7. Aguardar troponina em IAM com supra de ST
        elif "aguardar" in err_norm and ("troponina" in err_norm or "marcador" in err_norm or "enzima" in err_norm):
            if any(term in full_corpus for term in ["aguardar troponina", "esperar a troponina", "aguardo o resultado da troponina", "esperar enzimas"]):
                flagged = True

        # 8. Tomografia em politraumatizado instável hemodinamicamente (FAST positivo)
        elif "tomografia" in err_norm and ("instavel" in err_norm or "fast" in err_norm):
            has_tc = any(a.get("action_target") == "tc" or "tomografia" in full_corpus for a in actions)
            if has_tc:
                flagged = True

        # 9. EDA / Endoscopia digestiva alta em abdome agudo perfurativo
        elif "endoscopia" in err_norm or "eda" in err_norm:
            if any(term in full_corpus for term in ["eda", "endoscopia", "endoscopia digestiva"]):
                flagged = True

        # 10. Rx / TC antes de descompressão no Pneumotórax Hipertensivo
        elif ("radiografia" in err_norm or "tomografia" in err_norm) and "pneumotorax" in station_subtema:
            rx_done = any(a.get("action_type") == "lab_imaging" and a.get("action_target") in ["rx", "raio_x", "tc"] for a in actions)
            decompression_done = any(a.get("action_type") == "procedure" and "puncture" in str(a.get("procedure_type", "")) for a in actions)
            if rx_done and not decompression_done:
                flagged = True

        # 11. Antibiótico ou Corticoide em Bronquiolite Viral Aguda típica
        elif "cortico" in err_norm and "bronquiolite" in station_subtema:
            if any(term in full_corpus for term in ["prednisolona", "prednisona", "dexametasona", "hidrocortisona", "corticoide"]):
                flagged = True
        elif "antibiotico" in err_norm and "bronquiolite" in station_subtema:
            if any(term in full_corpus for term in ["amoxicilina", "azitromicina", "ceftriaxona", "claritromicina", "ampicilina"]):
                flagged = True

        # 12. Corticoide/Anti-histamínico antes de Adrenalina ou Adrenalina SC na Anafilaxia
        elif "adrenalina" in err_norm and "anafilaxia" in station_subtema:
            if any(term in full_corpus for term in ["adrenalina sc", "subcutanea", "adrenalina subcutanea"]):
                flagged = True

        # 13. AAS ou Anti-inflamatório (AINE) na suspeita de Dengue
        elif ("anti-inflamatorio" in err_norm or "aas" in err_norm) and "dengue" in station_subtema:
            if any(term in full_corpus for term in ["aas", "aspirina", "ibuprofeno", "cetoprofeno", "nimesulida", "diclofenaco"]):
                flagged = True

        # 14. Diazepam ou Fenitoína em Pré-eclâmpsia (Sulfato de Magnésio é exclusivo)
        elif ("diazepam" in err_norm or "fenitoina" in err_norm) and "preeclampsia" in station_subtema:
            if any(term in full_corpus for term in ["diazepam", "fenitoina", "hidantal"]):
                flagged = True

        # 15. Insulina pura sem glicose na Hipercalemia Grave
        elif "insulina" in err_norm and "glicose" in err_norm and "hipercalemia" in station_subtema:
            has_insulin = any("insulina" in full_corpus for _ in [1])
            has_glucose = any(term in full_corpus for term in ["glicose 50", "glicose 10", "glicoinsulina", "sg 50"])
            if has_insulin and not has_glucose:
                flagged = True

        # 16. Diurético poupador de K+ (Espironolactona) na Hipercalemia
        elif "espironolactona" in err_norm or "poupador" in err_norm:
            if "espironolactona" in full_corpus:
                flagged = True

        # 17. Succinilcolina na intoxicação por organofosforado/carbamato
        elif "succinilcolina" in err_norm:
            if "succinilcolina" in full_corpus:
                flagged = True

        # 18. Tocolíticos no Descolamento Prematuro de Placenta (DPP)
        elif "tocolitico" in err_norm:
            if any(term in full_corpus for term in ["tocolise", "atosibana", "salbutamol", "terbutalina", "nifedipino para tocolise"]):
                flagged = True

        # 19. Amiodarona na Taquicardia Ventricular instável em choque
        elif "amiodarona" in err_norm and "taquicardia" in station_subtema:
            if any(term in full_corpus for term in ["amiodarona venosa", "amiodarona 300"]):
                flagged = True

        # 20. Dopamina na Sepse / Choque Séptico
        elif "dopamina" in err_norm and "sepse" in station_subtema:
            if "dopamina" in full_corpus:
                flagged = True

        # 21. Regra Geral de Alta Indevida
        elif "alta" in err_norm and ("hipoxemia" in err_norm or "observacao" in err_norm):
            if any(phrase in full_corpus for phrase in ["dar alta", "libero para casa", "alta hospitalar", "alta para casa"]):
                flagged = True

        if flagged and err not in detected_violations:
            detected_violations.append(err)

    return detected_violations


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
    elapsed_seconds: int = 0
) -> dict[str, Any]:
    """Processa fala/pergunta do aluno ao paciente virtual ou ao examinador."""
    sess = db.execute("""
        SELECT s.id, s.station_id, s.user_id, s.status, s.transcript_json, s.actions_taken_json,
               st.title, st.area, st.subtema, st.patient_persona_json, st.scenario_door_markdown,
               st.checklist_barema_json
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

    now_iso = datetime.now(timezone.utc).isoformat()
    clean_msg = message.strip()

    # Adiciona a mensagem do aluno ao transcript
    transcript.append({
        "sender": "candidato",
        "message": clean_msg,
        "timestamp": now_iso,
        "elapsed_seconds": elapsed_seconds
    })

    # Decisão de resposta via Ator Virtual com inteligência e fallback médico
    system_prompt = (
        f"Você é o paciente simulado em uma prova prática presencial de residência médica (OSCE).\n"
        f"NOME: {persona.get('name', 'Paciente')}, IDADE: {persona.get('age', 'Adulto')}, GÊNERO: {persona.get('gender', '')}.\n"
        f"QUEIXA PRINCIPAL: {persona.get('chief_complaint')}\n"
        f"HISTÓRICO OCULTO: {json.dumps(persona, ensure_ascii=False)}\n\n"
        f"REGRAS DE ATUAÇÃO RIGOROSAS:\n"
        f"1. Fale como um paciente LEIGO com dor/desconforto. NUNCA use jargões médicos como 'retroesternal', 'eclâmpsia', 'pneumoperitônio'.\n"
        f"2. NUNCA revele o diagnóstico de graça. Só conte detalhes específicos se o médico perguntar expressamente.\n"
        f"3. Responda em no máximo 2 a 3 frases curtas e realistas para manter a dinâmica ágil de prova.\n"
        f"4. Se o médico se apresentar ou demonstrar empatia, responda de forma receptiva.\n"
    )

    history_str = "\n".join([
        f"{t['sender'].upper()}: {t['message']}"
        for t in transcript[-6:]
    ])

    user_prompt = f"Diálogo recente na sala de exame:\n{history_str}\n\nResponda como o paciente {persona.get('name')}:"

    reply_text = ""
    try:
        resp = generate_content_with_fallback(
            prompt=user_prompt,
            system_instruction=system_prompt,
            timeout=12,
            temperature=0.3
        )
        reply_text = resp.get("text", "").strip()
    except Exception as e:
        logger.warning(f"OSCE LLM fallback ativado: {e}")

    if not reply_text:
        # Fallback determinístico contextual de alta fidelidade
        msg_lower = clean_msg.lower()
        if any(w in msg_lower for w in ["dor", "onde dói", "sente", "queima", "aperta"]):
            reply_text = persona.get("pain_characteristics") or persona.get("chief_complaint", "Dói muito aqui no peito, doutor.")
        elif any(w in msg_lower for w in ["quando", "começou", "tempo", "horas", "minutos"]):
            reply_text = f"Começou de repente faz pouco tempo, doutor. {persona.get('chief_complaint', '')}"
        elif any(w in msg_lower for w in ["fuma", "cigarro", "bebe", "álcool", "remédio", "pressão", "diabete", "histórico"]):
            reply_text = persona.get("past_medical_history") or persona.get("past_history", "Não tomo nenhum remédio doutor.")
        elif any(w in msg_lower for w in ["falta de ar", "suor", "suando", "enjoo", "náusea", "vomit"]):
            reply_text = persona.get("associated_symptoms", "Tô sentindo uma náusea forte e um suor frio.")
        elif any(w in msg_lower for w in ["viagra", "sildenafila", "ereção"]):
            reply_text = persona.get("sildenafil_use", "Não tomei nada disso não, doutor.")
        elif any(w in msg_lower for w in ["olá", "bom dia", "boa tarde", "nome", "sou o médico", "vamos cuidar"]):
            reply_text = f"Doutor, por favor me ajuda, tá doendo demais! {persona.get('chief_complaint', '')}"
        else:
            reply_text = "Entendi, doutor. O que o senhor vai fazer pra me ajudar?"

    transcript.append({
        "sender": "paciente",
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
        "sender": "paciente",
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


def generate_timeline_post_mortem(
    station_meta: dict[str, Any],
    transcript: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    evaluated_items: list[dict[str, Any]],
    elapsed_seconds: int
) -> dict[str, Any]:
    """
    Reconstitui a cronologia beira-leito da estação segundo a segundo:
    - Identifica marcos da anamnese, sinais vitais, ECG, labs, manequim e prescrição
    - Detecta atrasos operacionais (porta-ECG, porta-ação inicial)
    - Detecta períodos de hesitação/inércia (> 65s sem ação)
    - Sinaliza quebras críticas de segurança clínica
    """
    events = []

    # 1. Evento de Abertura
    inst_name = station_meta.get("institution", "Banca Oficial")
    st_title = station_meta.get("title", "Estação Clínica")
    events.append({
        "time_seconds": 0,
        "time_formatted": "00:00",
        "event_type": "start",
        "title": "Entrada na Sala de Exame",
        "description": f"Candidato entra no consultório da banca ({inst_name} • {st_title}).",
        "status": "neutral",
        "feedback": "Início da contagem regressiva oficial. Boa prática: cumprimentar paciente e se identificar.",
        "score_impact": "Início da Prova"
    })

    candidate_action_times = [0]

    # 2. Processa Ações Clínicas Estruturadas
    for act in actions:
        sec = int(act.get("elapsed_seconds", 0))
        act_type = act.get("action_type")
        act_target = act.get("action_target", "")
        payload = act.get("payload", {})
        candidate_action_times.append(sec)

        m = sec // 60
        s = sec % 60
        tf = f"{m:02d}:{s:02d}"

        if act_type == "vitals":
            status = "timely" if sec <= 90 else ("neutral" if sec <= 180 else "delayed")
            feedback = (
                "Monitorização de sinais vitais realizada com rapidez cirúrgica."
                if status == "timely" else
                "Sinais vitais checados adequadamente."
                if status == "neutral" else
                "Atenção ao tempo: em emergência, sinais vitais devem ser checados nos primeiros 90 segundos."
            )
            events.append({
                "time_seconds": sec,
                "time_formatted": tf,
                "event_type": "vitals",
                "title": "Aferição de Sinais Vitais & Monitor",
                "description": "Sinais vitais checados no monitor: PA, FC, FR, SatO2 e temperatura.",
                "status": status,
                "feedback": feedback,
                "score_impact": "+ Pontos Vitais"
            })

        elif act_type == "physical_exam":
            status = "timely" if sec <= 180 else "neutral"
            target_label = act_target.replace("_", " ").capitalize()
            events.append({
                "time_seconds": sec,
                "time_formatted": tf,
                "event_type": "physical_exam",
                "title": f"Exame Físico: {target_label}",
                "description": f"Palpação e ausculta direcionada ao segmento {target_label}.",
                "status": status,
                "feedback": f"Segmento {target_label} examinado com busca ativa de achados do barema.",
                "score_impact": "+1.0 pt"
            })

        elif act_type == "lab_imaging":
            target_norm = act_target.lower()
            is_ecg = any(k in target_norm for k in ["ecg", "eletro", "eletrocardiograma"])
            is_fast = any(k in target_norm for k in ["fast", "efast", "ultrassom"])

            if is_ecg:
                status = "timely" if sec <= 120 else ("neutral" if sec <= 240 else "delayed")
                feedback = (
                    "Meta Porta-ECG de excelência: solicitado em menos de 2 minutos de prova."
                    if status == "timely" else
                    "ECG solicitado em tempo aceitável para a queixa apresentada."
                    if status == "neutral" else
                    "Atraso Porta-ECG: dor torácica/isquemia exige solicitação imediata (< 2-3 min)."
                )
                events.append({
                    "time_seconds": sec,
                    "time_formatted": tf,
                    "event_type": "lab_imaging",
                    "title": "Solicitação de ECG 12 Derivações",
                    "description": "Eletrocardiograma de 12 derivações entregue pela banca.",
                    "status": status,
                    "feedback": feedback,
                    "score_impact": "Porta-ECG"
                })
            elif is_fast:
                status = "timely" if sec <= 180 else "neutral"
                events.append({
                    "time_seconds": sec,
                    "time_formatted": tf,
                    "event_type": "procedure",
                    "title": "Ultrassom E-FAST Beira-Leito",
                    "description": "Rastreamento ultrassonográfico de líquido livre em janelas torácicas e abdominais.",
                    "status": status,
                    "feedback": "Protocolo ATLS: busca precoce de hemoperitônio ou hemo/pneumotórax.",
                    "score_impact": "+2.0 pts"
                })
            else:
                events.append({
                    "time_seconds": sec,
                    "time_formatted": tf,
                    "event_type": "lab_imaging",
                    "title": f"Exame Complementar: {act_target.upper()}",
                    "description": f"Solicitado exame {act_target.upper()} e interpretado laudo.",
                    "status": "neutral",
                    "feedback": "Exame complementar solicitado e analisado junto à banca examinadora.",
                    "score_impact": "+0.5 a 1.0 pt"
                })

        elif act_type == "prescription":
            drugs_summary = payload.get("text", act_target)
            status = "timely" if sec <= 360 else "delayed"
            feedback = (
                "Prescrição administrada oportunamente antes da fase final da estação."
                if status == "timely" else
                "Prescrição realizada tardiamente no final da prova. Priorize estabilização precoce."
            )
            events.append({
                "time_seconds": sec,
                "time_formatted": tf,
                "event_type": "prescription",
                "title": "Prescrição Farmacológica na Prancheta",
                "description": f"Administração assinada na prancheta de emergência: {drugs_summary[:120]}...",
                "status": status,
                "feedback": feedback,
                "score_impact": "Conduta Terapêutica"
            })

        elif act_type == "procedure":
            proc_title = payload.get("title", act_target)
            events.append({
                "time_seconds": sec,
                "time_formatted": tf,
                "event_type": "procedure",
                "title": f"Procedimento: {proc_title}",
                "description": "Execução de procedimento beira-leito no manequim interativo.",
                "status": "timely",
                "feedback": "Procedimento invasivo executado com indicação e técnica corretas.",
                "score_impact": "+2.0 pts"
            })

    # 3. Adiciona Marcos de Anamnese e Diálogo a partir do Transcript
    for item in transcript:
        if item.get("sender") == "candidato":
            sec = int(item.get("elapsed_seconds", 0))
            candidate_action_times.append(sec)
            msg = item.get("message", "")
            msg_lower = msg.lower()

            m = sec // 60
            s = sec % 60
            tf = f"{m:02d}:{s:02d}"

            if any(w in msg_lower for w in ["minha conduta", "prescrevo", "indico cirurgia", "encaminho", "passo o caso"]):
                events.append({
                    "time_seconds": sec,
                    "time_formatted": tf,
                    "event_type": "conduct",
                    "title": "Verbalização da Conduta Definitiva",
                    "description": msg[:140] + ("..." if len(msg) > 140 else ""),
                    "status": "timely" if sec >= 240 else "neutral",
                    "feedback": "Conduta e encaminhamento verbalizados claramente para o examinador.",
                    "score_impact": "+1.5 pts"
                })
            elif len(msg) > 15 and not any(e["time_seconds"] == sec and e["event_type"] == "anamnese" for e in events):
                events.append({
                    "time_seconds": sec,
                    "time_formatted": tf,
                    "event_type": "anamnese",
                    "title": "Interação Clínica com o Paciente",
                    "description": f'"{msg[:110]}..."',
                    "status": "timely" if sec <= 180 else "neutral",
                    "feedback": "Investigação sintomática, acolhimento e escuta atenta do paciente.",
                    "score_impact": "+ Diálogo"
                })

    # 4. Detecção de Períodos de Hesitação / Inércia (gaps >= 70s)
    candidate_action_times.sort()
    unique_times = sorted(list(set(candidate_action_times)))
    for i in range(len(unique_times) - 1):
        t1 = unique_times[i]
        t2 = unique_times[i + 1]
        gap = t2 - t1
        if gap >= 70:
            gap_mid = t1 + (gap // 2)
            m = gap_mid // 60
            s = gap_mid % 60
            events.append({
                "time_seconds": gap_mid,
                "time_formatted": f"{m:02d}:{s:02d}",
                "event_type": "hesitacao",
                "title": f"Período de Hesitação ({gap}s sem ação)",
                "description": f"Intervalo de {gap} segundos sem perguntas ou intervenções ativas do candidato.",
                "status": "delayed",
                "feedback": f"Atenção ao ritmo: {gap} segundos sem conduta. Na 2ª fase presencial, cada minuto ocioso consome tempo crucial de barema.",
                "score_impact": "Ritmo Comprometido"
            })

    # 5. Omissões Críticas Específicas
    st_title_lower = station_meta.get("title", "").lower()
    st_subtema_lower = station_meta.get("subtema", "").lower()
    all_targets = [str(a.get("action_target", "")).lower() for a in actions]
    all_types = [str(a.get("action_type", "")).lower() for a in actions]

    if "vitals" not in all_types:
        events.append({
            "time_seconds": elapsed_seconds or 480,
            "time_formatted": f"{(elapsed_seconds or 480)//60:02d}:{(elapsed_seconds or 480)%60:02d}",
            "event_type": "omissao",
            "title": "Omissão Crítica: Sinais Vitais Não Checados",
            "description": "Candidato não solicitou monitorização ou sinais vitais durante toda a estação.",
            "status": "critical_gap",
            "feedback": "Falta de segurança: todo atendimento beira-leito deve iniciar com a checagem dos sinais vitais.",
            "score_impact": "Perda Grave de Barema"
        })

    if ("sca" in st_title_lower or "coronariana" in st_subtema_lower or "taquicardia" in st_title_lower) and not any("ecg" in t for t in all_targets):
        events.append({
            "time_seconds": elapsed_seconds or 480,
            "time_formatted": f"{(elapsed_seconds or 480)//60:02d}:{(elapsed_seconds or 480)%60:02d}",
            "event_type": "omissao",
            "title": "Omissão Crítica: Eletrocardiograma Não Solicitado",
            "description": "Em queixa de dor torácica/isquemia, o ECG de 12 derivações é item obrigatório do barema.",
            "status": "critical_gap",
            "feedback": "Erro eliminatório: tempo porta-ECG não atingido porque o exame não foi solicitado.",
            "score_impact": "Eliminatório / -2.0 pts"
        })

    events.sort(key=lambda x: x["time_seconds"])

    timely_count = sum(1 for e in events if e.get("status") == "timely")
    delayed_count = sum(1 for e in events if e.get("status") == "delayed")
    critical_count = sum(1 for e in events if e.get("status") == "critical_gap")

    first_action_sec = unique_times[1] if len(unique_times) > 1 else elapsed_seconds
    ecg_sec = next((e["time_seconds"] for e in events if "ecg" in e["title"].lower()), None)

    if critical_count > 0 or delayed_count >= 3:
        pace_label = "Hesitante / Atrasos Críticos"
    elif timely_count >= 4 and delayed_count <= 1:
        pace_label = "Ritmo Cirúrgico / Ágil"
    else:
        pace_label = "Equilibrado / Médio"

    return {
        "events": events,
        "summary": {
            "total_events": len(events),
            "timely_count": timely_count,
            "delayed_count": delayed_count,
            "critical_gaps_count": critical_count,
            "door_to_first_action_seconds": first_action_sec,
            "door_to_ecg_seconds": ecg_sec,
            "pace_label": pace_label
        }
    }


def generate_competency_radar(
    station_meta: dict[str, Any],
    evaluated_items: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    transcript: list[dict[str, Any]],
    elapsed_seconds: int,
    critical_warnings: Optional[list[str]] = None
) -> dict[str, Any]:
    """
    Calcula o Radar de Competências Médicas em 6 dimensões fundamentais de prova prática:
    1. Comunicação & Empatia
    2. Raciocínio Clínico & Anamnese
    3. Exame Físico & Habilidades Práticas
    4. Indicação & Interpretação de Exames Complementares
    5. Tomada de Decisão & Segurança Farmacológica
    6. Gestão do Tempo Beira-Leito
    """
    category_scores = {
        "comunicacao_empatia": {"earned": 0.0, "max": 0.0, "items": []},
        "raciocinio_clinico": {"earned": 0.0, "max": 0.0, "items": []},
        "exame_fisico": {"earned": 0.0, "max": 0.0, "items": []},
        "exames_complementares": {"earned": 0.0, "max": 0.0, "items": []},
        "seguranca_farmacologica": {"earned": 0.0, "max": 0.0, "items": []},
        "gestao_tempo": {"earned": 0.0, "max": 0.0, "items": []}
    }

    for it in evaluated_items:
        cat = it.get("category", "").lower()
        earned = float(it.get("score_earned", 0.0))
        weight = float(it.get("weight", 1.0))

        if "comunicacao" in cat or "empatia" in cat or "relacao" in cat:
            key = "comunicacao_empatia"
        elif "anamnese" in cat or "diagnostico" in cat or "raciocinio" in cat:
            key = "raciocinio_clinico"
        elif "fisico" in cat or "manobra" in cat or "procedimento" in cat:
            key = "exame_fisico"
        elif "lab" in cat or "imagem" in cat or "complementar" in cat or ("exame" in cat and "fisico" not in cat):
            key = "exames_complementares"
        elif "farmaco" in cat or "prescricao" in cat or "tratamento" in cat or "conduta" in cat:
            key = "seguranca_farmacologica"
        else:
            key = "raciocinio_clinico"

        category_scores[key]["earned"] += earned
        category_scores[key]["max"] += weight
        category_scores[key]["items"].append(it)

    # Competência 6: Gestão de Tempo
    time_score_max = 2.0
    time_score_earned = 2.0
    if elapsed_seconds > 450:
        time_score_earned -= 0.5
    action_times = sorted([int(a.get("elapsed_seconds", 0)) for a in actions if a.get("elapsed_seconds")])
    for i in range(len(action_times) - 1):
        if action_times[i+1] - action_times[i] >= 75:
            time_score_earned -= 0.5
            break
    time_score_earned = max(0.5, time_score_earned)
    category_scores["gestao_tempo"]["earned"] = time_score_earned
    category_scores["gestao_tempo"]["max"] = time_score_max

    dim_configs = [
        ("comunicacao_empatia", "Comunicação & Empatia", "Relação médico-paciente, acolhimento e clareza de linguagem."),
        ("raciocinio_clinico", "Raciocínio & Anamnese", "Investigação sintomática, fatores de risco e hipótese diagnóstica."),
        ("exame_fisico", "Exame Físico & Habilidades", "Ausculta, palpação, monitorização e procedimentos beira-leito."),
        ("exames_complementares", "Exames Complementares", "Indicação criteriosa de ECG, imagem, gasometria e laboratoriais."),
        ("seguranca_farmacologica", "Segurança Farmacológica", "Doses corretas, vias seguras, contraindicações e drogas prioritárias."),
        ("gestao_tempo", "Gestão do Tempo", "Ritmo, dinamismo e tomada de decisão antes dos avisos da banca.")
    ]

    dimensions = []
    total_pct = 0.0

    for key, name, desc in dim_configs:
        earned = category_scores[key]["earned"]
        c_max = category_scores[key]["max"]
        if c_max == 0:
            c_max = 1.0
            earned = 0.8  # Fallback padrão quando o barema da estação não foca exclusivamente nessa categoria

        pct = round(min(100.0, max(0.0, (earned / c_max) * 100)), 1)
        if key == "seguranca_farmacologica" and critical_warnings:
            # Penalização severa por quebra de segurança do paciente
            penal_pct = max(15.0, pct - (len(critical_warnings) * 35.0))
            pct = round(penal_pct, 1)
        total_pct += pct

        if pct >= 80.0:
            level = "Excelente"
            feedback = "Domínio seguro nesta competência. Execução precisa segundo o gabarito oficial."
        elif pct >= 60.0:
            level = "Satisfatório"
            feedback = "Bom desempenho, com oportunidades de refinamento e maior agilidade."
        else:
            level = "Necessita Atenção"
            feedback = "Ponto de atenção na prova prática. Revise os passos capitais no FSRS."

        dimensions.append({
            "key": key,
            "name": name,
            "score_earned": round(earned, 1),
            "score_max": round(c_max, 1),
            "percentage": pct,
            "level": level,
            "description": desc,
            "feedback": feedback
        })

    overall_avg = round(total_pct / len(dimensions), 1)

    sorted_dims = sorted(dimensions, key=lambda d: d["percentage"], reverse=True)
    strengths = [d["name"] for d in sorted_dims[:2] if d["percentage"] >= 65]
    if not strengths:
        strengths = [sorted_dims[0]["name"]]
    weaknesses = [d["name"] for d in sorted_dims[-2:] if d["percentage"] < 75]

    return {
        "overall_average": overall_avg,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "dimensions": dimensions
    }


def finish_osce_session(
    db,
    session_id: str,
    user_id: str,
    conduct_notes: Optional[str] = None
) -> dict[str, Any]:
    """
    Finaliza a estação de prova prática e executa a auditoria completa do Barema Oficial:
    - Calcula nota ponderada de 0.0 a 10.0
    - Avalia cada item do checklist com citações de evidência
    - Constrói a Linha do Tempo Beira-Leito ("Timeline Post-Mortem") com marcos e atrasos
    - Computa o Radar de Competências Médicas em 6 dimensões
    - Detecta faltas eliminatórias graves
    - Sintetiza parecer clínico do Preceptor Sênior
    - Gera Flashcards de Choque no formato FSRS e Criador de Cards
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
        f"{a.get('action_type', '')} {a.get('action_target', '')}".lower() for a in actions
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
            "title": item.get("title"),
            "category": item.get("category"),
            "weight": weight,
            "score_earned": earned,
            "status": status,
            "evidence": evidence
        })

        if status != "cumprido_total":
            shock_cards.append({
                "station_code": sess["subtema"],
                "front": f"🚨 [OSCE {sess['institution']} - {sess['area']}]\nQual é a conduta obrigatória segundo o barema oficial para:\n👉 **{item.get('title')}**?",
                "back": f"💡 **Critério de Avaliação da Banca**:\n{item.get('description', '')}\n\n⚠️ **Palavras-chave de aprovação**: {', '.join(item.get('keywords', []))}",
                "category": item.get("category"),
                "weight": weight
            })

    final_score_normalized = round(min(10.0, (total_score / max(1.0, max_score)) * 10.0), 1)

    critical_warnings = evaluate_critical_safety_violations(
        critical_errors=critical_errors,
        evidence_text=all_evidence_corpus,
        actions=actions,
        station_meta=dict(sess)
    )

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

    # Computa Timeline Post-Mortem e Radar de Competências
    timeline_data = generate_timeline_post_mortem(
        station_meta=dict(sess),
        transcript=transcript,
        actions=actions,
        evaluated_items=evaluated_items,
        elapsed_seconds=sess["elapsed_seconds"]
    )

    radar_data = generate_competency_radar(
        station_meta=dict(sess),
        evaluated_items=evaluated_items,
        actions=actions,
        transcript=transcript,
        elapsed_seconds=sess["elapsed_seconds"],
        critical_warnings=critical_warnings
    )

    preceptor_feedback = {
        "final_score": final_score_normalized,
        "max_score": 10.0,
        "approved": final_score_normalized >= 7.0,
        "station_title": sess["title"],
        "institution": sess["institution"],
        "summary": (
            f"Desempenho de {final_score_normalized}/10.0 na estação de {sess['title']} ({sess['institution']}). "
            + ("Excelente domínio técnico beira-leito, com atendimento estruturado e cumprimento dos pontos capitais da banca."
               if final_score_normalized >= 8.5 else
               "Atendimento satisfatório, porém com perda de pontos em passos operacionais e justificativa de conduta."
               if final_score_normalized >= 6.0 else
               "Atenção crítica: falhas fundamentais no barema que causariam eliminação ou pontuação insuficiente na 2ª fase presencial.")
        ),
        "critical_warnings": critical_warnings,
        "shock_cards_count": len(shock_cards),
        "timeline_post_mortem": timeline_data,
        "competency_radar": radar_data
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
            json.dumps({"items": evaluated_items, "critical_warnings": critical_warnings}, ensure_ascii=False),
            json.dumps(preceptor_feedback, ensure_ascii=False),
            json.dumps(transcript, ensure_ascii=False),
            session_id
        ))

    return {
        "session_id": session_id,
        "final_score": final_score_normalized,
        "status": "completed",
        "evaluated_items": evaluated_items,
        "preceptor_feedback": preceptor_feedback,
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


def export_osce_flashcards(db, session_id: str, user_id: str) -> dict[str, Any]:
    """Exporta os Flashcards de Choque do barema diretamente para a tabela de flashcards do MedQuest."""
    report = get_osce_session_report(db, session_id, user_id)
    if not report:
        raise ValueError("Sessão não encontrada.")

    evaluated_items = report.get("checklist_evaluation", [])
    station_subtema = report.get("subtema", "OSCE Prático")
    station_area = report.get("area", "Clínica Médica")

    exported_count = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    with db_transaction(db, immediate=True):
        for item in evaluated_items:
            if item.get("status") != "cumprido_total":
                front = (
                    f"🚨 [OSCE {report.get('institution')} - {station_area}]\n"
                    f"Qual a conduta e critérios da banca para:\n"
                    f"👉 **{item.get('title')}**?"
                )
                existing_card = db.execute(
                    "SELECT id FROM flashcards WHERE user_id = ? AND front = ?",
                    (user_id, front)
                ).fetchone()
                if existing_card:
                    continue

                back = (
                    f"💡 **Critério de Avaliação do Barema**:\n{item.get('evidence', '')}\n\n"
                    f"📌 **Subtema**: {station_subtema} ({report.get('code')})"
                )
                db.execute("""
                    INSERT INTO flashcards (
                        user_id, question_id, front, back,
                        created_at, next_review_date, source_context,
                        deck_name, tags, source_type, is_ai_generated
                    ) VALUES (
                        ?, NULL, ?, ?,
                        ?, ?, ?,
                        ?, ?, 'osce_barema', 1
                    )
                """, (
                    user_id, front, back,
                    now_iso, now_iso, f"{station_area} > {station_subtema}",
                    f"OSCE {report.get('institution')}", f"osce,2a_fase,{report.get('code')}"
                ))
                exported_count += 1

    try:
        from .questions import invalidate_user_caches
        invalidate_user_caches(user_id)
    except Exception:
        pass

    return {
        "success": True,
        "cards_created": exported_count,
        "exported_count": exported_count,
        "message": f"{exported_count} flashcards de choque adicionados à sua revisão ativa FSRS."
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
    if proc_type_clean == "efast" or site_clean in ("morrison", "splenorenal", "pelvic", "pericardial", "pleural_right", "pleural_left"):
        is_trauma_fast = "FAST" in station_code or "trauma" in sess["title"].lower() or "politrauma" in sess["title"].lower()

        if site_clean == "morrison":
            if is_trauma_fast:
                findings_desc = (
                    "Janela Hepatorrenal (Morrison): Presença de lâmina fina de líquido livre anecoico "
                    "no recesso entre o lobo hepático direito e o córtex renal anterior. Espaço de Morrison POSITIVO para líquido livre."
                )
                is_positive_finding = True
            else:
                findings_desc = "Janela Hepatorrenal (Morrison): Interface hepatorrenal nítida sem acúmulo de líquido anecoico."
        elif site_clean == "splenorenal":
            if is_trauma_fast:
                findings_desc = (
                    "Janela Esplenorrenal (Recesso de Koller): Presença de volumosa quantidade de líquido livre anecoico "
                    "circundando o polo inferior e hilo do baço, com irregularidade cortical compatível com laceração esplênica ativa. FAST POSITIVO."
                )
                is_positive_finding = True
            else:
                findings_desc = "Janela Esplenorrenal: Recesso de Koller sem coleções ou líquido livre visível."
        elif site_clean == "pelvic":
            if is_trauma_fast:
                findings_desc = (
                    "Janela Pélvica / Suprapúbica: Presença de líquido livre anecoico acumulado no fundo de saco peritoneal posterior. FAST POSITIVO."
                )
                is_positive_finding = True
            else:
                findings_desc = "Janela Pélvica: Bexiga fisiologicamente preenchida, sem líquido livre em escavação pélvica."
        elif site_clean == "pericardial":
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

    # 2. TORACOCENTESE DE ALÍVIO COM AGULHA
    elif proc_type_clean in ("puncture", "thoracocentesis") or "thoracocentesis" in site_clean:
        is_pneumo = "PNEUMO" in station_code or "pneumotórax" in sess["title"].lower()
        if is_pneumo:
            findings_desc = (
                "Descompressão torácica imediata com agulha no 2º EIC na linha hemiclavicular! "
                "Ocorre escape audível e vigoroso de ar sob alta pressão! O murmúrio vesicular retorna parcialmente, "
                "a turgência jugular atenua e a SatO2 eleva-se rapidamente para 93%."
            )
            is_positive_finding = True
        else:
            findings_desc = "Punção realizada com agulha no espaço intercostal. Não houve saída de ar sob pressão ou sangue."
        examiner_message = f"Procedimento de Toracocentese de Alívio executado: {findings_desc}"

    # 3. DRENAGEM TORÁCICA TUBULAR EM SELO D'ÁGUA
    elif proc_type_clean in ("drainage", "chest_tube") or "chest_tube" in site_clean:
        findings_desc = (
            "Dreno torácico tubular 32 Fr introduzido no 5º EIC na linha axilar média (triângulo de segurança) "
            "e conectado a selo d'água. Dreno posicionado com sucesso, fixado com ponto em bailarina. "
            "Observa-se oscilação adequada da coluna d'água e drenagem de pequena quantidade de secreção serossanguinolenta."
        )
        examiner_message = f"Drenagem Torácica Fechada: {findings_desc}"
        is_positive_finding = True

    # 4. MANOBRA DE HAMILTON (COMPRESSÃO BIMANUAL UTERINA)
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

    # 5. CARDIOVERSÃO ELÉTRICA SINCRONIZADA
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

    # 6. ACESSO VENOSO PROFUNDO / INTRAÓSSEO
    elif proc_type_clean in ("vascular", "intraosseous") or "intraosseous" in site_clean or "central_vein" in site_clean:
        if "intraosseous" in site_clean or proc_type_clean == "intraosseous":
            findings_desc = (
                "Punção intraóssea realizada na tíbia proximal (2 cm abaixo e medial à tuberosidade tibial). "
                "Aspiração de medula óssea positiva e infusão livre de soro sem extravasamento. Via de emergência garantida."
            )
        else:
            findings_desc = (
                "Acesso venoso central obtido por punção de veia subclávia direita sob técnica de Seldinger. "
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


