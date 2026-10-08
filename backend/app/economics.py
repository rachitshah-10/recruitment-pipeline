"""Economics metrics: resource burn, hiring economics, revenue at risk.

Layers:
- Raw data: pipeline_weeks, training_weeks, people (workbook) plus
  resource_rates and demand_forecast (assumption / demo tables).
- compute(): turns raw rows into plain metric dicts. Both the Economics
  page and the recommendation engine read from it.
- build_economics(): shapes compute() for the Economics page.

Counting rules:
- Hiring counts are weekly snapshots, so a date range uses the latest
  week inside the range. Weeks are never summed.
- A blank hiring count is unreported, not zero.
- basis="inferred": someone counted at a later stage must have passed the
  earlier ones, so earlier stages are at least as large as later ones.
  Those values are tagged "inferred". basis="reported" uses typed counts only.
- Rejected and on-hold totals have no stage on the sheet, so stage volumes
  (and the hours built on them) are lower bounds.
"""

import math
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from statistics import mean, median
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app import config
from app.analytics import BILLING_WEEKS, _roster, available_weeks
from app.models import DemandForecast, Person, PipelineWeek, ResourceRate, TrainingWeek

PHASES = ("recruitment", "training", "deployment")

# stage code, label, pending field, cleared field
CHAIN = (
    ("screening", "Screening", "screening_pending", "screening_cleared"),
    ("l1", "L1 interview", "l1_pending", "l1_cleared"),
    ("berribot", "Assessment (Berribot)", "berribot_applied", "berribot_cleared"),
    ("l2", "L2 interview", "l2_pending", "l2_cleared"),
    ("l3", "L3 interview", "l3_pending", "l3_cleared"),
    ("cto", "CTO interview", "cto_pending", "cto_cleared"),
    ("offers", "Offer", "offer_extended", "offer_accepted"),
)
STAGE_FIELDS = (
    "applications_total", "screening_pending", "screening_cleared", "l1_pending", "l1_cleared",
    "berribot_applied", "berribot_cleared", "l2_pending", "l2_cleared", "l3_pending", "l3_cleared",
    "cto_pending", "cto_cleared", "offer_extended", "offer_accepted", "joined", "on_hold", "rejected",
    "slots_needed",
)
DRIVER_LABELS = {
    "applications": "applications",
    "screening": "candidates screened",
    "l1": "L1 candidates",
    "berribot": "assessments",
    "l2": "L2 candidates",
    "l3": "L3 candidates",
    "cto": "CTO candidates",
    "offers": "offers",
    "accepted": "accepted offers",
    "academy_weeks": "academy weeks",
    "trainee_weeks": "trainee-weeks",
    "deployments": "client starts",
}
STAGE_GROUPS = {
    "applicant": "Sourcing & screening",
    "interview": "Interviews & assessment",
    "offer": "Offers",
    "accepted": "Acceptance checks",
    "training": "Training",
    "deployment": "Deployment onboarding",
}
PIPELINE_DRIVERS = ("applications", "screening", "l1", "berribot", "l2", "l3", "cto", "offers", "accepted")


@dataclass
class Filters:
    start: Optional[date] = None
    end: Optional[date] = None
    phase: Optional[str] = None
    role: Optional[str] = None
    location: Optional[str] = None
    cohort: Optional[str] = None
    basis: str = "inferred"

    def as_json(self) -> dict:
        data = asdict(self)
        data["start"] = self.start.isoformat() if self.start else None
        data["end"] = self.end.isoformat() if self.end else None
        return data


# ---------------------------------------------------------------- helpers


def _sum(values) -> Optional[float]:
    present = [value for value in values if value is not None]
    return sum(present) if present else None


def _div(top: Optional[float], bottom: Optional[float]) -> Optional[float]:
    if top is None or not bottom:
        return None
    return top / bottom


def _r(value: Optional[float], digits: int = 2) -> Optional[float]:
    return None if value is None else round(value, digits)


def _overlap_weeks(start: date, end: date, window_start: Optional[date], window_end: date) -> float:
    lo = max(start, window_start) if window_start else start
    hi = min(end, window_end)
    return max(0, (hi - lo).days) / 7.0


