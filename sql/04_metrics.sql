-- 04_metrics.sql : independent metric definitions (see docs/metric_definitions.md). Aug-2026 is partial (data ends 8-Aug): flagged, excluded from MoM.
CREATE SCHEMA IF NOT EXISTS metrics;

-- (a) the business' probable headline, rebuilt from RAW: every SUCCESS row (duplicates included), calendar-month, source timestamps
CREATE OR REPLACE TABLE metrics.reported_headline AS
WITH m AS (SELECT strftime(event_at,'%Y-%m') AS month, sum(amount) AS reported_success FROM raw.payments WHERE payment_status='SUCCESS' GROUP BY 1)
SELECT month, reported_success, reported_success / lag(reported_success) OVER (ORDER BY month) - 1 AS reported_mom FROM m ORDER BY month;

-- (b) golden monthly scorecard
CREATE OR REPLACE TABLE metrics.monthly AS
WITH cal AS (
  SELECT month_ist AS month, min(event_date_ist) AS first_d, max(event_date_ist) AS last_d FROM golden.fact_payment GROUP BY 1),
pay AS (
  SELECT month_ist AS month,
    sum(CASE WHEN payment_status='SUCCESS' THEN amount END) AS success_amt,
    sum(CASE WHEN payment_status='REVERSED' THEN amount END) AS reversed_amt,
    sum(net_amount) AS net_recovery,
    count(*) FILTER (WHERE payment_status='SUCCESS') AS success_n,
    count(DISTINCT account_id) FILTER (WHERE payment_status='SUCCESS') AS paying_accounts
  FROM golden.fact_payment GROUP BY 1),
call AS (
  SELECT month_ist AS month,
    count(*) FILTER (WHERE direction='OUTBOUND') AS outbound_dials,
    count(*) FILTER (WHERE direction='OUTBOUND' AND is_answered) AS answered,
    count(DISTINCT account_id) FILTER (WHERE direction='OUTBOUND') AS accts_dialed,
    count(DISTINCT account_id) FILTER (WHERE direction='OUTBOUND' AND is_answered) AS accts_answered,
    sum(duration_sec) FILTER (WHERE is_answered)/60.0 AS talk_minutes,
    sum(duration_sec) FILTER (WHERE direction='OUTBOUND')/60.0 AS dial_minutes
  FROM golden.fact_call GROUP BY 1),
exposure AS (  -- constant-definition denominator: outstanding of all accounts opened on/before month end (no status filter => no survivorship)
  SELECT m.month, sum(a.outstanding_amount) AS exposure, count(*) AS accts
  FROM (SELECT DISTINCT month_ist AS month, last_day(strptime(month_ist||'-01','%Y-%m-%d')) AS me FROM golden.fact_payment) m
  JOIN golden.dim_account a ON a.opened_at <= m.me GROUP BY 1),
sess AS (SELECT month, sum(hours) AS agent_hours FROM clean.sessions GROUP BY 1),
wa AS (SELECT strftime(event_at,'%Y-%m') AS month, count(*) FILTER (WHERE event_type<>'FAILED') AS wa_msgs FROM raw.whatsapp_events GROUP BY 1),
sm AS (SELECT strftime(event_at,'%Y-%m') AS month, count(*) FILTER (WHERE event_type<>'FAILED') AS sms_msgs FROM raw.sms_events GROUP BY 1),
fv AS (SELECT strftime(event_at,'%Y-%m') AS month, count(*) AS visits FROM raw.field_visits GROUP BY 1),
cfg AS (SELECT * FROM read_json_auto('config/assumptions.json'))
SELECT pay.month, cal.first_d, cal.last_d,
  date_diff('day', cal.first_d, cal.last_d) + 1 AS days_observed,
  day(last_day(strptime(pay.month||'-01','%Y-%m-%d'))) AS days_in_month,
  (cal.last_d < last_day(strptime(pay.month||'-01','%Y-%m-%d'))) AS is_partial_month,
  pay.success_amt, pay.reversed_amt, pay.net_recovery, pay.success_n, pay.paying_accounts,
  pay.net_recovery / (date_diff('day', cal.first_d, cal.last_d) + 1) AS net_recovery_per_day,
  pay.net_recovery / exposure.exposure AS recovery_rate_of_exposure,
  pay.net_recovery / (date_diff('day', cal.first_d, cal.last_d) + 1) / exposure.exposure * 30 AS recovery_rate_30d_norm,
  pay.net_recovery / exposure.accts AS recovery_per_account,
  call.outbound_dials, call.answered, call.answered * 1.0 / call.outbound_dials AS contact_rate,
  call.accts_answered * 1.0 / call.accts_dialed AS account_contact_rate,
  sess.agent_hours, pay.net_recovery / sess.agent_hours AS recovery_per_agent_hour,
  (sess.agent_hours * cfg.agent_cost_per_logged_hour_inr + call.dial_minutes * cfg.voice_cost_per_minute_inr
   + wa.wa_msgs * cfg.whatsapp_cost_per_message_inr + sm.sms_msgs * cfg.sms_cost_per_message_inr + fv.visits * cfg.field_cost_per_visit_inr) AS assumed_cost_inr,
  (sess.agent_hours * cfg.agent_cost_per_logged_hour_inr + call.dial_minutes * cfg.voice_cost_per_minute_inr
   + wa.wa_msgs * cfg.whatsapp_cost_per_message_inr + sm.sms_msgs * cfg.sms_cost_per_message_inr + fv.visits * cfg.field_cost_per_visit_inr) / pay.net_recovery AS cost_per_rupee_recovered
FROM pay JOIN cal USING (month) JOIN call USING (month) JOIN exposure USING (month)
LEFT JOIN sess USING (month) LEFT JOIN wa USING (month) LEFT JOIN sm USING (month) LEFT JOIN fv USING (month) CROSS JOIN cfg
ORDER BY pay.month;

-- (c) MoM on golden definitions, full months only
CREATE OR REPLACE TABLE metrics.mom AS
SELECT m.month, h.reported_success, h.reported_mom,
  m.net_recovery, m.net_recovery / lag(m.net_recovery) OVER (ORDER BY m.month) - 1 AS golden_net_mom,
  m.net_recovery_per_day / lag(m.net_recovery_per_day) OVER (ORDER BY m.month) - 1 AS golden_per_day_mom,
  m.recovery_rate_30d_norm, m.is_partial_month
FROM metrics.monthly m JOIN metrics.reported_headline h USING (month) ORDER BY m.month;
