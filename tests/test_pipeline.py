"""Invariants for the golden layer. Run: python src/run_pipeline.py && pytest -q"""
import os, duckdb, pytest

DB = "outputs/collections.duckdb"

@pytest.fixture(scope="module")
def con():
    if not os.path.exists(DB):
        pytest.skip("run `python src/run_pipeline.py` first")
    c = duckdb.connect(DB, read_only=True)
    yield c
    c.close()

def one(con, sql):
    return con.execute(sql).fetchall()[0][0]

def test_payment_ids_unique(con):
    assert one(con, "select count(*) - count(distinct payment_id) from golden.fact_payment") == 0

def test_call_ids_unique(con):
    assert one(con, "select count(*) - count(distinct call_id) from golden.fact_call") == 0

def test_payment_row_reconciliation(con):
    raw = one(con, "select count(*) from raw.payments")
    rej = one(con, "select count(*) from clean.rejects where src='payments'")
    gold = one(con, "select count(*) from golden.fact_payment")
    assert raw - rej == gold

def test_payment_amount_reconciliation(con):
    raw = one(con, "select sum(amount) from raw.payments")
    rej = one(con, "select sum(s.amount) from stg.payments s join clean.rejects x on x.src='payments' and x._raw_row=s._raw_row")
    gold = one(con, "select sum(amount) from golden.fact_payment")
    assert abs(raw - rej - gold) < 0.01

def test_call_row_reconciliation(con):
    assert one(con, "select count(*) from raw.calls") - one(con, "select count(*) from clean.rejects where src='calls'") == one(con, "select count(*) from golden.fact_call")

def test_reference_not_used_for_dedupe(con):
    # references are legitimately shared across accounts; dedupe on them would lose rows
    assert one(con, "select count(*) from (select payment_reference from golden.fact_payment where payment_reference is not null group by 1 having count(*)>1)") > 1000

def test_headline_reproduced(con):
    mom = one(con, "select reported_mom from metrics.mom where month='2026-03'")
    assert 0.105 < mom < 0.115

def test_per_day_change_is_flat(con):
    v = one(con, "select golden_per_day_mom from metrics.mom where month='2026-03'")
    assert abs(v) < 0.02

def test_partial_month_flagged(con):
    assert one(con, "select is_partial_month from metrics.monthly where month='2026-08'") is True
    assert one(con, "select count(*) from metrics.monthly where is_partial_month") == 1

def test_timezone_conversion(con):
    assert str(one(con, "select to_ist(timestamp '2026-03-01 20:00:00','UTC')")) == "2026-03-02 01:30:00"
    assert str(one(con, "select to_ist(timestamp '2026-03-01 20:00:00','Asia/Dubai')")) == "2026-03-01 21:30:00"
    assert str(one(con, "select to_ist(timestamp '2026-03-01 20:00:00','Asia/Kolkata')")) == "2026-03-01 20:00:00"

def test_legacy_ptp_code_mapped(con):
    assert one(con, "select count(*) from clean.dispositions where disposition_norm='PTP'") == 0

def test_children_inherit_parent_account(con):
    assert one(con, "select count(*) from clean.attempts a join clean.calls c using(call_id) where a.account_id<>c.account_id") == 0
    assert one(con, "select count(*) from clean.dispositions a join clean.calls c using(call_id) where a.account_id<>c.account_id") == 0

def test_net_amount_signs(con):
    assert one(con, "select count(*) from golden.fact_payment where (payment_status='SUCCESS' and net_amount<=0) or (payment_status='REVERSED' and net_amount>=0) or (payment_status in ('PENDING','FAILED') and net_amount<>0)") == 0

def test_attribution_is_strictly_before_payment(con):
    assert one(con, "select count(*) from golden.payment_attribution where touch_ts is not null and touch_ts > event_ts_ist") == 0
