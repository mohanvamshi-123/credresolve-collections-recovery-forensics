-- 05_dq_waterfall.sql : Raw -> Rejected/Corrected -> Golden, quantified. Counts rows and Rs.
CREATE OR REPLACE TABLE metrics.dq_waterfall AS
SELECT * FROM (
SELECT 1 AS ord, 'payments' AS dataset, 'raw rows' AS step, count(*) AS n, sum(amount) AS amount FROM raw.payments
UNION ALL SELECT 2,'payments','rejected: duplicate payment_id', count(*), (SELECT sum(s.amount) FROM stg.payments s JOIN clean.rejects x ON x.src='payments' AND x._raw_row=s._raw_row) FROM clean.rejects WHERE src='payments'
UNION ALL SELECT 3,'payments','golden rows', count(*), sum(amount) FROM golden.fact_payment
UNION ALL SELECT 4,'payments','  of which SUCCESS (gross recovery)', count(*), sum(amount) FROM golden.fact_payment WHERE payment_status='SUCCESS'
UNION ALL SELECT 5,'payments','  of which REVERSED (netted off)', count(*), sum(amount) FROM golden.fact_payment WHERE payment_status='REVERSED'
UNION ALL SELECT 6,'payments','  of which PENDING (excluded, unconfirmed)', count(*), sum(amount) FROM golden.fact_payment WHERE payment_status='PENDING'
UNION ALL SELECT 7,'payments','  of which FAILED (excluded)', count(*), sum(amount) FROM golden.fact_payment WHERE payment_status='FAILED'
UNION ALL SELECT 8,'payments','corrected: missing payment_reference (kept, flagged)', count(*), sum(amount) FROM golden.fact_payment WHERE ref_missing
UNION ALL SELECT 9,'payments','corrected: month changes after IST normalisation', count(*), sum(amount) FROM golden.fact_payment WHERE month_ist <> month_src
UNION ALL SELECT 10,'calls','raw rows', count(*), NULL FROM raw.calls
UNION ALL SELECT 11,'calls','rejected: duplicate call_id', count(*), NULL FROM clean.rejects WHERE src='calls'
UNION ALL SELECT 12,'calls','golden rows', count(*), NULL FROM golden.fact_call
UNION ALL SELECT 13,'calls','corrected: agent_id recovered from sibling duplicate', count(*), NULL FROM (SELECT call_id FROM raw.calls WHERE agent_id IS NULL) n JOIN golden.fact_call g USING(call_id) WHERE g.agent_id IS NOT NULL
UNION ALL SELECT 14,'calls','still missing agent_id (tenure=UNKNOWN)', count(*), NULL FROM golden.fact_call WHERE agent_id IS NULL
UNION ALL SELECT 15,'calls','corrected: IST date differs from source date', count(*), NULL FROM golden.fact_call WHERE event_date_ist <> CAST(event_at_src AS DATE)
UNION ALL SELECT 16,'calls','corrected: IST month differs from source month', count(*), NULL FROM golden.fact_call WHERE month_ist <> month_src
UNION ALL SELECT 17,'calls','corrected: IST hour differs from source hour', count(*), NULL FROM golden.fact_call WHERE hour_ist <> hour_src
UNION ALL SELECT 18,'calls','non-ANSWERED calls carrying talk duration > 0 (unusable for talk-time)', count(*), NULL FROM golden.fact_call WHERE NOT is_answered AND duration_sec > 0
UNION ALL SELECT 19,'agents','raw rows', count(*), NULL FROM raw.agents
UNION ALL SELECT 20,'agents','golden agent_id (latest version wins)', count(*), NULL FROM golden.dim_agent
UNION ALL SELECT 21,'agents','agent_ids with updated_at < joined_at (timestamp conflict)', count(*), NULL FROM golden.dim_agent WHERE ts_conflict
UNION ALL SELECT 22,'borrowers','raw rows', count(*), NULL FROM raw.borrowers
UNION ALL SELECT 23,'borrowers','golden borrower_id', count(*), NULL FROM clean.dim_borrower
UNION ALL SELECT 24,'accounts','accounts with null/orphan borrower_id (state=UNKNOWN)', count(*), NULL FROM golden.dim_account WHERE borrower_orphan
UNION ALL SELECT 25,'call_attempts','raw rows', count(*), NULL FROM raw.call_attempts
UNION ALL SELECT 26,'call_attempts','account_id disagrees with parent call (re-keyed to calls)', count(*), NULL FROM raw.call_attempts a JOIN clean.calls c USING (call_id) WHERE a.account_id <> c.account_id
UNION ALL SELECT 27,'call_dispositions','raw rows', count(*), NULL FROM raw.call_dispositions
UNION ALL SELECT 28,'call_dispositions','account_id disagrees with parent call (re-keyed to calls)', count(*), NULL FROM raw.call_dispositions a JOIN clean.calls c USING (call_id) WHERE a.account_id <> c.account_id
UNION ALL SELECT 29,'call_dispositions','legacy code PTP mapped to PROMISE_TO_PAY', count(*), NULL FROM raw.call_dispositions WHERE disposition_code = 'PTP'
UNION ALL SELECT 30,'agent_sessions','raw rows', count(*), NULL FROM raw.agent_sessions
UNION ALL SELECT 31,'agent_sessions','rejected: logout<=login or >14h', count(*), NULL FROM clean.rejects WHERE src='agent_sessions'
UNION ALL SELECT 32,'account_status_history','recorded_at earlier than event_at (back-dated / overwritten)', count(*), NULL FROM raw.account_status_history WHERE recorded_at < event_at
UNION ALL SELECT 33,'payments','payment_reference reused across different accounts (NOT duplicates; do not dedupe on it)', count(*), NULL FROM (SELECT payment_reference FROM clean.payments WHERE payment_reference IS NOT NULL GROUP BY 1 HAVING count(DISTINCT account_id) > 1)
) ORDER BY ord;
