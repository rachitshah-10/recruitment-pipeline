"""Academy cohorts for the cohort-health page.

Academy A is the workbook roster. Its week-6 class averages are the real
trainer numbers; the per-person split, resumes, and Academies B and C are
illustrative and seeded with a fixed random seed.
"""

import random
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app import config
from app.database import SessionLocal
from app.models import AcademyCohort, Person, TraineeProfile, TraineeWeekScore

WEEK_TOPICS = (
    "Python and software fundamentals",
    "APIs and data modelling",
    "SQL and enterprise data",
    "Cloud foundations",
    "LLM application basics",
    "Retrieval-Augmented Generation & Enterprise Data Fluency",
    "Evaluation and guardrails",
    "Agents and tool use",
    "System design for client work",
    "Client communication",
    "Capstone build",
    "Capstone review",
)

EDUCATION = (
    "B.S. Computer Science",
    "M.S. Computer Science",
    "B.S. Information Systems",
    "Bootcamp, software engineering",
)
CERT_POOL = ("AWS Cloud Practitioner", "Azure Fundamentals", "Google Associate Cloud Engineer")

ACADEMY_B = (
    "Maya Chen", "Oliver Grant", "Priya Raman", "Lucas Meyer", "Amira Hassan", "Jonah Blake",
    "Sofia Alvarez", "Ethan Park", "Leila Osman", "Noah Berg", "Hannah Idris", "Caleb Nguyen",
    "Isla Moreau", "Freya Lind", "Mateo Silva", "Nora Kapoor", "Julian Okonkwo", "Aisha Rahman",
)
ACADEMY_C = (
    ("Elena Vasquez", "TriNet"),
    ("Thomas Wright", "SEI"),
    ("Amina Diallo", "PMI"),
    ("Felix Bauer", "Hiscox"),
    ("Chloe Nakamura", "M&T Bank"),
    ("Diego Morales", "Peabody"),
    ("Omar Farouk", None),
    ("Grace Pemberton", None),
    ("Sana Iqbal", None),
    ("Henrik Dahl", None),
    ("Ruby Callahan", None),
    ("Kenji Sato", None),
    ("Amara Boateng", None),
    ("Patrick Doyle", None),
    ("Yasmin Haddad", None),
    ("Connor Walsh", None),
)
LOCATIONS = ("USA", "USA", "USA", "UK", "India", "Canada")


def _anchored(rng, count, target, spread, low, high):
    """Values whose mean is exactly target, each inside [low, high]."""
    if count <= 0:
        return []
    noise = [rng.uniform(-spread, spread) for _ in range(count)]
    noise[-1] = -sum(noise[:-1])
    values = [target + item for item in noise]
    for _ in range(20):
        values = [min(high, max(low, value)) for value in values]
        drift = count * target - sum(values)
        if abs(drift) < 1e-9:
            return values
        if drift > 0:
            index = max(range(count), key=lambda item: high - values[item])
            room = high - values[index]
            take = min(drift, room)
        else:
            index = max(range(count), key=lambda item: values[item] - low)
            room = values[index] - low
            take = -min(-drift, room)
        if abs(take) < 1e-12:
            break
        values[index] += take
    return values


def _csv(values):
    return ", ".join(values)


def _split(text):
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def _resume(rng):
    skills = rng.sample(list(config.CORE_SKILLS), rng.randint(3, 6))
    if rng.random() < 0.4:
        skills.append(rng.choice(("Java", "Tableau", "Spark")))
    certs = rng.sample(CERT_POOL, rng.choice((0, 0, 1, 1, 2)))
    return {
        "years_experience": round(rng.uniform(0.4, 6.0), 1),
        "education": rng.choice(EDUCATION),
        "skills": _csv(skills),
        "certifications": _csv(certs),
    }


def _add_week(db, trainee_id, week, hands_on, proctored):
    topic = WEEK_TOPICS[week - 1] if 1 <= week <= len(WEEK_TOPICS) else None
    db.add(
        TraineeWeekScore(
            trainee_id=trainee_id,
            week=week,
            hands_on=hands_on,
            proctored=proctored,
            topic=topic,
        )
    )


