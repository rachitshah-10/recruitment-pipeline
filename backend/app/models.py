from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint

from app.database import Base


class PipelineWeek(Base):
    """One HR row: a cohort and role for a single week ending."""

    __tablename__ = "pipeline_weeks"

    id = Column(Integer, primary_key=True)
    week_ending = Column(Date, nullable=False, index=True)
    cohort = Column(String, nullable=False)
    role = Column(String, nullable=False)
    source = Column(String)
    applications_total = Column(Integer)
    screening_pending = Column(Integer)
    screening_cleared = Column(Integer)
    l1_pending = Column(Integer)
    l1_cleared = Column(Integer)
    berribot_applied = Column(Integer)
    berribot_cleared = Column(Integer)
    l2_pending = Column(Integer)
    l2_cleared = Column(Integer)
    l3_pending = Column(Integer)
    l3_cleared = Column(Integer)
    cto_pending = Column(Integer)
    cto_cleared = Column(Integer)
    offer_extended = Column(Integer)
    offer_accepted = Column(Integer)
    joined = Column(Integer)
    on_hold = Column(Integer)
    rejected = Column(Integer)
    slots_needed = Column(Integer)
    notes = Column(Text)


class TrainingWeek(Base):
    __tablename__ = "training_weeks"

    id = Column(Integer, primary_key=True)
    week = Column(Integer, nullable=False, unique=True)
    hands_on = Column(Float)
    proctored = Column(Float)
    overall = Column(Float)
    active_students = Column(Integer)
    topic = Column(String)


class Person(Base):
    __tablename__ = "people"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    location = Column(String, nullable=False)
    career_stage = Column(String, nullable=False)
    start_date = Column(Date, nullable=False)
    source = Column(String)
    client = Column(String)
    client_start = Column(Date)
    client_end = Column(Date)
    hourly_rate = Column(Float)
    hours_per_week = Column(Float)


class ResourceRate(Base):
    """How much internal time or external spend one unit of an activity uses.

    The workbook has no resource hours or costs, so these rows are
    editable assumptions. Volumes always come from the workbook; only the
    per-unit hours and costs live here.
    """

    __tablename__ = "resource_rates"

    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False, unique=True)
    label = Column(String, nullable=False)
    phase = Column(String, nullable=False)  # recruitment | training | deployment
    stage = Column(String, nullable=False)  # applicant | interview | offer | accepted | training | deployment
    driver = Column(String, nullable=False)  # which volume this activity scales with
    cost_type = Column(String, nullable=False)  # internal | external
    resource_role = Column(String)
    hours_per_unit = Column(Float)
    hourly_cost_usd = Column(Float)
    unit_cost_usd = Column(Float)
    weekly_capacity_units = Column(Float)
    sort_order = Column(Integer, nullable=False, default=100)
    is_placeholder = Column(Integer, nullable=False, default=1)
    notes = Column(Text)


class DemandForecast(Base):
    """Open client demand for FDEs. Not in the workbook; seeded rows are demo."""

    __tablename__ = "demand_forecast"

    id = Column(Integer, primary_key=True)
    client = Column(String, nullable=False)
    role = Column(String, nullable=False)
    location = Column(String)
    fdes_needed = Column(Integer, nullable=False)
    needed_by = Column(Date, nullable=False)
    hourly_rate = Column(Float)
    hours_per_week = Column(Float)
    status = Column(String, nullable=False, default="open")
    is_demo = Column(Integer, nullable=False, default=1)


class InterviewFeedback(Base):
    """One interviewer's verdict on a candidate. Not in the workbook; seeded rows are demo."""

    __tablename__ = "interview_feedback"

    id = Column(Integer, primary_key=True)
    cohort = Column(String, nullable=False)
    role = Column(String, nullable=False)
    candidate = Column(String, nullable=False)
    round = Column(String, nullable=False)  # L1 | L2 | CTO
    interviewer = Column(String, nullable=False)
    rating = Column(String, nullable=False)  # Strong hire | Hire | No hire | Strong no hire
    comment = Column(Text)
    interview_date = Column(Date, nullable=False, index=True)
    is_demo = Column(Integer, nullable=False, default=1)


class AcademyCohort(Base):
    """One academy batch. Academy A is the workbook roster; B and C are illustrative."""

    __tablename__ = "academy_cohorts"

    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    start_date = Column(Date, nullable=False)
    program_weeks = Column(Integer, nullable=False)
    source = Column(String, nullable=False)  # workbook | demo


class TraineeProfile(Base):
    """A person inside an academy cohort, with the resume fields the readiness score uses."""

    __tablename__ = "trainee_profiles"

    id = Column(Integer, primary_key=True)
    cohort_id = Column(Integer, ForeignKey("academy_cohorts.id"), nullable=False, index=True)
    person_id = Column(Integer)
    name = Column(String, nullable=False)
    location = Column(String, nullable=False)
    hire_source = Column(String)
    years_experience = Column(Float, nullable=False)
    education = Column(String, nullable=False)
    skills = Column(Text, nullable=False)
    certifications = Column(Text)
    client = Column(String)
    client_start = Column(Date)
    is_demo = Column(Integer, nullable=False, default=1)


class TraineeWeekScore(Base):
    """Hands-on and proctored result for one trainee in one academy week."""

    __tablename__ = "trainee_week_scores"
    __table_args__ = (UniqueConstraint("trainee_id", "week", name="uq_trainee_week"),)

    id = Column(Integer, primary_key=True)
    trainee_id = Column(Integer, ForeignKey("trainee_profiles.id"), nullable=False, index=True)
    week = Column(Integer, nullable=False)
    hands_on = Column(Float, nullable=False)
    proctored = Column(Float, nullable=False)
    topic = Column(String)


class RecommendationStatus(Base):
    """Leadership decision on a generated recommendation, keyed by its stable id."""

    __tablename__ = "recommendation_status"

    id = Column(Integer, primary_key=True)
    rec_id = Column(String, nullable=False, unique=True)
    status = Column(String, nullable=False, default="OPEN")
    first_seen = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
