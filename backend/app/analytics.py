"""Operations metrics.

Rules follow the Momentuum Blue workbook:

- A blank hiring count is unreported, not zero. Totals add the numbers that exist.
- In pipeline = screening, L1, Berribot, L2, L3, CTO, and offer-extended pending.
- On hold, rejects, and cumulative clears are not part of the live pipeline.
- Monthly revenue = hourly rate x hours/week x 4, for contracts active on the as-of date.
- Utilization = FDEs active at a client / joined FDEs who are not trainees.
- Ending soon = contract end within 60 days, still active.
- Available later = still in training, or not started yet.
"""

from collections import Counter
from datetime import date, datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import Person, PipelineWeek, TrainingWeek

BILLING_WEEKS = 4
ENDING_SOON_DAYS = 60
ROLES = ("Associate FDE", "FDE", "Senior FDE")
ROLE_KEYS = (
    ("Associate FDE", "associate"),
    ("FDE", "fde"),
    ("Senior FDE", "senior"),
)

PIPELINE_FIELDS = (
    "screening_pending",
    "l1_pending",
    "berribot_applied",
    "l2_pending",
    "l3_pending",
    "cto_pending",
    "offer_extended",
)

FLOW = (
    ("screening_pending", "Screening pending", False),
    ("screening_cleared", "Screening cleared", True),
    ("l1_pending", "L1 pending", False),
    ("l1_cleared", "L1 cleared", True),
    ("berribot_applied", "Berribot applied", False),
    ("berribot_cleared", "Berribot cleared", True),
    ("l2_pending", "L2 pending", False),
    ("l2_cleared", "L2 cleared", True),
    ("l3_pending", "L3 pending", False),
    ("l3_cleared", "L3 cleared", True),
    ("cto_pending", "CTO round pending", False),
    ("cto_cleared", "CTO round cleared", True),
    ("offer_extended", "Offer extended", False),
    ("offer_accepted", "Offers accepted", True),
    ("joined", "Joined", True),
)

OTHER = (
    ("applications_total", "Applications"),
    ("on_hold", "On hold"),
    ("rejected", "Rejected"),
    ("slots_needed", "Slots needed next week"),
)

BUCKET_ORDER = {
    "Active at client": 0,
    "On bench": 1,
    "Client starting soon": 2,
    "Contract ended": 3,
    "Yet to join": 4,
    "In training": 5,
}


def _iso(value: Optional[date]) -> Optional[str]:
    return value.isoformat() if value else None


def _pretty(value: Optional[date]) -> Optional[str]:
    if value is None:
        return None
    return value.strftime("%-d %b %Y")


def _money(value: Optional[float]) -> str:
    if value is None:
        return "unbilled"
    return "${:,.0f}/mo".format(value)


def _num(values: List[Optional[int]]) -> Optional[int]:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return int(sum(present))


def _field(rows: List[PipelineWeek], role: str, field: str) -> Optional[int]:
    scoped = [row for row in rows if row.role == role]
    if not scoped:
        return None
    return _num([getattr(row, field) for row in scoped])


def _across(rows: List[PipelineWeek], field: str) -> Dict[str, Optional[int]]:
    result = {}
    values = []
    for role, key in ROLE_KEYS:
        value = _field(rows, role, field)
        result[key] = value
        values.append(value)
    result["total"] = _num(values)
    return result


def _pipeline_for_role(rows: List[PipelineWeek], role: str) -> Optional[int]:
    if not any(row.role == role for row in rows):
        return None
    return _num([_field(rows, role, field) for field in PIPELINE_FIELDS])


def _pipeline_across(rows: List[PipelineWeek]) -> Dict[str, Optional[int]]:
    result = {}
    values = []
    for role, key in ROLE_KEYS:
        value = _pipeline_for_role(rows, role)
        result[key] = value
        values.append(value)
    result["total"] = _num(values)
    return result


def _stage(label: str, counts: Dict[str, Optional[int]], cumulative: bool, emphasis: bool = False):
    return {
        "label": label,
        "cumulative": cumulative,
        "emphasis": emphasis,
        "associate": counts["associate"],
        "fde": counts["fde"],
        "senior": counts["senior"],
        "total": counts["total"],
    }


def available_weeks(db: Session) -> List[date]:
    rows = (
        db.query(PipelineWeek.week_ending)
        .distinct()
        .order_by(PipelineWeek.week_ending)
        .all()
    )
    return [row[0] for row in rows]


def _pipeline_for_week(db: Session, week: Optional[date]) -> List[PipelineWeek]:
    query = db.query(PipelineWeek).order_by(PipelineWeek.id)
    if week is not None:
        query = query.filter(PipelineWeek.week_ending == week)
    return query.all()