def _seed_scores(db, rng, trainees, weeks, hands_target, proctored_target, spread):
    for week in weeks:
        hands = _anchored(rng, len(trainees), hands_target, spread, 0.62, 0.995)
        proctored = _anchored(rng, len(trainees), proctored_target, spread, 0.62, 0.995)
        for trainee, hand, proc in zip(trainees, hands, proctored):
            _add_week(db, trainee.id, week, hand, proc)


def _rising_scores(db, rng, trainees, last_week, start_mean, end_mean):
    ability = [rng.uniform(-0.06, 0.06) for _ in trainees]
    for week in range(1, last_week + 1):
        progress = (week - 1) / float(max(last_week - 1, 1))
        center = start_mean + (end_mean - start_mean) * progress
        for trainee, tilt in zip(trainees, ability):
            value = min(0.99, max(0.64, center + tilt + rng.uniform(-0.025, 0.025)))
            gap = rng.uniform(-0.03, 0.03)
            _add_week(db, trainee.id, week, value, min(0.995, max(0.64, value + gap)))
    db.flush()
    last = (
        db.query(TraineeWeekScore)
        .filter(
            TraineeWeekScore.trainee_id.in_([trainee.id for trainee in trainees]),
            TraineeWeekScore.week == last_week,
        )
        .all()
    )
    by_id = {row.trainee_id: row for row in last}
    hands = _anchored(rng, len(trainees), end_mean, 0.04, 0.70, 0.995)
    proctored = _anchored(rng, len(trainees), min(0.99, end_mean + 0.015), 0.04, 0.70, 0.995)
    for trainee, hand, proc in zip(trainees, hands, proctored):
        by_id[trainee.id].hands_on = hand
        by_id[trainee.id].proctored = proc
    for trainee in trainees[:3]:
        row = by_id[trainee.id]
        row.hands_on = max(0.64, row.hands_on - 0.08)
        row.proctored = max(0.64, row.proctored - 0.08)


def ensure_academy():
    db = SessionLocal()
    try:
        if db.query(AcademyCohort).count():
            return
        rng = random.Random(42)
        _seed_academy_a(db, rng)
        _seed_academy_b(db, rng)
        _seed_academy_c(db, rng)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _cohort_row(db, code, name, start, source):
    row = AcademyCohort(
        code=code,
        name=name,
        start_date=start,
        program_weeks=config.TRAINING_PROGRAM_WEEKS,
        source=source,
    )
    db.add(row)
    db.flush()
    return row


def _profile(db, cohort, name, location, hire_source, resume, person_id=None, client=None, client_start=None):
    row = TraineeProfile(
        cohort_id=cohort.id,
        person_id=person_id,
        name=name,
        location=location,
        hire_source=hire_source,
        years_experience=resume["years_experience"],
        education=resume["education"],
        skills=resume["skills"],
        certifications=resume["certifications"],
        client=client,
        client_start=client_start,
        is_demo=1,
    )
    db.add(row)
    db.flush()
    return row


def _seed_academy_a(db, rng):
    cohort = _cohort_row(db, "A", "Academy A", date(2026, 8, 17), "workbook")
    people = db.query(Person).filter(Person.career_stage == "Trainee").order_by(Person.name).all()
    trainees = [
        _profile(db, cohort, person.name, person.location, person.source or "External", _resume(rng), person_id=person.id)
        for person in people
    ]
    if trainees:
        _seed_scores(db, rng, trainees, [6], 0.95, 0.97, 0.045)


def _seed_academy_b(db, rng):
    cohort = _cohort_row(db, "B", "Academy B", date(2026, 9, 22), "demo")
    trainees = [
        _profile(db, cohort, name, LOCATIONS[index % len(LOCATIONS)], "External", _resume(rng))
        for index, name in enumerate(ACADEMY_B)
    ]
    _seed_scores(db, rng, trainees, [1], 0.80, 0.82, 0.05)
    _seed_scores(db, rng, trainees, [2], 0.84, 0.86, 0.05)


def _seed_academy_c(db, rng):
    cohort = _cohort_row(db, "C", "Academy C", date(2026, 7, 20), "demo")
    placed_on = date(2026, 10, 5)
    trainees = []
    for index, (name, client) in enumerate(ACADEMY_C):
        trainees.append(
            _profile(
                db,
                cohort,
                name,
                LOCATIONS[index % len(LOCATIONS)],
                "External" if index % 5 else "Internal",
                _resume(rng),
                client=client,
                client_start=placed_on if client else None,
            )
        )
    _rising_scores(db, rng, trainees, 12, 0.78, 0.93)


