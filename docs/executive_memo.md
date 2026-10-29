# Executive memo: was recovery really up 11% month-on-month?

**To:** Leadership team  **From:** Data Analytics  **Date:** 27 Oct 2026  **Data:** 1 Jan to 8 Aug 2026, 17 source tables

## Bottom line
**No. Recovery did not improve.** The reported +11% is March (31 days) compared with February (28 days). The calendar adds 10.7 points on its own. Per calendar day, net recovery moved **-0.1%** (95% CI about -7% to +8%, p = 0.98) and has been flat from January to July at roughly **₹55 lakh a day** (₹202 Cr annualised). The number is reproduced exactly: summing every SUCCESS payment row by calendar month gives +10.99% for March.

## What happened
| | Reported | Independent |
|---|---|---|
| Mar vs Feb recovery | +11.0% | **-0.1% per day** (+10.6% before the per-day adjustment) |
| Contact rate | up | flat at 19.4-20.5% every month |
| Recovery per agent-hour | n/a | flat, ~₹15-16k |
| PTP kept rate | ~50% | **4.8% verified by actual payments** |
| Duplicate payments | none | 500 replayed rows, ₹3.8 Cr (inflates gross SUCCESS by 2.0%, evenly each month) |

Cleaning (duplicates, reversals, IST time zones) moves the monthly figures by under 1 point. The calendar effect is the whole story. Three other reporting practices also mislead: "ACTIVE accounts only" denominators (75% of payers sit on accounts marked closed/paid/written-off, so the filter drops most of the base); crediting the latest campaign (33% of the time that campaign started after the payment); and PTP status as a proxy for cash.

## Why it happened, and what did *not* cause it
We tested portfolio mix (DPD, loan type, risk segment, vintage), client geography (state; language is not in the data), agent, agent tenure, campaign, channel, vendor, hour of day and attempt number. **None is significant after multiple-testing control**; agent-to-agent spread is exactly what chance produces. The targeting-strategy change shows no detectable effect (difference-in-differences -0.04 pp, 95% CI ±0.5 pp). After any outreach, a borrower's 7-day payment probability (1.6-1.9%) equals the 1.9% of an arbitrary account-day: **no channel shows measurable incremental recovery.**

## How confident are we
**High (fact):** the headline is a calendar and duplication artefact; the data-quality issues listed above. **Strong evidence:** no mix shift, no driver effect, no targeting effect (these rule out *large* effects only; the ±0.5 pp interval cannot exclude a +13% relative lift). **Hypothesis:** tenure (agent dates conflict), vendor timezones, and anything needing language or dated balances, which the data lack.

## What we should do
**Invest the ₹10 Cr in better borrower targeting (option 4), released in stages.** More agents, telephony, AI voice, WhatsApp and field all buy more touches, and measured value per touch is about zero; 54% of calls already fall outside 08:00-19:00 IST, so more calling would amplify a compliance risk. Targeting is the only option whose cost does not scale with touches, and it builds the missing capability: a randomized holdout that measures incremental recovery.
Current features (DPD, risk, balance) have no predictive power for payment (pseudo-R² 0.0003), so the money must buy new signal (bureau/alternative data, best-time and contactability data) and experiment infrastructure.
**Release ₹1.5 Cr for a 90-day holdout; release ₹8.5 Cr only if measured lift reaches break-even.**

## Expected financial impact (assumption-driven, low confidence)
| Scenario (lift on ₹202 Cr annual recovery) | Probability | 12-month incremental | ROI 12m | ROI 36m |
|---|---|---|---|---|
| Downside: 0% (what the data show today) | 50% | ₹0 | -100% | -100% |
| Base: +3% | 35% | ₹6.1 Cr | -39% | +83% |
| Upside: +8% | 15% | ₹16.2 Cr | +62% | +386% |
| **Probability-weighted, full ₹10 Cr** | | **₹4.6 Cr** | **-54%** | **+37%** |
| Staged plan (gate at 50%) | | ₹4.6 Cr on ₹5.75 Cr expected spend | -21% | loss capped at ₹1.5 Cr |

Break-even lift is 4.9% of annual recovery in 12 months, 1.6% over 36 months. The lifts are assumptions because the data contain no measurable lift to anchor on; the holdout replaces them (about 40,000 account-days per arm detect +10%). Recovered rupees are valued at 100%; at a 10% commission the revenue break-even is ten times higher, which is why the spend is gated.

## Do now
1. Retire the +11% metric; report recovery **per calendar day with a confidence interval**. 2. Deduplicate payments on `payment_id` at ingestion (not on `payment_reference`, which is reused). 3. Compliance review of calling hours. 4. Reconcile PTP status to payment events. 5. Capture cost, language, and dated balances.
