# Metric definitions: reported (probable) vs independent

Implemented in `sql/04_metrics.sql`. "Reported" = our reconstruction of the simplest calculation consistent with the +11% headline.

| Metric | Probable reported | Independent definition | Why |
|---|---|---|---|
| **Recovery** | Sum of all SUCCESS payment rows (duplicates in), calendar month | Deduped by `payment_id`; SUCCESS − REVERSED; IST month; **per calendar day** | Removes replays, chargebacks and the 28/30/31-day artefact. Only the per-day change (-0.1%) is comparable across months |
| **Recovery rate** | Recovery / ACTIVE-account balance | Net recovery per day × 30 / outstanding of **all** accounts | Status is a snapshot unrelated to payment; filtering on it drops 75% of payers |
| **Recovery per account** | Recovery / accounts paying | Net recovery / all accounts in scope | Dividing by payers only rewards losing non-payers (survivorship) |
| **Contact rate** | Connected / attempts incl. inbound and duplicates | ANSWERED outbound / outbound dials (deduped); plus account-level: accounts answered / accounts dialed | Inbound and replays inflate it; `calls.call_status` is the source of truth. Stable at 19.4-20.5% |
| **RPC** | Connected calls | Answered calls with a right-party disposition / answered calls, **reported with disposition coverage (32%)** | Disposition missing for 68%; contradictions exist, so RPC is a lower bound |
| **PTP rate** | PTPs / connected | (`PROMISE_TO_PAY` + legacy `PTP`) / dispositioned calls | Legacy code must be merged |
| **PTP kept rate** | KEPT / (KEPT + BROKEN) ≈ 50% | **Verified**: share of PTPs with a SUCCESS payment on the account between PTP date and promised date + 3d (≈ 4-5%) | The status field is not corroborated by cash |
| **Recovery per agent-hour** | Recovery / agents × fixed hours | Net recovery / logged session hours (sessions cleaned, IST) | Hours actually logged; ~₹15-16k, flat |
| **Cost per ₹ recovered** | n/a (no cost data) | (agent-hours × rate + call-minutes × rate + messages × rate + visits × rate) / net recovery, rates in `config/assumptions.json` | **Assumption-driven**; ~1.7 paise per ₹; flat |
| **Channel conversion** | Payments attributed to last campaign / touches | P(SUCCESS payment within 7d after touch) vs the same probability for random account-days (incremental lift) | Last-campaign credit assigns payments to campaigns that started after them in 33% of cases; windowed last-touch plus a baseline measures *incremental* effect |
| **Attribution** | Latest campaign on account | Last touch strictly before payment, window chosen at query time (7d default) | Window moves attributed recovery from 3% (1d) to 55% (30d); always show the window |

Conventions: IST everywhere; partial months flagged and excluded from MoM; every rate states its denominator and coverage.
