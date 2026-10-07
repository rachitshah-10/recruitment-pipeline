-- Leadership KPI views for the Recruitment Pipeline Dashboard
-- Requires schema.sql to be applied first.
-- Apply: sqlite3 recruitment.db < backend/schema/views.sql

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Pipeline: wait time per stage event
-- ---------------------------------------------------------------------------

DROP VIEW IF EXISTS v_applicant_stage_waits;
CREATE VIEW v_applicant_stage_waits AS
SELECT
    e.id AS event_id,
    e.applicant_id,
    a.full_name,
    a.status AS applicant_status,
    c.code AS channel_code,
    r.display_name AS role_name,
    co.name AS cohort_name,
    s.code AS stage_code,
    s.display_name AS stage_name,
    s.sort_order,
    e.entered_at,
    e.exited_at,
    e.outcome,
    CAST(
        julianday(COALESCE(e.exited_at, datetime('now'))) - julianday(e.entered_at)
        AS REAL
    ) AS wait_days
FROM applicant_stage_events e
JOIN applicants a ON a.id = e.applicant_id
JOIN pipeline_stages s ON s.id = e.stage_id
JOIN channels c ON c.id = a.channel_id
JOIN roles r ON r.id = a.role_id
LEFT JOIN cohorts co ON co.id = a.target_cohort_id;

DROP VIEW IF EXISTS v_pipeline_stage_summary;
CREATE VIEW v_pipeline_stage_summary AS
SELECT
    stage_code,
    stage_name,
    sort_order,
    COUNT(*) AS applicants_in_stage_events,
    SUM(CASE WHEN exited_at IS NULL THEN 1 ELSE 0 END) AS currently_waiting,
    ROUND(AVG(wait_days), 2) AS avg_wait_days,
    ROUND(MIN(wait_days), 2) AS min_wait_days,
    ROUND(MAX(wait_days), 2) AS max_wait_days
FROM v_applicant_stage_waits
GROUP BY stage_code, stage_name, sort_order
ORDER BY sort_order;

DROP VIEW IF EXISTS v_pipeline_by_channel;
CREATE VIEW v_pipeline_by_channel AS
SELECT
    c.code AS channel_code,
    c.display_name AS channel_name,
    COUNT(*) AS applicants,
    SUM(CASE WHEN a.status = 'in_process' THEN 1 ELSE 0 END) AS in_process,
    SUM(CASE WHEN a.status = 'offer_extended' THEN 1 ELSE 0 END) AS offer_extended,
    SUM(CASE WHEN a.status = 'offer_accepted' THEN 1 ELSE 0 END) AS offer_accepted,
    SUM(CASE WHEN a.status = 'joined' THEN 1 ELSE 0 END) AS joined,
    SUM(CASE WHEN a.status = 'rejected' THEN 1 ELSE 0 END) AS rejected,
    SUM(CASE WHEN a.status = 'on_hold' THEN 1 ELSE 0 END) AS on_hold
FROM applicants a
JOIN channels c ON c.id = a.channel_id
GROUP BY c.code, c.display_name;

DROP VIEW IF EXISTS v_pipeline_funnel_current;
CREATE VIEW v_pipeline_funnel_current AS
SELECT
    s.sort_order,
    s.code AS stage_code,
    s.display_name AS stage_name,
    COUNT(a.id) AS headcount
FROM pipeline_stages s
LEFT JOIN applicants a
    ON a.current_stage_id = s.id
   AND a.status IN ('in_process', 'offer_extended', 'on_hold')
GROUP BY s.sort_order, s.code, s.display_name
ORDER BY s.sort_order;

-- ---------------------------------------------------------------------------
-- Cohorts: scores + gap to cohort average (proxy for median in SQLite)
-- ---------------------------------------------------------------------------

DROP VIEW IF EXISTS v_cohort_week_avg;
CREATE VIEW v_cohort_week_avg AS
SELECT
    t.cohort_id,
    co.name AS cohort_name,
    tws.week_number,
    COUNT(tws.id) AS scored_trainees,
    ROUND(AVG(tws.hands_on_pct), 4) AS cohort_hands_on_avg,
    ROUND(AVG(tws.proctored_pct), 4) AS cohort_proctored_avg,
    ROUND(AVG(tws.overall_pct), 4) AS cohort_overall_avg,
    ROUND(AVG(tws.attendance_pct), 4) AS cohort_attendance_avg