def _monthly_revenue(person: Person) -> Optional[int]:
    if person.hourly_rate is None or person.hours_per_week is None:
        return None
    return int(round(person.hourly_rate * person.hours_per_week * BILLING_WEEKS))


def _bucket(person: Person, as_of: date) -> str:
    if person.start_date and person.start_date > as_of:
        return "Yet to join"
    contract_open = (
        person.client
        and person.client_start
        and person.client_start <= as_of
        and (person.client_end is None or person.client_end >= as_of)
    )
    if contract_open:
        return "Active at client"
    if person.client and person.client_start and person.client_start > as_of:
        return "Client starting soon"
    if person.client and person.client_end and person.client_end < as_of:
        return "Contract ended"
    if person.career_stage == "Trainee":
        return "In training"
    return "On bench"


def _issues(person: Person) -> List[str]:
    issues = []
    if person.client_start and person.start_date and person.client_start < person.start_date:
        issues.append("Client start is earlier than the Momentuum Blue start")
    if person.client and (person.hourly_rate is None or person.hours_per_week is None):
        issues.append("Client assigned but billing rate or hours missing")
    return issues


def _roster(db: Session, as_of: date) -> List[dict]:
    people = db.query(Person).order_by(Person.id).all()
    names = Counter(person.name.strip().lower() for person in people)
    roster = []
    for person in people:
        bucket = _bucket(person, as_of)
        revenue = _monthly_revenue(person)
        counts = bucket == "Active at client"
        days = None
        ending = False
        if person.client_end is not None:
            days = (person.client_end - as_of).days
            ending = counts and 0 <= days <= ENDING_SOON_DAYS
        issues = _issues(person)
        if names[person.name.strip().lower()] > 1:
            issues.append("Duplicate FDE name")
        roster.append(
            {
                "id": person.id,
                "name": person.name,
                "location": person.location,
                "career_stage": person.career_stage,
                "start_date": _iso(person.start_date),
                "source": person.source,
                "client": person.client,
                "client_start": _iso(person.client_start),
                "client_end": _iso(person.client_end),
                "hourly_rate": person.hourly_rate,
                "hours_per_week": person.hours_per_week,
                "monthly_revenue": revenue if counts else None,
                "bucket": bucket,
                "ending_soon": ending,
                "days_to_contract_end": days if person.client_end else None,
                "issues": issues,
                "available": "later" if bucket in ("In training", "Yet to join") else "now",
            }
        )
    roster.sort(key=lambda person: (not person["ending_soon"], BUCKET_ORDER.get(person["bucket"], 9), person["name"]))
    return roster


def _clients(roster: List[dict]) -> List[dict]:
    grouped = {}
    for person in roster:
        if person["bucket"] != "Active at client" or not person["client"]:
            continue
        row = grouped.setdefault(
            person["client"],
            {"client": person["client"], "active_fdes": 0, "monthly_revenue": 0, "rates": []},
        )
        row["active_fdes"] += 1
        row["monthly_revenue"] += person["monthly_revenue"] or 0
        if person["hourly_rate"] is not None:
            row["rates"].append(person["hourly_rate"])
    clients = []
    for row in grouped.values():
        rates = row.pop("rates")
        row["avg_rate"] = round(sum(rates) / len(rates), 2) if rates else None
        clients.append(row)
    clients.sort(key=lambda row: (-row["monthly_revenue"], row["client"]))
    return clients


def _locations(roster: List[dict]) -> List[dict]:
    grouped = {}
    for person in roster:
        row = grouped.setdefault(person["location"], {"location": person["location"], "now": 0, "later": 0, "total": 0})
        row[person["available"]] += 1
        row["total"] += 1
    order = {"USA": 0, "India": 1, "UK": 2, "LATAM": 3, "Canada": 4}
    return sorted(grouped.values(), key=lambda row: (order.get(row["location"], 9), row["location"]))


def _joiners(roster: List[dict]) -> List[dict]:
    dates = []
    for person in roster:
        if person["start_date"]:
            dates.append(date.fromisoformat(person["start_date"]))
    if not dates:
        return []
    start = min(dates).replace(day=1)
    end = max(dates).replace(day=1)
    counts = Counter(value.replace(day=1) for value in dates)
    months = []
    cursor = start
    while cursor <= end:
        months.append({"month": cursor.strftime("%b %Y"), "joiners": counts.get(cursor, 0)})
        if cursor.month == 12:
            cursor = cursor.replace(year=cursor.year + 1, month=1)
        else:
            cursor = cursor.replace(month=cursor.month + 1)
    return months


