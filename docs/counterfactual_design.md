# Counterfactual: "what if we had not changed the targeting strategy?"

## Question
Estimate recovery in the post-change period had the old targeting continued, i.e. the average treatment effect on the treated (ATT) of the new strategy on 14-day payment probability and on rupees recovered.

## Design
| Element | Choice |
|---|---|
| **Unit** | Account-target-day (`daily_targeting` row) |
| **Treatment** | Account targeted by a campaign on the **new** strategy (`strategy_version` v2/v3) |
| **Control** | Account targeted by **legacy/v1** campaigns in the same weeks |
| **Outcome** | SUCCESS payment within 14 days after `target_date` (and ₹ net recovered) |
| **Identification** | Difference-in-differences: (post − pre) for treated minus (post − pre) for control, pre = 14 days before target date; covariates DPD bucket, risk segment, loan type; SEs clustered by account |
| **Validation** | Pre-period balance; permutation placebo (500 re-labellings); event-study of weekly effects before/after the switch |

If a clean switch date exists (the business says one does; the data does not show one: `strategy_version` is mixed in every month), run the same DiD on **calendar time** with never-switched segments as control, and check parallel trends over at least 8 pre-weeks.

## Key assumptions
1. **Parallel trends**: absent the change, treated and control would have moved together.
2. **No interference**: targeting one account does not change another's outcome (shared agents or telephony capacity can violate this).
3. **Consistent targeting record**: `strategy_version` on the campaign is what actually drove selection (unverified here).
4. **No concurrent shocks** hitting only one arm (new vendor, new agents, a client change).

## Confounders and how they are handled
Portfolio mix (DPD, risk, loan: adjusted); seasonality and month length (per-day outcome, both arms same weeks); agent/vendor assignment (check balance; add fixed effects); selection into targeting (the targeting engine picks accounts non-randomly: use propensity-score matching/IPW on pre-period payments and contacts, or restrict to a quota-based randomized slice); attribution window (outcome is any payment, not attributed payments).

## What the available data show
Treated 3.65% vs control 3.83% 14-day payment probability post, 3.59% vs 3.72% pre. **DiD = -0.04 pp, 95% CI [-0.57, +0.49] pp, p = 0.87**; placebo sd = 0.27 pp. We can exclude effects larger than roughly ±13% relative; we cannot confirm any effect.

## Limitations
No randomization; power is limited (≈40k accounts per arm to detect +10% relative, ≈160k for +5%); `strategy_version` may not reflect the true targeting logic; pre-period of 14 days is short; no dated balances, so portfolio-acquisition effects cannot be separated from targeting effects.

## Recommended production design (what to do next)
Account-level randomized holdout: 10% of eligible accounts per day stay on legacy targeting. The counterfactual is then measured, not modelled. Complement with Bayesian shrinkage by segment for faster reads.
