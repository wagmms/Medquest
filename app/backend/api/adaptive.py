"""Deterministic adaptive-learning scoring for study queues and diagnostics."""
import json
import math
from datetime import datetime, timezone

from fsrs import Card, Scheduler

_scheduler = Scheduler(enable_fuzzing=False)


def _utc(value=None):
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def fsrs_metrics(card_json, now=None):
    """Return safe FSRS metrics; corrupt/legacy cards remain usable."""
    if not card_json:
        return {"retrievability": None, "stability": None, "difficulty": None}
    try:
        card = Card.from_dict(json.loads(card_json))
        retrievability = _scheduler.get_card_retrievability(card, _utc(now))
        return {
            "retrievability": round(max(0.0, min(1.0, float(retrievability))), 4),
            "stability": round(float(card.stability), 4) if card.stability is not None else None,
            "difficulty": round(float(card.difficulty), 4) if card.difficulty is not None else None,
        }
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        return {"retrievability": None, "stability": None, "difficulty": None}


def topic_priority(attempts, correct, retrievability=None, coverage=0.0):
    """Bayesian error estimate weighted by evidence, memory risk and coverage."""
    attempts = max(0, int(attempts or 0))
    correct = max(0, min(attempts, int(correct or 0)))
    confidence = 1.0 - math.exp(-attempts / 5.0)
    error_estimate = ((attempts - correct) + 2.0) / (attempts + 4.0)
    memory_risk = 0.5 if retrievability is None else 1.0 - retrievability
    coverage_gap = 1.0 - max(0.0, min(1.0, float(coverage or 0.0)))
    score = (0.55 * error_estimate * confidence) + (0.30 * memory_risk) + (0.15 * coverage_gap)
    return round(score, 4), round(confidence, 4)


def _due(next_review_date, now):
    if not next_review_date:
        return False
    try:
        return _utc(next_review_date) <= now
    except (TypeError, ValueError):
        return False


FOCUS_CONFIGS = {
    "coverage": {
        "topic_mult": 30.0,
        "coverage_gap": 80.0,
        "review_due": 40.0,
        "latest_wrong": 30.0,
        "memory_risk": 20.0,
    },
    "balanced": {
        "topic_mult": 40.0,
        "coverage_gap": 40.0,
        "review_due": 80.0,
        "latest_wrong": 50.0,
        "memory_risk": 40.0,
    },
    "retention": {
        "topic_mult": 50.0,
        "coverage_gap": 10.0,
        "review_due": 110.0,
        "latest_wrong": 80.0,
        "memory_risk": 60.0,
    },
}