def _checks(roster: List[dict]) -> List[dict]:
    buckets = Counter(person["bucket"] for person in roster)
    date_mismatches = sum(
        1 for person in roster if any("earlier than" in issue for issue in person["issues"])
    )
    duplicates = sum(1 for person in roster if any("Duplicate" in issue for issue in person["issues"]))
    missing_rate = sum(
        1 for person in roster if any("billing rate" in issue for issue in person["issues"])
    )
    bucket_gap = abs(sum(buckets.values()) - len(roster))
    return [
        {"count": date_mismatches, "label": "Client start is earlier than the person's Momentuum Blue start"},
        {"count": duplicates, "label": "Duplicate FDE names"},
        {"count": missing_rate, "label": "Client assigned but billing rate or hours missing"},
        {"count": bucket_gap, "label": "Status buckets do not add up to headcount"},
    ]


def build_deployment(db: Session, as_of: date) -> dict:
    roster = _roster(db, as_of)
    clients = _clients(roster)
    active = [person for person in roster if person["bucket"] == "Active at client"]
    joined = [person for person in roster if person["bucket"] != "Yet to join"]
    joined_fdes = [person for person in joined if person["career_stage"] != "Trainee"]
    bench = [person for person in roster if person["bucket"] == "On bench"]
    ending = [person for person in roster if person["ending_soon"]]
    rates = [person["hourly_rate"] for person in active if person["hourly_rate"] is not None]
    monthly = sum(person["monthly_revenue"] or 0 for person in active)
    revenue_at_risk = sum(person["monthly_revenue"] or 0 for person in ending)
    utilization = (len(active) / len(joined_fdes)) if joined_fdes else None
    return {
        "as_of": _iso(as_of),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "headcount": len(roster),
        "joined": len(joined),
        "yet_to_join": sum(1 for person in roster if person["bucket"] == "Yet to join"),
        "active_at_client": len(active),
        "on_bench": len(bench),
        "in_training": sum(1 for person in roster if person["bucket"] == "In training"),
        "starting_soon": sum(1 for person in roster if person["bucket"] == "Client starting soon"),
        "joined_fdes": len(joined_fdes),
        "utilization": utilization,
        "monthly_revenue": monthly,
        "annualized_revenue": monthly * 12,
        "avg_rate": round(sum(rates) / len(rates), 2) if rates else None,
        "contracts_ending_soon": len(ending),
        "revenue_at_risk": revenue_at_risk,
        "available_now": sum(1 for person in roster if person["available"] == "now"),
        "available_later": sum(1 for person in roster if person["available"] == "later"),
        "clients": clients,
        "locations": _locations(roster),
        "joiners_by_month": _joiners(roster),
        "checks": _checks(roster),
        "checks_flagged": sum(1 for check in _checks(roster) if check["count"]),
        "roster": roster,
    }


def _training_checks(weeks: List[TrainingWeek]) -> List[dict]:
    mismatch = 0
    score_without_students = 0
    partial = 0
    for week in weeks:
        if week.hands_on is not None and week.proctored is not None and week.overall is not None:
            average = (week.hands_on + week.proctored) / 2
            if abs(week.overall - average) > 0.01 + 1e-9:
                mismatch += 1
        if week.overall is not None and week.active_students is None:
            score_without_students += 1
        if week.overall is None and (week.hands_on is not None or week.proctored is not None):
            partial += 1
    week_numbers = [week.week for week in weeks]
    duplicates = len(week_numbers) - len(set(week_numbers))
    return [
        {"count": mismatch, "label": "Weeks where overall differs from the hands-on and proctored average by more than 1 point"},
        {"count": score_without_students, "label": "Weeks with a score but no active-student count"},
        {"count": duplicates, "label": "Duplicate week numbers"},
        {"count": partial, "label": "Weeks with a component score but no overall average"},
    ]


