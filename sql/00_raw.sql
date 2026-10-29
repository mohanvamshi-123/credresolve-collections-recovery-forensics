-- 00_raw.sql : land every source CSV untouched into schema raw. ${RAW} is substituted by src/run_pipeline.py
CREATE SCHEMA IF NOT EXISTS raw;
CREATE OR REPLACE TABLE raw.borrowers              AS SELECT * FROM read_csv_auto('${RAW}/borrowers.csv', sample_size=-1);
CREATE OR REPLACE TABLE raw.accounts               AS SELECT * FROM read_csv_auto('${RAW}/accounts.csv', sample_size=-1);
CREATE OR REPLACE TABLE raw.agents                 AS SELECT * FROM read_csv_auto('${RAW}/agents.csv', sample_size=-1);
CREATE OR REPLACE TABLE raw.agent_sessions         AS SELECT * FROM read_csv_auto('${RAW}/agent_sessions.csv', sample_size=-1);
CREATE OR REPLACE TABLE raw.campaigns              AS SELECT * FROM read_csv_auto('${RAW}/campaigns.csv', sample_size=-1);
CREATE OR REPLACE TABLE raw.daily_targeting        AS SELECT * FROM read_csv_auto('${RAW}/daily_targeting.csv', sample_size=-1);
CREATE OR REPLACE TABLE raw.calls                  AS SELECT * FROM read_csv_auto('${RAW}/calls.csv', sample_size=-1);
CREATE OR REPLACE TABLE raw.call_attempts          AS SELECT * FROM read_csv_auto('${RAW}/call_attempts.csv', sample_size=-1);
CREATE OR REPLACE TABLE raw.call_dispositions      AS SELECT * FROM read_csv_auto('${RAW}/call_dispositions.csv', sample_size=-1);
CREATE OR REPLACE TABLE raw.whatsapp_events        AS SELECT * FROM read_csv_auto('${RAW}/whatsapp_events.csv', sample_size=-1);
CREATE OR REPLACE TABLE raw.sms_events             AS SELECT * FROM read_csv_auto('${RAW}/sms_events.csv', sample_size=-1);
CREATE OR REPLACE TABLE raw.field_visits           AS SELECT * FROM read_csv_auto('${RAW}/field_visits.csv', sample_size=-1);
CREATE OR REPLACE TABLE raw.promises_to_pay        AS SELECT * FROM read_csv_auto('${RAW}/promises_to_pay.csv', sample_size=-1);
CREATE OR REPLACE TABLE raw.payments               AS SELECT * FROM read_csv_auto('${RAW}/payments.csv', sample_size=-1);
CREATE OR REPLACE TABLE raw.vendor_telephony       AS SELECT * FROM read_csv_auto('${RAW}/vendor_telephony.csv', sample_size=-1);
CREATE OR REPLACE TABLE raw.complaints             AS SELECT * FROM read_csv_auto('${RAW}/complaints.csv', sample_size=-1);
CREATE OR REPLACE TABLE raw.account_status_history AS SELECT * FROM read_csv_auto('${RAW}/account_status_history.csv', sample_size=-1);