def rank_adaptive_candidates(db, user_id, where, params, limit, now=None, adaptive_focus="balanced"):
    """Rank eligible questions with twin questions and configurable focus ratios."""
    now = _utc(now)
    cfg = FOCUS_CONFIGS.get(adaptive_focus, FOCUS_CONFIGS["balanced"])

    rows = db.execute(
        f"""
        SELECT q.id, q.source_file, q.source_number, q.year, q.institution_code,
               q.institution_label, q.topic, q.area, q.subtema,
               COUNT(a.id) AS attempts, COALESCE(SUM(a.is_correct), 0) AS correct,
               (SELECT a2.is_correct FROM attempts a2
                WHERE a2.user_id = ? AND a2.question_id = q.id
                ORDER BY a2.id DESC LIMIT 1) AS latest_correct,
               sr.next_review_date, sr.fsrs_card
        FROM questions q
        LEFT JOIN attempts a ON a.question_id = q.id AND a.user_id = ?
        LEFT JOIN spaced_repetition sr ON sr.question_id = q.id AND sr.user_id = ?
        WHERE {where}
        GROUP BY q.id
        """,
        [user_id, user_id, user_id, *params],
    ).fetchall()

    topic_totals = {}
    for row in rows:
        topic = row["subtema"] or row["topic"] or "Sem tema"
        stats = topic_totals.setdefault(topic, [0, 0])
        stats[0] += row["attempts"]
        stats[1] += row["correct"]

    # Pool of unattempted questions from current rows, grouped by topic
    unseen_by_topic = {}
    for row in rows:
        if row["attempts"] == 0:
            topic = row["subtema"] or row["topic"] or "Sem tema"
            unseen_by_topic.setdefault(topic, []).append(row)

    # Track paired twin questions: twin_id -> (orig_id, orig_inst, topic)
    paired_twin_ids = {}
    replaced_orig_ids = set()

    for row in rows:
        is_due = _due(row["next_review_date"], now)
        if is_due and row["latest_correct"] == 1:
            orig_id = row["id"]
            orig_inst = row["institution_code"] or ""
            topic = row["subtema"] or row["topic"] or "Sem tema"

            twin_candidate = None
            candidates = unseen_by_topic.get(topic, [])
            for c in candidates:
                if c["id"] not in paired_twin_ids:
                    if c["institution_code"] != orig_inst:
                        twin_candidate = c
                        break
            if twin_candidate is None:
                for c in candidates:
                    if c["id"] not in paired_twin_ids:
                        twin_candidate = c
                        break

            if twin_candidate is None and topic != "Sem tema":
                db_twin = db.execute(
                    """
                    SELECT q.id, q.source_file, q.source_number, q.year, q.institution_code,
                           q.institution_label, q.topic, q.area, q.subtema,
                           0 AS attempts, 0 AS correct, NULL AS latest_correct,
                           NULL AS next_review_date, NULL AS fsrs_card
                    FROM questions q
                    WHERE q.missing_alts = 0
                      AND COALESCE(NULLIF(q.subtema, ''), q.topic) = ?
                      AND q.id NOT IN (SELECT question_id FROM attempts WHERE user_id = ?)
                    ORDER BY (q.institution_code != ?) DESC, q.id ASC
                    LIMIT 1
                    """,
                    (topic, user_id, orig_inst),
                ).fetchone()
                if db_twin and db_twin["id"] not in paired_twin_ids:
                    twin_candidate = db_twin

            if twin_candidate is not None:
                paired_twin_ids[twin_candidate["id"]] = (orig_id, orig_inst, topic)
                replaced_orig_ids.add(orig_id)

    ranked = []
    seen_ids = set()

    for row in rows:
        qid = row["id"]
        if qid in replaced_orig_ids:
            continue

        item = dict(row)
        metrics = fsrs_metrics(item.pop("fsrs_card"), now)
        topic = item["subtema"] or item["topic"] or "Sem tema"
        topic_attempts, topic_correct = topic_totals.get(topic, [0, 0])
        topic_score, _ = topic_priority(topic_attempts, topic_correct, metrics["retrievability"])
        is_due = _due(item.pop("next_review_date"), now)
        reasons = []

        score = topic_score * cfg["topic_mult"]

        if qid in paired_twin_ids:
            orig_id, orig_inst, orig_topic = paired_twin_ids[qid]
            score += cfg["review_due"]
            reasons.append("twin_concept_review")
            item["is_twin"] = True
            item["twin_for_question_id"] = orig_id
            item["twin_origin_institution"] = orig_inst
            item["twin_subtema"] = orig_topic
        elif is_due:
            score += cfg["review_due"]
            reasons.append("review_due")
            item["is_twin"] = False
        else:
            item["is_twin"] = False

        if item["latest_correct"] == 0:
            score += cfg["latest_wrong"]
            reasons.append("latest_attempt_wrong")

        if item["attempts"] == 0 and qid not in paired_twin_ids:
            score += cfg["coverage_gap"]
            reasons.append("coverage_gap")

        if metrics["retrievability"] is not None and metrics["retrievability"] < 0.9:
            score += (0.9 - metrics["retrievability"]) * cfg["memory_risk"]
            reasons.append("memory_at_risk")

        score -= min(item["attempts"], 10) * 1.5
        item["adaptive_score"] = round(score, 3)
        item["adaptive_reasons"] = reasons or ["balanced_practice"]
        item["retrievability"] = metrics["retrievability"]
        item.pop("attempts", None)
        item.pop("correct", None)
        item.pop("latest_correct", None)
        ranked.append(item)
        seen_ids.add(qid)

    for twin_id, (orig_id, orig_inst, orig_topic) in paired_twin_ids.items():
        if twin_id not in seen_ids:
            twin_row = db.execute(
                """
                SELECT q.id, q.source_file, q.source_number, q.year, q.institution_code,
                       q.institution_label, q.topic, q.area, q.subtema
                FROM questions q WHERE q.id = ?
                """,
                (twin_id,),
            ).fetchone()
            if twin_row:
                item = dict(twin_row)
                topic_attempts, topic_correct = topic_totals.get(orig_topic, [0, 0])
                topic_score, _ = topic_priority(topic_attempts, topic_correct, None)
                score = topic_score * cfg["topic_mult"] + cfg["review_due"]
                item["is_twin"] = True
                item["twin_for_question_id"] = orig_id
                item["twin_origin_institution"] = orig_inst
                item["twin_subtema"] = orig_topic
                item["adaptive_score"] = round(score, 3)
                item["adaptive_reasons"] = ["twin_concept_review"]
                item["retrievability"] = None
                ranked.append(item)
                seen_ids.add(twin_id)

    ranked.sort(key=lambda item: (-item["adaptive_score"], item["id"]))
    return ranked[:limit]


