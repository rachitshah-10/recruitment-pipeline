"""Thresholds and weights for the Economics and Leadership Actions views.

Every rule and risk level reads from here. Change a number here and both
pages pick it up on the next refresh.
"""

# Rule 1 - recruitment bottleneck
QUEUE_THRESHOLD = 20  # candidates waiting at one stage
QUEUE_CLEAR_WEEKS = 2  # target weeks to clear a stage queue
INTERVIEWER_HOURS_PER_WEEK = 6  # interview hours one added interviewer can give per week
AVG_WAIT_DAYS_THRESHOLD = 5  # only used once candidate-level stage dates exist

# Rule 2 - cohort performance
READINESS_FLOOR = 0.90
DECLINE_WEEKS = 2  # consecutive reported weeks of decline
COMPONENT_GAP = 0.05  # hands-on vs proctored gap that counts as significant

# Rule 3 - capacity shortage
FORECAST_HORIZON_DAYS = 120
TRAINING_PROGRAM_WEEKS = 12
TRAINEE_GRADUATES_AS = "Associate FDE"

# Rule 4 - bench
BENCH_DAYS_THRESHOLD = 14

# Rule 5 - contract expiration
CONTRACT_WARNING_DAYS = 60
CONTRACT_URGENT_DAYS = 30

# Rule 6 - resource inefficiency
RESOURCE_SHARE_THRESHOLD = 0.35  # share of recruitment hours held by one activity
RESOURCE_MIN_HOURS = 40  # below this many recruitment hours, shares are too small to judge

# Rule 7 - internal mobility
MOBILITY_MIN_GAP = 0.20  # internal time-to-deployment must be at least this much shorter (relative)
MOBILITY_MIN_PEOPLE = 3  # minimum joined people in each group
STRATEGIC_URGENCY = 25  # urgency for rules with no deadline (process / sourcing changes)

# Rule 8 - recruitment source inefficiency
SOURCE_MIN_APPLICANTS = 10
SOURCE_REJECT_SHARE = 0.50

# Revenue-at-risk levels
RISK_HIGH_REVENUE = 15000  # USD per month
RISK_MEDIUM_REVENUE = 5000
RISK_HIGH_DAYS = 30
RISK_MEDIUM_DAYS = 60
DELAYED_DEPLOYMENT_DAYS = 45  # joiners/graduates within this window without a client

# Recommendation scoring. Weights must add up to 1.
SCORE_WEIGHTS = {
    "impact": 0.40,
    "urgency": 0.30,
    "revenue_risk": 0.20,
    "confidence": 0.10,
}
REVENUE_FULL_SCALE = 50000  # monthly USD that scores 100 on revenue risk
PEOPLE_FULL_SCALE = 25  # people affected that scores 100 on impact
URGENCY_HORIZON_DAYS = 90  # an event this far out scores 0 on urgency
PRIORITY_HIGH = 65
PRIORITY_MEDIUM = 40

# Confidence by where an input came from (0-100). A recommendation takes
# the lowest value among its inputs.
CONFIDENCE = {
    "workbook": 95,
    "inferred": 75,
    "assumption": 60,
    "demo": 40,
}

SOURCES = {
    "workbook": "Workbook (HR-Input, Input - Trainers, Master-Input)",
    "inferred": "Calculated from workbook counts",
    "assumption": "resource_rates (editable assumption)",
    "demo": "demand_forecast (demo seed)",
}


def as_dict() -> dict:
    return {
        "queue_threshold": QUEUE_THRESHOLD,
        "queue_clear_weeks": QUEUE_CLEAR_WEEKS,
        "interviewer_hours_per_week": INTERVIEWER_HOURS_PER_WEEK,
        "readiness_floor": READINESS_FLOOR,
        "bench_days_threshold": BENCH_DAYS_THRESHOLD,
        "contract_warning_days": CONTRACT_WARNING_DAYS,
        "resource_share_threshold": RESOURCE_SHARE_THRESHOLD,
        "risk_high_revenue": RISK_HIGH_REVENUE,
        "risk_medium_revenue": RISK_MEDIUM_REVENUE,
        "risk_high_days": RISK_HIGH_DAYS,
        "risk_medium_days": RISK_MEDIUM_DAYS,
        "score_weights": SCORE_WEIGHTS,
        "priority_high": PRIORITY_HIGH,
        "priority_medium": PRIORITY_MEDIUM,
        "confidence": CONFIDENCE,
    }
