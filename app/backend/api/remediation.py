"""Módulo de Diagnóstico de Pontos Cegos e Treino de Recuperação Ativa (Caderno de Erros)."""
from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from .adaptive import fsrs_metrics, _utc, _due
from .services.planner import USP_WEIGHTS, get_normalized_area


def calculate_blindspots(db, user_id: str, limit: int = 6) -> Dict[str, Any]:
    """Calcula os pontos cegos multidimensionais do aluno e métricas de cura."""
    limit = max(1, min(limit, 20))
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    # 1. Obter histórico agrupado por questão para identificar resolvidas vs pendentes
    # Uma questão é considerada "curada" se tem pelo menos um erro no passado e o último é acerto.
    # Uma questão é considerada "não resolvida" se a última tentativa for erro.
    curation_rows = db.execute(
        """
        WITH ranked_attempts AS (
            SELECT
                a.question_id,
                a.is_correct,
                a.selected_letter,
                a.answered_at,
                ROW_NUMBER() OVER (PARTITION BY a.question_id ORDER BY a.id DESC) as rn
            FROM attempts a
            WHERE a.user_id = ?
        ),
        question_summary AS (
            SELECT
                a.question_id,
                MAX(CASE WHEN ra.rn = 1 THEN ra.is_correct END) AS latest_is_correct,
                SUM(CASE WHEN a.is_correct = 0 THEN 1 ELSE 0 END) AS total_wrongs,
                COUNT(a.id) AS total_attempts
            FROM attempts a
            JOIN ranked_attempts ra ON ra.question_id = a.question_id
            WHERE a.user_id = ?
            GROUP BY a.question_id
        )
        SELECT
            COUNT(CASE WHEN latest_is_correct = 0 THEN 1 END) AS unresolved_count,
            COUNT(CASE WHEN latest_is_correct = 1 AND total_wrongs > 0 THEN 1 END) AS healed_count,
            COUNT(*) AS total_unique_answered
        FROM question_summary
        """,
        (user_id, user_id),
    ).fetchone()

    unresolved_total = int(curation_rows["unresolved_count"] or 0) if curation_rows else 0
    healed_total = int(curation_rows["healed_count"] or 0) if curation_rows else 0
    total_unique_answered = int(curation_rows["total_unique_answered"] or 0) if curation_rows else 0

    total_error_encounters = unresolved_total + healed_total
    healing_rate_pct = (
        round((healed_total / total_error_encounters) * 100, 1)
        if total_error_encounters > 0
        else 100.0 if total_unique_answered > 0 else 0.0
    )

    # 2. Dados por subtema: tentativas, acertos, erros não resolvidos
    subtema_rows = db.execute(
        """
        WITH latest_attempts AS (
            SELECT
                question_id,
                is_correct,
                selected_letter,
                ROW_NUMBER() OVER (PARTITION BY question_id ORDER BY id DESC) as rn
            FROM attempts
            WHERE user_id = ?
        )
        SELECT
            COALESCE(NULLIF(q.subtema, ''), q.topic) AS subtema,
            MIN(q.area) AS raw_area,
            COUNT(DISTINCT CASE WHEN la.is_correct = 0 THEN q.id END) AS unresolved_count,
            COUNT(a.id) AS attempts,
            SUM(a.is_correct) AS correct,
            SUM(CASE WHEN a.is_correct = 0 THEN 1 ELSE 0 END) AS wrong_count
        FROM attempts a
        JOIN questions q ON q.id = a.question_id
        LEFT JOIN latest_attempts la ON la.question_id = q.id AND la.rn = 1
        WHERE a.user_id = ? AND COALESCE(NULLIF(q.subtema, ''), q.topic) IS NOT NULL
        GROUP BY COALESCE(NULLIF(q.subtema, ''), q.topic)
        HAVING wrong_count > 0 OR unresolved_count > 0
        """,
        (user_id, user_id),
    ).fetchall()

    if not subtema_rows:
        return {
            "summary": {
                "total_blindspots": 0,
                "unresolved_errors_count": 0,
                "healed_count": 0,
                "healing_rate_pct": 100.0 if total_unique_answered > 0 else 0.0,
                "total_unique_answered": total_unique_answered,
            },
            "blindspots": [],
        }

    # 3. Mapear FSRS por subtema
    fsrs_rows = db.execute(
        """
        SELECT COALESCE(NULLIF(q.subtema, ''), q.topic) AS subtema,
               sr.fsrs_card, sr.next_review_date
        FROM spaced_repetition sr
        JOIN questions q ON q.id = sr.question_id
        WHERE sr.user_id = ? AND COALESCE(NULLIF(q.subtema, ''), q.topic) IS NOT NULL
        """,
        (user_id,),
    ).fetchall()

    fsrs_by_subtema: Dict[str, Dict[str, Any]] = {}
    for r in fsrs_rows:
        sub = r["subtema"]
        bucket = fsrs_by_subtema.setdefault(sub, {"retrievabilities": [], "cards_due": 0})
        metrics = fsrs_metrics(r["fsrs_card"], now)
        if metrics["retrievability"] is not None:
            bucket["retrievabilities"].append(metrics["retrievability"])
        if _due(r["next_review_date"], now):
            bucket["cards_due"] += 1

    # 4. Mapear distratores frequentes por subtema
    distractor_rows = db.execute(
        """
        SELECT
            COALESCE(NULLIF(q.subtema, ''), q.topic) AS subtema,
            a.selected_letter,
            COUNT(*) as frequency
        FROM attempts a
        JOIN questions q ON q.id = a.question_id
        WHERE a.user_id = ? AND a.is_correct = 0 AND a.selected_letter IS NOT NULL AND a.selected_letter != ''
        GROUP BY COALESCE(NULLIF(q.subtema, ''), q.topic), a.selected_letter
        HAVING frequency >= 2
        ORDER BY frequency DESC
        """,
        (user_id,),
    ).fetchall()

    distractor_by_subtema: Dict[str, Dict[str, Any]] = {}
    for d in distractor_rows:
        sub = d["subtema"]
        if sub not in distractor_by_subtema:
            distractor_by_subtema[sub] = {
                "letter": d["selected_letter"].upper(),
                "count": d["frequency"],
            }

    # 5. Calcular Score de Gravidade (Severity Score)
    blindspots = []
    for r in subtema_rows:
        subtema_name = r["subtema"]
        raw_area = r["raw_area"] or "Outros"
        norm_area = get_normalized_area(raw_area)
        attempts = int(r["attempts"] or 0)
        correct = int(r["correct"] or 0)
        wrong_count = int(r["wrong_count"] or 0)
        unresolved = int(r["unresolved_count"] or 0)

        accuracy = (correct / attempts) if attempts > 0 else 0.0
        accuracy_pct = round(accuracy * 100, 1)

        area_weight = USP_WEIGHTS.get(norm_area, 0.20)
        area_mult = area_weight * 5.0  # normalizado em torno de 1.0 (0.75 a 1.50)

        # FSRS
        mem_info = fsrs_by_subtema.get(subtema_name, {"retrievabilities": [], "cards_due": 0})
        min_retrievability = min(mem_info["retrievabilities"]) if mem_info["retrievabilities"] else None
        cards_due = mem_info["cards_due"]

        # Componentes do score
        unresolved_score = min(unresolved * 6.0, 30.0)
        error_rate_score = (1.0 - accuracy) * 35.0
        sample_confidence = 1.0 - math.exp(-attempts / 4.0)

        memory_risk_score = 0.0
        if min_retrievability is not None and min_retrievability < 0.85:
            memory_risk_score += (0.85 - min_retrievability) * 20.0
        if cards_due > 0:
            memory_risk_score += min(cards_due * 3.0, 15.0)

        distractor_info = distractor_by_subtema.get(subtema_name)
        distractor_score = 5.0 if distractor_info and distractor_info["count"] >= 2 else 0.0

        # Score global ponderado
        raw_severity = (
            (unresolved_score * 1.2)
            + (error_rate_score * sample_confidence)
            + memory_risk_score
            + distractor_score
        ) * area_mult

        severity_score = round(raw_severity, 2)

        # Classificação categórica
        if severity_score >= 30.0 or unresolved >= 3:
            severity = "CRITICAL"
        elif severity_score >= 18.0 or unresolved >= 1:
            severity = "HIGH"
        else:
            severity = "MODERATE"

        # Insight clínico pedagógico
        if distractor_info and distractor_info["count"] >= 2:
            clinical_insight = (
                f"Você costuma errar marcando a alternativa {distractor_info['letter']} "
                f"({distractor_info['count']}x). Atenção redobrada aos distratores comuns."
            )
        elif unresolved >= 2:
            clinical_insight = (
                f"{unresolved} questões com erro pendente de retificação imediata neste tema."
            )
        elif accuracy < 0.5 and attempts >= 3:
            clinical_insight = (
                f"Acurácia baixa ({accuracy_pct}% em {attempts} questões). Treino de fixação recomendado."
            )
        elif cards_due > 0:
            clinical_insight = (
                f"{cards_due} cartão(ões) FSRS vencidos com alta probabilidade de esquecimento."
            )
        else:
            clinical_insight = f"Taxa de acerto de {accuracy_pct}%. Reforce o tema para consolidar o domínio."

        blindspots.append({
            "subtema": subtema_name,
            "area": norm_area,
            "severity": severity,
            "severity_score": severity_score,
            "unresolved_count": unresolved,
            "wrong_count": wrong_count,
            "attempts": attempts,
            "correct": correct,
            "accuracy_pct": accuracy_pct,
            "frequent_distractor": distractor_info,
            "fsrs_status": {
                "min_retrievability": round(min_retrievability, 3) if min_retrievability is not None else None,
                "cards_due": cards_due,
            },
            "clinical_insight": clinical_insight,
            "workout_url": f"/estudar?subtema={quote(subtema_name)}&mode=remediation&limit=10",
        })

    # Ordenar por severidade decrescente e retornar os top N
    blindspots.sort(key=lambda b: (-b["severity_score"], -b["unresolved_count"], b["subtema"]))

    return {
        "summary": {
            "total_blindspots": len(blindspots),
            "unresolved_errors_count": unresolved_total,
            "healed_count": healed_total,
            "healing_rate_pct": healing_rate_pct,
            "total_unique_answered": total_unique_answered,
        },
        "blindspots": blindspots[:limit],
    }