def _calendar_week(start, as_of, program_weeks):
    if as_of < start:
        return 0
    return min((as_of - start).days // 7 + 1, program_weeks)


def _supply_date(start, program_weeks):
    return start + timedelta(days=program_weeks * 7)


def _experience_points(years):
    if years >= 4:
        return 95
    if years >= 2:
        return 80
    if years >= 1:
        return 60
    return 40


def _education_points(label):
    if label.startswith("M."):
        return 90
    if label.startswith("Bootcamp"):
        return 60
    return 75


def _cert_points(certs):
    if len(certs) >= 2:
        return 95
    if len(certs) == 1:
        return 70
    return 40


def _split(text):
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def _resume_fit(profile):
    skills = _split(profile.skills)
    certs = _split(profile.certifications)
    matched = [skill for skill in config.CORE_SKILLS if skill in skills]
    missing = [skill for skill in config.CORE_SKILLS if skill not in skills]
    parts = {
        "experience": _experience_points(profile.years_experience),
        "skills": (len(matched) / float(len(config.CORE_SKILLS))) * 100,
        "certifications": _cert_points(certs),
        "education": _education_points(profile.education),
    }
    score = sum(parts[key] * weight for key, weight in config.RESUME_PARTS.items())
    return {
        "score": round(score, 1),
        "years_experience": profile.years_experience,
        "education": profile.education,
        "skills": skills,
        "certifications": certs,
        "matched_skills": matched,
        "missing_skills": missing,
        "parts": {key: round(value, 1) for key, value in parts.items()},
    }


def _band(score):
    if score >= config.BAND_DEPLOY:
        return "Deploy-ready"
    if score >= config.BAND_COACHING:
        return "Needs coaching"
    return "At risk"


def _placed(profile, person, as_of):
    if person is not None:
        if not person.client or not person.client_start or person.client_start > as_of:
            return False, None
        if person.client_end and person.client_end < as_of:
            return False, None
        return True, person.client
    if profile.client and profile.client_start and profile.client_start <= as_of:
        return True, profile.client
    return False, None


def _mean(values):
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present) / float(len(present))


def _reason(latest, class_hands, class_proctored, missing, declining, decline_points):
    issues = []
    if latest and class_proctored is not None:
        gap = round((class_proctored - latest["proctored"]) * 100)
        if gap >= 5:
            issues.append((gap, "Proctored {:.0%} is {} points under the class".format(latest["proctored"], gap)))
    if latest and class_hands is not None:
        gap = round((class_hands - latest["hands_on"]) * 100)
        if gap >= 5:
            issues.append((gap, "Hands-on {:.0%} is {} points under the class".format(latest["hands_on"], gap)))
    if missing:
        issues.append((len(missing) * 8, "Missing {} of {} core skills".format(len(missing), len(config.CORE_SKILLS))))
    if issues:
        issues.sort(key=lambda item: item[0], reverse=True)
        line = issues[0][1]
    else:
        line = "Assessments and resume both clear the bar"
    if declining and decline_points:
        line += ". Scores fell {:.0f} points over the last two weeks".format(decline_points)
    return line + "."


def _candidate(profile, scores, person, as_of, class_hands, class_proctored):
    ordered = sorted(scores, key=lambda row: row.week)
    recent = ordered[-config.READINESS_RECENT_WEEKS:]
    weekly = [
        {
            "week": row.week,
            "hands_on": row.hands_on,
            "proctored": row.proctored,
            "overall": (row.hands_on + row.proctored) / 2.0,
            "topic": row.topic,
        }
        for row in ordered
    ]
    recent_overalls = [(row.hands_on + row.proctored) / 2.0 for row in recent]
    assessment = _mean(recent_overalls)
    assessment_100 = assessment * 100 if assessment is not None else None
    resume = _resume_fit(profile)
    if assessment_100 is None:
        score = resume["score"]
    else:
        score = config.ASSESSMENT_WEIGHT * assessment_100 + config.RESUME_WEIGHT * resume["score"]
    declining = False
    decline_points = None
    if len(recent_overalls) >= 2 and recent_overalls[-2] - recent_overalls[-1] > config.SCORE_DECLINE_POINTS:
        declining = True
        decline_points = round((recent_overalls[-2] - recent_overalls[-1]) * 100, 1)
    latest = weekly[-1] if weekly else None
    placed, client = _placed(profile, person, as_of)
    return {
        "id": profile.id,
        "name": profile.name,
        "location": profile.location,
        "hire_source": profile.hire_source,
        "illustrative": True,
        "score": round(score, 1),
        "band": _band(score),
        "assessment": round(assessment_100, 1) if assessment_100 is not None else None,
        "resume_fit": resume["score"],
        "declining": declining,
        "decline_points": decline_points,
        "placed": placed,
        "client": client,
        "reason": _reason(latest, class_hands, class_proctored, resume["missing_skills"], declining, decline_points),
        "weeks": weekly,
        "resume": resume,
        "weights": {"assessment": config.ASSESSMENT_WEIGHT, "resume": config.RESUME_WEIGHT},
    }