def get_adaptive_signals_by_topic(db, user_id, now=None):
    """Compute deterministic adaptive signals for ALL topics for the given user."""
    now = _utc(now)
    rows = db.execute(
        """
        WITH AttemptRanks AS (
            SELECT
                q.id as question_id,
                COALESCE(NULLIF(q.subtema, ''), q.topic) as topic,
                a.is_correct,
                ROW_NUMBER() OVER (PARTITION BY COALESCE(NULLIF(q.subtema, ''), q.topic) ORDER BY a.answered_at ASC) as rn
            FROM attempts a
            JOIN questions q ON q.id = a.question_id
            WHERE a.user_id = ? AND q.missing_alts=0 AND COALESCE(NULLIF(q.subtema, ''), q.topic) IS NOT NULL
        ),
        TopicStats AS (
            SELECT
                topic,
                COUNT(DISTINCT question_id) AS answered,
                SUM(CASE WHEN rn <= 5 THEN is_correct ELSE 0 END) as diag_correct,
                SUM(CASE WHEN rn <= 5 THEN 1 ELSE 0 END) as diag_attempts,
                SUM(CASE WHEN rn > 5 THEN is_correct ELSE 0 END) as prac_correct,
                SUM(CASE WHEN rn > 5 THEN 1 ELSE 0 END) as prac_attempts,
                SUM(is_correct) as correct,
                COUNT(is_correct) as attempts
            FROM AttemptRanks
            GROUP BY topic
        )
        SELECT COALESCE(NULLIF(q.subtema, ''), q.topic) AS topic, MIN(q.area) AS area,
               COUNT(DISTINCT q.id) AS available,
               COALESCE(ts.attempts, 0) AS attempts,
               COALESCE(ts.answered, 0) AS answered,
               COALESCE(ts.correct, 0) AS correct,
               COALESCE(ts.diag_correct, 0) AS diag_correct,
               COALESCE(ts.diag_attempts, 0) AS diag_attempts,
               COALESCE(ts.prac_correct, 0) AS prac_correct,
               COALESCE(ts.prac_attempts, 0) AS prac_attempts
        FROM questions q 
        LEFT JOIN TopicStats ts ON ts.topic = COALESCE(NULLIF(q.subtema, ''), q.topic)
        WHERE q.missing_alts=0 AND COALESCE(NULLIF(q.subtema, ''), q.topic) IS NOT NULL
        GROUP BY COALESCE(NULLIF(q.subtema, ''), q.topic)
        """,
        (user_id,),
    ).fetchall()
    fsrs_rows = db.execute(
        """SELECT COALESCE(NULLIF(q.subtema, ''), q.topic) AS topic,
                  sr.fsrs_card, sr.next_review_date
           FROM spaced_repetition sr JOIN questions q ON q.id=sr.question_id
           WHERE sr.user_id=?""",
        (user_id,),
    ).fetchall()
    memory = {}
    for row in fsrs_rows:
        metrics = fsrs_metrics(row["fsrs_card"], now)
        bucket = memory.setdefault(row["topic"], {"values": [], "due": 0})
        if metrics["retrievability"] is not None:
            bucket["values"].append(metrics["retrievability"])
        if _due(row["next_review_date"], now):
            bucket["due"] += 1

    signals = {}
    for row in rows:
        topic_name = row["topic"]
        mem = memory.get(topic_name, {"values": [], "due": 0})
        retrievability = min(mem["values"]) if mem["values"] else None
        coverage = row["answered"] / row["available"] if row["available"] else 0.0
        score, confidence = topic_priority(row["attempts"], row["correct"], retrievability, coverage)
        reasons = []
        if row["attempts"] and row["correct"] / row["attempts"] < 0.65:
            reasons.append("low_accuracy")
        if mem["due"]:
            reasons.append("reviews_due")
        if retrievability is not None and retrievability < 0.9:
            reasons.append("memory_at_risk")
        if row["attempts"] > 0 and coverage < 0.2:
            reasons.append("low_coverage")
        signals[topic_name] = {
            "topic": topic_name, "area": row["area"], "available": row["available"],
            "attempts": row["attempts"], "correct": row["correct"], "answered": row["answered"],
            "accuracy": round(row["correct"] / row["attempts"], 4) if row["attempts"] else None,
            "diag_accuracy": round(row["diag_correct"] / row["diag_attempts"], 4) if row["diag_attempts"] else None,
            "prac_accuracy": round(row["prac_correct"] / row["prac_attempts"], 4) if row["prac_attempts"] else None,
            "coverage": round(coverage, 4), "confidence": round(confidence, 4),
            "retrievability": retrievability, "due_count": mem["due"],
            "priority_score": score, "reasons": reasons,
        }
    return signals


