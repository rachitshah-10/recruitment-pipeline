"""Deterministic leadership recommendation engine.

Each rule reads metrics from economics.compute(), decides triggered /
not triggered / insufficient data, and returns recommendations whose
every number traces back to a metric, a threshold, and a source table.

Score = sum(weight x component), weights in config.SCORE_WEIGHTS:
- impact: people affected vs PEOPLE_FULL_SCALE, or monthly revenue vs
  REVENUE_FULL_SCALE, whichever is larger (rules may define their own basis)
- urgency: days to the event over URGENCY_HORIZON_DAYS (0 days = 100)
- revenue_risk: monthly revenue at stake vs REVENUE_FULL_SCALE (0 if not calculable)
- confidence: lowest confidence among the data origins the rule used
"""

import math
import re
from datetime import date, datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app import config
from app.economics import Filters, _coverage, _money, compute, options
from app.models import RecommendationStatus

STATUSES = ("OPEN", "ACCEPTED", "DISMISSED")


# ---------------------------------------------------------------- scoring


def _clip(value: float) -> float:
    return max(0.0, min(100.0, value))


def _urgency_from_days(days: Optional[int]) -> (float, str):
    if days is None:
        return float(config.STRATEGIC_URGENCY), "No deadline in data; strategic default {}".format(config.STRATEGIC_URGENCY)
    value = _clip((1 - max(days, 0) / float(config.URGENCY_HORIZON_DAYS)) * 100)
    return value, "{} day(s) to event over a {}-day horizon".format(max(days, 0), config.URGENCY_HORIZON_DAYS)


def score(impact: (float, str), urgency: (float, str), revenue: Optional[float], origins: List[str]) -> dict:
    revenue_value = _clip((revenue or 0) / config.REVENUE_FULL_SCALE * 100)
    revenue_basis = (
        "{}/month vs {} full scale".format(_money(revenue), _money(config.REVENUE_FULL_SCALE))
        if revenue else "Revenue impact not calculable from data, scored 0"
    )
    used = sorted(set(origins)) or ["workbook"]
    confidence = min(config.CONFIDENCE[o] for o in used)
    weakest = min(used, key=lambda o: config.CONFIDENCE[o])
    parts = {
        "impact": (_clip(impact[0]), impact[1]),
        "urgency": (_clip(urgency[0]), urgency[1]),
        "revenue_risk": (revenue_value, revenue_basis),
        "confidence": (float(confidence), "Lowest input confidence: {} ({})".format(weakest, config.SOURCES[weakest])),
    }
    components = []
    total = 0.0
    for key, weight in config.SCORE_WEIGHTS.items():
        value, basis = parts[key]
        contribution = weight * value
        total += contribution
        components.append({"key": key, "weight": weight, "value": round(value, 1), "contribution": round(contribution, 1), "basis": basis})
    total = round(total)
    if total >= config.PRIORITY_HIGH:
        priority = "HIGH"
    elif total >= config.PRIORITY_MEDIUM:
        priority = "MEDIUM"
    else:
        priority = "LOW"
    return {
        "score": total,
        "priority": priority,
        "confidence": confidence,
        "breakdown": {
            "components": components,
            "thresholds": {"high": config.PRIORITY_HIGH, "medium": config.PRIORITY_MEDIUM},
            "origins": used,
        },
    }


def _impact(people: Optional[float] = None, revenue: Optional[float] = None) -> (float, str):
    people_part = (people or 0) / config.PEOPLE_FULL_SCALE * 100
    revenue_part = (revenue or 0) / config.REVENUE_FULL_SCALE * 100
    if people_part >= revenue_part:
        return people_part, "{} people affected vs {} full scale".format(int(people or 0), config.PEOPLE_FULL_SCALE)
    return revenue_part, "{}/month vs {} full scale".format(_money(revenue), _money(config.REVENUE_FULL_SCALE))


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _trigger(metric: str, value, threshold, source: str, comparator: str = ">=") -> dict:
    return {"metric": metric, "value": value, "threshold": threshold, "comparator": comparator, "source": source}


def _rec(**fields) -> dict:
    origins = fields.pop("origins")
    s = score(fields.pop("impact_score"), fields.pop("urgency_score"), fields["impact"].get("value") if fields["impact"].get("type") == "revenue" else None,
              origins)
    fields.update({
        "score": s["score"], "priority": s["priority"], "confidence": s["confidence"], "score_breakdown": s["breakdown"],
        "data_origins": origins,
        "uses_sample": any(origin in ("assumption", "demo") for origin in origins),
    })
    return fields


def _no_revenue(note: str = "Revenue impact cannot currently be calculated from available data.") -> dict:
    return {"type": "revenue", "value": None, "period": "monthly", "calculable": False, "estimated": False, "note": note}


# ---------------------------------------------------------------- rules