def _money(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    if abs(value) >= 1000:
        return "${:,.1f}K".format(value / 1000.0)
    return "${:,.0f}".format(value)


def risk_level(revenue: Optional[float], days: Optional[int]) -> dict:
    """HIGH needs both money and urgency; MEDIUM needs either; else LOW."""
    big = revenue is not None and revenue >= config.RISK_HIGH_REVENUE
    moderate = revenue is not None and revenue >= config.RISK_MEDIUM_REVENUE
    soon = days is not None and days <= config.RISK_HIGH_DAYS
    near = days is not None and days <= config.RISK_MEDIUM_DAYS
    if big and soon:
        level = "HIGH"
    elif moderate or near:
        level = "MEDIUM"
    else:
        level = "LOW"
    reason = "revenue {} (high >= {}, medium >= {}); {} (high <= {}d, medium <= {}d)".format(
        _money(revenue) if revenue is not None else "not calculable",
        _money(config.RISK_HIGH_REVENUE),
        _money(config.RISK_MEDIUM_REVENUE),
        "now" if days == 0 else ("{} days away".format(days) if days is not None else "no date"),
        config.RISK_HIGH_DAYS,
        config.RISK_MEDIUM_DAYS,
    )
    return {"level": level, "reason": reason}


# ---------------------------------------------------------------- raw data


def _pipeline_rows(db: Session, filters: Filters) -> (Optional[date], List[PipelineWeek]):
    weeks = [w for w in available_weeks(db) if w <= filters.end and (filters.start is None or w >= filters.start)]
    if not weeks:
        return None, []
    week = weeks[-1]
    query = db.query(PipelineWeek).filter(PipelineWeek.week_ending == week)
    if filters.cohort:
        query = query.filter(PipelineWeek.cohort == filters.cohort)
    if filters.role:
        query = query.filter(PipelineWeek.role == filters.role)
    return week, query.order_by(PipelineWeek.id).all()


def _row_volumes(row: PipelineWeek, basis: str) -> Dict[str, dict]:
    """Per-stage volumes for one hiring row."""
    out = {}
    downstream = None
    for code, _label, pending_field, cleared_field in reversed(CHAIN):
        pending = getattr(row, pending_field)
        cleared = getattr(row, cleared_field)
        reported = pending is not None or cleared is not None
        if basis == "reported":
            if not reported:
                out[code] = None
                continue
            out[code] = {
                "waiting": pending,
                "passed": cleared,
                "entered": (pending or 0) + (cleared or 0),
                "origin": "workbook",
            }
            continue
        options = [value for value in (cleared, downstream) if value is not None]
        passed = max(options) if options else None
        if pending is None and passed is None:
            out[code] = None
            continue
        inferred = downstream is not None and (cleared is None or downstream > cleared)
        entered = (pending or 0) + (passed or 0)
        out[code] = {
            "waiting": pending,
            "passed": passed,
            "entered": entered,
            "origin": "inferred" if inferred else "workbook",
        }
        downstream = entered
    apps = row.applications_total
    if basis == "reported" or downstream is None:
        out["applications"] = None if apps is None else {"entered": apps, "waiting": None, "passed": None, "origin": "workbook"}
    else:
        value = max(apps or 0, downstream)
        out["applications"] = {
            "entered": value,
            "waiting": None,
            "passed": downstream,
            "origin": "workbook" if apps is not None and apps >= downstream else "inferred",
        }
    accepted = row.offer_accepted
    out["accepted"] = None if accepted is None else {"entered": accepted, "waiting": None, "passed": None, "origin": "workbook"}
    return out


def _filter_roster(roster: List[dict], filters: Filters) -> List[dict]:
    rows = roster
    if filters.location:
        rows = [p for p in rows if p["location"] == filters.location]
    if filters.role:
        rows = [p for p in rows if p["career_stage"] == filters.role]
    return rows


def _academies(trainees: List[dict]) -> List[dict]:
    groups: Dict[str, List[dict]] = {}
    for person in trainees:
        if person["start_date"]:
            groups.setdefault(person["start_date"], []).append(person)
    academies = []
    for start_iso, people in sorted(groups.items()):
        start = date.fromisoformat(start_iso)
        academies.append(
            {
                "start": start,
                "end": start + timedelta(weeks=config.TRAINING_PROGRAM_WEEKS),
                "people": people,
            }
        )
    return academies


# ---------------------------------------------------------------- compute


def compute(db: Session, filters: Filters) -> dict:
    as_of = filters.end
    week, rows = _pipeline_rows(db, filters)
    full_roster = _roster(db, as_of)
    roster = _filter_roster(full_roster, filters)
    rates = db.query(ResourceRate).order_by(ResourceRate.sort_order, ResourceRate.id).all()
    notes = []
    if filters.location:
        notes.append("The hiring sheet has no location, so the location filter does not narrow recruitment counts.")
    if filters.cohort:
        notes.append("The roster has no cohort column, so the cohort filter only narrows recruitment counts.")
    if week is None:
        notes.append("No hiring week falls inside the selected date range.")

    # Recruitment volumes, per row and summed.
    row_volumes = [(row, _row_volumes(row, filters.basis)) for row in rows]
    volumes: Dict[str, dict] = {}
    for driver in PIPELINE_DRIVERS:
        parts = [vol[driver] for _row, vol in row_volumes if vol.get(driver)]
        if not parts:
            volumes[driver] = {"value": None, "waiting": None, "passed": None, "origin": None}
            continue
        origins = {part["origin"] for part in parts}
        volumes[driver] = {
            "value": sum(part["entered"] for part in parts),
            "waiting": _sum(part["waiting"] for part in parts),
            "passed": _sum(part["passed"] for part in parts),
            "origin": "inferred" if "inferred" in origins else "workbook",
        }

    # Training volumes.
    include_trainees = filters.role in (None, "Trainee")
    trainees = [p for p in roster if p["career_stage"] == "Trainee"] if include_trainees else []
    academies = _academies(trainees)
    window_start = filters.start
    academy_weeks = 0.0
    trainee_weeks = 0.0
    trainee_records = []
    for academy in academies:
        weeks_in = _overlap_weeks(academy["start"], academy["end"], window_start, as_of)
        academy_weeks += weeks_in
        for person in academy["people"]:
            trainee_weeks += weeks_in
            trainee_records.append(
                {"name": person["name"], "location": person["location"], "start_date": person["start_date"],
                 "academy_ends": academy["end"].isoformat(), "weeks_in_range": round(weeks_in, 1)}
            )
    volumes["academy_weeks"] = {"value": round(academy_weeks, 2) if academies else None, "origin": "inferred" if academies else None,
                                "waiting": None, "passed": None}
    volumes["trainee_weeks"] = {"value": round(trainee_weeks, 2) if academies else None, "origin": "inferred" if academies else None,
                                "waiting": None, "passed": None}

    # Deployments started in range.
    deployments = [
        p for p in roster
        if p["client_start"]
        and date.fromisoformat(p["client_start"]) <= as_of
        and (filters.start is None or date.fromisoformat(p["client_start"]) >= filters.start)
    ]
    volumes["deployments"] = {"value": len(deployments), "origin": "workbook", "waiting": None, "passed": None}

    # Activities.
    activities = []
    for rate in rates:
        vol = volumes.get(rate.driver, {"value": None, "origin": None})
        units = vol["value"]
        hours = None
        cost = None
        if rate.cost_type == "internal":
            if units is not None and rate.hours_per_unit is not None:
                hours = units * rate.hours_per_unit
                if rate.hourly_cost_usd is not None:
                    cost = hours * rate.hourly_cost_usd
        elif units is not None and rate.unit_cost_usd is not None:
            cost = units * rate.unit_cost_usd
        activities.append(
            {
                "code": rate.code,
                "label": rate.label,
                "phase": rate.phase,
                "stage": rate.stage,
                "stage_group": STAGE_GROUPS.get(rate.stage, rate.stage),
                "driver": rate.driver,
                "driver_label": DRIVER_LABELS.get(rate.driver, rate.driver),
                "cost_type": rate.cost_type,
                "resource_role": rate.resource_role,
                "units": _r(units, 2),
                "units_origin": vol.get("origin"),
                "waiting": vol.get("waiting"),
                "passed": vol.get("passed"),
                "hours": _r(hours, 1),
                "cost": _r(cost, 0),
                "hours_per_unit": rate.hours_per_unit,
                "hourly_cost_usd": rate.hourly_cost_usd,
                "unit_cost_usd": rate.unit_cost_usd,
                "weekly_capacity_units": rate.weekly_capacity_units,
                "is_placeholder": bool(rate.is_placeholder),
                "notes": rate.notes,
            }
        )

    # Per-row recruitment cost (for source and cohort comparisons).
    rate_by_driver: Dict[str, List[ResourceRate]] = {}
    for rate in rates:
        if rate.phase == "recruitment":
            rate_by_driver.setdefault(rate.driver, []).append(rate)
    row_costs = []
    for row, vol in row_volumes:
        cost = 0.0
        hours = 0.0
        for driver, driver_rates in rate_by_driver.items():
            part = vol.get(driver)
            if not part:
                continue
            for rate in driver_rates:
                if rate.cost_type == "internal" and rate.hours_per_unit is not None:
                    h = part["entered"] * rate.hours_per_unit
                    hours += h
                    cost += h * (rate.hourly_cost_usd or 0)
                elif rate.unit_cost_usd is not None:
                    cost += part["entered"] * rate.unit_cost_usd
        row_costs.append(
            {
                "id": row.id,
                "cohort": row.cohort,
                "role": row.role,
                "source": row.source or "Unspecified",
                "applications": row.applications_total,
                "accepted": row.offer_accepted,
                "rejected": row.rejected,
                "on_hold": row.on_hold,
                "waiting": _sum(getattr(row, field) for _c, _l, field, _x in CHAIN),
                "hours": round(hours, 1),
                "cost": round(cost, 0),
            }
        )

    # Stage queues for the bottleneck rule.
    capacity_by_stage = {
        rate.driver: rate for rate in rates if rate.cost_type == "internal" and rate.weekly_capacity_units is not None
    }
    queues = []
    for code, label, pending_field, cleared_field in CHAIN:
        waiting = _sum(getattr(row, pending_field) for row in rows)
        if waiting is None:
            continue
        rate = capacity_by_stage.get(code)
        queues.append(
            {
                "code": code,
                "label": label,
                "waiting": int(waiting),
                "passed": _sum(getattr(row, cleared_field) for row in rows),
                "by_row": [
                    {"cohort": row.cohort, "role": row.role, "waiting": getattr(row, pending_field)}
                    for row in rows if getattr(row, pending_field)
                ],
                "hours_per_unit": rate.hours_per_unit if rate else None,
                "weekly_capacity_units": rate.weekly_capacity_units if rate else None,
                "rate_is_placeholder": bool(rate.is_placeholder) if rate else None,
            }
        )
    slots_needed = _sum(row.slots_needed for row in rows)

    revenue = _revenue(db, filters, full_roster, roster, as_of)

    return {
        "as_of": as_of,
        "week": week,
        "rows": rows,
        "row_volumes": row_volumes,
        "row_costs": row_costs,
        "roster": roster,
        "full_roster": full_roster,
        "volumes": volumes,
        "activities": activities,
        "trainees": trainees,
        "trainee_records": trainee_records,
        "academies": academies,
        "deployments": deployments,
        "queues": queues,
        "slots_needed": slots_needed,
        "revenue": revenue,
        "rates": rates,
        "notes": notes,
        "training": _training(db),
        "sources": _sources(roster, row_costs, as_of),
    }


def _training(db: Session) -> dict:
    weeks = db.query(TrainingWeek).order_by(TrainingWeek.week).all()
    scored = [w for w in weeks if w.overall is not None]
    latest = scored[-1] if scored else None
    history = [{"week": w.week, "overall": w.overall, "hands_on": w.hands_on, "proctored": w.proctored,
                "active_students": w.active_students} for w in scored]
    declining = 0
    for prev, cur in zip(scored, scored[1:]):
        declining = declining + 1 if cur.overall < prev.overall else 0
    return {
        "weeks_total": len(weeks),
        "weeks_scored": len(scored),
        "latest": history[-1] if history else None,
        "previous": history[-2] if len(history) > 1 else None,
        "average": mean([w.overall for w in scored]) if scored else None,
        "declining_weeks": declining,
        "history": history,
        "topic": latest.topic if latest else None,
    }


def _sources(roster: List[dict], row_costs: List[dict], as_of: date) -> List[dict]:
    """Internal vs external: deployment speed from the roster, hiring yield from the sheet."""
    groups: Dict[str, dict] = {}
    for person in roster:
        if person["bucket"] == "Yet to join":
            continue
        source = person["source"] or "Unspecified"
        group = groups.setdefault(source, {"source": source, "joined": 0, "deployed": 0, "days": [], "trainees": 0})
        group["joined"] += 1
        if person["career_stage"] == "Trainee":
            group["trainees"] += 1
        if person["client_start"] and date.fromisoformat(person["client_start"]) <= as_of:
            group["deployed"] += 1
            if person["start_date"]:
                days = (date.fromisoformat(person["client_start"]) - date.fromisoformat(person["start_date"])).days
                group["days"].append(max(0, days))
    for row in row_costs:
        group = groups.setdefault(row["source"], {"source": row["source"], "joined": 0, "deployed": 0, "days": [], "trainees": 0})
        for key in ("applications", "accepted", "rejected"):
            if row[key] is not None:
                group[key] = group.get(key, 0) + row[key]
        group["recruitment_cost"] = group.get("recruitment_cost", 0) + row["cost"]
    out = []
    for group in groups.values():
        days = group.pop("days")
        group["deployment_rate"] = _r(_div(group["deployed"], group["joined"]), 3)
        group["avg_days_to_deploy"] = _r(mean(days), 1) if days else None
        group["academy_share"] = _r(_div(group["trainees"], group["joined"]), 3)
        group.setdefault("applications", None)
        group.setdefault("accepted", None)
        group.setdefault("rejected", None)
        group.setdefault("recruitment_cost", None)
        group["cost_per_hire"] = _r(_div(group["recruitment_cost"], group["accepted"]), 0)
        group["reject_share"] = _r(_div(group["rejected"], group["applications"]), 3)
        out.append(group)
    out.sort(key=lambda g: g["source"])
    return out


# ---------------------------------------------------------------- revenue


def _role_rates(full_roster: List[dict]) -> Dict[str, float]:
    by_role: Dict[str, List[float]] = {}
    for person in full_roster:
        if person["bucket"] == "Active at client" and person["hourly_rate"] is not None:
            by_role.setdefault(person["career_stage"], []).append(person["hourly_rate"])
    return {role: mean(values) for role, values in by_role.items()}


def _standard_hours(full_roster: List[dict]) -> float:
    hours = [p["hours_per_week"] for p in full_roster if p["bucket"] == "Active at client" and p["hours_per_week"]]
    return median(hours) if hours else 40.0


def _potential(person: dict, role: str, role_rates: Dict[str, float], hours: float) -> (Optional[float], str):
    if person.get("hourly_rate") is not None and person.get("hours_per_week") is not None:
        return person["hourly_rate"] * person["hours_per_week"] * BILLING_WEEKS, "own billing rate"
    rate = role_rates.get(role)
    if rate is None:
        return None, "no billing rate for {} in data".format(role)
    return rate * hours * BILLING_WEEKS, "average active {} rate ${:.0f}/h x {:.0f}h x {}".format(role, rate, hours, BILLING_WEEKS)


def _revenue(db: Session, filters: Filters, full_roster: List[dict], roster: List[dict], as_of: date) -> dict:
    role_rates = _role_rates(full_roster)
    hours = _standard_hours(full_roster)
    active = [p for p in roster if p["bucket"] == "Active at client"]
    monthly = sum(p["monthly_revenue"] or 0 for p in active)

    ending = []
    for p in active:
        days = p["days_to_contract_end"]
        if days is not None and 0 <= days <= config.CONTRACT_WARNING_DAYS:
            ending.append({**_person(p), "days": days, "revenue": p["monthly_revenue"], "client_end": p["client_end"],
                           "risk": risk_level(p["monthly_revenue"], days)})
    ending.sort(key=lambda p: p["days"])

    bench = []
    for p in roster:
        if p["bucket"] not in ("On bench", "Contract ended"):
            continue
        since = date.fromisoformat(p["start_date"]) if p["start_date"] else as_of
        if p["client_end"] and date.fromisoformat(p["client_end"]) < as_of:
            since = max(since, date.fromisoformat(p["client_end"]))
        value, basis = _potential(p, p["career_stage"], role_rates, hours)
        bench.append({**_person(p), "days_on_bench": (as_of - since).days, "revenue": _r(value, 0), "revenue_basis": basis,
                      "bench_since": since.isoformat()})
    bench.sort(key=lambda p: -p["days_on_bench"])

    delayed = []
    for p in roster:
        if p["client"]:
            continue
        if p["bucket"] == "Yet to join" and p["career_stage"] != "Trainee":
            days = (date.fromisoformat(p["start_date"]) - as_of).days
            role = p["career_stage"]
            event = "joins {}".format(p["start_date"])
        elif p["career_stage"] == "Trainee" and p["start_date"]:
            graduation = date.fromisoformat(p["start_date"]) + timedelta(weeks=config.TRAINING_PROGRAM_WEEKS)
            days = (graduation - as_of).days
            role = config.TRAINEE_GRADUATES_AS
            event = "graduates {}".format(graduation.isoformat())
        else:
            continue
        if days > config.DELAYED_DEPLOYMENT_DAYS:
            continue
        value, basis = _potential(p, role, role_rates, hours)
        delayed.append({**_person(p), "days": max(days, 0), "event": event, "deploys_as": role,
                        "revenue": _r(value, 0), "revenue_basis": basis})
    delayed.sort(key=lambda p: p["days"])

    capacity = _capacity(db, filters, full_roster, as_of)

    def _total(items, key="revenue"):
        values = [item[key] for item in items if item.get(key) is not None]
        return sum(values) if values else None

    sources = []
    if ending:
        value = _total(ending)
        days = min(p["days"] for p in ending)
        sources.append({"key": "contracts", "label": "Contracts ending soon", "fdes": len(ending), "revenue": value,
                        "days": days, "basis": "Active contracts ending within {} days (workbook rates)".format(config.CONTRACT_WARNING_DAYS),
                        "origin": "workbook", "calculable": value is not None, **risk_level(value, days)})
    if bench:
        value = _total(bench)
        sources.append({"key": "bench", "label": "Bench (unassigned FDEs)", "fdes": len(bench), "revenue": value, "days": 0,
                        "basis": "Joined, not in training, no active client. Revenue estimated at average active rate for role.",
                        "origin": "inferred", "calculable": value is not None, **risk_level(value, 0)})
    if capacity["gap_fdes"]:
        open_rows = [row for row in capacity["rows"] if row["gap"]]
        value = sum(row["revenue_exposure"] or 0 for row in open_rows) or None
        days = min(row["days"] for row in open_rows)
        sources.append({"key": "capacity", "label": "Capacity shortage (unfilled demand)", "fdes": capacity["gap_fdes"],
                        "revenue": value, "days": max(days, 0),
                        "basis": "Demand forecast minus projected available FDEs (demand table is demo data).",
                        "origin": "demo", "calculable": value is not None, **risk_level(value, max(days, 0))})
    if delayed:
        value = _total(delayed)
        days = min(p["days"] for p in delayed)
        missing = sum(1 for p in delayed if p["revenue"] is None)
        sources.append({"key": "delayed", "label": "Delayed deployment (no client lined up)", "fdes": len(delayed),
                        "revenue": value, "days": days,
                        "basis": "Joining or graduating within {} days with no client. {}".format(
                            config.DELAYED_DEPLOYMENT_DAYS,
                            "{} of {} have no billing rate for their role, so revenue covers only the rest.".format(missing, len(delayed))
                            if missing else "Revenue estimated at average active rate for role."),
                        "origin": "inferred", "calculable": value is not None, **risk_level(value, days)})
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    sources.sort(key=lambda s: (order[s["level"]], -(s["revenue"] or 0)))

    calculable = [s["revenue"] for s in sources if s["revenue"] is not None]
    return {
        "monthly_revenue": monthly,
        "active_fdes": len(active),
        "revenue_at_risk": _total(ending) or 0,
        "total_at_risk": sum(calculable) if calculable else None,
        "existing_at_risk": _total(ending) or 0,
        "bench_revenue": _total(bench),
        "contracts_revenue": _total(ending),
        "capacity_revenue": next((s["revenue"] for s in sources if s["key"] == "capacity"), None),
        "delayed_revenue": _total(delayed),
        "role_rates": {role: round(rate, 2) for role, rate in role_rates.items()},
        "standard_hours": hours,
        "sources": sources,
        "contracts": ending,
        "bench": bench,
        "delayed": delayed,
        "capacity": capacity,
    }


def _person(p: dict) -> dict:
    return {"id": p["id"], "name": p["name"], "role": p["career_stage"], "location": p["location"], "client": p["client"],
            "source": p["source"]}


def _capacity(db: Session, filters: Filters, full_roster: List[dict], as_of: date) -> dict:
    """Greedy match of open demand to people who will be free by the needed-by date."""
    horizon = as_of + timedelta(days=config.FORECAST_HORIZON_DAYS)
    query = db.query(DemandForecast).filter(DemandForecast.status == "open").order_by(DemandForecast.needed_by)
    demand = [d for d in query.all() if d.needed_by <= horizon]
    if filters.role:
        demand = [d for d in demand if d.role == filters.role]
    if filters.location:
        demand = [d for d in demand if d.location == filters.location]

    supply = []
    for p in full_roster:
        if filters.location and p["location"] != filters.location:
            continue
        if p["bucket"] in ("On bench", "Contract ended"):
            supply.append((p, p["career_stage"], as_of, "unassigned now"))
        elif p["bucket"] == "Yet to join" and not p["client"] and p["career_stage"] != "Trainee":
            supply.append((p, p["career_stage"], date.fromisoformat(p["start_date"]), "joins {}".format(p["start_date"])))
        elif p["career_stage"] == "Trainee" and not p["client"] and p["start_date"]:
            graduation = date.fromisoformat(p["start_date"]) + timedelta(weeks=config.TRAINING_PROGRAM_WEEKS)
            supply.append((p, config.TRAINEE_GRADUATES_AS, graduation, "graduates {}".format(graduation.isoformat())))
        elif p["bucket"] == "Active at client" and p["client_end"]:
            end = date.fromisoformat(p["client_end"])
            if end <= horizon:
                supply.append((p, p["career_stage"], end + timedelta(days=1), "{} contract ends {}".format(p["client"], p["client_end"])))
    supply.sort(key=lambda item: item[2])
    used = set()
    rows = []
    for d in demand:
        matches = [item for item in supply if item[1] == d.role and item[2] <= d.needed_by and item[0]["id"] not in used]
        take = matches[: d.fdes_needed]
        for item in take:
            used.add(item[0]["id"])
        gap = d.fdes_needed - len(take)
        monthly_each = (d.hourly_rate or 0) * (d.hours_per_week or 0) * BILLING_WEEKS if d.hourly_rate else None
        rows.append(
            {
                "id": d.id,
                "client": d.client,
                "role": d.role,
                "location": d.location,
                "needed": d.fdes_needed,
                "needed_by": d.needed_by.isoformat(),
                "days": (d.needed_by - as_of).days,
                "allocated": [{"name": item[0]["name"], "why": item[3]} for item in take],
                "gap": gap,
                "revenue_exposure": _r(gap * monthly_each, 0) if monthly_each is not None else None,
                "is_demo": bool(d.is_demo),
            }
        )
    by_role: Dict[str, dict] = {}
    for row in rows:
        group = by_role.setdefault(row["role"], {"role": row["role"], "needed": 0, "allocated": 0, "gap": 0, "first_gap_date": None})
        group["needed"] += row["needed"]
        group["allocated"] += len(row["allocated"])
        group["gap"] += row["gap"]
        if row["gap"] and (group["first_gap_date"] is None or row["needed_by"] < group["first_gap_date"]):
            group["first_gap_date"] = row["needed_by"]
    return {
        "rows": rows,
        "by_role": sorted(by_role.values(), key=lambda g: -g["gap"]),
        "gap_fdes": sum(row["gap"] for row in rows),
        "demand_fdes": sum(row["needed"] for row in rows),
        "any_demo": any(row["is_demo"] for row in rows),
        "horizon_days": config.FORECAST_HORIZON_DAYS,
    }


# ---------------------------------------------------------------- page shaping


def _drilldown(activity: dict, ctx: dict) -> dict:
    driver = activity["driver"]
    if driver in PIPELINE_DRIVERS:
        rows = []
        for row, vol in ctx["row_volumes"]:
            part = vol.get(driver)
            rows.append({
                "week": row.week_ending.isoformat(), "cohort": row.cohort, "role": row.role, "source": row.source or "–",
                "waiting": part["waiting"] if part else None, "passed": part["passed"] if part else None,
                "units": part["entered"] if part else None, "origin": part["origin"] if part else "not reported",
            })
        return {"title": "Hiring rows (pipeline_weeks)", "columns": ["week", "cohort", "role", "source", "waiting", "passed", "units", "origin"],
                "rows": rows}
    if driver in ("academy_weeks", "trainee_weeks"):
        return {"title": "Trainees in range (people)", "columns": ["name", "location", "start_date", "academy_ends", "weeks_in_range"],
                "rows": ctx["trainee_records"]}
    if driver == "deployments":
        return {"title": "Client starts in range (people)", "columns": ["name", "career_stage", "location", "client", "client_start"],
                "rows": [{k: p[k] for k in ("name", "career_stage", "location", "client", "client_start")} for p in ctx["deployments"]]}
    return {"title": "No records", "columns": [], "rows": []}


def _coverage(db: Session, ctx: dict) -> List[dict]:
    rows = ctx["rows"]
    total_fields = len(rows) * len(STAGE_FIELDS)
    filled = sum(1 for row in rows for field in STAGE_FIELDS if getattr(row, field) is not None)
    weeks = len(available_weeks(db))
    training = ctx["training"]
    placeholders = [r for r in ctx["rates"] if r.is_placeholder]
    internal = [r for r in ctx["rates"] if r.cost_type == "internal"]
    clients = [p for p in ctx["full_roster"] if p["client"]]
    rated = [p for p in clients if p["hourly_rate"] is not None and p["hours_per_week"] is not None]
    demo_demand = db.query(DemandForecast).filter(DemandForecast.is_demo == 1).count()
    total_demand = db.query(DemandForecast).count()

    def status(ok, partial=False):
        return "ok" if ok else ("partial" if partial else "missing")

    return [
        {"label": "Recruitment pipeline", "status": status(filled == total_fields and total_fields > 0, filled > 0),
         "detail": "{} weekly snapshot(s); {} of {} stage fields reported in the selected week".format(weeks, filled, total_fields)},
        {"label": "Candidate-level stage dates (wait times)", "status": "missing",
         "detail": "Sheet has counts only, so waiting days and oldest candidate cannot be calculated"},
        {"label": "Training scores", "status": status(training["weeks_scored"] >= 2, training["weeks_scored"] > 0),
         "detail": "{} of {} weeks scored".format(training["weeks_scored"], training["weeks_total"])},
        {"label": "Per-student scores", "status": "missing", "detail": "Only cohort averages are reported"},
        {"label": "Deployment roster", "status": "ok", "detail": "{} people".format(len(ctx["full_roster"]))},
        {"label": "Billing rates", "status": status(len(rated) == len(clients), bool(rated)),
         "detail": "{} of {} people with a client have rate and hours; unassigned people use the role average".format(len(rated), len(clients))},
        {"label": "Resource hours & cost", "status": "assumption" if placeholders else "ok",
         "detail": "{} of {} rates are unedited placeholders ({} internal activities)".format(len(placeholders), len(ctx["rates"]), len(internal))},
        {"label": "Demand forecast", "status": "demo" if demo_demand else ("ok" if total_demand else "missing"),
         "detail": "{} of {} demand rows are demo seed".format(demo_demand, total_demand) if total_demand else "No demand rows"},
        {"label": "Salary / margin", "status": "missing", "detail": "Revenue ratios use revenue, not profit"},
        {"label": "Outreach / sourcing funnel", "status": "missing", "detail": "No outreach or channel data"},
    ]


def _insights(burn: dict, revenue: dict, hiring: dict) -> List[str]:
    out = []
    groups = [g for g in burn["concentration"] if g["phase"] == "recruitment" and g["hours"]]
    rec_hours = sum(g["hours"] for g in groups)
    if groups and rec_hours:
        top = max(groups, key=lambda g: g["hours"])
        out.append("{} account for {:.0%} of recruitment resource hours ({:,.0f} of {:,.0f} h).".format(
            top["label"], top["hours"] / rec_hours, top["hours"], rec_hours))
    ranked = [a for a in burn["activities"] if a["hours"]]
    if ranked:
        top = max(ranked, key=lambda a: a["hours"])
        extra = " {} candidates are still waiting at this stage.".format(int(top["waiting"])) if top.get("waiting") else ""
        out.append("Largest single activity: {} ({:,.0f} h, {}).{}".format(top["label"], top["hours"], _money(top["cost"]), extra))
    if revenue["bench"]:
        value = revenue["bench_revenue"]
        out.append("{} FDE{} on the bench{}.".format(
            len(revenue["bench"]), " is" if len(revenue["bench"]) == 1 else "s are",
            ", representing approximately {}/month of potential revenue".format(_money(value)) if value else ""))
    if revenue["contracts"]:
        first = revenue["contracts"][0]
        out.append("{} contract{} expire within {} days, representing {}/month; the nearest ({}, {}) ends in {} days.".format(
            len(revenue["contracts"]), "" if len(revenue["contracts"]) == 1 else "s", config.CONTRACT_WARNING_DAYS,
            _money(revenue["contracts_revenue"]), first["client"], first["name"], first["days"]))
    if len(out) < 4 and hiring["kpis"]["cost_per_hire"]:
        out.append("Each accepted offer costs about {} in recruitment effort.".format(_money(hiring["kpis"]["cost_per_hire"])))
    return out[:4]


def _resource_burn(ctx: dict, filters: Filters) -> dict:
    activities = [a for a in ctx["activities"] if not filters.phase or a["phase"] == filters.phase]
    total_hours = sum(a["hours"] or 0 for a in activities)
    total_cost = sum(a["cost"] or 0 for a in activities)
    accepted = ctx["volumes"]["accepted"]["value"]
    deployments = ctx["volumes"]["deployments"]["value"]
    enriched = []
    for a in activities:
        success = a["passed"]
        if a["driver"] == "accepted":
            success = a["units"]
        elif a["driver"] == "deployments":
            success = a["units"]
        enriched.append({
            **a,
            "share_hours": _r(_div(a["hours"], total_hours), 4),
            "share_cost": _r(_div(a["cost"], total_cost), 4),
            "successes": success,
            "cost_per_success": _r(_div(a["cost"], success), 0),
            "cost_per_hire": _r(_div(a["cost"], accepted), 0),
            "cost_per_deployment": _r(_div(a["cost"], deployments), 0),
            "records": _drilldown(a, ctx),
        })
    groups: Dict[str, dict] = {}
    for a in enriched:
        g = groups.setdefault(a["stage_group"], {"label": a["stage_group"], "phase": a["phase"], "hours": 0.0, "cost": 0.0, "activities": 0})
        g["hours"] += a["hours"] or 0
        g["cost"] += a["cost"] or 0
        g["activities"] += 1
    concentration = sorted(groups.values(), key=lambda g: -g["hours"])
    for g in concentration:
        g["share_hours"] = _r(_div(g["hours"], total_hours), 4)
        g["share_cost"] = _r(_div(g["cost"], total_cost), 4)
    headline = None
    if concentration and total_hours:
        top = concentration[0]
        headline = "{} consume {:.0%} of {} resource hours and {:.0%} of cost.".format(
            top["label"], top["share_hours"], filters.phase or "all", top["share_cost"] or 0)
    recruitment_cost = sum(a["cost"] or 0 for a in activities if a["phase"] == "recruitment")
    return {
        "kpis": {
            "total_hours": round(total_hours, 1),
            "total_cost": round(total_cost, 0),
            "recruitment_cost": round(recruitment_cost, 0),
            "cost_per_hire": _r(_div(recruitment_cost, accepted), 0) if recruitment_cost else None,
            "cost_per_deployment": _r(_div(total_cost, deployments), 0),
            "accepted": accepted,
            "deployments": deployments,
        },
        "activities": enriched,
        "concentration": concentration,
        "headline": headline,
    }


def _hiring(ctx: dict) -> dict:
    acts = ctx["activities"]
    vols = ctx["volumes"]

    def cost(phase=None, cost_type=None, stage=None):
        return round(sum(a["cost"] or 0 for a in acts if (phase is None or a["phase"] == phase)
                         and (cost_type is None or a["cost_type"] == cost_type)
                         and (stage is None or a["stage"] == stage)), 0)

    def hours(stage):
        return round(sum(a["hours"] or 0 for a in acts if a["stage"] == stage), 1)

    recruitment = cost("recruitment")
    training = cost("training")
    deployment = cost("deployment")
    total = recruitment + training + deployment
    applicants = vols["applications"]["value"]
    interview_values = [vols[d]["value"] for d in ("l1", "berribot", "l2") if vols[d]["value"] is not None]
    interviewed = max(interview_values) if interview_values else None
    offers = vols["offers"]["value"]
    accepted = vols["accepted"]["value"]
    trainees = len(ctx["trainees"])
    trainees_deployed = sum(1 for p in ctx["trainees"] if p["bucket"] == "Active at client")
    deployments = vols["deployments"]["value"]
    monthly = ctx["revenue"]["monthly_revenue"]

    def origin(*drivers):
        found = {vols[d]["origin"] for d in drivers if vols[d]["origin"]}
        return "inferred" if "inferred" in found else ("workbook" if found else None)

    lifecycle = [
        {"key": "applicant", "label": "Applicant", "people": applicants, "origin": origin("applications"),
         "conversion": None, "conversion_note": "Start of funnel",
         "outcome": interviewed, "outcome_label": "reached interviews"},
        {"key": "interview", "label": "Interview", "people": interviewed, "origin": origin("l1", "berribot", "l2"),
         "conversion": _div(interviewed, applicants), "conversion_note": "of applicants",
         "outcome": offers, "outcome_label": "received offers"},
        {"key": "offer", "label": "Offer", "people": offers, "origin": origin("offers"),
         "conversion": _div(offers, interviewed), "conversion_note": "of interviewed",
         "outcome": accepted, "outcome_label": "accepted"},
        {"key": "accepted", "label": "Accepted", "people": accepted, "origin": origin("accepted"),
         "conversion": _div(accepted, offers), "conversion_note": "of offers",
         "outcome": accepted, "outcome_label": "accepted"},
        {"key": "training", "label": "Training", "people": trainees or None, "origin": "workbook" if trainees else None,
         "conversion": None, "conversion_note": "Academy cohort from the roster, not the same people as the hiring funnel",
         "outcome": trainees_deployed, "outcome_label": "trainees placed at a client"},
        {"key": "deployment", "label": "Deployment", "people": deployments, "origin": "workbook",
         "conversion": None, "conversion_note": "Client starts in range, includes direct (non-academy) hires",
         "outcome": deployments, "outcome_label": "client starts"},
    ]
    for stage in lifecycle:
        stage["hours"] = hours(stage["key"])
        stage["cost"] = cost(stage=stage["key"])
        stage["conversion"] = _r(stage["conversion"], 4)
        stage["cost_per_outcome"] = _r(_div(stage["cost"], stage["outcome"]), 0)

    breakdown = [
        {"label": "Internal recruitment time", "cost": cost("recruitment", "internal"), "kind": "internal"},
        {"label": "External recruitment spend", "cost": cost("recruitment", "external"), "kind": "external"},
        {"label": "Training (trainer time)", "cost": cost("training", "internal"), "kind": "internal"},
        {"label": "Training (external spend)", "cost": cost("training", "external"), "kind": "external"},
        {"label": "Deployment onboarding time", "cost": cost("deployment", "internal"), "kind": "internal"},
    ]
    efficiency = [
        {"label": "Cost per hire", "value": _r(_div(recruitment, accepted), 0), "format": "money",
         "explain": "Recruitment cost in period ÷ accepted offers ({})".format(accepted if accepted is not None else "not reported")},
        {"label": "Cost per deployment", "value": _r(_div(total, deployments), 0), "format": "money",
         "explain": "Total talent investment ÷ client starts in period ({})".format(deployments)},
        {"label": "Monthly revenue per $1 of acquisition cost", "value": _r(_div(monthly, recruitment), 2), "format": "ratio",
         "explain": "Current monthly run-rate ÷ recruitment cost in period. Revenue, not margin; run-rate includes people hired earlier."},
        {"label": "Monthly revenue per $1 of total talent investment", "value": _r(_div(monthly, total), 2), "format": "ratio",
         "explain": "Current monthly run-rate ÷ recruitment + training + deployment cost. Salaries are not in the data, so this is not ROI."},
    ]
    return {
        "kpis": {
            "recruitment_cost": recruitment,
            "training_cost": training,
            "deployment_cost": deployment,
            "total_investment": total,
            "cost_per_applicant": _r(_div(recruitment, applicants), 0),
            "cost_per_offer": _r(_div(recruitment, offers), 0),
            "cost_per_hire": _r(_div(recruitment, accepted), 0),
            "cost_per_deployment": _r(_div(total, deployments), 0),
            "applicants": applicants,
            "offers": offers,
            "accepted": accepted,
            "deployments": deployments,
            "other_costs": None,
        },
        "breakdown": breakdown,
        "lifecycle": lifecycle,
        "efficiency": efficiency,
        "sources": ctx["sources"],
    }


def options(db: Session) -> dict:
    roles = {r[0] for r in db.query(PipelineWeek.role).distinct()} | {r[0] for r in db.query(Person.career_stage).distinct()}
    return {
        "roles": sorted(roles),
        "locations": sorted({r[0] for r in db.query(Person.location).distinct()}),
        "cohorts": sorted({r[0] for r in db.query(PipelineWeek.cohort).distinct()}),
        "weeks": [w.isoformat() for w in available_weeks(db)],
        "phases": list(PHASES),
    }


def build_economics(db: Session, filters: Filters) -> dict:
    ctx = compute(db, filters)
    burn = _resource_burn(ctx, filters)
    hiring = _hiring(ctx)
    revenue = ctx["revenue"]
    return {
        "as_of": filters.end.isoformat(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "week_ending": ctx["week"].isoformat() if ctx["week"] else None,
        "filters": filters.as_json(),
        "options": options(db),
        "notes": ctx["notes"],
        "burn": burn,
        "hiring": hiring,
        "revenue": {k: v for k, v in revenue.items()},
        "insights": _insights(burn, revenue, hiring),
        "coverage": _coverage(db, ctx),
        "config": config.as_dict(),
        "rates": [
            {"code": r.code, "label": r.label, "phase": r.phase, "cost_type": r.cost_type, "resource_role": r.resource_role,
             "driver_label": DRIVER_LABELS.get(r.driver, r.driver), "hours_per_unit": r.hours_per_unit,
             "hourly_cost_usd": r.hourly_cost_usd, "unit_cost_usd": r.unit_cost_usd,
             "weekly_capacity_units": r.weekly_capacity_units, "is_placeholder": bool(r.is_placeholder), "notes": r.notes}
            for r in ctx["rates"]
        ],
    }


EDITABLE = ("hours_per_unit", "hourly_cost_usd", "unit_cost_usd", "weekly_capacity_units")


def save_rates(db: Session, updates: List[dict]) -> None:
    if not isinstance(updates, list) or not updates:
        raise ValueError("Send at least one rate.")
    known = {r.code: r for r in db.query(ResourceRate).all()}
    for item in updates:
        rate = known.get(item.get("code")) if isinstance(item, dict) else None
        if rate is None:
            raise ValueError("Unknown rate.")
        changed = False
        for field in EDITABLE:
            if field not in item:
                continue
            value = item[field]
            if value in (None, ""):
                continue
            try:
                number = float(value)
            except (TypeError, ValueError):
                raise ValueError("{} {} must be a number.".format(rate.label, field))
            if number < 0 or math.isnan(number):
                raise ValueError("{} {} cannot be negative.".format(rate.label, field))
            if getattr(rate, field) != number:
                setattr(rate, field, number)
                changed = True
        if changed:
            rate.is_placeholder = 0
    db.commit()