def build_learning_profile(db, user_id, now=None, subtema=None, limit=15):
    """Build a transparent personalized diagnosis and daily goal."""
    now = _utc(now)
    signals = get_adaptive_signals_by_topic(db, user_id, now=now)
    due_total = sum(item["due_count"] for item in signals.values())

    topics = []
    for item in signals.values():
        reasons = list(item["reasons"])
        if item["coverage"] < 0.2 and "low_coverage" not in reasons:
            reasons.append("low_coverage")
        topics.append({
            **item,
            "reasons": reasons or ["balanced_practice"],
        })

    topics.sort(key=lambda item: (-item["priority_score"], item["topic"]))
    if subtema is not None:
        topics = [item for item in topics if item["topic"] == subtema]
    config = db.execute(
        "SELECT questions_per_day, target_score, exam_date, hours_per_day FROM planner_config WHERE user_id=?",
        (user_id,),
    ).fetchone()
    daily_goal = int(config["questions_per_day"] if config and config["questions_per_day"] else 30)
    hours_per_day = int(config["hours_per_day"] if config and config["hours_per_day"] else 4)
    
    # Orçamento de tempo: 1 questão = 3 min (resolução + leitura + flashcard) -> 20 q/h
    max_capacity = hours_per_day * 20
    reviews_to_do_today = min(due_total, max_capacity)
    backlog_pending = max(0, due_total - max_capacity)
    questions_today = min(max(daily_goal, reviews_to_do_today), max_capacity)

    return {
        "generated_at": now.isoformat(),
        "goal": {
            "questions_today": questions_today, 
            "configured_daily_questions": daily_goal,
            "reviews_due": due_total,
            "reviews_to_do_today": reviews_to_do_today,
            "backlog_pending": backlog_pending,
            "hours_budget": hours_per_day,
            "max_capacity": max_capacity,
            "target_score": config["target_score"] if config else None,
            "exam_date": config["exam_date"] if config else None,
        },
        "topics": topics[:limit] if limit is not None else topics,
        "method": {
            "deterministic": True,
            "signals": ["FSRS retrievability", "accuracy with evidence confidence", "coverage", "due reviews"],
        },
    }