def rule_bottleneck(ctx: dict) -> dict:
    name = "Recruitment bottleneck"
    week = ctx["week"].isoformat() if ctx["week"] else None
    if not ctx["queues"]:
        return {"rule": "R1", "name": name, "status": "insufficient_data", "detail": "No stage has a waiting count in the selected week.", "recommendations": []}
    recs = []
    for q in ctx["queues"]:
        if q["waiting"] < config.QUEUE_THRESHOLD:
            continue
        hpu = q["hours_per_unit"]
        cap = q["weekly_capacity_units"]
        source = "pipeline_weeks ({}, week ending {})".format(q["label"].split(" ")[0] + " pending", week)
        triggers = [_trigger("Candidates waiting at {}".format(q["label"]), q["waiting"], config.QUEUE_THRESHOLD, source)]
        metrics = [
            {"label": "Candidates waiting", "value": q["waiting"]},
            {"label": "Average wait", "value": "Not available (no candidate-level stage dates)"},
            {"label": "Oldest candidate", "value": "Not available (no candidate-level stage dates)"},
        ]
        origins = ["workbook"]
        action = "Schedule the {} waiting {} candidates before adding new applicants to this stage.".format(q["waiting"], q["label"])
        effect = "Queue reduced below {} candidates.".format(config.QUEUE_THRESHOLD)
        urgency = (_clip(q["waiting"] / config.QUEUE_THRESHOLD * 50), "{} waiting is {:.1f}x the threshold of {}".format(
            q["waiting"], q["waiting"] / config.QUEUE_THRESHOLD, config.QUEUE_THRESHOLD))
        evidence = ["{} candidates waiting at {}".format(q["waiting"], q["label"])]
        if hpu is not None and cap is not None:
            origins.append("assumption")
            required = q["waiting"] / config.QUEUE_CLEAR_WEEKS * hpu
            available = cap * hpu
            gap = required - available
            weeks_now = q["waiting"] / cap if cap else None
            metrics += [
                {"label": "Available capacity", "value": "{:.0f} h/week ({:.0f} slots x {} h)".format(available, cap, hpu)},
                {"label": "Required capacity", "value": "{:.0f} h/week (clear queue in {} weeks)".format(required, config.QUEUE_CLEAR_WEEKS)},
                {"label": "Capacity gap", "value": "{:.0f} h/week".format(max(gap, 0))},
                {"label": "Weeks to clear at current capacity", "value": "{:.1f}".format(weeks_now) if weeks_now else "n/a"},
            ]
            evidence.append("{:.0f} interviewer-hours/week available vs {:.0f} needed".format(available, required))
            if weeks_now:
                evidence.append("{:.1f} weeks to clear at current capacity (target {})".format(weeks_now, config.QUEUE_CLEAR_WEEKS))
                urgency = (_clip(weeks_now / config.QUEUE_CLEAR_WEEKS * 50),
                           "{:.1f} weeks to clear vs {}-week target (2x target = 100)".format(weeks_now, config.QUEUE_CLEAR_WEEKS))
            if gap > 0:
                people = math.ceil(gap / config.INTERVIEWER_HOURS_PER_WEEK)
                triggers.append(_trigger("{} capacity gap (h/week)".format(q["label"]), round(gap), 0, "resource_rates (capacity assumption)", ">"))
                evidence.append("{:.0f} interviewer-hours/week capacity gap".format(gap))
                action = "Add {} interviewer{} to {} for the next {} weeks (about {:.0f} extra interviewer-hours per week).".format(
                    people, "" if people == 1 else "s", q["label"], config.QUEUE_CLEAR_WEEKS, gap)
                effect = "Queue of {} cleared in about {} weeks instead of {:.1f}.".format(q["waiting"], config.QUEUE_CLEAR_WEEKS, weeks_now or 0)
        else:
            metrics.append({"label": "Available capacity", "value": "Not set in resource_rates"})
        if ctx["slots_needed"]:
            evidence.append("HR reports {} interview slots needed next week".format(int(ctx["slots_needed"])))
            metrics.append({"label": "Interview slots needed next week (HR)", "value": int(ctx["slots_needed"])})
        recs.append(_rec(
            id="bottleneck-{}".format(q["code"]),
            rule_code="R1",
            rule_name=name,
            title="Increase {} capacity".format(q["label"]),
            category="Recruitment",
            summary="{} candidates are waiting for {}.".format(q["waiting"], q["label"]),
            why_it_matters="Candidates waiting longer drop out or accept other offers, which delays hiring and deployment.",
            evidence=evidence,
            metrics=metrics,
            supporting_metrics=[{"label": "{} / {}".format(r["cohort"], r["role"]), "value": "{} waiting".format(r["waiting"])} for r in q["by_row"]],
            triggered_by=triggers,
            impact=_no_revenue(),
            impact_chain=["Capacity gap at {}".format(q["label"]), "Longer candidate wait", "Delayed hiring", "Delayed deployment", "Potential revenue impact"],
            recommended_action=action,
            expected_effect=effect,
            data_sources=["pipeline_weeks", "resource_rates"],
            impact_score=_impact(people=q["waiting"]),
            urgency_score=urgency,
            origins=origins,
        ))
    largest = max(ctx["queues"], key=lambda q: q["waiting"])
    detail = "{} stage(s) at or above {} waiting.".format(len(recs), config.QUEUE_THRESHOLD) if recs else \
        "Largest queue is {} with {} waiting, below the threshold of {}.".format(largest["label"], largest["waiting"], config.QUEUE_THRESHOLD)
    detail += " Average-wait check (>{} days) not evaluated: no candidate-level stage dates.".format(config.AVG_WAIT_DAYS_THRESHOLD)
    return {"rule": "R1", "name": name, "status": "triggered" if recs else "not_triggered", "detail": detail, "recommendations": recs}


