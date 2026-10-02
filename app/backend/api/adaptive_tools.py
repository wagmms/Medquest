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

        # 3. Subtemas com maior impacto de perda de pontos e significância estatística
        # Critério adaptativo: quando o aluno já tem volume considerável de questões,
        # exige-se uma amostragem mínima para evitar falso-positivo em temas com 1-2 questões.
        if total_attempts >= 50:
            min_attempts = 5
            min_wrong = 2
        elif total_attempts >= 20:
            min_attempts = 3
            min_wrong = 1
        else:
            min_attempts = 2
            min_wrong = 1

        weak_query = """
            WITH latest_attempts AS (
                SELECT question_id, is_correct,
                       ROW_NUMBER() OVER (PARTITION BY question_id ORDER BY id DESC) as rn
                FROM attempts
                WHERE user_id = ?
            )
            SELECT
                COALESCE(NULLIF(q.subtema, ''), q.topic) AS topic_name,
                COALESCE(NULLIF(q.area, ''), 'Medicina Geral') AS area_name,
                COUNT(a.id) AS attempts,
                SUM(a.is_correct) AS correct,
                SUM(CASE WHEN a.is_correct = 0 THEN 1 ELSE 0 END) AS wrong_count,
                COUNT(DISTINCT CASE WHEN la.is_correct = 0 THEN q.id END) AS unresolved_count
            FROM attempts a
            JOIN questions q ON q.id = a.question_id
            LEFT JOIN latest_attempts la ON la.question_id = q.id AND la.rn = 1
            WHERE a.user_id = ? AND COALESCE(NULLIF(q.subtema, ''), q.topic) IS NOT NULL
            GROUP BY topic_name, area_name
            HAVING attempts >= ? AND wrong_count >= ?
            ORDER BY
                (unresolved_count * 2.5 + wrong_count * 1.5 + (1.0 - CAST(correct AS FLOAT) / attempts) * 10.0) DESC,
                wrong_count DESC,
                attempts DESC
            LIMIT ?
        """

        weak_rows = db.execute(
            weak_query,
            (user_id, user_id, min_attempts, min_wrong, limit)
        ).fetchall()

        # Fallback inteligente se o filtro estrito não encontrar temas (ex: acurácia muito alta ou usuário com poucos erros)
        if not weak_rows and total_attempts > 0:
            fallback_query = """
                SELECT
                    COALESCE(NULLIF(q.subtema, ''), q.topic) AS topic_name,
                    COALESCE(NULLIF(q.area, ''), 'Medicina Geral') AS area_name,
                    COUNT(a.id) AS attempts,
                    SUM(a.is_correct) AS correct,
                    SUM(CASE WHEN a.is_correct = 0 THEN 1 ELSE 0 END) AS wrong_count,
                    0 AS unresolved_count
                FROM attempts a
                JOIN questions q ON q.id = a.question_id
                WHERE a.user_id = ? AND COALESCE(NULLIF(q.subtema, ''), q.topic) IS NOT NULL
                GROUP BY topic_name, area_name
                HAVING wrong_count > 0
                ORDER BY wrong_count DESC, attempts DESC
                LIMIT ?
            """
            weak_rows = db.execute(fallback_query, (user_id, limit)).fetchall()

        weak_topics: List[Dict[str, Any]] = []
        for r in weak_rows:
            att = r["attempts"]
            cor = r["correct"] or 0
            wrong = r["wrong_count"] or (att - cor)
            unres = r["unresolved_count"] if "unresolved_count" in r.keys() else 0
            acc = round((cor / att) * 100, 1) if att > 0 else 0.0
            weak_topics.append({
                "topic": r["topic_name"],
                "area": r["area_name"],
                "attempts": att,
                "correct": cor,
                "wrong": wrong,
                "unresolved": unres,
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
    """Formata o relatório diagnóstico para injeção no prompt do Preceptor IA com rigor estatístico."""
    if not data or not data.get("has_data"):
        return """### DADOS DIAGNÓSTICOS DO ALUNO (TOOL CALLING):
O aluno ainda não possui histórico suficiente de questões resolvidas nesta conta.
Instrua-o a iniciar com uma bateria de 10 a 15 questões dos temas de maior incidência da USP/ENARE (Cardiologia, Cirurgia do Trauma, Síndromes Febris e Pré-Natal) para calibrar o motor adaptativo.
"""

    total_att = data.get("total_attempts", 0)
    lines = [
        "### DADOS DIAGNÓSTICOS EM TEMPO REAL DO ALUNO (TOOL CALLING: get_student_weak_topics):",
        f"- **Volume Amostral Total**: {total_att} questões resolvidas",
        f"- **Acurácia Média Global**: {data.get('overall_accuracy_pct', 0.0)}%",
        f"- **Revisões Espaçadas (FSRS v6) Vencidas Hoje**: {data.get('srs_due_count', 0)} questões",
        "",
        "🔥 **GARGALOS CRÍTICOS REAIS COM MATURIDADE ESTATÍSTICA (Altos Pontos Perdidos):**"
    ]

    weak_list = data.get("weak_topics", [])
    if weak_list:
        for idx, wt in enumerate(weak_list, 1):
            unres_info = f", {wt.get('unresolved', 0)} erros em aberto" if wt.get("unresolved", 0) > 0 else ""
            lines.append(
                f"  {idx}. **{wt['topic']}** ({wt['area']}): {wt['wrong']} erros em {wt['attempts']} tentativas "
                f"({wt['accuracy_pct']}% acerto{unres_info})"
            )
    else:
        lines.append("  (Nenhum tema com volume crítico de erros detectado. Aluno com alta performance geral.)")

    lines.append("")
    lines.append("⛔ DIRETRIZ ESTATÍSTICA OBRIGATÓRIA PARA O PRECEPTOR:")
    lines.append("- NUNCA mencione temas isolados com 1 ou 2 questões como 'calcanhar de aquiles' ou fraqueza do aluno.")
    lines.append("- O calcanhar de Aquiles e foco prioritário DEVE ser o subtema #1 da lista acima, onde há volume real de erros acumulados.")
    lines.append("- Se o volume global for alto (ex: > 100 Qs), valorize a consistência global mas seja cirúrgico nos erros reais.")

    return "\n".join(lines) + "\n"

