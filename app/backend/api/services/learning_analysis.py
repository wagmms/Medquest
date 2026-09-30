"""Learning evidence, separate from practice volume and exam predictions.

Rank exposures before applying reporting windows. Each question contributes at
most one first response and one delayed-review outcome per reporting window.
The 24-hour boundary is a reporting convention, not a scheduling prescription.
Latest recorded state follows attempt ID, matching the error notebook/study queue;
first exposure and delayed reviews follow occurrence timestamps, including uploads.
"""
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from ..adaptive import fsrs_metrics, _due
from ..srs import QUESTION_DESIRED_RETENTION

DELAY_HOURS = 24


def _measure(correct=0, total=0):
    return {"correct": correct, "total": total,
            "accuracy": round(correct / total, 4) if total else None}


def _add(measure, correct):
    measure["total"] += 1
    measure["correct"] += int(correct or 0)


def _finalize(measure):
    measure.update(_measure(measure["correct"], measure["total"]))


def _topic(area, topic, legacy_topic=False):
    return {
        "area": area, "topic": topic, "legacy_topic": legacy_topic,
        "available": 0, "answered": 0, "unseen": 0,
        "new_questions": _measure(), "previous_new_questions": _measure(),
        "delayed_reviews": _measure(), "previous_delayed_reviews": _measure(),
        "unresolved": 0, "recurring": 0, "corrected": 0,
        "retained_corrections": 0, "pending_checks": 0,
        "due": 0, "tracked": 0, "at_risk": 0,
        "min_retrievability": None, "last_answered_at": None,
    }


def _study_url(institution, area, topic, status, legacy=False, limit=10):
    params = {"status": status, "limit": limit}
    if institution:
        params["institution"] = institution
    if area:
        params["area"] = area
    if topic:
        params["topic" if legacy else "subtema"] = topic
    return "/estudar?" + urlencode(params)