def rule_cohort(ctx: dict) -> dict:
    name = "Cohort performance risk"
    t = ctx["training"]
    latest = t["latest"]
    if latest is None:
        return {"rule": "R2", "name": name, "status": "insufficient_data", "detail": "No training week has been scored.", "recommendations": []}
    below = latest["overall"] < config.READINESS_FLOOR
    declining = t["declining_weeks"] >= config.DECLINE_WEEKS
    gap = None
    if latest["hands_on"] is not None and latest["proctored"] is not None:
        gap = latest["hands_on"] - latest["proctored"]
    weak_component = gap is not None and abs(gap) >= config.COMPONENT_GAP
    trend = "{} consecutive declining week(s)".format(t["declining_weeks"]) if t["weeks_scored"] > 1 else \
        "trend needs 2+ scored weeks ({} reported)".format(t["weeks_scored"])
    detail = "Week {} overall {:.0%} vs floor {:.0%}; {}; hands-on vs proctored gap {}.".format(
        latest["week"], latest["overall"], config.READINESS_FLOOR, trend,
        "{:+.0f} pts".format(gap * 100) if gap is not None else "n/a")
    if not (below or declining or weak_component):
        return {"rule": "R2", "name": name, "status": "not_triggered", "detail": detail, "recommendations": []}
    source = "training_weeks (Input - Trainers, week {})".format(latest["week"])
    triggers = []
    if below:
        triggers.append(_trigger("Overall readiness", "{:.0%}".format(latest["overall"]), "{:.0%}".format(config.READINESS_FLOOR), source, "<"))
    if declining:
        triggers.append(_trigger("Consecutive declining weeks", t["declining_weeks"], config.DECLINE_WEEKS, source))
    if weak_component:
        weaker = "hands-on" if gap < 0 else "proctored"
        triggers.append(_trigger("{} below the other component".format(weaker.capitalize()), "{:.0f} pts".format(abs(gap) * 100),
                                 "{:.0f} pts".format(config.COMPONENT_GAP * 100), source))
    students = latest["active_students"] or 0
    focus = "hands-on" if gap is not None and gap < 0 else "assessment"
    rec = _rec(
        id="cohort-week-{}".format(latest["week"]),
        rule_code="R2",
        rule_name=name,
        title="Intervene in the current academy cohort",
        category="Cohort",
        summary="Week {} readiness is {:.0%}; {}.".format(latest["week"], latest["overall"], trend),
        why_it_matters="Trainees below readiness graduate late or underperform at clients, delaying billable deployment.",
        evidence=[detail],
        metrics=[
            {"label": "Current score", "value": "{:.0%}".format(latest["overall"])},
            {"label": "Previous score", "value": "{:.0%}".format(t["previous"]["overall"]) if t["previous"] else "Not reported"},
            {"label": "Cohort average (all scored weeks)", "value": "{:.0%}".format(t["average"])},
            {"label": "Trend", "value": trend},
            {"label": "Students at risk", "value": "Not available (no per-student scores)"},
        ],
        supporting_metrics=[{"label": "Active students", "value": students}, {"label": "Topic", "value": t["topic"] or "–"}],
        triggered_by=triggers,
        impact=_no_revenue("Revenue impact cannot currently be calculated: there is no billing rate for graduating trainees."),
        impact_chain=["Lower readiness", "Delayed graduation", "Delayed deployment", "Potential revenue impact"],
        recommended_action="Assign targeted {} mentoring for the cohort this week and re-test before the next module.".format(focus),
        expected_effect="Readiness back above {:.0%} by the next scored week.".format(config.READINESS_FLOOR),
        data_sources=["training_weeks"],
        impact_score=_impact(people=students),
        urgency_score=(80.0 if below else 50.0, "Below floor = 80, trend/component only = 50"),
        origins=["workbook"],
    )
    return {"rule": "R2", "name": name, "status": "triggered", "detail": detail, "recommendations": [rec]}


