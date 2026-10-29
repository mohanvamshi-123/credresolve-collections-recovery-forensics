# Data Quality Report

Source: `collections_30k_dataset.zip` (17 tables, 1 Jan to 8 Aug 2026; August is a partial month). All counts are produced by `sql/05_dq_waterfall.sql` (`outputs/tables/dq_waterfall.csv`) and re-checked by `tests/test_pipeline.py`.

## Raw to Rejected/Corrected to Golden

| Dataset | Raw rows | Rejected | Golden rows | What happened |
|---|---:|---:|---:|---|
| payments | 25,500 | 500 (₹3.84 Cr) | 25,000 | exact replays of `payment_id` removed |
| calls | 91,350 | 1,350 | 90,000 | duplicate `call_id` removed; sibling copy with `agent_id` kept |
| agents | 30,000 | 29,000 | 1,000 | 29.6 versions per `agent_id`; latest `updated_at` wins |
| borrowers | 30,600 | 19,585 | 11,015 | latest `updated_at` wins |
| agent_sessions | 15,000 | 0 | 15,000 | none had logout <= login or > 14h |
| call_attempts | 120,000 | 0 | 120,000 | re-keyed to parent call (see issue 7) |
| call_dispositions | 35,000 | 0 | 35,000 | re-keyed to parent call; `PTP` mapped to `PROMISE_TO_PAY` |

Payments golden composition: SUCCESS 17,534 (₹131.6 Cr), REVERSED 1,254 (₹9.5 Cr, netted off), PENDING 2,535 and FAILED 3,677 (excluded from recovery).
**Headline impact:** gross SUCCESS recovery falls 1.97% after dedupe; net-of-reversal recovery is ₹122.1 Cr (Jan to 8 Aug).

## Issues, detection, treatment, business impact

| # | Issue | Detection | Treatment | Business impact | Class |
|---|---|---|---|---|---|
| 1 | **Calendar artefact in the headline**: MoM compares 31-day March with 28-day February | Rebuilt headline from raw: SUCCESS rows, calendar month = +10.99% | Report recovery per calendar day; exclude partial August | **Entire +11% (10.7 pts of it)**; per-day change -0.1%, p = 0.98 | Fact |
| 2 | 500 duplicate payment rows | `payment_id` appears twice with identical fields | Keep first row; log in `clean.rejects` | +1.97% on gross SUCCESS, ~even each month, so no trend created | Fact |
| 3 | `payment_reference` is NOT unique: 3,406 references shared by 7,216 rows across different accounts/amounts | Same reference, different account and amount; 0 pairs with same account+amount | **Do not dedupe on reference**; 371 null references kept and flagged | Reference-based dedupe would delete ~3.8k genuine payments | Fact |
| 4 | Mixed time zones (calls: UTC / Kolkata / Dubai ≈ 1/3 each) | `timezone` column; vs IST | Convert to IST (+330 / +90 / 0 min) | 8,791 calls change date, 305 change month, 59,962 change hour | Fact |
| 5 | Payments carry no timezone | n/a | Assume provider vendor timezone (**assumption**) | Monthly net moves < 0.6% (full months); no effect on conclusions | Assumption, tested |
| 6 | Duplicate `call_id` with conflicts (79 ids have copies that differ) | Group by `call_id` | Prefer copy with `agent_id`, then earliest `event_at` (later = late re-ingest) | 68 `agent_id`s recovered; some copies carry later timestamps (e.g. +3 days) | Fact |
| 7 | Child tables disagree with parent call on keys | `call_attempts`/`call_dispositions` account_id ≠ `calls.account_id` in 119,992/120,000 and 35,000/35,000 rows | Join by `call_id`; inherit account/agent from `calls` | Any account-level contact/PTP metric built from child keys is wrong | Fact |
| 8 | `borrower_id` on fact tables disagrees with `accounts.borrower_id` (~100%) | Join check | `account_id` is the join key; borrower attributes come via `accounts` | Geography analysis relies on this choice | Fact |
| 9 | 2,913 accounts have null/orphan borrower | 455 null + orphans vs `borrowers` | `state = UNKNOWN` (kept) | Geography incomplete for ~10% of accounts | Fact |
| 10 | Agent identity: 1,099 `employee_code`s for 1,000 `agent_id`s, each code on ~27 ids; only 10 names | Cardinality of mappings | `agent_id` is canonical (all facts use it); code not used as a merge key | Agent-level conclusions rest on `agent_id` only | Fact |
| 11 | Agent timestamp conflicts: `updated_at` < `joined_at` for 4,078 rows (975 agents) | Row check | Tenure from latest version; flagged | **Tenure findings are Hypothesis-level** | Fact |
| 12 | 1,759 calls with no agent (2.0%) | Null check after dedupe | `tenure_bucket = UNKNOWN`; kept in totals | Negligible | Fact |
| 13 | Disposition schema versions (legacy / v1 / v2) coexist; legacy `PTP` = `PROMISE_TO_PAY` | Code × version × month | Map `PTP`→`PROMISE_TO_PAY`; code mix is stable over time (chi² p = 0.88) | Unmapped, PTP counts split in two (3,904 rows); no trend created | Fact |
| 14 | Only 32% of outbound calls have a disposition; 7,136 unanswered calls carry PTP/PAID | Coverage and contradiction checks | RPC/PTP reported with coverage; `calls.call_status` is truth for contact | RPC is a lower bound; PTP rate not headline-grade | Fact |
| 15 | `call_status` and `attempt_status` independent | Cross-tab | `calls.call_status` primary | Contact rate depends on this choice (flagged) | Fact |
| 16 | `duration_sec` populated for every status (avg ~450 s even for BUSY/FAILED) | Mean by status | Talk time from ANSWERED only | Raw talk-time metrics overstate by ~5x | Fact |
| 17 | PTP `KEPT` not corroborated by payments | Payment on account by promised date + 3d: 4.8% of KEPT vs 4.6% random baseline | Do not use PTP status as a recovery proxy | Claimed kept rate ~50% is not credible | Fact |
| 18 | `accounts.status` is a snapshot unrelated to payments; 75% of successful payments are on non-ACTIVE accounts | Payments by status | Never filter denominators on it | "ACTIVE only" denominator = survivorship bias | Fact |
| 19 | Campaign definitions inconsistent: only 19% of calls fall inside their campaign's start/end window; same `campaign_name` has 5 target definitions and 5 channels | Window and cardinality checks | Campaign tag is not used as truth for attribution | Campaign ROI untrustworthy | Fact |
| 20 | `account_status_history.recorded_at` precedes `event_at` in 50% of rows (30,191) | Row check | Not used for point-in-time status | Point-in-time portfolio-status analysis not possible | Fact |
| 21 | Compliance: 54% of outbound calls fall outside 08:00-19:00 IST | Hour distribution after IST | Reported, not corrected | Regulatory exposure (if timestamps are right) | Fact |
| 22 | No cost, language, or dated-balance fields exist | Schema | Costs are **assumptions** in `config/assumptions.json`; `state` proxies language | Cost metrics and ROI are conditional | Gap |
| 23 | Partial final month (payments end 8 Aug) | Date range | Flag `is_partial_month`; excluded from MoM | Raw August shows -74% MoM | Fact |

## Assumptions
1. `event_at` in `calls` is in the zone named in `calls.timezone`; WhatsApp/SMS/field/PTP timestamps are IST.
2. REVERSED rows are chargebacks booked in the month they occur and netted from recovery (the data has no link to the original payment).
3. PENDING and FAILED are not recovery.
4. Duplicate = same `payment_id` (or `call_id`). Nothing is dropped for being an outlier.
