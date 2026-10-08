"""Rule-based assistant.

Matches the question against keyword intents and answers from the same
builders the dashboards use, so replies always reflect live data. No LLM.
"""

import re
from datetime import date
from typing import Callable, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.analytics import build_cohort, build_deployment, build_recruitment
from app.economics import Filters
from app.recommendations import build_actions

SUGGESTIONS = [
    "How is the pipeline?",
    "Where is the bottleneck?",
    "How is interview feedback?",
    "What is our monthly revenue?",
    "Who is on the bench?",
    "Which contracts end soon?",
    "How is the academy cohort doing?",
    "What should leadership do?",
]


def _money(value: Optional[float]) -> str:
    if value is None:
        return "not reported"
    return "${:,.0f}".format(value)


def _pct(value: Optional[float]) -> str:
    if value is None:
        return "not reported"
    return "{:.0%}".format(value)


def _count(value: Optional[int], label: str) -> str:
    return "{} not reported".format(label) if value is None else "{} {}".format(value, label)


def _names(people: List[dict]) -> str:
    names = [person["name"] for person in people]
    if len(names) <= 2:
        return " and ".join(names)
    return "{}, and {}".format(", ".join(names[:-1]), names[-1])


def _greeting(db: Session, as_of: date) -> str:
    return (
        "Hi! I can answer questions about hiring, deployment, revenue, the academy cohort, "
        "and leadership actions. Try one of the suggestions below, or ask about a person by name."
    )


def _pipeline(db: Session, as_of: date) -> str:
    data = build_recruitment(db, None, as_of)
    if not data["cohorts"]:
        return "No hiring data has been loaded yet."
    lines = ["For the week ending {}:".format(data["week_ending"])]
    for cohort in data["cohorts"]:
        s = cohort["summary"]
        lines.append(
            "• {}: {}, {}, {}, {}.".format(
                cohort["name"], _count(s["in_pipeline"], "in pipeline"), _count(s["in_cto"], "in the CTO round"),
                _count(s["offers_accepted"], "offers accepted"), _count(s["rejected"], "rejected"),
            )
        )
    return "\n".join(lines)


def _bottleneck(db: Session, as_of: date) -> str:
    data = build_recruitment(db, None, as_of)
    pressure = data.get("pressure")
    if not pressure:
        return "No hiring data has been loaded yet, so I can't tell where the bottleneck is."
    return "{} (week ending {}). {}".format(
        pressure["headline"][:1].upper() + pressure["headline"][1:], data["week_ending"], pressure["detail"]
    )


def _offers(db: Session, as_of: date) -> str:
    data = build_recruitment(db, None, as_of)
    if not data["cohorts"]:
        return "No hiring data has been loaded yet."
    lines = ["Offers and joiners for the week ending {}:".format(data["week_ending"])]
    for cohort in data["cohorts"]:
        s = cohort["summary"]
        lines.append("• {}: {}, {}.".format(
            cohort["name"], _count(s["offers_accepted"], "offers accepted"), _count(s["joined"], "joined")))
    return "\n".join(lines)


def _feedback(db: Session, as_of: date) -> str:
    data = build_recruitment(db, None, as_of)
    blocks = [c for c in data["cohorts"] if c.get("feedback", {}).get("overall", {}).get("total")]
    if not blocks:
        return "No interview feedback has been recorded yet."
    lines = ["Interview feedback up to the week ending {} (sample data):".format(data["week_ending"])]
    for cohort in blocks:
        o = cohort["feedback"]["overall"]
        lines.append("• {}: {} strong hire, {} hire, {} no hire, {} strong no hire ({} hire rate).".format(
            cohort["name"], o["strong_hire"], o["hire"], o["no_hire"], o["strong_no_hire"], _pct(o["hire_rate"])))
    return "\n".join(lines)