def rule_capacity(ctx: dict) -> dict:
    name = "Capacity shortage"
    cap = ctx["revenue"]["capacity"]
    if not cap["rows"]:
        return {"rule": "R3", "name": name, "status": "insufficient_data",
                "detail": "No open demand within {} days for the current filters.".format(cap["horizon_days"]), "recommendations": []}
    recs = []
    as_of = ctx["as_of"]
    for group in cap["by_role"]:
        if not group["gap"]:
            continue
        rows = [r for r in cap["rows"] if r["role"] == group["role"] and r["gap"]]
        revenue = sum(r["revenue_exposure"] or 0 for r in rows) or None
        first = min(rows, key=lambda r: r["needed_by"])
        days = (date.fromisoformat(first["needed_by"]) - as_of).days
        origins = ["demo" if any(r["is_demo"] for r in rows) else "workbook", "inferred"]
        recs.append(_rec(
            id="capacity-{}".format(_slug(group["role"])),
            rule_code="R3",
            rule_name=name,
            title="Start {} recruitment".format(group["role"]),
            category="Deployment",
            summary="Projected gap of {} {}{} by {}.".format(group["gap"], group["role"], "" if group["gap"] == 1 else "s", first["needed_by"]),
            why_it_matters="Demand that cannot be staffed is revenue the business does not book.",
            evidence=["Demand {} vs {} available by need date".format(group["needed"], group["allocated"]),
                      "Gap {} {}".format(group["gap"], group["role"]),
                      "Earliest unfilled need: {} on {}".format(first["client"], first["needed_by"])]
                     + (["Estimated revenue exposure {}/month".format(_money(revenue))] if revenue else []),
            metrics=[
                {"label": "Forecast demand", "value": group["needed"]},
                {"label": "Available capacity", "value": group["allocated"]},
                {"label": "Gap", "value": group["gap"]},
                {"label": "Expected date", "value": first["needed_by"]},
                {"label": "Estimated revenue exposure", "value": "{}/month".format(_money(revenue)) if revenue else "Not calculable"},
            ],
            supporting_metrics=[{"label": "{} ({} needed by {})".format(r["client"], r["needed"], r["needed_by"]),
                                 "value": "{} matched, gap {}".format(len(r["allocated"]), r["gap"])} for r in cap["rows"] if r["role"] == group["role"]],
            triggered_by=[_trigger("Projected {} demand minus supply".format(group["role"]), group["gap"], 0,
                                   "demand_forecast (demo) + people roster", ">")],
            impact={"type": "revenue", "value": revenue, "period": "monthly", "calculable": revenue is not None, "estimated": True,
                    "note": "Demand rates come from the demand_forecast table, which holds demo rows."},
            impact_chain=["Demand exceeds supply", "Unstaffed client roles", "Revenue not booked"],
            recommended_action="Open recruitment for {} {}{} now; the first unfilled need is {} on {}.".format(
                group["gap"], group["role"], "" if group["gap"] == 1 else "s", first["client"], first["needed_by"]),
            expected_effect="Supply covers demand by {} if hires land in time.".format(first["needed_by"]),
            data_sources=["demand_forecast", "people"],
            impact_score=_impact(people=group["gap"], revenue=revenue),
            urgency_score=_urgency_from_days(days),
            origins=origins,
        ))
    detail = "{} role(s) short; {} of {} demanded FDEs unmatched.".format(len(recs), cap["gap_fdes"], cap["demand_fdes"]) if recs else \
        "All {} demanded FDEs can be matched to people free by the need date.".format(cap["demand_fdes"])
    return {"rule": "R3", "name": name, "status": "triggered" if recs else "not_triggered", "detail": detail, "recommendations": recs}


def rule_bench(ctx: dict) -> dict:
    name = "Bench / underutilization"
    bench = ctx["revenue"]["bench"]
    long = [p for p in bench if p["days_on_bench"] >= config.BENCH_DAYS_THRESHOLD]
    if not bench:
        return {"rule": "R4", "name": name, "status": "not_triggered", "detail": "Nobody is on the bench.", "recommendations": []}
    if not long:
        return {"rule": "R4", "name": name, "status": "not_triggered",
                "detail": "{} on the bench, none beyond {} days.".format(len(bench), config.BENCH_DAYS_THRESHOLD), "recommendations": []}
    revenue = sum(p["revenue"] or 0 for p in long) or None
    estimated = any(p["revenue_basis"] != "own billing rate" for p in long)
    demand = [r for r in ctx["revenue"]["capacity"]["rows"] if any(r["role"] == p["role"] for p in long)]
    names = ", ".join(p["name"] for p in long)
    rec = _rec(
        id="bench-" + "-".join(str(p["id"]) for p in long),
        rule_code="R4",
        rule_name=name,
        title="Prioritise deployment of {} bench FDE{}".format(len(long), "" if len(long) == 1 else "s"),
        category="Deployment",
        summary="{} {} been unassigned for {}+ days.".format(names, "has" if len(long) == 1 else "have", config.BENCH_DAYS_THRESHOLD),
        why_it_matters="Every week on the bench is billable capacity the business pays for but does not bill.",
        evidence=["{} ({}) on bench {} days, potential {}/month".format(p["name"], p["role"], p["days_on_bench"], _money(p["revenue"]) if p["revenue"] else "n/a")
                  for p in long],
        metrics=[
            {"label": "FDEs on bench beyond threshold", "value": len(long)},
            {"label": "Days on bench (longest)", "value": long[0]["days_on_bench"]},
            {"label": "Billing rate basis", "value": "; ".join(sorted({p["revenue_basis"] for p in long}))},
            {"label": "Potential monthly revenue", "value": "{}/month".format(_money(revenue)) if revenue else "Not calculable"},
        ],
        supporting_metrics=[{"label": "Open demand: {} {}".format(r["client"], r["role"]), "value": "{} needed by {}".format(r["needed"], r["needed_by"])}
                            for r in demand],
        triggered_by=[_trigger("Days on bench ({})".format(p["name"]), p["days_on_bench"], config.BENCH_DAYS_THRESHOLD, "people (Master-Input)") for p in long],
        impact={"type": "revenue", "value": revenue, "period": "monthly", "calculable": revenue is not None, "estimated": estimated,
                "note": "Estimated at the average active billing rate for the same role." if estimated else "Uses each person's own billing rate."},
        impact_chain=["FDE unassigned", "No billable hours", "Foregone monthly revenue"],
        recommended_action="Put {} forward for open client roles{} before opening new hiring for the same role.".format(
            names, " ({})".format(", ".join(sorted({r["client"] for r in demand}))) if demand else ""),
        expected_effect="Up to {}/month of revenue recovered once placed.".format(_money(revenue)) if revenue else "Bench reduced.",
        data_sources=["people", "demand_forecast"] if demand else ["people"],
        impact_score=_impact(people=len(long), revenue=revenue),
        urgency_score=(100.0, "Revenue is being foregone now"),
        origins=["inferred" if estimated else "workbook"],
    )
    return {"rule": "R4", "name": name, "status": "triggered", "detail": "{} of {} bench FDEs beyond {} days.".format(
        len(long), len(bench), config.BENCH_DAYS_THRESHOLD), "recommendations": [rec]}