def _pct(value):
    if value is None:
        return "unscored"
    return "{:.0%}".format(value)


def _pretty(iso_value):
    if not iso_value:
        return "unknown"
    return date.fromisoformat(iso_value).strftime("%-d %b %Y")


def _verdict(name, card, class_overall):
    supply = _pretty(card["supply_date"])
    if card["provisional"]:
        return (
            "{name} is in week {calendar} of {program}, with only {filed} weeks scored, "
            "so the {overall} average is provisional. {placed} of {headcount} are on a client. "
            "They become supply on {supply}."
        ).format(
            name=name,
            calendar=card["calendar_week"],
            program=card["program_weeks"],
            filed=card["filed_week"] or 0,
            overall=_pct(class_overall),
            placed=card["placed"],
            headcount=card["headcount"],
            supply=supply,
        )
    if card["filing_lag"] and card["clears_bar"]:
        return (
            "{name} clears the {bar} bar at {overall}, on a week {filed} score while the calendar is week {calendar}. "
            "{placed} of {headcount} have a client. They become supply on {supply}."
        ).format(
            name=name,
            bar=_pct(config.READINESS_FLOOR),
            overall=_pct(class_overall),
            filed=card["filed_week"],
            calendar=card["calendar_week"],
            placed=card["placed"],
            headcount=card["headcount"],
            supply=supply,
        )
    if card["calendar_week"] and card["calendar_week"] >= card["program_weeks"]:
        return (
            "{name} has finished the {program}-week academy. {ready} are deploy-ready and {placed} are already on a client. "
            "The supply date was {supply}."
        ).format(
            name=name,
            program=card["program_weeks"],
            ready=card["deploy_ready"],
            placed=card["placed"],
            supply=supply,
        )
    return (
        "{name} is at {overall} against a {bar} bar, week {calendar} of {program}. "
        "{placed} of {headcount} are on a client. Supply date {supply}."
    ).format(
        name=name,
        overall=_pct(class_overall),
        bar=_pct(config.READINESS_FLOOR),
        calendar=card["calendar_week"],
        program=card["program_weeks"],
        placed=card["placed"],
        headcount=card["headcount"],
        supply=supply,
    )


