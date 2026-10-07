from sqlalchemy import Column, Date, Float, Integer, String, Text

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