def rule_contracts(ctx: dict) -> dict:
    name = "Contract expiration"
    contracts = ctx["revenue"]["contracts"]
    if not contracts:
        return {"rule": "R5", "name": name, "status": "not_triggered",
                "detail": "No active contract ends within {} days.".format(config.CONTRACT_WARNING_DAYS), "recommendations": []}
    recs = []
    for c in contracts:
        urgent = c["days"] <= config.CONTRACT_URGENT_DAYS
        replacement = [r for r in ctx["revenue"]["capacity"]["rows"] if r["role"] == c["role"]]
        recs.append(_rec(
            id="contract-{}".format(c["id"]),
            rule_code="R5",
            rule_name=name,
            title="Review {} renewal ({})".format(c["client"], c["name"]),
            category="Deployment",
            summary="{}'s {} contract ends {} ({} days).".format(c["name"], c["client"], c["client_end"], c["days"]),
            why_it_matters="If the contract is not renewed, {}/month leaves the run-rate and {} returns to the bench.".format(
                _money(c["revenue"]), c["name"]),
            evidence=["Client: {}".format(c["client"]), "FDE: {} ({})".format(c["name"], c["role"]),
                      "Contract end: {}".format(c["client_end"]), "Monthly revenue: {}".format(_money(c["revenue"])),
                      "Days remaining: {}".format(c["days"])],
            metrics=[
                {"label": "Client", "value": c["client"]},
                {"label": "FDE", "value": c["name"]},
                {"label": "Contract end date", "value": c["client_end"]},
                {"label": "Monthly revenue", "value": _money(c["revenue"])},
                {"label": "Days remaining", "value": c["days"]},
                {"label": "Risk level", "value": c["risk"]["level"]},
            ],
            supporting_metrics=[{"label": "Open demand for {} at {}".format(r["role"], r["client"]), "value": "{} by {}".format(r["needed"], r["needed_by"])}
                                for r in replacement],
            triggered_by=[_trigger("Days to contract end", c["days"], config.CONTRACT_WARNING_DAYS, "people (Master-Input End_date_with_Current_Client)", "<=")],
            impact={"type": "revenue", "value": c["revenue"], "period": "monthly", "calculable": c["revenue"] is not None, "estimated": False,
                    "note": "Rate x hours/week x {} from the roster.".format(4)},
            impact_chain=["Contract end date", "No renewal", "FDE returns to bench", "Monthly revenue lost"],
            recommended_action=("Confirm renewal with {} this week; if it will not renew, line up {}'s next assignment now."
                                if urgent else "Start the renewal conversation with {}, and identify a next assignment for {} as a fallback.").format(
                c["client"], c["name"]),
            expected_effect="{}/month kept on the run-rate, or {} redeployed without bench time.".format(_money(c["revenue"]), c["name"]),
            data_sources=["people"],
            impact_score=_impact(revenue=c["revenue"]),
            urgency_score=_urgency_from_days(c["days"]),
            origins=["workbook"],
        ))
    return {"rule": "R5", "name": name, "status": "triggered", "detail": "{} contract(s) end within {} days.".format(
        len(recs), config.CONTRACT_WARNING_DAYS), "recommendations": recs}


