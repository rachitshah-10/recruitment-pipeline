# Data Schema Guide

SQLite schema for the Momentuum Blue leadership dashboard. Focus is **data for decisions**; the web UI stays basic for now.

**Files**
- [`backend/schema/schema.sql`](backend/schema/schema.sql) — tables, indexes, seed data
- [`backend/schema/views.sql`](backend/schema/views.sql) — pipeline, cohort, deployment, and economics KPIs

**Apply locally**
```bash
cd backend
sqlite3 recruitment.db < schema/schema.sql
sqlite3 recruitment.db < schema/views.sql
```

---

## Plain-language explanation

The database has five layers leadership cares about:

1. **Recruitment pipeline** — Every applicant is one person-row. We store channel (LinkedIn, Handshake, External, Internal), target role/cohort, current status, and a history of stage visits with dates. Wait time is days between entering and leaving a stage. Outcomes include offer extended/accepted/declined, rejected, on hold, joined.

2. **Cohorts** — Accepted hires enroll as trainees in a cohort (~20). Weekly per-student scores power line charts, gap-to-cohort-average underperform flags, and promote / watch / exit signals.

3. **Deployment** — Lightweight FDE roster: location, career stage, client assignment, billing rate, hours. Monthly revenue = rate × hours × billing weeks/month (same idea as the Excel Calc sheet).

4. **Economics (main focus)** — A **unit-cost rate card** (cost per screen, per interview, per hire, training per trainee-month, fixed monthly burn, etc.) plus optional monthly spend snapshots. Leadership metrics such as cost/applicant, cost/hire, revenue at risk, and revenue/investment ratio are **computed in views**, not typed by hand.

5. **Leadership actions** — Rules (or later a simple model) write rows into `leadership_recommendations`: what to do, why, severity, and which entity it is about.

```text
Applicant ──stage events──► Pipeline waits / funnel
    │
    └─(joined)──► Person ──► Trainee (cohort scores)
                      │
                      └─► Deployment ──► Revenue / revenue at risk
                                            │
Cost rate card + snapshots ─────────────────┴──► Economics KPIs
Rules / model ──────────────────────────────────► Recommendations
```

---

## What was already in the Excel file

Source workbook: `MB_Master_Dashboard_AB_V2.xlsx`

| Excel sheet | Content | Maps to |
|-------------|---------|---------|
| **HR-Input** | Weekly **aggregate** funnel counts by Cohort / Role / Source; stages Screening → L1 → Berribot → L2 → L3 → CTO → Offer → Joined; on_hold, rejected, slots_needed, notes | `pipeline_weekly_snapshots` (bridge only). Person-level pipeline is new. |
| **Input - Trainers** | Weekly **class** averages (hands-on, proctored, overall), active students, topic (Week 6 populated) | `training_week_meta` |
| **Master-Input** | 38 FDEs: name, location, career stage, MB start, source, current client, dates, $/hr, hours/week, monthly revenue formula | `people` + `deployments` + `clients` |
| **Calc** | billing_weeks_per_month = 4, ending_soon_days = 60 | `app_settings` |
| Dashboard sheets | Charts/formulas only | Recreate via SQL views + UI — do not store as tables |

Excel has **no** person-level applicants, **no** stage timestamps, **no** per-student scores, and **no cost data** (revenue only).

---

## New data you need to add

| Data | Why | Table(s) |
|------|-----|----------|
| Individual applicants + channel | Intake mix, conversion by source | `applicants`, `channels` |
| Stage entry/exit timestamps | Wait times, bottlenecks | `applicant_stage_events` |
| Person-level offer / reject / hold | Outcome funnel | `applicants.status` |
| Per-student weekly scores + attendance | Cohort graphs | `trainee_week_scores` |
| Promote / underperform flags | Actionable cohort view | `trainees.promotion_eligible`, `risk_flag` |
| Unit costs (rate card) | All economics KPIs | `cost_unit_rates` (placeholders seeded) |
| Monthly spend overrides (optional) | Burn / recruiting / training / deployment spend | `cost_snapshots` |
| Recommendation outcomes | Leadership action feed | `leadership_recommendations` |
| Stable numeric IDs | Reliable joins (Excel used display names) | all PKs |

Placeholder unit costs are seeded so Economics pages can render before finance provides real numbers — replace them in `cost_unit_rates`.

---

## Core tables (quick map)

| Area | Tables |
|------|--------|
| Reference | `app_settings`, `pipeline_stages`, `channels`, `roles`, `locations`, `clients` |
| Pipeline | `cohorts`, `applicants`, `applicant_stage_events`, `pipeline_weekly_snapshots` |
| Training | `trainees`, `trainee_week_scores`, `training_week_meta` |
| Deployment | `people`, `deployments` |
| Economics | `cost_unit_rates`, `cost_snapshots` |
| Actions | `recommendation_rules`, `leadership_recommendations` |

### Important views

| View | Purpose |
|------|---------|
| `v_applicant_stage_waits` | Per-event wait days |
| `v_pipeline_stage_summary` / `v_pipeline_by_channel` / `v_pipeline_funnel_current` | Pipeline leadership cards |
| `v_trainee_score_gaps` | Score vs cohort average (chart + underperform signal) |
| `v_cohort_risk_summary` | Promote / watch / underperforming counts |
| `v_deployment_monthly_revenue` / `v_monthly_revenue_total` | Revenue |
| `v_revenue_at_risk` | Contracts ending within `ending_soon_days` |
| `v_hiring_cost_by_stage` | Stage events × unit rates |
| `v_unit_economics` / `v_economics_leadership` | cost/applicant, cost/offer, cost/hire, cost/deployment, ROI |
| `v_open_recommendations` | Action feed |

---

## Design choices locked in

- **Person-level recruiting** (not Excel weekly aggregates as the primary grain).
- **Unit-cost economics** (rate card), with optional monthly snapshots for actual spend overlays.
- Cohort “gap to median” is implemented as **gap to cohort average** in SQL (SQLite has no built-in median); the app can compute a true median later if needed.
