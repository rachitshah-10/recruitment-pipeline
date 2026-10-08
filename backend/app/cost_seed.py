"""Seed the tables the workbook does not cover: resource rates and demand.

Kept out of seed.py so hiring/roster imports stay untouched. Startup
inserts a row only when its key is missing, so edited values survive.
"""

from datetime import date

from app.database import SessionLocal
from app.models import DemandForecast, ResourceRate

# code, label, phase, stage, driver, cost_type, resource_role,
# hours_per_unit, hourly_cost_usd, unit_cost_usd, weekly_capacity_units, notes
PLACEHOLDER_RATES = (
    ("sourcing", "Sourcing / job boards", "recruitment", "applicant", "applications", "external", None,
     None, None, 25.0, None, "External spend per application received."),
    ("recruiter_screening", "Recruiter screening", "recruitment", "applicant", "screening", "internal", "Recruiter",
     0.75, 45.0, None, 40.0, "Recruiter time per screened candidate."),
    ("l1_interview", "L1 interviews", "recruitment", "interview", "l1", "internal", "FDE interviewer",
     1.0, 70.0, None, 30.0, "One interviewer, one hour."),
    ("assessment_review", "Assessment (Berribot) review", "recruitment", "interview", "berribot", "internal", "FDE interviewer",
     0.25, 70.0, None, 60.0, "Internal review of each automated assessment."),
    ("assessment_license", "Assessment (Berribot) licence", "recruitment", "interview", "berribot", "external", None,
     None, None, 15.0, None, "External spend per assessment taken."),
    ("l2_interview", "L2 interviews", "recruitment", "interview", "l2", "internal", "Senior interviewer panel",
     2.0, 85.0, None, 20.0, "Two-person panel, one hour each."),
    ("l3_interview", "L3 interviews", "recruitment", "interview", "l3", "internal", "Principal interviewer",
     1.5, 95.0, None, 10.0, "Principal interviewer, 90 minutes."),
    ("cto_interview", "CTO interviews", "recruitment", "interview", "cto", "internal", "CTO",
     1.0, 200.0, None, 6.0, "CTO final round."),
    ("offer_processing", "Offer processing", "recruitment", "offer", "offers", "internal", "Recruiter",
     2.0, 45.0, None, None, "Approvals, letters, negotiation."),
    ("background_check", "Background check", "recruitment", "accepted", "accepted", "external", None,
     None, None, 150.0, None, "External spend per accepted offer."),
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
        existing = {row[0] for row in db.query(ResourceRate.code).all()}
        for order, row in enumerate(PLACEHOLDER_RATES):
            code, label, phase, stage, driver, cost_type, role, hours, hourly, unit, capacity, notes = row
            if code in existing:
                continue
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