def build_cohort(db: Session, as_of: date) -> dict:
    stored = db.query(TrainingWeek).order_by(TrainingWeek.week).all()
    by_week = {week.week: week for week in stored}
    last_number = max(by_week) if by_week else 12
    upper = max(12, last_number)
    series = []
    for number in range(1, upper + 1):
        week = by_week.get(number)
        series.append(
            {
                "week": number,
                "hands_on": week.hands_on if week else None,
                "proctored": week.proctored if week else None,
                "overall": week.overall if week else None,
                "active_students": week.active_students if week else None,
                "topic": week.topic if week else None,
                "reported": bool(week and week.overall is not None),
            }
        )
    reported = [week for week in series if week["reported"]]
    latest = reported[-1] if reported else None
    previous = reported[-2] if len(reported) > 1 else None
    with_students = [week for week in series if week["active_students"] is not None]
    change = None
    if latest and previous and latest["overall"] is not None and previous["overall"] is not None:
        change = latest["overall"] - previous["overall"]
    overalls = [week["overall"] for week in reported if week["overall"] is not None]
    best = max(reported, key=lambda week: week["overall"]) if reported else None
    lowest = min(reported, key=lambda week: week["overall"]) if reported else None
    student_delta = None
    if with_students:
        student_delta = with_students[-1]["active_students"] - with_students[0]["active_students"]

    trainees = [
        person
        for person in _roster(db, as_of)
        if person["career_stage"] == "Trainee"
    ]
    trainees.sort(key=lambda person: person["name"])
    location_counts = Counter(person["location"] for person in trainees)
    source_counts = Counter(person["source"] or "Unspecified" for person in trainees)
    start_counts = Counter(person["start_date"] for person in trainees)

    return {
        "as_of": _iso(as_of),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "latest": latest,
        "previous_week": previous["week"] if previous else None,
        "change_vs_previous": change,
        "average_overall": (sum(overalls) / len(overalls)) if overalls else None,
        "best_week": best,
        "lowest_week": lowest,
        "weeks_reported": len(reported),
        "students_vs_first_week": student_delta,
        "weeks": series,
        "trainees": trainees,
        "trainee_summary": {
            "count": len(trainees),
            "locations": [{"name": name, "count": count} for name, count in location_counts.most_common()],
            "sources": [{"name": name, "count": count} for name, count in source_counts.most_common()],
            "start_dates": [{"date": name, "count": count} for name, count in start_counts.most_common()],
        },
        "checks": _training_checks(stored),
    }


def _cohort_block(name: str, rows: List[PipelineWeek]) -> dict:
    flow = []
    for field, label, cumulative in FLOW:
        flow.append(_stage(label, _across(rows, field), cumulative))
    other = []
    for field, label in OTHER:
        other.append(_stage(label, _across(rows, field), False, emphasis=(field == "slots_needed")))
    notes = [
        {"role": row.role, "source": row.source, "text": row.notes}
        for row in rows
        if row.notes
    ]
    summary_fields = {
        "in_pipeline": _pipeline_across(rows)["total"],
        "in_cto": _across(rows, "cto_pending")["total"],
        "offers_accepted": _across(rows, "offer_accepted")["total"],
        "joined": _across(rows, "joined")["total"],
        "rejected": _across(rows, "rejected")["total"],
        "slots_needed": _across(rows, "slots_needed")["total"],
        "on_hold": _across(rows, "on_hold")["total"],
    }
    return {"name": name, "summary": summary_fields, "flow": flow, "other": other, "notes": notes}


def _pressure(rows: List[PipelineWeek]) -> dict:
    slots = _across(rows, "slots_needed")
    waiting = _across(rows, "l2_pending")
    slots_total = slots["total"] or 0
    waiting_total = waiting["total"] or 0
    ranked = max(ROLE_KEYS, key=lambda item: slots[item[1]] or 0)
    role_name, role_key = ranked
    return {
        "slots_needed": slots["total"],
        "l2_pending": waiting["total"],
        "headline": "{} interview slots needed next week".format(slots_total),
        "detail": (
            "{} candidates are already waiting on L2. {} accounts for {} of those slots, "
            "with {} people in that round."
        ).format(waiting_total, role_name, slots[role_key] or 0, waiting[role_key] or 0),
    }


def build_recruitment(db: Session, week: Optional[date], as_of: date) -> dict:
    weeks = available_weeks(db)
    selected = week or (weeks[-1] if weeks else None)
    rows = _pipeline_for_week(db, selected) if selected else []
    names = sorted({row.cohort for row in rows})
    return {
        "as_of": _iso(as_of),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "weeks": [_iso(value) for value in weeks],
        "week_ending": _iso(selected),
        "pressure": _pressure(rows) if rows else None,
        "cohorts": [_cohort_block(name, [row for row in rows if row.cohort == name]) for name in names],
    }