def rule_resources(ctx: dict) -> dict:
    name = "Excessive resource consumption"
    acts = [a for a in ctx["activities"] if a["phase"] == "recruitment" and a["hours"]]
    total = sum(a["hours"] for a in acts)
    if total < config.RESOURCE_MIN_HOURS:
        return {"rule": "R6", "name": name, "status": "insufficient_data",
                "detail": "{:.0f} recruitment hours calculable; needs at least {} to compare stages.".format(total, config.RESOURCE_MIN_HOURS),
                "recommendations": []}
    recs = []
    for a in acts:
        share = a["hours"] / total
        if share < config.RESOURCE_SHARE_THRESHOLD:
            continue
        conversion = a["passed"] / a["units"] if a["passed"] is not None and a["units"] else None
        per_success = a["cost"] / a["passed"] if a["cost"] and a["passed"] else None
        backlog = a["waiting"] / a["units"] if a["waiting"] and a["units"] else 0
        origins = ["assumption"] + (["inferred"] if a["units_origin"] == "inferred" else ["workbook"])
        recs.append(_rec(
            id="resources-{}".format(a["code"]),
            rule_code="R6",
            rule_name=name,
            title="Review the {} process".format(a["label"]),
            category="Economics",
            summary="{} use {:.0%} of recruitment resource hours.".format(a["label"], share),
            why_it_matters="A single stage holding this much interviewer time limits how many candidates the team can move forward.",
            evidence=["{:,.0f} resource hours ({:.0%} of {:,.0f})".format(a["hours"], share, total),
                      "Resource cost {}".format(_money(a["cost"])),
                      "Pass-through {}".format("{:.0%}".format(conversion) if conversion is not None else "not reported"),
                      "Cost per successful candidate {}".format(_money(per_success) if per_success else "not calculable")],
            metrics=[
                {"label": "Resource hours", "value": "{:,.0f}".format(a["hours"])},
                {"label": "Resource cost", "value": _money(a["cost"])},
                {"label": "Share of recruitment hours", "value": "{:.0%}".format(share)},
                {"label": "Conversion (passed / entered)", "value": "{:.0%}".format(conversion) if conversion is not None else "Not reported"},
                {"label": "Cost per successful outcome", "value": _money(per_success) if per_success else "Not calculable"},
                {"label": "Volume basis", "value": "{} {} ({})".format(a["units"], a["driver_label"], a["units_origin"])},
            ],
            supporting_metrics=[{"label": "Rate assumption", "value": "{} h x ${}/h per unit".format(a["hours_per_unit"], a["hourly_cost_usd"])},
                                {"label": "Still waiting", "value": a["waiting"] if a["waiting"] is not None else "–"}],
            triggered_by=[_trigger("{} share of recruitment hours".format(a["label"]), "{:.0%}".format(share),
                                   "{:.0%}".format(config.RESOURCE_SHARE_THRESHOLD), "pipeline_weeks volumes x resource_rates")],
            impact={"type": "cost", "value": a["cost"], "period": "period", "calculable": a["cost"] is not None, "estimated": True,
                    "note": "Cost uses editable rate assumptions."},
            impact_chain=["High hours at one stage", "Interviewer time unavailable elsewhere", "Slower funnel", "Higher cost per hire"],
            recommended_action="Review {} format: shorten or split the panel, add a pre-screen gate, or move part of it to the assessment.".format(a["label"]),
            expected_effect="Lower hours per candidate at this stage without reducing pass quality.",
            data_sources=["pipeline_weeks", "resource_rates"],
            impact_score=(share * 100, "{:.0%} share of recruitment hours".format(share)),
            urgency_score=(backlog * 100 if backlog else float(config.STRATEGIC_URGENCY),
                           "{:.0%} of stage volume still waiting".format(backlog) if backlog else "No backlog; strategic default"),
            origins=origins,
        ))
    top = max(acts, key=lambda a: a["hours"])
    detail = "{} activit{} at or above {:.0%} of recruitment hours.".format(len(recs), "y" if len(recs) == 1 else "ies", config.RESOURCE_SHARE_THRESHOLD) if recs \
        else "Largest is {} at {:.0%}, below {:.0%}.".format(top["label"], top["hours"] / total, config.RESOURCE_SHARE_THRESHOLD)
    return {"rule": "R6", "name": name, "status": "triggered" if recs else "not_triggered", "detail": detail, "recommendations": recs}


