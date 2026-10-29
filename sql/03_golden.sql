-- 03_golden.sql : analytical layer. One row = one business event, deduped, in IST, with trusted dimensions attached.
CREATE SCHEMA IF NOT EXISTS golden;
CREATE OR REPLACE TABLE golden.dim_agent   AS SELECT * FROM clean.dim_agent;
CREATE OR REPLACE TABLE golden.dim_account AS SELECT * FROM clean.dim_account;

-- Net recovery convention: SUCCESS counts +amount, REVERSED counts -amount (a reversal row is a chargeback/return; it carries its own
-- payment_id/reference so it cannot be linked to the original: booked in the month it occurs). PENDING and FAILED are never recovery.
CREATE OR REPLACE TABLE golden.fact_payment AS
SELECT p.*, a.loan_type, a.dpd_bucket, a.risk_segment, a.state, a.outstanding_amount, a.acct_status_snapshot,
       CASE p.payment_status WHEN 'SUCCESS' THEN p.amount WHEN 'REVERSED' THEN -p.amount ELSE 0 END AS net_amount
FROM clean.payments p JOIN clean.dim_account a USING (account_id);

CREATE OR REPLACE TABLE golden.fact_call AS
WITH d AS (SELECT call_id, disposition_norm, disposition_version,
                  row_number() OVER (PARTITION BY call_id ORDER BY event_ts_ist DESC) rn FROM clean.dispositions),
     att AS (SELECT call_id, max(attempt_no) AS attempt_no, any_value(attempt_status) AS attempt_status FROM clean.attempts GROUP BY 1)
SELECT c.*, d.disposition_norm, d.disposition_version, att.attempt_no, att.attempt_status,
       a.dpd_bucket, a.loan_type, a.risk_segment, a.state,
       g.team, g.joined_at AS agent_joined_at,
       CASE WHEN c.agent_id IS NULL OR g.joined_at IS NULL THEN 'UNKNOWN'
            WHEN date_diff('day', g.joined_at, c.event_ts_ist) < 90  THEN '<3m'
            WHEN date_diff('day', g.joined_at, c.event_ts_ist) < 180 THEN '3-6m'
            WHEN date_diff('day', g.joined_at, c.event_ts_ist) < 365 THEN '6-12m' ELSE '12m+' END AS tenure_bucket,
       CASE WHEN c.hour_ist < 8 THEN 'before_8am' WHEN c.hour_ist < 12 THEN '08-12' WHEN c.hour_ist < 16 THEN '12-16'
            WHEN c.hour_ist < 19 THEN '16-19' ELSE 'after_7pm' END AS time_band_ist,
       c.call_status = 'ANSWERED' AS is_answered
FROM clean.calls c JOIN clean.dim_account a USING (account_id)
LEFT JOIN d ON d.call_id = c.call_id AND d.rn = 1 LEFT JOIN att ON att.call_id = c.call_id
LEFT JOIN clean.dim_agent g ON g.agent_id = c.agent_id;

-- Every outreach on an account, any channel. WhatsApp/SMS/Field carry no timezone in source: assumed IST.
CREATE OR REPLACE TABLE golden.fact_touch AS
SELECT account_id, event_ts_ist AS touch_ts, 'VOICE' AS channel, campaign_id, call_status = 'ANSWERED' AS engaged, call_id AS touch_id
FROM clean.calls WHERE direction = 'OUTBOUND'
UNION ALL SELECT account_id, event_at, 'WHATSAPP', NULL, event_type IN ('READ','REPLIED','PAYMENT_CLICK'), whatsapp_event_id
FROM raw.whatsapp_events WHERE event_type <> 'FAILED'
UNION ALL SELECT account_id, event_at, 'SMS', NULL, event_type = 'CLICKED', sms_event_id
FROM raw.sms_events WHERE event_type <> 'FAILED'
UNION ALL SELECT account_id, event_at, 'FIELD', NULL, outcome IN ('CONTACTED','PTP','PAID'), visit_id
FROM raw.field_visits;

-- Last-touch attribution for SUCCESS payments: the latest touch STRICTLY BEFORE the payment (lag_days >= 0). No window applied here;
-- windows are applied at query time so the sensitivity is transparent.
CREATE OR REPLACE TABLE golden.payment_attribution AS
SELECT p.payment_id, p.account_id, p.event_ts_ist, p.amount, p.month_ist, p.dpd_bucket, p.loan_type, p.risk_segment, p.state,
       t.channel AS lt_channel, t.campaign_id AS lt_campaign, t.engaged AS lt_engaged, t.touch_ts,
       date_diff('minute', t.touch_ts, p.event_ts_ist) / 1440.0 AS lag_days
FROM golden.fact_payment p
ASOF LEFT JOIN golden.fact_touch t ON p.account_id = t.account_id AND p.event_ts_ist >= t.touch_ts
WHERE p.payment_status = 'SUCCESS';

-- The "latest campaign" shortcut (credits the account's most recent campaign over the whole period, even if it started AFTER the payment)
CREATE OR REPLACE TABLE golden.latest_campaign_by_account AS
SELECT account_id, arg_max(campaign_id, event_ts_ist) AS latest_campaign FROM clean.calls WHERE campaign_id IS NOT NULL GROUP BY 1;

CREATE OR REPLACE TABLE golden.fact_ptp AS
SELECT p.*, a.dpd_bucket, a.loan_type, a.risk_segment,
  -- verified kept: a SUCCESS payment on the same account between PTP creation and promised_date + 3 days
  EXISTS (SELECT 1 FROM clean.payments pay WHERE pay.account_id = p.account_id AND pay.payment_status = 'SUCCESS'
          AND pay.event_ts_ist BETWEEN p.ptp_ts AND p.promised_date + INTERVAL 3 DAY) AS verified_paid
FROM clean.ptp p JOIN clean.dim_account a USING (account_id);