FROM trainee_week_scores tws
JOIN trainees t ON t.id = tws.trainee_id
JOIN cohorts co ON co.id = t.cohort_id
GROUP BY t.cohort_id, co.name, tws.week_number;

DROP VIEW IF EXISTS v_trainee_score_gaps;
CREATE VIEW v_trainee_score_gaps AS
SELECT
    tws.id AS score_id,
    t.id AS trainee_id,
    p.full_name,
    t.cohort_id,
    co.name AS cohort_name,
    tws.week_number,
    tws.hands_on_pct,
    tws.proctored_pct,
    tws.overall_pct,
    tws.attendance_pct,
    cwa.cohort_overall_avg,
    ROUND(tws.overall_pct - cwa.cohort_overall_avg, 4) AS gap_to_cohort_avg,
    t.promotion_eligible,
    t.risk_flag,
    t.status AS trainee_status
FROM trainee_week_scores tws
JOIN trainees t ON t.id = tws.trainee_id
JOIN people p ON p.id = t.person_id
JOIN cohorts co ON co.id = t.cohort_id
JOIN v_cohort_week_avg cwa
  ON cwa.cohort_id = t.cohort_id
 AND cwa.week_number = tws.week_number;

DROP VIEW IF EXISTS v_cohort_risk_summary;
CREATE VIEW v_cohort_risk_summary AS
SELECT
    co.id AS cohort_id,
    co.name AS cohort_name,
    COUNT(t.id) AS trainee_count,
    SUM(CASE WHEN t.risk_flag = 'none' THEN 1 ELSE 0 END) AS risk_none,
    SUM(CASE WHEN t.risk_flag = 'watch' THEN 1 ELSE 0 END) AS risk_watch,
    SUM(CASE WHEN t.risk_flag = 'underperforming' THEN 1 ELSE 0 END) AS risk_underperforming,
    SUM(CASE WHEN t.promotion_eligible = 1 THEN 1 ELSE 0 END) AS promotion_eligible_count
FROM cohorts co
LEFT JOIN trainees t ON t.cohort_id = co.id
GROUP BY co.id, co.name;

-- ---------------------------------------------------------------------------
-- Deployment + revenue
-- ---------------------------------------------------------------------------

DROP VIEW IF EXISTS v_deployment_monthly_revenue;
CREATE VIEW v_deployment_monthly_revenue AS
SELECT
    d.id AS deployment_id,
    p.id AS person_id,
    p.full_name,
    p.career_stage,
    p.status AS person_status,
    loc.display_name AS location_name,
    cl.name AS client_name,
    d.start_date,
    d.end_date,
    d.billing_rate_usd,
    d.hours_per_week,
    d.is_current,
    CAST(COALESCE(
        (SELECT value FROM app_settings WHERE key = 'billing_weeks_per_month'),
        '4'
    ) AS REAL) AS billing_weeks_per_month,
    ROUND(
        d.billing_rate_usd
        * d.hours_per_week
        * CAST(COALESCE(
            (SELECT value FROM app_settings WHERE key = 'billing_weeks_per_month'),
            '4'
          ) AS REAL),
        2
    ) AS monthly_revenue_usd
FROM deployments d
JOIN people p ON p.id = d.person_id
JOIN clients cl ON cl.id = d.client_id
LEFT JOIN locations loc ON loc.id = p.location_id;

DROP VIEW IF EXISTS v_monthly_revenue_total;
CREATE VIEW v_monthly_revenue_total AS
SELECT
    ROUND(SUM(monthly_revenue_usd), 2) AS monthly_revenue_usd,
    COUNT(*) AS active_deployments
FROM v_deployment_monthly_revenue
WHERE is_current = 1;

DROP VIEW IF EXISTS v_revenue_at_risk;
CREATE VIEW v_revenue_at_risk AS
SELECT
    v.*,
    CAST(COALESCE(
        (SELECT value FROM app_settings WHERE key = 'ending_soon_days'),
        '60'
    ) AS INTEGER) AS ending_soon_days,
    CAST(
        julianday(v.end_date) - julianday('now')
        AS REAL
    ) AS days_until_end
