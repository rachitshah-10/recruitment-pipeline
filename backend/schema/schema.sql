-- Momentuum Blue Recruitment Pipeline Dashboard
-- SQLite schema: tables, indexes, and reference/seed data
-- Apply: sqlite3 recruitment.db < backend/schema/schema.sql
-- Then:  sqlite3 recruitment.db < backend/schema/views.sql

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Reference / settings
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_stages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    code         TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    sort_order   INTEGER NOT NULL,
    is_terminal  INTEGER NOT NULL DEFAULT 0 CHECK (is_terminal IN (0, 1))
);

CREATE TABLE IF NOT EXISTS channels (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    code         TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS roles (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    code         TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS locations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    code         TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clients (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

-- ---------------------------------------------------------------------------
-- Cohorts
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cohorts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    target_size INTEGER NOT NULL DEFAULT 20,
    start_date  TEXT,                          -- ISO date YYYY-MM-DD
    status      TEXT NOT NULL DEFAULT 'planned'
                CHECK (status IN ('planned', 'recruiting', 'training', 'graduated', 'closed')),
    notes       TEXT
);

-- ---------------------------------------------------------------------------
-- People (roster) + deployment
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS people (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name     TEXT NOT NULL,
    location_id   INTEGER REFERENCES locations(id),
    career_stage  TEXT NOT NULL
                  CHECK (career_stage IN ('Trainee', 'FDE', 'Senior FDE', 'Associate FDE')),
    source        TEXT,                        -- Internal / External (Excel grain)
    start_date_mb TEXT,                        -- start with Momentuum Blue
    status        TEXT NOT NULL DEFAULT 'yet_to_join'
                  CHECK (status IN ('training', 'deployed', 'bench', 'yet_to_join', 'alumni')),
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (full_name)
);

CREATE TABLE IF NOT EXISTS deployments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id        INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    client_id        INTEGER NOT NULL REFERENCES clients(id),
    start_date       TEXT NOT NULL,
    end_date         TEXT,
    billing_rate_usd REAL NOT NULL CHECK (billing_rate_usd >= 0),
    hours_per_week   REAL NOT NULL DEFAULT 40 CHECK (hours_per_week >= 0),
    is_current       INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
    notes            TEXT
);

CREATE INDEX IF NOT EXISTS idx_deployments_person ON deployments(person_id);
CREATE INDEX IF NOT EXISTS idx_deployments_client ON deployments(client_id);
CREATE INDEX IF NOT EXISTS idx_deployments_current ON deployments(is_current);
CREATE INDEX IF NOT EXISTS idx_deployments_end_date ON deployments(end_date);

-- ---------------------------------------------------------------------------
-- Recruitment pipeline (person-level)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS applicants (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name            TEXT NOT NULL,
    email                TEXT,
    channel_id           INTEGER NOT NULL REFERENCES channels(id),
    role_id              INTEGER NOT NULL REFERENCES roles(id),
    target_cohort_id     INTEGER REFERENCES cohorts(id),
    applied_at           TEXT NOT NULL,       -- ISO datetime
    current_stage_id     INTEGER REFERENCES pipeline_stages(id),
    status               TEXT NOT NULL DEFAULT 'in_process'
                         CHECK (status IN (
                             'in_process',
                             'offer_extended',
                             'offer_accepted',
                             'offer_declined',
                             'rejected',
                             'on_hold',
                             'joined',
                             'withdrawn'
                         )),
    rejected_at_stage_id INTEGER REFERENCES pipeline_stages(id),
    person_id            INTEGER REFERENCES people(id),  -- set when joined / rostered
    notes                TEXT,
    created_at           TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_applicants_channel ON applicants(channel_id);
CREATE INDEX IF NOT EXISTS idx_applicants_role ON applicants(role_id);
CREATE INDEX IF NOT EXISTS idx_applicants_cohort ON applicants(target_cohort_id);
CREATE INDEX IF NOT EXISTS idx_applicants_status ON applicants(status);
CREATE INDEX IF NOT EXISTS idx_applicants_stage ON applicants(current_stage_id);
CREATE INDEX IF NOT EXISTS idx_applicants_applied_at ON applicants(applied_at);

CREATE TABLE IF NOT EXISTS applicant_stage_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_id INTEGER NOT NULL REFERENCES applicants(id) ON DELETE CASCADE,
    stage_id     INTEGER NOT NULL REFERENCES pipeline_stages(id),
    entered_at   TEXT NOT NULL,
    exited_at    TEXT,                         -- NULL while current
    outcome      TEXT CHECK (outcome IS NULL OR outcome IN (
                     'cleared', 'rejected', 'on_hold', 'withdrawn'
                 )),
    owner        TEXT,                         -- recruiter / interviewer
    notes        TEXT
);

CREATE INDEX IF NOT EXISTS idx_stage_events_applicant ON applicant_stage_events(applicant_id);
CREATE INDEX IF NOT EXISTS idx_stage_events_stage ON applicant_stage_events(stage_id);
CREATE INDEX IF NOT EXISTS idx_stage_events_entered ON applicant_stage_events(entered_at);

-- Optional bridge from Excel HR-Input (weekly aggregate counts)
CREATE TABLE IF NOT EXISTS pipeline_weekly_snapshots (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    week_ending            TEXT NOT NULL,     -- ISO date
    cohort_id              INTEGER REFERENCES cohorts(id),
    role_id                INTEGER REFERENCES roles(id),
    channel_id             INTEGER REFERENCES channels(id),
    applications_total     INTEGER,
    screening_pending      INTEGER,
    screening_cleared      INTEGER,
    l1_pending             INTEGER,
    l1_cleared             INTEGER,
    berribot_applied       INTEGER,
    berribot_cleared       INTEGER,
    l2_pending             INTEGER,
    l2_cleared             INTEGER,
    l3_pending             INTEGER,
    l3_cleared             INTEGER,
    cto_pending            INTEGER,
    cto_cleared            INTEGER,
    offer_extended         INTEGER,
    offer_accepted         INTEGER,
    joined                 INTEGER,
    on_hold                INTEGER,
    rejected               INTEGER,
    slots_needed_next_week INTEGER,
    notes                  TEXT,
    UNIQUE (week_ending, cohort_id, role_id, channel_id)
);

CREATE INDEX IF NOT EXISTS idx_pipeline_snapshots_week ON pipeline_weekly_snapshots(week_ending);

-- ---------------------------------------------------------------------------
-- Training / cohort performance
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS trainees (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id          INTEGER NOT NULL REFERENCES people(id),
    applicant_id       INTEGER REFERENCES applicants(id),
    cohort_id          INTEGER NOT NULL REFERENCES cohorts(id),
    enrolled_at        TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'active'
                       CHECK (status IN ('active', 'graduated', 'exited', 'promoted')),
    promotion_eligible INTEGER NOT NULL DEFAULT 0 CHECK (promotion_eligible IN (0, 1)),
    risk_flag          TEXT NOT NULL DEFAULT 'none'
                       CHECK (risk_flag IN ('none', 'watch', 'underperforming')),
    notes              TEXT,
    UNIQUE (person_id, cohort_id)
);

CREATE INDEX IF NOT EXISTS idx_trainees_cohort ON trainees(cohort_id);
CREATE INDEX IF NOT EXISTS idx_trainees_risk ON trainees(risk_flag);

CREATE TABLE IF NOT EXISTS trainee_week_scores (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    trainee_id    INTEGER NOT NULL REFERENCES trainees(id) ON DELETE CASCADE,
    week_number   INTEGER NOT NULL CHECK (week_number >= 1),
    hands_on_pct  REAL CHECK (hands_on_pct IS NULL OR (hands_on_pct >= 0 AND hands_on_pct <= 1)),
    proctored_pct REAL CHECK (proctored_pct IS NULL OR (proctored_pct >= 0 AND proctored_pct <= 1)),
    overall_pct   REAL CHECK (overall_pct IS NULL OR (overall_pct >= 0 AND overall_pct <= 1)),
    attendance_pct REAL CHECK (attendance_pct IS NULL OR (attendance_pct >= 0 AND attendance_pct <= 1)),
    notes         TEXT,
    UNIQUE (trainee_id, week_number)
);

CREATE INDEX IF NOT EXISTS idx_trainee_scores_week ON trainee_week_scores(week_number);

-- Class-level rollup (maps to Excel Input - Trainers)
CREATE TABLE IF NOT EXISTS training_week_meta (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cohort_id       INTEGER NOT NULL REFERENCES cohorts(id),
    week_number     INTEGER NOT NULL CHECK (week_number >= 1),
    topic           TEXT,
    active_students INTEGER,
    hands_on_avg    REAL,
    proctored_avg   REAL,
    overall_avg     REAL,
    UNIQUE (cohort_id, week_number)
);

-- ---------------------------------------------------------------------------
-- Economics (unit-cost rate card + monthly snapshots)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cost_unit_rates (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    category       TEXT NOT NULL
                   CHECK (category IN (
                       'recruiting', 'screening', 'interview', 'offer',
                       'training', 'deployment', 'overhead', 'resource_burn'
                   )),
    metric_key     TEXT NOT NULL,
    unit_cost_usd  REAL NOT NULL CHECK (unit_cost_usd >= 0),
    effective_from TEXT NOT NULL,              -- ISO date
    effective_to   TEXT,                       -- NULL = still active
    notes          TEXT,
    UNIQUE (metric_key, effective_from)
);

CREATE INDEX IF NOT EXISTS idx_cost_rates_key ON cost_unit_rates(metric_key);
CREATE INDEX IF NOT EXISTS idx_cost_rates_category ON cost_unit_rates(category);

CREATE TABLE IF NOT EXISTS cost_snapshots (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    month                TEXT NOT NULL UNIQUE, -- first of month YYYY-MM-01
    resource_burn_usd    REAL NOT NULL DEFAULT 0,
    recruiting_spend_usd REAL NOT NULL DEFAULT 0,
    training_spend_usd   REAL NOT NULL DEFAULT 0,
    deployment_spend_usd REAL NOT NULL DEFAULT 0,
    notes                TEXT
);

-- ---------------------------------------------------------------------------
-- Leadership actions / recommendations
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS recommendation_rules (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    rule_type  TEXT NOT NULL CHECK (rule_type IN ('threshold', 'tree', 'model')),
    params_json TEXT,                          -- JSON blob of thresholds / features
    enabled    INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS leadership_recommendations (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    category         TEXT NOT NULL
                     CHECK (category IN ('pipeline', 'cohort', 'deployment', 'economics')),
    severity         TEXT NOT NULL
                     CHECK (severity IN ('info', 'watch', 'action_needed')),
    title            TEXT NOT NULL,
    rationale        TEXT NOT NULL,
    suggested_action TEXT NOT NULL,
    entity_type      TEXT,                     -- applicants | trainees | deployments | cohorts | ...
    entity_id        INTEGER,
    status           TEXT NOT NULL DEFAULT 'open'
                     CHECK (status IN ('open', 'accepted', 'dismissed')),
    model_version    TEXT,
    rule_id          INTEGER REFERENCES recommendation_rules(id)
);

CREATE INDEX IF NOT EXISTS idx_recommendations_status ON leadership_recommendations(status);
CREATE INDEX IF NOT EXISTS idx_recommendations_category ON leadership_recommendations(category);
CREATE INDEX IF NOT EXISTS idx_recommendations_severity ON leadership_recommendations(severity);

-- ---------------------------------------------------------------------------
-- Seed: settings
-- ---------------------------------------------------------------------------

INSERT OR IGNORE INTO app_settings (key, value) VALUES
    ('billing_weeks_per_month', '4'),
    ('ending_soon_days', '60'),
    ('as_of_date', date('now'));

-- ---------------------------------------------------------------------------
-- Seed: pipeline stages (Excel HR-Input order)
-- ---------------------------------------------------------------------------

INSERT OR IGNORE INTO pipeline_stages (id, code, display_name, sort_order, is_terminal) VALUES
    (1, 'screening', 'Screening', 10, 0),
    (2, 'l1',        'L1 Interview', 20, 0),
    (3, 'berribot',  'Berribot', 30, 0),
    (4, 'l2',        'L2 Interview', 40, 0),
    (5, 'l3',        'L3 Interview', 50, 0),
    (6, 'cto',       'CTO Review', 60, 0),
    (7, 'offer',     'Offer', 70, 0),
    (8, 'joined',    'Joined', 80, 1);

-- ---------------------------------------------------------------------------
-- Seed: channels, roles, locations
-- ---------------------------------------------------------------------------

INSERT OR IGNORE INTO channels (id, code, display_name) VALUES
    (1, 'linkedin',  'LinkedIn'),
    (2, 'handshake', 'Handshake'),
    (3, 'external',  'External'),
    (4, 'internal',  'Internal');

INSERT OR IGNORE INTO roles (id, code, display_name) VALUES
    (1, 'associate_fde', 'Associate FDE'),
    (2, 'fde',           'FDE'),
    (3, 'senior_fde',    'Senior FDE');

INSERT OR IGNORE INTO locations (id, code, display_name) VALUES
    (1, 'usa',   'USA'),
    (2, 'uk',    'UK'),
    (3, 'latam', 'LATAM'),
    (4, 'india', 'India'),
    (5, 'canada','Canada');

INSERT OR IGNORE INTO cohorts (id, name, target_size, status) VALUES
    (1, 'Cohort 1', 20, 'training'),
    (2, 'Cohort 2', 20, 'recruiting');

-- ---------------------------------------------------------------------------
-- Seed: placeholder unit-cost rate card (edit with real finance numbers)
-- Costs are illustrative placeholders for leadership dashboard demos.
-- ---------------------------------------------------------------------------

INSERT OR IGNORE INTO cost_unit_rates (category, metric_key, unit_cost_usd, effective_from, notes) VALUES
    ('recruiting',    'per_application',            25.00,   date('now'), 'Sourcing / ads allocated per application'),
    ('screening',     'per_screen',                 40.00,   date('now'), 'Recruiter screen time'),
    ('interview',     'per_l1',                     75.00,   date('now'), 'L1 interviewer time'),
    ('interview',     'per_berribot',               15.00,   date('now'), 'Berribot assessment cost'),
    ('interview',     'per_l2',                    150.00,   date('now'), 'L2 panel time'),
    ('interview',     'per_l3',                    200.00,   date('now'), 'L3 panel time'),
    ('interview',     'per_cto',                   300.00,   date('now'), 'CTO review time'),
    ('offer',         'per_offer_extended',        100.00,   date('now'), 'Offer packaging / legal'),
    ('offer',         'per_hire_joined',          2500.00,   date('now'), 'Signing / onboarding allocation'),
    ('training',      'training_per_trainee_month', 3500.00, date('now'), 'Academy cost per trainee per month'),
    ('deployment',    'deployment_setup_per_fde',  1500.00,  date('now'), 'Client setup / ramp'),
    ('resource_burn', 'monthly_resource_burn_fixed', 50000.00, date('now'), 'Fixed monthly program burn placeholder');

INSERT OR IGNORE INTO recommendation_rules (name, rule_type, params_json, enabled) VALUES
    ('stage_wait_p90', 'threshold',
     '{"stage":"l2","p90_days_max":14,"severity":"action_needed"}', 1),
    ('trainee_below_cohort_avg', 'threshold',
     '{"gap_pct_points":-0.10,"weeks":2,"severity":"watch"}', 1),
    ('revenue_at_risk_window', 'threshold',
     '{"ending_soon_days_key":"ending_soon_days","severity":"action_needed"}', 1),
    ('slots_vs_offers_gap', 'threshold',
     '{"min_gap":10,"severity":"action_needed"}', 1),
    ('cost_per_hire_uptrend', 'threshold',
     '{"mom_increase_pct":0.15,"severity":"watch"}', 1);