def _revenue(db: Session, as_of: date) -> str:
    d = build_deployment(db, as_of)
    text = "Monthly run-rate is {} ({} annualized) from {} FDEs active at clients, at an average of {}/hr.".format(
        _money(d["monthly_revenue"]), _money(d["annualized_revenue"]), d["active_at_client"],
        _money(d["avg_rate"]) if d["avg_rate"] is not None else "an unknown rate",
    )
    if d["revenue_at_risk"]:
        text += " {} a month is at risk from {} contract(s) ending within 60 days.".format(
            _money(d["revenue_at_risk"]), d["contracts_ending_soon"])
    return text


def _utilization(db: Session, as_of: date) -> str:
    d = build_deployment(db, as_of)
    return "Utilization is {}: {} of {} joined FDEs (excluding trainees) are active at a client.".format(
        _pct(d["utilization"]), d["active_at_client"], d["joined_fdes"])


def _bench(db: Session, as_of: date) -> str:
    d = build_deployment(db, as_of)
    bench = [p for p in d["roster"] if p["bucket"] == "On bench"]
    if not bench:
        return "Nobody is on the bench right now."
    return "{} FDE{} on the bench: {}.".format(
        len(bench), " is" if len(bench) == 1 else "s are", _names(bench))


def _contracts(db: Session, as_of: date) -> str:
    d = build_deployment(db, as_of)
    ending = sorted((p for p in d["roster"] if p["ending_soon"]), key=lambda p: p["days_to_contract_end"])
    if not ending:
        return "No active contracts end within the next 60 days."
    lines = ["{} contract(s) end within 60 days:".format(len(ending))]
    for p in ending:
        lines.append("• {} at {}: ends {} ({} days), {}/mo.".format(
            p["name"], p["client"], p["client_end"], p["days_to_contract_end"], _money(p["monthly_revenue"])))
    return "\n".join(lines)


def _clients(db: Session, as_of: date) -> str:
    d = build_deployment(db, as_of)
    if not d["clients"]:
        return "No FDEs are active at a client right now."
    lines = ["Active clients, by monthly revenue:"]
    for c in d["clients"]:
        lines.append("• {}: {} FDE{}, {}/mo.".format(
            c["client"], c["active_fdes"], "" if c["active_fdes"] == 1 else "s", _money(c["monthly_revenue"])))
    return "\n".join(lines)


def _headcount(db: Session, as_of: date) -> str:
    d = build_deployment(db, as_of)
    return (
        "Headcount is {}: {} active at a client, {} on the bench, {} in training, "
        "{} starting at a client soon, and {} yet to join."
    ).format(d["headcount"], d["active_at_client"], d["on_bench"], d["in_training"],
             d["starting_soon"], d["yet_to_join"])


def _locations(db: Session, as_of: date) -> str:
    d = build_deployment(db, as_of)
    if not d["locations"]:
        return "No people are on the roster yet."
    lines = ["People by location (available now / later):"]
    for loc in d["locations"]:
        lines.append("• {}: {} total ({} now, {} later).".format(
            loc["location"], loc["total"], loc["now"], loc["later"]))
    return "\n".join(lines)


def _training(db: Session, as_of: date) -> str:
    c = build_cohort(db, as_of)
    latest = c["latest"]
    if not latest:
        return "No academy week has been scored yet."
    text = "Week {} ({}) overall score is {}".format(
        latest["week"], latest["topic"] or "no topic", _pct(latest["overall"]))
    if c["change_vs_previous"] is not None:
        pts = round(c["change_vs_previous"] * 100)
        text += ", {} {} pts vs week {}".format("up" if pts >= 0 else "down", abs(pts), c["previous_week"])
    if c["weeks_reported"] > 1:
        text += ". Average across {} reported weeks is {}".format(c["weeks_reported"], _pct(c["average_overall"]))
    text += "."
    if latest["active_students"] is not None:
        text += " {} active students.".format(latest["active_students"])
    return text