def _alerts(hiring: dict, deployment: dict) -> List[dict]:
    alerts = []
    pressure = hiring.get("pressure")
    if pressure and (pressure["slots_needed"] or 0) and (pressure["l2_pending"] or 0):
        alerts.append(
            {
                "tone": "warning",
                "title": "L2 is the bottleneck",
                "body": "{}. {}".format(pressure["headline"][:1].upper() + pressure["headline"][1:], pressure["detail"]),
            }
        )
    ending = [person for person in deployment["roster"] if person["ending_soon"]]
    ending.sort(key=lambda person: person["days_to_contract_end"])
    for person in ending:
        tone = "danger" if person["days_to_contract_end"] <= 14 else "warning"
        alerts.append(
            {
                "tone": tone,
                "title": "{} ends {}".format(person["client"], _pretty(date.fromisoformat(person["client_end"]))),
                "body": "{} ({}) comes off the run-rate in {} days. {}".format(
                    person["name"],
                    person["career_stage"],
                    person["days_to_contract_end"],
                    _money(person["monthly_revenue"]),
                ),
            }
        )
    bench = [person for person in deployment["roster"] if person["bucket"] == "On bench"]
    if bench:
        alerts.append(
            {
                "tone": "warning",
                "title": "{} joined FDEs on the bench".format(len(bench)),
                "body": "{} have started, are not in the academy, and have no client.".format(_join_names(bench)),
            }
        )
    for person in deployment["roster"]:
        if any("earlier than" in issue for issue in person["issues"]):
            alerts.append(
                {
                    "tone": "danger",
                    "title": "Roster date to fix",
                    "body": "{}'s {} contract starts {}, before the Momentuum Blue start on {}.".format(
                        person["name"],
                        person["client"],
                        _pretty(date.fromisoformat(person["client_start"])),
                        _pretty(date.fromisoformat(person["start_date"])),
                    ),
                }
            )
    joined_blank = hiring.get("offers_accepted") is not None and all(
        cohort["summary"]["joined"] is None for cohort in hiring.get("cohorts", [])
    )
    if joined_blank and hiring.get("cohorts"):
        alerts.append(
            {
                "tone": "info",
                "title": "Joined counts are unreported",
                "body": "The hiring sheet has offers accepted, and the cumulative joined column is still blank.",
            }
        )
    return alerts


def build_executive(db: Session, as_of: date, week: Optional[date]) -> dict:
    recruitment = build_recruitment(db, week, as_of)
    deployment = build_deployment(db, as_of)
    cohort = build_cohort(db, as_of)
    rows = []
    selected = date.fromisoformat(recruitment["week_ending"]) if recruitment["week_ending"] else None
    if selected:
        rows = _pipeline_for_week(db, selected)
    funnel = []
    if rows:
        funnel.append(_stage("In pipeline now", _pipeline_across(rows), False, True))
        for field, label in (
            ("l1_cleared", "L1 cleared"),
            ("berribot_cleared", "Berribot cleared"),
            ("l2_cleared", "L2 cleared"),
            ("l3_cleared", "L3 cleared"),
        ):
            funnel.append(_stage(label, _across(rows, field), True))
        funnel.append(_stage("In CTO round", _across(rows, "cto_pending"), False))
        funnel.append(_stage("Offers accepted", _across(rows, "offer_accepted"), True))
        funnel.append(_stage("Joined till date", _across(rows, "joined"), True))
        funnel.append(_stage("Slots needed next week", _across(rows, "slots_needed"), False, True))

    latest = cohort["latest"] or {}
    offers = _across(rows, "offer_accepted")["total"] if rows else None
    in_cto = _across(rows, "cto_pending")["total"] if rows else None
    hiring_for_alerts = {
        "pressure": recruitment["pressure"],
        "offers_accepted": offers,
        "cohorts": recruitment["cohorts"],
    }
    return {
        "as_of": _iso(as_of),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "week_ending": recruitment["week_ending"],
        "kpis": {
            "offers_accepted": offers,
            "in_cto": in_cto,
            "slots_needed": _across(rows, "slots_needed")["total"] if rows else None,
            "training_average": latest.get("overall"),
            "training_week": latest.get("week"),
            "active_students": latest.get("active_students"),
            "training_topic": latest.get("topic"),
            "active_at_client": deployment["active_at_client"],
            "headcount": deployment["headcount"],
            "utilization": deployment["utilization"],
            "monthly_revenue": deployment["monthly_revenue"],
            "annualized_revenue": deployment["annualized_revenue"],
            "on_bench": deployment["on_bench"],
            "contracts_ending_soon": deployment["contracts_ending_soon"],
            "revenue_at_risk": deployment["revenue_at_risk"],
        },
        "funnel": funnel,
        "clients": deployment["clients"],
        "locations": deployment["locations"],
        "available_now": deployment["available_now"],
        "available_later": deployment["available_later"],
        "alerts": _alerts(hiring_for_alerts, deployment),
    }


def _join_names(people: List[dict]) -> str:
    names = [person["name"] for person in people]
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return "{} and {}".format(names[0], names[1])
    return "{}, and {}".format(", ".join(names[:-1]), names[-1])