def _cohort_view(db, cohort, as_of):
    profiles = db.query(TraineeProfile).filter(TraineeProfile.cohort_id == cohort.id).order_by(TraineeProfile.name).all()
    people = {}
    person_ids = [profile.person_id for profile in profiles if profile.person_id]
    if person_ids:
        for person in db.query(Person).filter(Person.id.in_(person_ids)).all():
            people[person.id] = person
    score_rows = []
    if profiles:
        score_rows = db.query(TraineeWeekScore).filter(TraineeWeekScore.trainee_id.in_([profile.id for profile in profiles])).all()
    by_trainee = {}
    for row in score_rows:
        by_trainee.setdefault(row.trainee_id, []).append(row)
    filed_weeks = sorted({row.week for row in score_rows})
    latest_week = filed_weeks[-1] if filed_weeks else None
    latest_rows = [row for row in score_rows if row.week == latest_week] if latest_week else []
    class_hands = _mean([row.hands_on for row in latest_rows])
    class_proctored = _mean([row.proctored for row in latest_rows])
    class_overall = None
    if class_hands is not None and class_proctored is not None:
        class_overall = (class_hands + class_proctored) / 2.0

    shared_start = cohort.start_date
    if people:
        starts = {person.start_date for person in people.values()}
        shared_start = next(iter(starts)) if len(starts) == 1 else None
    calendar = _calendar_week(shared_start, as_of, cohort.program_weeks) if shared_start else None
    supply = _supply_date(shared_start, cohort.program_weeks).isoformat() if shared_start else None
    filing_lag = max(0, calendar - latest_week) if calendar is not None and latest_week is not None else None

    candidates = [
        _candidate(
            profile,
            by_trainee.get(profile.id, []),
            people.get(profile.person_id),
            as_of,
            class_hands,
            class_proctored,
        )
        for profile in profiles
    ]
    candidates.sort(key=lambda row: (-row["score"], row["name"]))
    placed = sum(1 for row in candidates if row["placed"])
    deploy_ready = sum(1 for row in candidates if row["band"] == "Deploy-ready")
    deploy_ready_unplaced = sum(1 for row in candidates if row["band"] == "Deploy-ready" and not row["placed"])
    clears = (
        class_overall is not None
        and class_overall >= config.READINESS_FLOOR
        and class_hands >= config.READINESS_FLOOR
        and class_proctored >= config.READINESS_FLOOR
    )
    provisional = latest_week is None or latest_week < config.PROVISIONAL_UNTIL_WEEK
    weeks_left = max(0, cohort.program_weeks - calendar) if calendar is not None else None
    topic = latest_rows[0].topic if latest_rows else None
    track = []
    for week in range(1, cohort.program_weeks + 1):
        week_rows = [row for row in score_rows if row.week == week]
        track.append(
            {
                "week": week,
                "filed": bool(week_rows),
                "current": calendar == week,
                "topic": week_rows[0].topic if week_rows else None,
                "overall": _mean([(row.hands_on + row.proctored) / 2.0 for row in week_rows]),
            }
        )
    card = {
        "code": cohort.code,
        "name": cohort.name,
        "source": cohort.source,
        "start_date": shared_start.isoformat() if shared_start else cohort.start_date.isoformat(),
        "program_weeks": cohort.program_weeks,
        "calendar_week": calendar,
        "filed_week": latest_week,
        "filing_lag": filing_lag,
        "weeks_left": weeks_left,
        "supply_date": supply,
        "headcount": len(profiles),
        "placed": placed,
        "deploy_ready": deploy_ready,
        "deploy_ready_unplaced": deploy_ready_unplaced,
        "clears_bar": clears,
        "provisional": provisional,
        "class_overall": class_overall,
    }
    return {
        "card": card,
        "verdict": _verdict(cohort.name, card, class_overall),
        "class_hands_on": class_hands,
        "class_proctored": class_proctored,
        "class_overall": class_overall,
        "readiness_floor": config.READINESS_FLOOR,
        "topic": topic,
        "illustrative_scores": True,
        "track": track,
        "candidates": candidates,
        "bands": {"deploy": config.BAND_DEPLOY, "coaching": config.BAND_COACHING},
    }


def _pipeline(cards):
    waiting = [card for card in cards if card["deploy_ready_unplaced"] and not card["provisional"]]
    waiting.sort(key=lambda card: card["supply_date"] or "9999")
    total = sum(card["deploy_ready_unplaced"] for card in waiting)
    parts = [
        "{} from {} by {}".format(card["deploy_ready_unplaced"], card["name"], _pretty(card["supply_date"]))
        for card in waiting
    ]
    if total and parts:
        sentence = "{} deploy-ready people still need a client: {}.".format(total, ", ".join(parts))
    else:
        sentence = "No deploy-ready people are waiting on a client."
    return {"deploy_ready_unplaced": total, "sentence": sentence}


def resume_file(db: Session, trainee_id: int):
    """A one-page PDF built from the candidate's stored resume fields."""
    profile = db.query(TraineeProfile).filter(TraineeProfile.id == trainee_id).first()
    if profile is None:
        return None
    cohort = db.query(AcademyCohort).filter(AcademyCohort.id == profile.cohort_id).first()
    return _resume_filename(profile.name), _pdf_bytes(_resume_stream(profile, cohort))


def _resume_filename(name):
    safe = "".join(ch if ch.isalnum() else "_" for ch in name).strip("_")
    while "__" in safe:
        safe = safe.replace("__", "_")
    return "{}_resume.pdf".format(safe or "candidate")


def _years_label(years):
    if years is None:
        return "Experience unreported"
    rounded = round(years)
    if abs(years - rounded) < 0.05:
        count = int(rounded)
        return "{} year{}".format(count, "" if count == 1 else "s")
    return "{:.1f} years".format(years)