FROM v_deployment_monthly_revenue v
WHERE v.is_current = 1
  AND v.end_date IS NOT NULL
  AND julianday(v.end_date) - julianday('now') <= CAST(COALESCE(
        (SELECT value FROM app_settings WHERE key = 'ending_soon_days'),
        '60'
      ) AS REAL)
  AND julianday(v.end_date) - julianday('now') >= 0;

DROP VIEW IF EXISTS v_revenue_at_risk_total;
CREATE VIEW v_revenue_at_risk_total AS
SELECT
    ROUND(SUM(monthly_revenue_usd), 2) AS revenue_at_risk_usd,
    COUNT(*) AS contracts_ending_soon
FROM v_revenue_at_risk;

-- ---------------------------------------------------------------------------
-- Economics: active rate card + hiring cost by stage + unit economics
-- ---------------------------------------------------------------------------

DROP VIEW IF EXISTS v_active_cost_rates;
CREATE VIEW v_active_cost_rates AS
SELECT cur.*
FROM cost_unit_rates cur
WHERE date(cur.effective_from) <= date('now')
  AND (cur.effective_to IS NULL OR date(cur.effective_to) >= date('now'));

-- Map pipeline stage codes to rate-card metric keys
DROP VIEW IF EXISTS v_hiring_cost_by_stage;
CREATE VIEW v_hiring_cost_by_stage AS
SELECT
    s.code AS stage_code,
    s.display_name AS stage_name,
    s.sort_order,
    mk.metric_key,
    COUNT(e.id) AS event_count,
    COALESCE(r.unit_cost_usd, 0) AS unit_cost_usd,
    ROUND(COUNT(e.id) * COALESCE(r.unit_cost_usd, 0), 2) AS total_cost_usd
FROM pipeline_stages s
LEFT JOIN (
    SELECT 'screening' AS stage_code, 'per_screen' AS metric_key
    UNION ALL SELECT 'l1', 'per_l1'
    UNION ALL SELECT 'berribot', 'per_berribot'
    UNION ALL SELECT 'l2', 'per_l2'
    UNION ALL SELECT 'l3', 'per_l3'
    UNION ALL SELECT 'cto', 'per_cto'
    UNION ALL SELECT 'offer', 'per_offer_extended'
    UNION ALL SELECT 'joined', 'per_hire_joined'
) mk ON mk.stage_code = s.code
LEFT JOIN applicant_stage_events e ON e.stage_id = s.id
LEFT JOIN v_active_cost_rates r ON r.metric_key = mk.metric_key
GROUP BY s.code, s.display_name, s.sort_order, mk.metric_key, r.unit_cost_usd
ORDER BY s.sort_order;

DROP VIEW IF EXISTS v_economics_counts;
CREATE VIEW v_economics_counts AS
SELECT
    (SELECT COUNT(*) FROM applicants) AS applicant_count,
    (SELECT COUNT(*) FROM applicants WHERE status IN ('offer_extended', 'offer_accepted', 'joined')) AS offer_count,
    (SELECT COUNT(*) FROM applicants WHERE status IN ('offer_accepted', 'joined')) AS hire_count,
    (SELECT COUNT(*) FROM deployments WHERE is_current = 1) AS deployment_count,
    (SELECT COUNT(*) FROM trainees WHERE status = 'active') AS active_trainee_count;

DROP VIEW IF EXISTS v_latest_cost_snapshot;
CREATE VIEW v_latest_cost_snapshot AS
SELECT *
FROM cost_snapshots
ORDER BY month DESC
LIMIT 1;

