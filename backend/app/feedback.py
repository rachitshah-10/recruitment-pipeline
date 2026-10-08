"""Interview feedback: demo seed and per-cohort rollup.

The workbook has no interviewer verdicts, so startup seeds a fixed,
reproducible set of demo rows (is_demo=1) when the table is empty.
Feedback is shown up to the selected hiring week.
"""

import random
from collections import Counter
from datetime import date, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import InterviewFeedback, PipelineWeek

RATINGS = ("Strong hire", "Hire", "No hire", "Strong no hire")
ROUNDS = ("L1", "L2", "CTO")
RATING_KEYS = {"Strong hire": "strong_hire", "Hire": "hire", "No hire": "no_hire", "Strong no hire": "strong_no_hire"}

# cohort, role, candidates, rating weights (strong hire, hire, no hire, strong no hire)
DEMO_GROUPS = (
    ("Cohort 1", "FDE", 14, (2, 4, 3, 1)),
    ("Cohort 1", "Senior FDE", 6, (3, 3, 2, 1)),
    ("Cohort 2", "Associate FDE", 22, (2, 5, 3, 1)),
)

INTERVIEWERS = {
    "L1": ("Priya Nair", "Marcus Lee", "Elena Ruiz", "Tom Becker"),
    "L2": ("Arjun Mehta", "Sarah Collins", "David Okafor"),
    "CTO": ("Rahul Kapoor",),
}

FIRST = ("Aisha", "Ben", "Chloe", "Dev", "Ethan", "Fatima", "Gabriel", "Hannah", "Ishaan", "Julia", "Kevin",
         "Lena", "Mateo", "Nina", "Omar", "Paige", "Quinn", "Ravi", "Sofia", "Tariq", "Uma", "Victor",
         "Wen", "Ximena", "Yusuf", "Zara", "Noah", "Maya", "Leo", "Ivy")
LAST = ("Adams", "Banerjee", "Carter", "Diaz", "Evans", "Fischer", "Gupta", "Hughes", "Iyer", "Johnson",
        "Khan", "Lopez", "Morgan", "Nguyen", "Owens", "Patel", "Reyes", "Singh", "Turner", "Walsh")

COMMENTS = {
    "Strong hire": (
        "Designed a clean RAG pipeline end to end and explained the trade-offs clearly.",
        "Excellent client communication; would put in front of a customer tomorrow.",
        "Debugged the live exercise fast and wrote production-quality code.",
    ),
    "Hire": (
        "Solid fundamentals and good problem decomposition; needs some coaching on system design.",
        "Good coding round, a little slow on the API integration question.",
        "Clear communicator with relevant project experience.",
    ),
    "No hire": (
        "Struggled with the data modelling question and needed heavy hints.",
        "Coding was fine but could not explain design decisions.",
        "Limited hands-on experience with LLM tooling for this level.",
    ),
    "Strong no hire": (
        "Could not complete the basic coding exercise.",
        "Answers did not match the experience on the resume.",
    ),
}


def ensure_feedback():
    db = SessionLocal()
    try:
        if db.query(InterviewFeedback).count():
            return
        latest = db.query(PipelineWeek.week_ending).order_by(PipelineWeek.week_ending.desc()).first()
        end = latest[0] if latest else date.today()
        rng = random.Random(42)
        names = rng.sample([(f, l) for f in FIRST for l in LAST], sum(group[2] for group in DEMO_GROUPS))
        for cohort, role, count, weights in DEMO_GROUPS:
            for _ in range(count):
                candidate = "{} {}".format(*names.pop())
                day = end - timedelta(days=rng.randint(5, 49))
                for round_name in ROUNDS:
                    rating = rng.choices(RATINGS, weights=weights)[0]
                    db.add(
                        InterviewFeedback(
                            cohort=cohort,
                            role=role,
                            candidate=candidate,
                            round=round_name,
                            interviewer=rng.choice(INTERVIEWERS[round_name]),
                            rating=rating,
                            comment=rng.choice(COMMENTS[rating]),
                            interview_date=day,
                            is_demo=1,
                        )
                    )
                    if rating in ("No hire", "Strong no hire"):
                        break
                    day += timedelta(days=rng.randint(4, 10))
                    if day > end:
                        break
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _counts(rows: List[InterviewFeedback]) -> dict:
    counts = Counter(row.rating for row in rows)
    result = {key: counts.get(rating, 0) for rating, key in RATING_KEYS.items()}
    result["total"] = len(rows)
    positive = result["strong_hire"] + result["hire"]
    result["hire_rate"] = (positive / len(rows)) if rows else None
    return result


def build_feedback(db: Session, cohort: str, week: Optional[date]) -> dict:
    query = db.query(InterviewFeedback).filter(InterviewFeedback.cohort == cohort)
    if week is not None:
        query = query.filter(InterviewFeedback.interview_date <= week)
    rows = query.order_by(InterviewFeedback.interview_date.desc(), InterviewFeedback.id.desc()).all()
    by_round = []
    for round_name in ROUNDS:
        scoped = [row for row in rows if row.round == round_name]
        if scoped:
            by_round.append({"round": round_name, **_counts(scoped)})
    return {
        "sample": any(row.is_demo for row in rows),
        "overall": _counts(rows),
        "by_round": by_round,
        "candidates": len({row.candidate for row in rows}),
        "recent": [
            {
                "id": row.id,
                "candidate": row.candidate,
                "role": row.role,
                "round": row.round,
                "interviewer": row.interviewer,
                "rating": row.rating,
                "comment": row.comment,
                "date": row.interview_date.isoformat(),
            }
            for row in rows[:8]
        ],
    }