def _wrap(text, width):
    words = (text or "").split()
    lines = []
    current = ""
    for word in words:
        trial = word if not current else current + " " + word
        if len(trial) > width and current:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


def _pdf_escape(text):
    cleaned = (
        (text or "")
        .replace("\u2014", "-")
        .replace("\u2013", "-")
        .replace("\u2019", "'")
        .encode("latin-1", "replace")
        .decode("latin-1")
    )
    return cleaned.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _resume_stream(profile, cohort):
    skills = _split(profile.skills)
    certs = _split(profile.certifications)
    y = [728]
    chunks = [
        "0.059 0.431 0.337 RG",
        "1.4 w",
        "72 752 m 540 752 l S",
    ]

    def text(value, size, bold, color="0 0 0"):
        font = "F2" if bold else "F1"
        chunks.append("{} rg".format(color))
        chunks.append(
            "BT /{} {} Tf 1 0 0 1 72 {} Tm ({}) Tj ET".format(font, size, y[0], _pdf_escape(value))
        )

    def section(label, body):
        text(label.upper(), 9, True, "0.059 0.431 0.337")
        y[0] -= 18
        for line in body:
            text(line, 12, False)
            y[0] -= 16
        y[0] -= 12

    text(profile.name, 22, True)
    y[0] -= 26
    meta = profile.location or ""
    if profile.hire_source:
        meta = "{}  ·  {}".format(meta, profile.hire_source).strip(" ·")
    text(meta, 11, False, "0.35 0.38 0.42")
    y[0] -= 40

    section("Education", [profile.education or "Unreported"])
    section("Experience", [_years_label(profile.years_experience)])
    section("Skills", _wrap(", ".join(skills), 78) or ["None listed"])
    if certs:
        section("Certifications", _wrap(", ".join(certs), 78))
    if cohort is not None:
        started = cohort.start_date.strftime("%-d %B %Y")
        section("Training", ["{}, started {}".format(cohort.name, started)])
    return "\n".join(chunks).encode("latin-1", "replace")


def _pdf_bytes(stream):
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
    ]
    header = b"%PDF-1.4\n"
    body = b""
    offsets = []
    cursor = len(header)
    for index, payload in enumerate(objects, start=1):
        offsets.append(cursor)
        piece = "{} 0 obj\n".format(index).encode("ascii") + payload + b"\nendobj\n"
        body += piece
        cursor += len(piece)
    xref = ["xref", "0 7", "0000000000 65535 f "]
    xref.extend("{:010d} 00000 n ".format(offset) for offset in offsets)
    trailer = "trailer\n<< /Size 7 /Root 1 0 R >>\nstartxref\n{}\n%%EOF\n".format(cursor)
    return header + body + ("\n".join(xref) + "\n").encode("ascii") + trailer.encode("ascii")


def build_academy(db: Session, as_of: date, cohort_code: Optional[str] = None) -> dict:
    cohorts = db.query(AcademyCohort).order_by(AcademyCohort.id).all()
    views = [_cohort_view(db, cohort, as_of) for cohort in cohorts]
    cards = [view["card"] for view in views]
    by_code = {view["card"]["code"]: view for view in views}
    selected_code = cohort_code if cohort_code in by_code else (cards[0]["code"] if cards else None)
    selected = by_code.get(selected_code)
    if selected:
        selected = dict(selected["card"])
        full = by_code[selected_code]
        selected.update(
            {
                "verdict": full["verdict"],
                "class_hands_on": full["class_hands_on"],
                "class_proctored": full["class_proctored"],
                "class_overall": full["class_overall"],
                "readiness_floor": full["readiness_floor"],
                "topic": full["topic"],
                "illustrative_scores": full["illustrative_scores"],
                "track": full["track"],
                "candidates": full["candidates"],
                "bands": full["bands"],
            }
        )
    return {
        "as_of": as_of.isoformat(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "pipeline": _pipeline(cards),
        "cohorts": cards,
        "selected_code": selected_code,
        "selected": selected,
        "note": (
            "Academy A names, start date, and the week-6 class average come from the workbook. "
            "Per-person scores and resumes are illustrative and anchored so that class average holds. "
            "Academies B and C are entirely illustrative."
        ),
    }