-- Blended monthly investment: latest snapshot spends + fixed burn rate +
-- training unit cost × active trainees + deployment setups (current)
DROP VIEW IF EXISTS v_total_investment;
CREATE VIEW v_total_investment AS
SELECT
    ROUND(
        COALESCE((SELECT resource_burn_usd FROM v_latest_cost_snapshot), 0)
        + COALESCE((SELECT recruiting_spend_usd FROM v_latest_cost_snapshot), 0)
        + COALESCE((SELECT training_spend_usd FROM v_latest_cost_snapshot), 0)
        + COALESCE((SELECT deployment_spend_usd FROM v_latest_cost_snapshot), 0)
        + CASE
            WHEN (SELECT resource_burn_usd FROM v_latest_cost_snapshot) IS NULL
              OR (SELECT resource_burn_usd FROM v_latest_cost_snapshot) = 0
            THEN COALESCE(
                (SELECT unit_cost_usd FROM v_active_cost_rates
                 WHERE metric_key = 'monthly_resource_burn_fixed'), 0)
            ELSE 0
          END
        + COALESCE(
            (SELECT unit_cost_usd FROM v_active_cost_rates
             WHERE metric_key = 'training_per_trainee_month'), 0)
          * COALESCE((SELECT active_trainee_count FROM v_economics_counts), 0)
        + COALESCE(
            (SELECT unit_cost_usd FROM v_active_cost_rates
             WHERE metric_key = 'deployment_setup_per_fde'), 0)
          * COALESCE((SELECT deployment_count FROM v_economics_counts), 0)
          / 12.0   -- amortize setup across a year for monthly view
    , 2) AS total_investment_usd,
    (SELECT month FROM v_latest_cost_snapshot) AS snapshot_month;

DROP VIEW IF EXISTS v_unit_economics;
CREATE VIEW v_unit_economics AS
SELECT
    ec.applicant_count,
    ec.offer_count,
    ec.hire_count,
    ec.deployment_count,
    ROUND(COALESCE((SELECT SUM(total_cost_usd) FROM v_hiring_cost_by_stage), 0), 2)
        AS recruiting_pipeline_cost_usd,
    ROUND(
        CASE WHEN ec.applicant_count > 0
             THEN COALESCE((SELECT SUM(total_cost_usd) FROM v_hiring_cost_by_stage), 0)
                  / ec.applicant_count
             ELSE NULL END
    , 2) AS cost_per_applicant,
    ROUND(
        CASE WHEN ec.offer_count > 0
             THEN COALESCE((SELECT SUM(total_cost_usd) FROM v_hiring_cost_by_stage), 0)
                  / ec.offer_count
             ELSE NULL END
    , 2) AS cost_per_offer,
    ROUND(
        CASE WHEN ec.hire_count > 0
             THEN COALESCE((SELECT SUM(total_cost_usd) FROM v_hiring_cost_by_stage), 0)
                  / ec.hire_count
             ELSE NULL END
    , 2) AS cost_per_hire,
    ROUND(
        CASE WHEN ec.deployment_count > 0
             THEN (SELECT total_investment_usd FROM v_total_investment)
                  / ec.deployment_count
             ELSE NULL END
    , 2) AS cost_per_deployment,
    (SELECT monthly_revenue_usd FROM v_monthly_revenue_total) AS monthly_revenue_usd,
    (SELECT revenue_at_risk_usd FROM v_revenue_at_risk_total) AS revenue_at_risk_usd,
    (SELECT total_investment_usd FROM v_total_investment) AS total_investment_usd,
    ROUND(
        CASE WHEN (SELECT total_investment_usd FROM v_total_investment) > 0
             THEN (SELECT monthly_revenue_usd FROM v_monthly_revenue_total)
                  / (SELECT total_investment_usd FROM v_total_investment)
             ELSE NULL END
    , 3) AS revenue_investment_ratio
FROM v_economics_counts ec;

DROP VIEW IF EXISTS v_economics_leadership;
CREATE VIEW v_economics_leadership AS
SELECT
    u.*,
    (SELECT contracts_ending_soon FROM v_revenue_at_risk_total) AS contracts_ending_soon,
    (SELECT COUNT(*) FROM leadership_recommendations WHERE status = 'open') AS open_recommendations,
    (SELECT COUNT(*) FROM leadership_recommendations
     WHERE status = 'open' AND severity = 'action_needed') AS open_actions_needed;

DROP VIEW IF EXISTS v_open_recommendations;
CREATE VIEW v_open_recommendations AS
SELECT *
FROM leadership_recommendations
WHERE status = 'open'
ORDER BY
    CASE severity
        WHEN 'action_needed' THEN 1
        WHEN 'watch' THEN 2
        ELSE 3
    END,
    created_at DESC;