def rule_mobility(ctx: dict) -> dict:
    name = "Internal mobility opportunity"
    sources = {s["source"]: s for s in ctx["sources"]}
    internal = sources.get("Internal")
    external = sources.get("External")
    if not internal or not external or internal["joined"] < config.MOBILITY_MIN_PEOPLE or external["joined"] < config.MOBILITY_MIN_PEOPLE:
        return {"rule": "R7", "name": name, "status": "insufficient_data",
                "detail": "Needs at least {} joined people from both Internal and External sources.".format(config.MOBILITY_MIN_PEOPLE), "recommendations": []}
    academy_days = config.TRAINING_PROGRAM_WEEKS * 7
    ext_days = []
    for p in ctx["roster"]:
        if (p["source"] or "") != "External" or p["bucket"] == "Yet to join":
            continue
        if p["client_start"]:
            ext_days.append(max(0, (date.fromisoformat(p["client_start"]) - date.fromisoformat(p["start_date"])).days))
        elif p["career_stage"] == "Trainee":
            ext_days.append(academy_days)
    int_days = internal["avg_days_to_deploy"]
    ext_avg = sum(ext_days) / len(ext_days) if ext_days else None
    if int_days is None or ext_avg is None:
        return {"rule": "R7", "name": name, "status": "insufficient_data", "detail": "Time to deployment not calculable for both groups.", "recommendations": []}
    faster = 1 - (int_days / ext_avg) if ext_avg else 0
    detail = "Internal avg {:.0f} days to client vs external at least {:.0f} days (academy counted at {} days).".format(int_days, ext_avg, academy_days)
    if faster < config.MOBILITY_MIN_GAP:
        return {"rule": "R7", "name": name, "status": "not_triggered", "detail": detail, "recommendations": []}
    training_cost = sum(a["cost"] or 0 for a in ctx["activities"] if a["phase"] == "training")
    trainees = len(ctx["trainees"])
    per_trainee = training_cost / trainees if trainees else None
    counter = []
    if internal.get("applications"):
        counter.append("Counter-signal: internal hiring rows show {} applications, {} accepted, {} rejected.".format(
            internal["applications"], internal["accepted"] or 0, internal["rejected"] or 0))
    rec = _rec(
        id="mobility-internal",
        rule_code="R7",
        rule_name=name,
        title="Increase internal recruitment activity",
        category="Recruitment",
        summary="Internal hires reach a client in {:.0f} days on average vs at least {:.0f} for external hires.".format(int_days, ext_avg),
        why_it_matters="Faster time to client means earlier revenue and no academy cost per hire.",
        evidence=[detail,
                  "Internal deployment rate {:.0%} ({} of {} joined)".format(internal["deployment_rate"] or 0, internal["deployed"], internal["joined"]),
                  "External deployment rate {:.0%} ({} of {} joined, {} in academy)".format(external["deployment_rate"] or 0, external["deployed"],
                                                                                         external["joined"], external["trainees"])]
                 + (["Training cost per external trainee in period: {}".format(_money(per_trainee))] if per_trainee else []) + counter,
        metrics=[
            {"label": "Internal time to client (avg days)", "value": "{:.0f}".format(int_days)},
            {"label": "External time to client (avg days, min)", "value": "{:.0f}".format(ext_avg)},
            {"label": "Internal deployment rate", "value": "{:.0%}".format(internal["deployment_rate"] or 0)},
            {"label": "External deployment rate", "value": "{:.0%}".format(external["deployment_rate"] or 0)},
            {"label": "Internal cost per hire", "value": _money(internal["cost_per_hire"]) if internal["cost_per_hire"] else "Not calculable (no accepted offers on internal rows)"},
            {"label": "External cost per hire", "value": _money(external["cost_per_hire"]) if external["cost_per_hire"] else "Not calculable"},
        ],
        supporting_metrics=[{"label": "Academy length assumed for trainees", "value": "{} days".format(academy_days)}],
        triggered_by=[_trigger("Internal time-to-client advantage", "{:.0%} faster".format(faster), "{:.0%}".format(config.MOBILITY_MIN_GAP),
                               "people (Master-Input start and client dates)")],
        impact=_no_revenue("Revenue impact cannot currently be calculated: it depends on how many additional internal candidates exist."),
        impact_chain=["More internal hires", "Shorter time to client", "Earlier billing", "Lower training cost"],
        recommended_action="Run an internal mobility drive for FDE roles and pre-qualify internal applicants before the self-assessment step.",
        expected_effect="More hires who reach a client in about {:.0f} days instead of {:.0f}+.".format(int_days, ext_avg),
        data_sources=["people", "pipeline_weeks"],
        impact_score=(faster * 100, "{:.0%} shorter time to client".format(faster)),
        urgency_score=(float(config.STRATEGIC_URGENCY), "Strategic, no deadline"),
        origins=["inferred"] + (["assumption"] if per_trainee else []),
    )
    return {"rule": "R7", "name": name, "status": "triggered", "detail": detail, "recommendations": [rec]}


def rule_source(ctx: dict) -> dict:
    name = "Recruitment source inefficiency"
    recs = []
    checked = 0
    for s in ctx["sources"]:
        apps = s.get("applications")
        if not apps or apps < config.SOURCE_MIN_APPLICANTS or s.get("rejected") is None:
            continue
        checked += 1
        share = s["rejected"] / apps
        if share < config.SOURCE_REJECT_SHARE or (s.get("accepted") or 0) > 0:
            continue
        recs.append(_rec(
            id="source-{}".format(_slug(s["source"])),
            rule_code="R8",
            rule_name=name,
            title="Tighten {} candidate pre-qualification".format(s["source"]),
            category="Recruitment",
            summary="{} of {} {} applicants rejected and none accepted yet.".format(s["rejected"], apps, s["source"]),
            why_it_matters="Screening and interviewing candidates who are rejected uses recruiter and interviewer time with no hire.",
            evidence=["{} applications".format(apps), "{} rejected ({:.0%})".format(s["rejected"], share), "0 accepted offers",
                      "Recruitment effort on this source: {}".format(_money(s["recruitment_cost"]))],
            metrics=[
                {"label": "Applications", "value": apps},
                {"label": "Rejected", "value": s["rejected"]},
                {"label": "Reject share", "value": "{:.0%}".format(share)},
                {"label": "Accepted", "value": s.get("accepted") or 0},
                {"label": "Recruitment cost on source", "value": _money(s["recruitment_cost"])},
            ],
            supporting_metrics=[],
            triggered_by=[_trigger("{} reject share".format(s["source"]), "{:.0%}".format(share), "{:.0%}".format(config.SOURCE_REJECT_SHARE),
                                   "pipeline_weeks (Applications_total, Rejected)"),
                          _trigger("{} accepted offers".format(s["source"]), 0, 0, "pipeline_weeks (Offer_accepted)", "=")],
            impact={"type": "cost", "value": s["recruitment_cost"], "period": "period", "calculable": True, "estimated": True,
                    "note": "Effort spent on this source with no hire yet (rate assumptions)."},
            impact_chain=["Low-fit applicants", "Screening and interview time spent", "No hires", "Higher cost per hire"],
            recommended_action="Add a short eligibility check before the {} self-assessment and share the role rubric with applicants.".format(s["source"].lower()),
            expected_effect="Lower reject share and fewer interview hours per hire from this source.",
            data_sources=["pipeline_weeks", "resource_rates"],
            impact_score=_impact(people=s["rejected"]),
            urgency_score=(float(config.STRATEGIC_URGENCY), "Strategic, no deadline"),
            origins=["workbook", "assumption"],
        ))
    if not checked:
        return {"rule": "R8", "name": name, "status": "insufficient_data",
                "detail": "No source has {}+ reported applications with a reject count.".format(config.SOURCE_MIN_APPLICANTS), "recommendations": []}
    return {"rule": "R8", "name": name, "status": "triggered" if recs else "not_triggered",
            "detail": "{} source(s) checked; {} flagged.".format(checked, len(recs)), "recommendations": recs}