def _actions(db: Session, as_of: date) -> str:
    data = build_actions(db, Filters(end=as_of))
    open_recs = [r for r in data["recommendations"] if r["status"] == "OPEN"]
    if not open_recs:
        return "There are no open leadership actions right now."
    lines = ["{} open action(s), {} high priority. Top ones:".format(len(open_recs), data["kpis"]["high"])]
    for rec in open_recs[:3]:
        lines.append("• [{}] {}: {}".format(rec["priority"], rec["title"], rec["summary"]))
    return "\n".join(lines)


Handler = Callable[[Session, date], str]

INTENTS: List[Tuple[Handler, Tuple[str, ...]]] = [
    (_greeting, ("hi", "hello", "hey", "help", "what can you do")),
    (_feedback, ("feedback", "strong hire", "no hire", "verdict", "verdicts", "interviewer", "interviewers", "hire rate")),
    (_bottleneck, ("bottleneck", "slot", "slots", "interview", "l2", "capacity", "stuck")),
    (_offers, ("offer", "offers", "accepted", "joined", "joiners")),
    (_pipeline, ("pipeline", "hiring", "recruit", "recruitment", "candidates", "funnel", "cto", "rejected")),
    (_revenue, ("revenue", "money", "earn", "billing", "run-rate", "run rate", "income")),
    (_utilization, ("utilization", "utilisation", "utilized", "deployed")),
    (_bench, ("bench", "unassigned", "idle", "free")),
    (_contracts, ("contract", "contracts", "ending", "renewal", "expire", "risk")),
    (_clients, ("client", "clients", "customer", "customers", "account")),
    (_headcount, ("headcount", "people", "team", "staff", "how many", "roster")),
    (_locations, ("location", "locations", "where", "country", "india", "usa", "uk")),
    (_training, ("training", "academy", "cohort", "score", "trainee", "trainees", "students")),
    (_actions, ("action", "actions", "recommend", "recommendation", "should", "leadership", "priority")),
]


def _score(text: str, keywords: Tuple[str, ...]) -> int:
    return sum(1 for word in keywords if re.search(r"\b{}\b".format(re.escape(word)), text))


def _person(db: Session, as_of: date, text: str) -> Optional[str]:
    roster = build_deployment(db, as_of)["roster"]
    match = [p for p in roster if p["name"].lower() in text]
    if not match:
        firsts: Dict[str, List[dict]] = {}
        for p in roster:
            firsts.setdefault(p["name"].split()[0].lower(), []).append(p)
        for first, people in firsts.items():
            if len(first) >= 3 and len(people) == 1 and re.search(r"\b{}\b".format(re.escape(first)), text):
                match = people
                break
    if not match:
        return None
    p = match[0]
    answer = "{} is a {} based in {}, currently {}.".format(
        p["name"], p["career_stage"], p["location"], p["bucket"].lower())
    if p["client"]:
        answer += " Client: {} ({} to {}).".format(p["client"], p["client_start"] or "?", p["client_end"] or "open-ended")
    if p["monthly_revenue"]:
        answer += " Bills {}/mo.".format(_money(p["monthly_revenue"]))
    if p["issues"]:
        answer += " Data issues: {}.".format("; ".join(p["issues"]).lower())
    return answer


def reply(db: Session, message: str, as_of: date) -> dict:
    text = (message or "").strip().lower()
    if not text:
        return {"reply": _greeting(db, as_of), "suggestions": SUGGESTIONS}
    person = _person(db, as_of, text)
    if person:
        return {"reply": person, "suggestions": SUGGESTIONS[:3]}
    scored = [(_score(text, keywords), handler) for handler, keywords in INTENTS]
    best, handler = max(scored, key=lambda item: item[0])
    if best == 0:
        return {
            "reply": "Sorry, I don't have an answer for that. I can help with hiring, revenue, bench, contracts, clients, training, and leadership actions.",
            "suggestions": SUGGESTIONS,
        }
    return {"reply": handler(db, as_of), "suggestions": SUGGESTIONS[:4]}
