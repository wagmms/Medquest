"""Ferramentas diagnósticas e adaptativas para Tool Calling no Preceptor IA."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def get_student_weak_topics(db, user_id: Optional[str], limit: int = 5) -> Dict[str, Any]:
    """
    Tool: Consulta o banco do MedQuest e extrai o diagnóstico adaptativo do aluno.
    Identifica subtemas com menor acurácia, volume de revisões espaçadas (FSRS) vencidas hoje
    e áreas de maior vulnerabilidade clínica.
    """
    if not db or not user_id:
        return {
            "status": "unauthenticated",
            "has_data": False,
            "message": "Nenhum histórico registrado ainda. Comece resolvendo questões no quiz para mapear seu desempenho!",
            "weak_topics": [],
            "srs_due_count": 0,
            "total_attempts": 0,
            "overall_accuracy_pct": 0.0,
        }

    try:
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Total de tentativas e acurácia global
        totals_row = db.execute(
            """
            SELECT COUNT(*) AS total, COALESCE(SUM(is_correct), 0) AS correct
            FROM attempts
            WHERE user_id = ?
            """,
            (user_id,)
        ).fetchone()

        total_attempts = totals_row["total"] if totals_row else 0
        total_correct = totals_row["correct"] if totals_row else 0
        overall_accuracy = (
            round((total_correct / total_attempts) * 100, 1) if total_attempts > 0 else 0.0
        )

        # 2. Revisões FSRS vencidas hoje
        srs_row = db.execute(
            """
            SELECT COUNT(*) AS srs_due
            FROM spaced_repetition
            WHERE user_id = ? AND next_review_date <= ?
            """,
            (user_id, now_iso)
        ).fetchone()
        srs_due_count = srs_row["srs_due"] if srs_row else 0

        # 3. Subtemas com menor acurácia (mínimo 2 tentativas para confiabilidade estatística)
        weak_rows = db.execute(
            """
            SELECT COALESCE(NULLIF(q.subtema, ''), q.topic) AS topic_name,
                   COALESCE(NULLIF(q.area, ''), 'Medicina Geral') AS area_name,
                   COUNT(a.id) AS attempts,
                   SUM(a.is_correct) AS correct
            FROM attempts a
            JOIN questions q ON q.id = a.question_id
            WHERE a.user_id = ? AND COALESCE(NULLIF(q.subtema, ''), q.topic) IS NOT NULL
            GROUP BY topic_name, area_name
            HAVING attempts >= 2
            ORDER BY (CAST(correct AS FLOAT) / attempts) ASC, attempts DESC
            LIMIT ?
            """,
            (user_id, limit)
        ).fetchall()

        # Fallback se o usuário ainda não tiver nenhum tema com >= 2 tentativas
        if not weak_rows and total_attempts > 0:
            weak_rows = db.execute(
                """
                SELECT COALESCE(NULLIF(q.subtema, ''), q.topic) AS topic_name,
                       COALESCE(NULLIF(q.area, ''), 'Medicina Geral') AS area_name,
                       COUNT(a.id) AS attempts,
                       SUM(a.is_correct) AS correct
                FROM attempts a
                JOIN questions q ON q.id = a.question_id
                WHERE a.user_id = ? AND COALESCE(NULLIF(q.subtema, ''), q.topic) IS NOT NULL
                GROUP BY topic_name, area_name
                ORDER BY (CAST(correct AS FLOAT) / attempts) ASC, attempts DESC
                LIMIT ?
                """,
                (user_id, limit)
            ).fetchall()

        weak_topics: List[Dict[str, Any]] = []
        for r in weak_rows:
            att = r["attempts"]
            cor = r["correct"] or 0
            acc = round((cor / att) * 100, 1) if att > 0 else 0.0
            weak_topics.append({
                "topic": r["topic_name"],
                "area": r["area_name"],
                "attempts": att,
                "correct": cor,
                "wrong": att - cor,
                "accuracy_pct": acc,
            })

        has_data = total_attempts > 0

        return {
            "status": "success",
            "has_data": has_data,
            "total_attempts": total_attempts,
            "overall_accuracy_pct": overall_accuracy,
            "srs_due_count": srs_due_count,
            "weak_topics": weak_topics,
        }

    except Exception as exc:
        logger.error("[AdaptiveTools] Erro ao recuperar pontos fracos: %s", exc)
        return {
            "status": "error",
            "has_data": False,
            "error": str(exc),
            "weak_topics": [],
            "srs_due_count": 0,
            "total_attempts": 0,
            "overall_accuracy_pct": 0.0,
        }


def format_student_diagnostic_block(data: Dict[str, Any]) -> str:
    """Formata o relatório diagnóstico para injeção no prompt do Preceptor IA."""
    if not data or not data.get("has_data"):
        return """### DADOS DIAGNÓSTICOS DO ALUNO (TOOL CALLING):
O aluno ainda não possui histórico suficiente de questões resolvidas nesta conta.
Instrua-o a iniciar com uma bateria de 10 a 15 questões dos temas de maior incidência da USP/ENARE (Cardiologia, Cirurgia do Trauma, Síndromes Febris e Pré-Natal) para calibrar o motor adaptativo.
"""

    lines = [
        "### DADOS DIAGNÓSTICOS EM TEMPO REAL DO ALUNO (TOOL CALLING: get_student_weak_topics):",
        f"- **Total de Questões Feitas**: {data.get('total_attempts', 0)} questões",
        f"- **Acurácia Média Global**: {data.get('overall_accuracy_pct', 0.0)}%",
        f"- **Revisões Espaçadas (FSRS) Vencidas Hoje**: {data.get('srs_due_count', 0)} questões prontas para revisão imediata",
        "",
        "**Subtemas Críticos (Menor Acurácia)**:"
    ]

    for wt in data.get("weak_topics", []):
        lines.append(
            f"  * **{wt['topic']}** ({wt['area']}): {wt['accuracy_pct']}% de acerto "
            f"({wt['wrong']} erros em {wt['attempts']} tentativas)"
        )

    return "\n".join(lines) + "\n"