RULES = (rule_bottleneck, rule_cohort, rule_capacity, rule_bench, rule_contracts, rule_resources, rule_mobility, rule_source)


# ---------------------------------------------------------------- page


def _statuses(db: Session, recs: List[dict]) -> Dict[str, RecommendationStatus]:
    rows = {row.rec_id: row for row in db.query(RecommendationStatus).all()}
    now = datetime.now()
    for rec in recs:
        if rec["id"] not in rows:
            row = RecommendationStatus(rec_id=rec["id"], status="OPEN", first_seen=now, updated_at=now)
            db.add(row)
            rows[rec["id"]] = row
    db.commit()
    return rows


def build_actions(db: Session, filters: Filters) -> dict:
    ctx = compute(db, filters)
    evaluations = [rule(ctx) for rule in RULES]
    recs = []
    for ev in evaluations:
        rule_recs = ev.pop("recommendations")
        ev["count"] = len(rule_recs)
        recs.extend(rule_recs)
    status_rows = _statuses(db, recs)
    generated = datetime.now().isoformat(timespec="seconds")
    freshness = {
        "hiring_week": ctx["week"].isoformat() if ctx["week"] else None,
        "training_week": ctx["training"]["latest"]["week"] if ctx["training"]["latest"] else None,
        "roster_as_of": ctx["as_of"].isoformat(),
        "generated_at": generated,
    }
    for rec in recs:
        row = status_rows[rec["id"]]
        rec["status"] = row.status
        rec["status_updated_at"] = row.updated_at.isoformat(timespec="seconds")
        rec["created_at"] = row.first_seen.isoformat(timespec="seconds")
        rec["data_freshness"] = freshness
    recs.sort(key=lambda r: (-r["score"], r["title"]))
    for index, rec in enumerate(recs, start=1):
        rec["rank"] = index
    open_recs = [r for r in recs if r["status"] == "OPEN"]
    revenue = ctx["revenue"]
    people_at_risk = len(revenue["bench"]) + len(revenue["contracts"])
    return {
        "as_of": ctx["as_of"].isoformat(),
        "generated_at": generated,
        "week_ending": freshness["hiring_week"],
        "filters": filters.as_json(),
        "options": options(db),
        "notes": ctx["notes"],
        "kpis": {
            "open": len(open_recs),
            "high": sum(1 for r in open_recs if r["priority"] == "HIGH"),
            "total": len(recs),
            "revenue_at_risk": revenue["total_at_risk"],
            "existing_at_risk": revenue["existing_at_risk"],
            "contracts_ending": len(revenue["contracts"]),
            "people_at_risk": people_at_risk,
            "people_at_risk_detail": "{} on bench + {} with contracts ending in {} days".format(
                len(revenue["bench"]), len(revenue["contracts"]), config.CONTRACT_WARNING_DAYS),
            "capacity_gap": revenue["capacity"]["gap_fdes"],
            "capacity_is_demo": revenue["capacity"]["any_demo"],
        },
        "recommendations": recs,
        "rules": evaluations,
        "coverage": _coverage(db, ctx),
        "config": config.as_dict(),
    }


def set_status(db: Session, rec_id: str, status: str) -> dict:
    status = (status or "").upper()
    if status not in STATUSES:
        raise ValueError("Status must be one of {}.".format(", ".join(STATUSES)))
    row = db.query(RecommendationStatus).filter(RecommendationStatus.rec_id == rec_id).first()
    now = datetime.now()
    if row is None:
        row = RecommendationStatus(rec_id=rec_id, status=status, first_seen=now, updated_at=now)
        db.add(row)
    else:
        row.status = status
        row.updated_at = now
    db.commit()
    return {"id": rec_id, "status": row.status, "updated_at": row.updated_at.isoformat(timespec="seconds")}