def generate_remediation_queue(
    db,
    user_id: str,
    subtema: Optional[str] = None,
    area: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Gera uma fila cirúrgica de treino de recuperação (Caderno de Erros + Gêmeas Inéditas)."""
    limit = max(1, min(limit, 50))

    target_subtemas = []
    if subtema:
        target_subtemas = [subtema]
    else:
        # Se nenhum subtema específico for passado, extrair os top pontos cegos do usuário
        bs_data = calculate_blindspots(db, user_id, limit=5)
        target_subtemas = [b["subtema"] for b in bs_data["blindspots"] if b.get("subtema")]

    # Se ainda assim não houver subtemas (aluno sem erros), seleciona subtemas gerais de maior peso
    if not target_subtemas:
        area_filter = f"AND q.area = ?" if area else ""
        area_param = [area] if area else []
        fallback_rows = db.execute(
            f"""
            SELECT DISTINCT COALESCE(NULLIF(q.subtema, ''), q.topic) as subtema
            FROM questions q
            WHERE q.missing_alts = 0 AND COALESCE(NULLIF(q.subtema, ''), q.topic) IS NOT NULL
            {area_filter}
            LIMIT 5
            """,
            area_param,
        ).fetchall()
        target_subtemas = [r["subtema"] for r in fallback_rows if r["subtema"]]

    if not target_subtemas:
        return []

    subtemas_placeholders = ",".join("?" * len(target_subtemas))

    # 1. Buscar questões com erro pendente (última tentativa foi incorreta) nesses subtemas
    # Cota: ~65% das vagas
    unresolved_quota = max(1, math.ceil(limit * 0.65))

    unresolved_rows = db.execute(
        f"""
        WITH latest_attempts AS (
            SELECT
                question_id,
                is_correct,
                ROW_NUMBER() OVER (PARTITION BY question_id ORDER BY id DESC) as rn
            FROM attempts
            WHERE user_id = ?
        )
        SELECT
            q.id, q.source_file, q.source_number, q.year, q.institution_code,
            q.institution_label, q.topic, q.area, q.subtema, q.editorial_status,
            'unresolved_error' AS remediation_reason
        FROM questions q
        JOIN latest_attempts la ON la.question_id = q.id AND la.rn = 1
        WHERE q.missing_alts = 0
          AND la.is_correct = 0
          AND COALESCE(NULLIF(q.subtema, ''), q.topic) IN ({subtemas_placeholders})
        ORDER BY q.id ASC
        LIMIT ?
        """,
        [user_id, *target_subtemas, unresolved_quota],
    ).fetchall()

    queue_items = [dict(r) for r in unresolved_rows]
    selected_ids = {item["id"] for item in queue_items}

    # 2. Completar com questões gêmeas inéditas dos mesmos subtemas (para testar fixação sem decoreba)
    needed = limit - len(queue_items)
    if needed > 0:
        placeholders_selected = ",".join("?" * len(selected_ids)) if selected_ids else "NULL"
        selected_params = list(selected_ids) if selected_ids else []

        twin_rows = db.execute(
            f"""
            SELECT
                q.id, q.source_file, q.source_number, q.year, q.institution_code,
                q.institution_label, q.topic, q.area, q.subtema, q.editorial_status,
                'twin_unseen_concept' AS remediation_reason
            FROM questions q
            WHERE q.missing_alts = 0
              AND COALESCE(NULLIF(q.subtema, ''), q.topic) IN ({subtemas_placeholders})
              AND q.id NOT IN (SELECT question_id FROM attempts WHERE user_id = ?)
              AND q.id NOT IN ({placeholders_selected})
            ORDER BY q.year DESC, q.id ASC
            LIMIT ?
            """,
            [*target_subtemas, user_id, *selected_params, needed],
        ).fetchall()

        for r in twin_rows:
            queue_items.append(dict(r))
            selected_ids.add(r["id"])

    # 3. Fallback: se ainda faltar para o limit, aceitar qualquer questão dos subtemas que não esteja na fila
    needed_fallback = limit - len(queue_items)
    if needed_fallback > 0:
        placeholders_selected = ",".join("?" * len(selected_ids)) if selected_ids else "NULL"
        selected_params = list(selected_ids) if selected_ids else []

        fallback_q_rows = db.execute(
            f"""
            SELECT
                q.id, q.source_file, q.source_number, q.year, q.institution_code,
                q.institution_label, q.topic, q.area, q.subtema, q.editorial_status,
                'remediation_practice' AS remediation_reason
            FROM questions q
            WHERE q.missing_alts = 0
              AND COALESCE(NULLIF(q.subtema, ''), q.topic) IN ({subtemas_placeholders})
              AND q.id NOT IN ({placeholders_selected})
            ORDER BY q.id ASC
            LIMIT ?
            """,
            [*target_subtemas, *selected_params, needed_fallback],
        ).fetchall()

        for r in fallback_q_rows:
            queue_items.append(dict(r))

    # Formatar flags como is_autoral
    for item in queue_items:
        item["is_autoral"] = bool(
            item.get("editorial_status") == "autoral"
            or (item.get("source_file") and "AUTORAL" in str(item.get("source_file")).upper())
        )

    return queue_items
