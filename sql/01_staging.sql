-- 01_staging.sql : stamp every row with a lineage id (_raw_row = position in source file). No business logic: lossless and re-runnable.
CREATE SCHEMA IF NOT EXISTS stg;
CREATE OR REPLACE MACRO tz_offset_min(tz) AS CASE tz WHEN 'UTC' THEN 330 WHEN 'Asia/Dubai' THEN 90 ELSE 0 END;  -- minutes to add to reach IST
CREATE OR REPLACE MACRO to_ist(ts, tz) AS ts + to_minutes(tz_offset_min(tz));

CREATE OR REPLACE TABLE stg.payments          AS SELECT row_number() OVER () AS _raw_row, * FROM raw.payments;
CREATE OR REPLACE TABLE stg.calls             AS SELECT row_number() OVER () AS _raw_row, * FROM raw.calls;
CREATE OR REPLACE TABLE stg.call_attempts     AS SELECT row_number() OVER () AS _raw_row, * FROM raw.call_attempts;
CREATE OR REPLACE TABLE stg.call_dispositions AS SELECT row_number() OVER () AS _raw_row, * FROM raw.call_dispositions;
CREATE OR REPLACE TABLE stg.agents            AS SELECT row_number() OVER () AS _raw_row, * FROM raw.agents;
CREATE OR REPLACE TABLE stg.borrowers         AS SELECT row_number() OVER () AS _raw_row, * FROM raw.borrowers;
CREATE OR REPLACE TABLE stg.accounts          AS SELECT row_number() OVER () AS _raw_row, * FROM raw.accounts;
CREATE OR REPLACE TABLE stg.promises_to_pay   AS SELECT row_number() OVER () AS _raw_row, * FROM raw.promises_to_pay;
CREATE OR REPLACE TABLE stg.agent_sessions    AS SELECT row_number() OVER () AS _raw_row, * FROM raw.agent_sessions;
CREATE OR REPLACE TABLE stg.vendor            AS SELECT * FROM raw.vendor_telephony;
