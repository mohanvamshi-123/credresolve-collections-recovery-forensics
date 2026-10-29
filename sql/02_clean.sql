-- 02_clean.sql : dedupe, entity resolution, timestamp normalisation. Every dropped row is logged in clean.rejects.
CREATE SCHEMA IF NOT EXISTS clean;
CREATE OR REPLACE TABLE clean.rejects (src VARCHAR, key VARCHAR, reason VARCHAR, _raw_row BIGINT);

-- PAYMENTS: dedupe on payment_id (NOT payment_reference: ~3.4k references are reused across different accounts/amounts)
CREATE OR REPLACE TABLE clean.payments AS
WITH r AS (
  SELECT p.*, coalesce(v.timezone,'Asia/Kolkata') AS src_tz,
         row_number() OVER (PARTITION BY payment_id ORDER BY event_at, _raw_row) AS rn
  FROM stg.payments p LEFT JOIN stg.vendor v ON v.vendor_id = p.provider_id)
SELECT payment_id, account_id, payment_reference, amount, payment_status, payment_method, provider_id, src_tz,
       event_at AS event_at_src, to_ist(event_at, src_tz) AS event_ts_ist,
       CAST(to_ist(event_at, src_tz) AS DATE) AS event_date_ist,
       strftime(to_ist(event_at, src_tz), '%Y-%m') AS month_ist,
       strftime(event_at, '%Y-%m') AS month_src,
       payment_reference IS NULL AS ref_missing
FROM r WHERE rn = 1;
INSERT INTO clean.rejects SELECT 'payments', payment_id, 'exact duplicate payment_id (retry/ingestion replay)', _raw_row
FROM (SELECT *, row_number() OVER (PARTITION BY payment_id ORDER BY event_at, _raw_row) rn FROM stg.payments) WHERE rn > 1;

-- CALLS: duplicate call_id -> keep the copy that has an agent_id, then the EARLIEST event_at (later copy = late-arriving re-ingest)
CREATE OR REPLACE TABLE clean.calls AS
WITH r AS (
  SELECT c.*, row_number() OVER (PARTITION BY call_id ORDER BY (agent_id IS NULL), event_at, _raw_row) AS rn,
         count(*) OVER (PARTITION BY call_id) AS n_copies
  FROM stg.calls c)
SELECT call_id, account_id, agent_id, campaign_id, direction, vendor_id, call_status, duration_sec, timezone AS src_tz,
       event_at AS event_at_src, to_ist(event_at, timezone) AS event_ts_ist,
       CAST(to_ist(event_at, timezone) AS DATE) AS event_date_ist,
       strftime(to_ist(event_at, timezone), '%Y-%m') AS month_ist,
       strftime(event_at, '%Y-%m') AS month_src,
       hour(to_ist(event_at, timezone)) AS hour_ist, hour(event_at) AS hour_src,
       n_copies > 1 AS was_duplicated
FROM r WHERE rn = 1;
INSERT INTO clean.rejects SELECT 'calls', call_id, 'duplicate call_id (kept copy with agent_id / earliest event_at)', _raw_row
FROM (SELECT *, row_number() OVER (PARTITION BY call_id ORDER BY (agent_id IS NULL), event_at, _raw_row) rn FROM stg.calls) WHERE rn > 1;

-- AGENTS: agent_id is the only key every fact table uses. employee_code is N:M with agent_id so it cannot be a merge key.
CREATE OR REPLACE TABLE clean.dim_agent AS
WITH r AS (SELECT *, row_number() OVER (PARTITION BY agent_id ORDER BY updated_at DESC, _raw_row) rn,
                  count(DISTINCT employee_code) OVER (PARTITION BY agent_id) AS n_employee_codes,
                  min(joined_at) OVER (PARTITION BY agent_id) AS first_joined_at,
                  count(*) OVER (PARTITION BY agent_id) AS n_versions
           FROM stg.agents)
SELECT agent_id, employee_code, vendor_id AS agent_vendor_id, team, status AS agent_status, joined_at, first_joined_at,
       updated_at, n_employee_codes, n_versions, (updated_at < joined_at) AS ts_conflict
FROM r WHERE rn = 1;

-- BORROWERS: 30,600 rows -> 11,015 ids; latest updated_at wins
CREATE OR REPLACE TABLE clean.dim_borrower AS
SELECT * EXCLUDE (rn) FROM (SELECT borrower_id, city, state, row_number() OVER (PARTITION BY borrower_id ORDER BY updated_at DESC, _raw_row) rn FROM stg.borrowers) WHERE rn = 1;

-- ACCOUNTS: account_id is the join key for all facts (borrower_id on fact tables disagrees with accounts.borrower_id ~100% of rows)
CREATE OR REPLACE TABLE clean.dim_account AS
SELECT a.account_id, a.borrower_id, a.loan_type, a.principal_amount, a.outstanding_amount, a.dpd, a.risk_segment, a.status AS acct_status_snapshot,
       a.opened_at, a.timezone AS acct_tz, a.schema_version,
       CASE WHEN a.dpd = 0 THEN '0' WHEN a.dpd < 30 THEN '1-29' WHEN a.dpd < 60 THEN '30-59' WHEN a.dpd < 90 THEN '60-89' ELSE '90+' END AS dpd_bucket,
       coalesce(b.state,'UNKNOWN') AS state, coalesce(b.city,'UNKNOWN') AS city,
       b.borrower_id IS NULL AS borrower_orphan
FROM stg.accounts a LEFT JOIN clean.dim_borrower b USING (borrower_id);

-- DISPOSITIONS / ATTEMPTS: child tables inherit account/agent from calls (their own copies disagree with calls ~100%)
CREATE OR REPLACE TABLE clean.dispositions AS
SELECT d.disposition_id, d.call_id, c.account_id, c.agent_id,
       CASE d.disposition_code WHEN 'PTP' THEN 'PROMISE_TO_PAY' ELSE d.disposition_code END AS disposition_norm,
       d.disposition_code AS disposition_raw, d.disposition_version,
       to_ist(d.event_at, c.src_tz) AS event_ts_ist
FROM stg.call_dispositions d JOIN clean.calls c USING (call_id);

CREATE OR REPLACE TABLE clean.attempts AS
SELECT a.attempt_id, a.call_id, c.account_id, c.agent_id, a.attempt_no, a.attempt_status, a.vendor_id AS attempt_vendor
FROM stg.call_attempts a JOIN clean.calls c USING (call_id);

CREATE OR REPLACE TABLE clean.ptp AS
SELECT ptp_id, account_id, agent_id, promised_amount, event_at AS ptp_ts, promised_date, status, source, strftime(event_at,'%Y-%m') AS month
FROM stg.promises_to_pay;

-- AGENT SESSIONS: drop impossible sessions (logout<=login or >14h); convert to IST
CREATE OR REPLACE TABLE clean.sessions AS
SELECT session_id, agent_id, channel, to_ist(login_at, timezone) AS login_ist, to_ist(logout_at, timezone) AS logout_ist,
       date_diff('second', login_at, logout_at)/3600.0 AS hours, strftime(to_ist(login_at, timezone),'%Y-%m') AS month
FROM stg.agent_sessions WHERE logout_at > login_at AND date_diff('second', login_at, logout_at) <= 14*3600;
INSERT INTO clean.rejects SELECT 'agent_sessions', session_id, 'logout<=login or >14h', _raw_row
FROM stg.agent_sessions WHERE NOT (logout_at > login_at AND date_diff('second', login_at, logout_at) <= 14*3600);
