"""Seed the tables the workbook does not cover: resource rates and demand.

Kept out of seed.py so hiring/roster imports stay untouched. Startup
inserts a row only when its key is missing, so edited values survive.
"""

from datetime import date

from app.database import SessionLocal
from app.models import DemandForecast, ResourceRate

# code, label, phase, stage, driver, cost_type, resource_role,
# hours_per_unit, hourly_cost_usd, unit_cost_usd, weekly_capacity_units, notes
# Interview process: resume screening, Berribot, L1, L2, CTO, HR, background verification, offer.
# The workbook has no HR-round column. L3 on the sheet is not a step in this process.
PLACEHOLDER_RATES = (
    ("sourcing", "Sourcing / job boards", "recruitment", "applicant", "applications", "external", None,
     None, None, 25.0, None, "External spend per application received."),
    ("recruiter_screening", "Resume screening", "recruitment", "applicant", "screening", "internal", "Recruiter",
     0.75, 45.0, None, 40.0, "Recruiter time per resume screened."),
    ("assessment_review", "Berribot interview", "recruitment", "interview", "berribot", "internal", "Reviewer",
     0.25, 70.0, None, 60.0, "Internal time to review each Berribot interview."),
    ("assessment_license", "Berribot interview licence", "recruitment", "interview", "berribot", "external", None,
     None, None, 15.0, None, "External spend per Berribot interview."),
    ("l1_interview", "L1 interview", "recruitment", "interview", "l1", "internal", "Senior FDE",
     1.0, 70.0, None, 30.0, "One senior FDE, one hour."),
    ("l2_interview", "L2 interview", "recruitment", "interview", "l2", "internal", "Senior FDE",
     1.0, 85.0, None, 20.0, "One senior FDE, one hour."),
    ("cto_interview", "CTO round", "recruitment", "interview", "cto", "internal", "CTO",
     1.0, 200.0, None, 6.0, "CTO round, one hour."),
    ("hr_round", "HR round", "recruitment", "interview", "hr", "internal", "HR",
     1.0, 45.0, None, None, "Workbook has no HR-round count, so this step has no volume."),
    ("background_check", "Background verification", "recruitment", "verification", "accepted", "external", None,
     None, None, 150.0, None, "External spend per accepted offer. The sheet has no separate verification count."),
    ("offer_processing", "Offer", "recruitment", "offer", "offers", "internal", "Recruiter",
     2.0, 45.0, None, None, "Approvals, letters, negotiation."),
    ("trainer_delivery", "Training delivery", "training", "training", "academy_weeks", "internal", "Trainer",
     30.0, 60.0, None, None, "Trainer hours per academy week, per running academy."),
    ("trainer_grading", "Training grading & mentoring", "training", "training", "trainee_weeks", "internal", "Trainer",
     0.5, 60.0, None, None, "Trainer hours per trainee per week."),
    ("training_platform", "Training platform", "training", "training", "trainee_weeks", "external", None,
     None, None, 40.0, None, "External spend per trainee per week."),
    ("client_onboarding", "Client onboarding", "deployment", "deployment", "deployments", "internal", "Delivery manager",
     8.0, 90.0, None, None, "Delivery manager hours per new client assignment."),
)

# client, role, location, fdes_needed, needed_by, hourly_rate, hours_per_week
DEMO_DEMAND = (
    ("TriNet", "Senior FDE", "USA", 2, date(2026, 11, 15), 100.0, 40.0),
    ("PMI", "Senior FDE", "USA", 1, date(2026, 12, 1), 100.0, 40.0),
    ("New logo (in negotiation)", "FDE", "USA", 4, date(2026, 12, 15), 75.0, 40.0),
    ("SEI", "Associate FDE", "USA", 4, date(2027, 1, 15), 60.0, 40.0),
)


def ensure_cost_rates():
    db = SessionLocal()
    try:
        known = {row.code: row for row in db.query(ResourceRate).all()}
        keep = set()
        for order, row in enumerate(PLACEHOLDER_RATES):
            code, label, phase, stage, driver, cost_type, role, hours, hourly, unit, capacity, notes = row
            keep.add(code)
            current = known.get(code)
            if current is None:
                db.add(
                    ResourceRate(
                        code=code,
                        label=label,
                        phase=phase,
                        stage=stage,
                        driver=driver,
                        cost_type=cost_type,
                        resource_role=role,
                        hours_per_unit=hours,
                        hourly_cost_usd=hourly,
                        unit_cost_usd=unit,
                        weekly_capacity_units=capacity,
                        sort_order=order,
                        is_placeholder=1,
                        notes=notes,
                    )
                )
                continue
            current.label = label
            current.phase = phase
            current.stage = stage
            current.driver = driver
            current.cost_type = cost_type
            current.resource_role = role
            current.sort_order = order
            current.notes = notes
            if current.is_placeholder:
                current.hours_per_unit = hours
                current.hourly_cost_usd = hourly
                current.unit_cost_usd = unit
                current.weekly_capacity_units = capacity
        for code, row in known.items():
            if code not in keep:
                db.delete(row)
        if not db.query(DemandForecast).count():
            for client, role, location, needed, needed_by, rate, hours in DEMO_DEMAND:
                db.add(
                    DemandForecast(
                        client=client,
                        role=role,
                        location=location,
                        fdes_needed=needed,
                        needed_by=needed_by,
                        hourly_rate=rate,
                        hours_per_week=hours,
                        status="open",
                        is_demo=1,
                    )
                )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
