# Was the "+11% recovery" actually real?

This is my submission for the CredResolve data analyst assignment. Short answer: no.

The +11% comes from comparing March with February. March has 31 days and February has 28, and that difference alone is about 10.7 points. When I look at recovery per calendar day, the change from February to March is about -0.1%. Recovery is basically flat from January to July, at around 55 lakh rupees a day.

The messy parts of the data (500 duplicated payments, reversals, mixed time zones) change the monthly numbers by less than 1 point, so they are not what produced the jump.

I also tested 17 things that could explain performance (vendor, agent, tenure, time of day, campaign, DPD, loan type and so on). None of them is significant once I correct for running so many tests. After any outreach, a borrower's chance of paying within 7 days is about the same as for a random borrower, so I could not find a channel that adds recovery.

For the Rs 10 Cr, I recommend better borrower targeting, released in stages. Spend Rs 1.5 Cr first on a randomized holdout test, and release the rest only if the test shows a real lift. I'm not very confident about the ROI numbers, because the data gave me no measured lift to base them on, so they rest on assumptions I state openly.

Start with `docs/executive_memo.md`, then `notebooks/analysis.ipynb`.

## How to run it

1. `pip install -r requirements.txt`
2. Put the unzipped CSVs from `collections_30k_dataset.zip` directly into `data/raw/`
3. `python src/run_pipeline.py` builds the database and the golden tables in `data/golden/`
4. `pytest -q tests` runs the checks (row counts reconcile, no duplicate IDs, time zones convert correctly, the +11% reproduces)
5. `python src/build_notebook.py`, then run `jupyter nbconvert --to notebook --execute analysis.ipynb --output analysis.ipynb` inside the `notebooks` folder
6. `python src/build_dashboard.py` and open `dashboard/index.html`

It takes under a minute.

## Where things are

| What | Where |
|---|---|
| SQL | `sql/` (run in order, 00 to 05) |
| Notebook | `notebooks/analysis.ipynb` |
| Golden dataset | `data/golden/` |
| Data quality report | `docs/data_quality_report.md` |
| Dashboard | `dashboard/index.html` |
| Executive memo | `docs/executive_memo.md` (also .docx and .pdf) |
| Architecture and production design | `docs/architecture.png`, `docs/production_design.md` |
| Metric definitions | `docs/metric_definitions.md` |
| Counterfactual design | `docs/counterfactual_design.md` |


- I removed duplicates using `payment_id` and `call_id`. I did not use `payment_reference`, because many references are shared between different accounts and amounts, and removing on it would have deleted about 3,800 real payments.
- `account_id` is the join key. The `borrower_id` and the account/agent IDs in the attempts and dispositions tables disagree with the main tables almost every time, so those tables take their keys from `calls`.
- Recovery means successful payments minus reversals, in IST, per calendar day. August is left out of month-on-month comparisons because the data stops on 8 August.
- I never filter on `accounts.status`. It is a current snapshot, and 75% of successful payments sit on accounts marked closed, paid or written off.

## Things to keep in mind

- There is no cost data, so costs are my assumptions (`config/assumptions.json`). Cost per rupee recovered and all ROI figures depend on them.
- Payments have no time zone column, so I assumed the provider's time zone. Changing that moves monthly totals by less than 0.6%.
- Language is not in the data, so I used state as a rough stand-in. Agent join dates are inconsistent for many agents, so I treat anything about tenure as a guess.
- The data looks very random. When I say "no effect", I mean I could not detect one, not that I proved there is none. I give confidence intervals where I can.