def build_learning_analysis(db, user_id, *, days=30, tz_offset=-180,
                            institution="", area="", subtema="", now=None):
    now = now or datetime.now(timezone.utc)
    local_now = now + timedelta(minutes=tz_offset)
    local_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
    start = local_start - timedelta(minutes=tz_offset)
    previous_start = start - timedelta(days=days)
    # Use Julian days in SQL to compare ISO strings with Z, offsets or spaces.
    bounds = (start.isoformat(), previous_start.isoformat(), now.isoformat())
    clauses = ["q.missing_alts = 0", "COALESCE(q.status, 'active') = 'active'"]
    params = []
    for field, value in (("institution_code", institution), ("area", area), ("subtema", subtema)):
        if value:
            clauses.append(f"q.{field} = ?")
            params.append(value)
    where = " AND ".join(clauses)
    # Null dates remain in the exposure ranking, conservatively preventing an
    # undated historical response from turning a later repeat into a first try.
    rows = db.execute(f"""
        WITH bounds AS (
            SELECT julianday(?) AS start, julianday(?) AS previous_start, julianday(?) AS now
        ), ordered AS (
            SELECT a.*, julianday(answered_at) AS moment,
                ROW_NUMBER() OVER (PARTITION BY question_id ORDER BY julianday(answered_at), id) AS first_rank,
                ROW_NUMBER() OVER (PARTITION BY question_id ORDER BY id DESC) AS latest_rank,
                LAG(julianday(answered_at)) OVER (PARTITION BY question_id ORDER BY julianday(answered_at), id) AS previous_moment
            FROM attempts a, bounds b
            WHERE a.user_id = ? AND a.is_correct IN (0, 1)
                AND (julianday(answered_at) <= b.now OR julianday(answered_at) IS NULL)
        ), marked AS (
            SELECT o.*,
                CASE WHEN moment - previous_moment >= 1 THEN 1 ELSE 0 END AS delayed,
                MAX(CASE WHEN is_correct = 0 THEN moment END) OVER (PARTITION BY question_id) AS last_error
            FROM ordered o
        ), evidence AS (
            SELECT question_id,
                MAX(CASE WHEN first_rank = 1 THEN moment END) AS first_moment,
                MAX(CASE WHEN first_rank = 1 THEN is_correct END) AS first_correct,
                MAX(CASE WHEN latest_rank = 1 THEN is_correct END) AS latest_correct,
                MAX(CASE WHEN latest_rank = 1 THEN answered_at END) AS last_answered_at,
                SUM(CASE WHEN is_correct = 0 THEN 1 ELSE 0 END) AS errors,
                MAX(CASE WHEN delayed = 1 AND is_correct = 1 AND moment > last_error THEN moment END) AS retained_at,
                MAX(CASE WHEN delayed = 1 AND moment >= b.start THEN moment END) AS review_moment,
                MAX(CASE WHEN delayed = 1 AND moment >= b.previous_start AND moment < b.start THEN moment END) AS previous_review_moment
            FROM marked, bounds b GROUP BY question_id
        )
        SELECT q.area, q.subtema, q.topic, q.id, e.*,
            (SELECT is_correct FROM marked m WHERE m.question_id = q.id AND m.moment = e.review_moment AND m.delayed = 1 ORDER BY id DESC LIMIT 1) AS review_correct,
            (SELECT is_correct FROM marked m WHERE m.question_id = q.id AND m.moment = e.previous_review_moment AND m.delayed = 1 ORDER BY id DESC LIMIT 1) AS previous_review_correct,
            sr.fsrs_card, sr.next_review_date,
            b.start AS window_start, b.previous_start AS prior_start
        FROM questions q CROSS JOIN bounds b
        LEFT JOIN evidence e ON e.question_id = q.id
        LEFT JOIN spaced_repetition sr ON sr.question_id = q.id AND sr.user_id = ?
        WHERE {where}
    """, (*bounds, user_id, user_id, *params)).fetchall()

    topics = {}
    weeks = {}
    for offset in range(0, days, 7):
        day = (local_start + timedelta(days=offset)).date().isoformat()
        weeks[day] = {"start": day, "new_questions": _measure(), "delayed_reviews": _measure()}

    def add_week(moment, key, correct):
        # Julian epoch conversion; offset controls the report's local calendar.
        stamp = datetime.fromtimestamp((moment - 2440587.5) * 86400, timezone.utc)
        day_index = ((stamp + timedelta(minutes=tz_offset)).date() - local_start.date()).days
        week = (local_start + timedelta(days=(day_index // 7) * 7)).date().isoformat()
        if week in weeks:
            _add(weeks[week][key], correct)

    for row in rows:
        r = dict(row)
        topic_name = r["subtema"] or r["topic"] or "Sem tema classificado"
        topic_area = r["area"] or "Sem área classificada"
        legacy = not bool(r["subtema"])
        key = (topic_area, topic_name, legacy)
        item = topics.setdefault(key, _topic(topic_area, topic_name, legacy))
        item["available"] += 1
        answered = r["question_id"] is not None
        item["answered"] += int(answered)
        item["unseen"] += int(not answered)
        first = r["first_moment"]
        if first is not None:
            if first >= r["window_start"]:
                _add(item["new_questions"], r["first_correct"])
                add_week(first, "new_questions", r["first_correct"])
            elif first >= r["prior_start"]:
                _add(item["previous_new_questions"], r["first_correct"])
        for prefix in ("", "previous_"):
            moment = r[f"{prefix}review_moment"]
            if moment is not None:
                _add(item[f"{prefix}delayed_reviews"], r[f"{prefix}review_correct"])
                if not prefix:
                    add_week(moment, "delayed_reviews", r["review_correct"])
        unresolved = answered and r["latest_correct"] == 0
        corrected = answered and r["latest_correct"] == 1 and r["errors"] > 0
        retained = corrected and r["retained_at"] is not None
        item["unresolved"] += int(unresolved)
        item["recurring"] += int(unresolved and r["errors"] > 1)
        item["corrected"] += int(corrected)
        item["retained_corrections"] += int(retained)
        item["pending_checks"] += int(corrected and not retained)
        last = r["last_answered_at"]
        if last and (not item["last_answered_at"] or last > item["last_answered_at"]):
            item["last_answered_at"] = last
        item["due"] += int(_due(r["next_review_date"], now))
        retention = fsrs_metrics(r["fsrs_card"], now)["retrievability"]
        if retention is not None:
            item["tracked"] += 1
            if retention < QUESTION_DESIRED_RETENTION:
                item["at_risk"] += 1
                item["min_retrievability"] = min(item["min_retrievability"] or 1, retention)

    measures = ("new_questions", "previous_new_questions", "delayed_reviews", "previous_delayed_reviews")
    counts = ("available", "answered", "unseen", "unresolved", "recurring", "corrected",
              "retained_corrections", "pending_checks", "due", "tracked", "at_risk")
    summary = {key: 0 for key in counts}
    summary.update({key: _measure() for key in measures})
    for item in topics.values():
        for key in measures:
            _finalize(item[key])
            summary[key]["correct"] += item[key]["correct"]
            summary[key]["total"] += item[key]["total"]
        for key in counts:
            summary[key] += item[key]
        recent = item["new_questions"]
        prior = item["previous_new_questions"]
        item["change_pp"] = round((recent["accuracy"] - prior["accuracy"]) * 100, 1) if min(recent["total"], prior["total"]) >= 5 else None
        item["reason"] = (
            "unresolved" if item["unresolved"] else
            "reviews_due" if item["due"] else
            "low_accuracy" if recent["total"] >= 5 and recent["accuracy"] < .7 else
            "needs_assessment" if recent["total"] < 5 and item["unseen"] else
            "follow_up" if item["pending_checks"] else "monitor"
        )
        # A topic can contain both corrected and unresolved items; expose counts
        # instead of declaring the whole topic mastered.
        item["follow_up"] = (
            "needs_work" if item["unresolved"] else
            "delayed_check_pending" if item["pending_checks"] else
            "retention_observed" if item["retained_corrections"] else
            "needs_assessment" if not item["answered"] else "monitor"
        )
        valid_topic = item["topic"] != "Sem tema classificado"
        valid_area = item["area"] != "Sem área classificada"
        item["actions"] = {
            name: _study_url(institution, item["area"] if valid_area else "",
                             item["topic"] if valid_topic else "", status, item["legacy_topic"])
            if count and (valid_topic or valid_area) else None
            for name, status, count in (("errors", "wrong", item["unresolved"]),
                                       ("new", "new", item["unseen"]),
                                       ("reviews", "srs_due", item["due"]))
        }
    for key in measures:
        _finalize(summary[key])
    for week in weeks.values():
        _finalize(week["new_questions"])
        _finalize(week["delayed_reviews"])

    ordered = sorted(topics.values(), key=lambda t: (-t["unresolved"], -t["due"],
                     t["new_questions"]["accuracy"] if t["new_questions"]["total"] >= 5 else 1,
                     t["area"], t["topic"]))
    remediation = [t for t in ordered if t["reason"] in ("unresolved", "reviews_due", "low_accuracy")][:3]
    exploration = [t for t in ordered if t["reason"] == "needs_assessment"][:2]
    priorities = remediation + exploration
    if not priorities:
        priorities = [t for t in ordered if t["reason"] == "follow_up"][:3]

    # Bank metadata (not another user's activity) keeps empty scopes selectable.
    options = db.execute("""
        SELECT institution_code, MIN(institution_label) AS institution_label, area, subtema
        FROM questions WHERE missing_alts = 0 AND COALESCE(status, 'active') = 'active'
        GROUP BY institution_code, area, subtema ORDER BY institution_code, area, subtema
    """).fetchall()
    institutions = {r["institution_code"]: r["institution_label"] or r["institution_code"] for r in options if r["institution_code"]}
    scoped_options = [r for r in options if not institution or r["institution_code"] == institution]
    config = db.execute("SELECT questions_per_day, hours_per_day FROM planner_config WHERE user_id = ?", (user_id,)).fetchone()
    hours = max(0, float(config["hours_per_day"] or 4)) if config else 4
    capacity = int(hours * 20)
    configured = max(0, int(config["questions_per_day"] or 30)) if config else 30
    goal = min(max(configured, summary["due"]), capacity, summary["available"])
    return {
        "generated_at": now.isoformat(),
        "scope": {"days": days, "tz_offset": tz_offset, "institution": institution, "area": area, "subtema": subtema,
                  "start": local_start.date().isoformat(), "end": local_now.date().isoformat(),
                  "previous_start": (local_start - timedelta(days=days)).date().isoformat(),
                  "previous_end": (local_start - timedelta(days=1)).date().isoformat()},
        "summary": summary, "topics": ordered, "priorities": priorities, "weeks": list(weeks.values()),
        "options": {"institutions": [{"key": k, "label": v} for k, v in institutions.items()],
                    "areas": sorted({r["area"] for r in scoped_options if r["area"]}),
                    "subtemas": sorted({r["subtema"] for r in scoped_options if r["subtema"] and (not area or r["area"] == area)})},
        "goal": {"questions": goal, "capacity": capacity, "hours": hours,
                 "reviews": min(summary["due"], goal), "pending": max(0, summary["due"] - goal)},
        "method": {"delayed_review_hours": DELAY_HOURS, "retention_target": QUESTION_DESIRED_RETENTION,
                   "comparison_minimum": 5},
    }
