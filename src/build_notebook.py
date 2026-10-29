"""Builds notebooks/analysis.ipynb (narrative + code) and executes it. Run: python src/build_notebook.py"""
import nbformat as nbf
nb = nbf.v4.new_notebook(); C = []
md = lambda s: C.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: C.append(nbf.v4.new_code_cell(s.strip()))

md("""# Collections recovery: was the "+11% month-on-month" real?
**Approach.** Rebuild the headline from raw data, then test every candidate explanation (duplicates, time zones, attribution, mix, denominators, agents, vendors) with simple, transparent statistics.
All numbers below come from the DuckDB database built by `python src/run_pipeline.py` (SQL in `sql/`). Every conclusion carries a label: **Fact / Strong evidence / Correlation / Hypothesis**.

**Bottom line (verified in the cells below):** the +11% is a **calendar artefact**. It is March's 31 days vs February's 28 days (+10.7%) plus a small duplicate/reversal effect. Per calendar day, recovery changed by about **-0.1%** (p = 0.98). No operational driver we can measure moves recovery or contact rate.""")
code("""
import os, duckdb, numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from scipy import stats
import statsmodels.formula.api as smf
os.chdir('..') if os.path.basename(os.getcwd())=='notebooks' else None
os.makedirs('outputs/figures',exist_ok=True); os.makedirs('outputs/tables',exist_ok=True)
con = duckdb.connect('outputs/collections.duckdb', read_only=True)
q = lambda sql: con.sql(sql).df()
pd.set_option('display.width',200,'display.max_columns',30,'display.float_format',lambda x:f'{x:,.4f}')
plt.rcParams.update({'figure.dpi':110,'axes.spines.top':False,'axes.spines.right':False,'font.size':9})
RAW = {t: con.execute(f'select count(*) from raw.{t}').fetchall()[0][0] for t in [r[0] for r in con.execute("select table_name from information_schema.tables where table_schema='raw'").fetchall()]}
pd.Series(RAW,name='raw_rows').sort_values(ascending=False).to_frame()
""")
md("""## 1. What happened
### 1a. Reproduce the headline
Only one construction of the data gives +11%: **sum of every `SUCCESS` payment row (duplicates included), by calendar month, March vs February**. That is almost certainly the reported number.""")
code("""
mom = q("select * from metrics.mom"); mom.to_csv('outputs/tables/mom.csv',index=False)
view = mom[['month','reported_success','reported_mom','net_recovery','golden_net_mom','golden_per_day_mom','is_partial_month']].copy()
view
""")
md("""Reading the table: `reported_mom` for 2026-03 is **+10.99%**. After de-duplication and netting reversals (`golden_net_mom`) it is still +10.6%, so cleaning explains only ~0.4 pts. The big move is the next column: dividing by days in the month (`golden_per_day_mom`) gives **-0.12%**.
August is a partial month (data stops 8-Aug) and must be excluded from any MoM; the raw series shows it as -74%.""")
code("""
fig,ax=plt.subplots(1,2,figsize=(11,3.6))
m=mom[~mom.is_partial_month].reset_index(drop=True)
w=.38;x=np.arange(len(m))
ax[0].bar(x-w/2,m.reported_mom.fillna(0)*100,w,label='Reported (raw SUCCESS, calendar month)',color='#c0504d')
ax[0].bar(x+w/2,m.golden_per_day_mom.fillna(0)*100,w,label='Golden (deduped, net, per day)',color='#1f4e79')
ax[0].set_xticks(x);ax[0].set_xticklabels(m.month.str[5:]);ax[0].axhline(0,c='k',lw=.6);ax[0].set_ylabel('MoM %');ax[0].legend(frameon=False,fontsize=7);ax[0].set_title('Month-on-month change')
dly=q("select event_date_ist d,sum(net_amount)/1e6 net from golden.fact_payment where event_date_ist<'2026-08-01' group by 1 order by 1");dly['d']=pd.to_datetime(dly.d)
ax[1].plot(dly.d,dly.net,lw=.6,c='#999');ax[1].plot(dly.d,dly.net.rolling(14).mean(),c='#1f4e79',lw=1.8,label='14-day mean');ax[1].set_title('Daily net recovery (Rs M): flat');ax[1].legend(frameon=False)
plt.tight_layout();plt.savefig('outputs/figures/headline_vs_golden.png');plt.show()
""")
md("""### 1b. Is any change statistically distinguishable from noise?
Daily net recovery has a coefficient of variation of ~15%, so a single month's mean carries ~±2.7% noise. Test Feb vs Mar per-day, and a linear trend over all 212 days.""")
code("""
d=q("select event_date_ist d,sum(net_amount) net from golden.fact_payment where event_date_ist<'2026-08-01' group by 1 order by 1");d['d']=pd.to_datetime(d.d);d['m']=d.d.dt.strftime('%Y-%m')
f,m_=d[d.m=='2026-02'].net,d[d.m=='2026-03'].net
t=stats.ttest_ind(m_,f,equal_var=False);rng=np.random.default_rng(1)
bs=[rng.choice(m_,len(m_)).mean()/rng.choice(f,len(f)).mean()-1 for _ in range(5000)]
sl=stats.linregress(np.arange(len(d)),d.net)
pd.Series({'Feb mean/day (Rs)':f.mean(),'Mar mean/day (Rs)':m_.mean(),'per-day change':m_.mean()/f.mean()-1,'Welch t-test p':t.pvalue,'bootstrap 95% CI low':np.percentile(bs,2.5),'bootstrap 95% CI high':np.percentile(bs,97.5),
 'linear trend, % of mean over period':sl.slope*len(d)/d.net.mean(),'trend p-value':sl.pvalue,'daily CV':d.net.std()/d.net.mean()}).to_frame('value')
""")
md("""**Fact:** per-day recovery Feb to Mar changed by ~-0.1% (95% CI about -7% to +8%). **Strong evidence:** there is no trend across Jan-Jul (p = 0.29). The only month that looks different is April (-4.9% per day), and that is within normal month-to-month noise.""")

md("""## 2. Data forensics (assignment Part 2, items A to G)
### Raw to Rejected/Corrected to Golden""")
code("""
wf=q("select ord,dataset,step,n,amount from metrics.dq_waterfall order by ord");wf.to_csv('outputs/tables/dq_waterfall.csv',index=False);wf
""")
md("""**A. Duplicate payments - Fact.** 500 payment rows are exact replays (same `payment_id`, timestamp, amount). They carry ₹3.84 Cr (all statuses); the SUCCESS-status subset is shown below. Do NOT dedupe on `payment_reference`: 3,406 references are shared by different accounts and amounts, so a reference-based dedupe would delete ~3,800 genuine payments.""")
code("""
dup=q('''select s.payment_status status,count(*) rows_rejected,sum(s.amount)/1e6 amt_m from stg.payments s join clean.rejects x on x.src='payments' and x._raw_row=s._raw_row group by 1 order by 1''')
ref=q('''select count(*) refs_shared,sum(n) rows_in_shared_refs from (select payment_reference,count(*) n from clean.payments where payment_reference is not null group by 1 having count(distinct account_id)>1)''')
same_acct=q('''select count(*) pairs_same_account_and_amount from clean.payments a join clean.payments b on a.payment_reference=b.payment_reference and a.payment_id<b.payment_id and a.account_id=b.account_id and a.amount=b.amount''')
print(dup.to_string(index=False));print(ref.to_string(index=False));print(same_acct.to_string(index=False))
inflation=q("select sum(case when payment_status='SUCCESS' then amount end) from raw.payments").iloc[0,0]/q("select sum(amount) from golden.fact_payment where payment_status='SUCCESS'").iloc[0,0]-1
print('Duplicates inflate gross SUCCESS recovery by',round(inflation*100,2),'%  (roughly flat across months, so they do not create a trend)')
print(q("select strftime(s.event_at,'%Y-%m') m,count(*) dups from stg.payments s join clean.rejects x on x.src='payments' and x._raw_row=s._raw_row group by 1 order by 1").T.to_string())
""")
md("""**B. Attribution errors - Strong evidence.** Crediting an account's *latest campaign* (a common shortcut) assigns payments to campaigns that **started after the payment** in about a third of cases. The proper rule is last touch strictly before the payment, inside a window. The window changes the story completely (below).""")
code("""
rows=[]
for w in [1,3,7,14,30,60,10000]:
    r=q(f"select count(*) filter(where lag_days<={w})*1.0/count(*) share_pay, sum(amount) filter(where lag_days<={w})/sum(amount) share_amt from golden.payment_attribution").iloc[0]
    rows.append({'window_days':w if w<10000 else 'any prior touch','share_of_payments_attributed':r.share_pay,'share_of_rupees':r.share_amt})
att=pd.DataFrame(rows);att.to_csv('outputs/tables/attribution_window.csv',index=False)
late=q('''select count(*) n,count(*) filter(where cm.start_at>p.event_ts_ist)*1.0/count(*) latest_campaign_started_after_payment from golden.payment_attribution p left join golden.latest_campaign_by_account l using(account_id) left join raw.campaigns cm on cm.campaign_id=l.latest_campaign''')
print(att.to_string(index=False));print(late.to_string(index=False))
inw=q("select count(*) filter(where f.event_ts_ist between c.start_at and c.end_at)*1.0/count(*) inside_window from golden.fact_call f join raw.campaigns c using(campaign_id)");print('calls dated inside their own campaign start/end window:',round(inw.iloc[0,0],3))
""")
md("""Only **18% of payments have any touch in the prior 7 days** and 55% within 30. Attribution is therefore extremely window-sensitive: a 30-day window credits 3x the recovery a 7-day window does. Also, only ~19% of calls fall inside the start/end window of the campaign they are tagged with (**inconsistent campaign definitions - Fact**), so campaign-level ROI cannot be trusted from the campaign tag alone.""")
md("""**C. Time-zone problems - Fact.** `calls.timezone` mixes UTC / Asia/Kolkata / Asia/Dubai (one third each). Converting all to IST changes the date of ~10% of calls (8,791), the month of 305 calls, and the hour of 67% (59,962). Payments have no timezone column; we used the provider's vendor timezone (assumption, tested below).""")
code("""
tz=q('''select count(*) calls, count(*) filter(where event_date_ist<>cast(event_at_src as date)) date_changed, count(*) filter(where month_ist<>month_src) month_changed, count(*) filter(where hour_ist<>hour_src) hour_changed,
 count(*) filter(where hour_src between 8 and 18)*1.0/count(*) in_window_src, count(*) filter(where hour_ist between 8 and 18)*1.0/count(*) in_window_ist from golden.fact_call where direction='OUTBOUND' ''');print(tz.T.to_string())
alt=q("select month_ist m,sum(net_amount) a from golden.fact_payment group by 1 order by 1");alt2=q("select strftime(event_at_src,'%Y-%m') m,sum(net_amount) a from golden.fact_payment group by 1 order by 1")
x=alt.merge(alt2,on='m');x['diff_pct']=x.a_x/x.a_y-1;print('Payment tz sensitivity (IST-normalised vs source-clock monthly net):');print(x.to_string(index=False))
""")
md("""Compliance angle (**Fact, subject to timestamps being correct**): about **54% of outbound calls fall outside 08:00-19:00 IST**, the window generally applied to borrower calls. This is independent of the recovery question but should be escalated.

**D. Vendor / disposition mapping - Fact (no drift found).** Three disposition schema versions (legacy, v1, v2) coexist in every month at ~33% each, and the legacy code `PTP` is the same concept as `PROMISE_TO_PAY` (3,904 rows). The *mix* of codes does not change over time (below), so code changes cannot manufacture a trend. They do split any PTP count in two if left unmapped: **`PTP` + `PROMISE_TO_PAY` must be summed.** Vendor ids also do not change meaning over time (all 15 appear in every month).""")
code("""
dd=q("select strftime(event_ts_ist,'%Y-%m') m,disposition_raw c,count(*) n from clean.dispositions where strftime(event_ts_ist,'%Y-%m')<'2026-08' group by 1,2")
t=dd.pivot(index='m',columns='c',values='n');print('chi2 p-value, code mix homogeneous across months:',round(stats.chi2_contingency(t)[1],3))
cov=q('''select count(*) outbound_calls, count(disposition_norm)*1.0/count(*) share_with_disposition,
 count(*) filter(where not is_answered and disposition_norm in ('PROMISE_TO_PAY','PAID'))  unanswered_but_PTP_or_PAID from golden.fact_call where direction='OUTBOUND' ''');print(cov.T.to_string())
""")
md("""Also **Fact:** only ~32% of outbound calls have a disposition, and 7,136 *unanswered* calls carry a `PROMISE_TO_PAY`/`PAID` disposition. `call_attempts.attempt_status` and `calls.call_status` are statistically independent (a call marked ANSWERED is as likely to have a FAILED attempt as a CONNECTED one). We therefore use `calls.call_status` as the single source of truth for contact, and re-key attempts and dispositions to their parent call via `call_id` (their own `account_id` and `agent_id` disagree with the parent call in ~100% of rows).

**E. Agent identity - Fact.** 30,000 agent rows describe 1,000 `agent_id`s (29.6 versions each). `employee_code` has 1,099 values, each mapped to ~27 different agent_ids, and there are only 10 distinct names. So no alternate key can resolve identity: `agent_id` is the only key facts use, so we use it and take the latest version per id. 975 agent_ids have at least one version with `updated_at` earlier than `joined_at`, so tenure is a low-confidence field (**Hypothesis** level for any tenure finding). 1,759 calls (2.0%) have no agent at all; 68 were repaired from a sibling duplicate.

**F. Portfolio mix - Strong evidence of no shift.** Recovery composition by DPD bucket, loan type and risk segment is statistically stable across months (tests below). **G. Denominator manipulation** is covered in section 3.""")
md("""## 3. Statistical investigation (Part 3)
### 3a. Mix effects, Simpson's paradox, cohort effects""")
code("""
res=[]
for col in ['dpd_bucket','loan_type','risk_segment']:
    cnt=q(f"select month_ist m,{col} g,count(*) n from golden.fact_payment where payment_status='SUCCESS' and month_ist<'2026-08' group by 1,2").pivot(index='m',columns='g',values='n')
    res.append({'dimension':col,'test':'chi2: payer mix same across months','p_value':stats.chi2_contingency(cnt)[1]})
coh=q("select strftime(opened_at,'%Y-%m') v,count(*) n from golden.dim_account group by 1 order by 1");print('account vintages:',coh.v.min(),'to',coh.v.max())
cnt=q("select month_ist m,strftime(a.opened_at,'%Y-%m') v,count(*) n from golden.fact_payment p join golden.dim_account a using(account_id) where payment_status='SUCCESS' and month_ist<'2026-08' group by 1,2").pivot(index='m',columns='v',values='n').fillna(0)
res.append({'dimension':'vintage (opened_at month)','test':'chi2: payer vintage mix same across months','p_value':stats.chi2_contingency(cnt)[1]})
pd.DataFrame(res)
""")
code("""
# Shift-share (Kitagawa) decomposition of Feb->Mar change in recovery per touched account, by DPD bucket
x=q('''with touched as (select distinct account_id, strftime(touch_ts,'%Y-%m') m from golden.fact_touch),
pay as (select account_id,month_ist m,sum(net_amount) r from golden.fact_payment group by 1,2)
select t.m, a.dpd_bucket seg, count(*) accts, coalesce(sum(p.r),0) rec from touched t join golden.dim_account a using(account_id) left join pay p on p.account_id=t.account_id and p.m=t.m
where t.m in ('2026-02','2026-03') group by 1,2''')
f=x[x.m=='2026-02'].set_index('seg');m=x[x.m=='2026-03'].set_index('seg')
w0,w1=f.accts/f.accts.sum(),m.accts/m.accts.sum();rf,rm=f.rec/f.accts,m.rec/m.accts
tot=(w1*rm).sum()-(w0*rf).sum();mix=((w1-w0)*(rf+rm)/2).sum();rate=(((w0+w1)/2)*(rm-rf)).sum()
print(pd.Series({'recovery per touched account Feb':(w0*rf).sum(),'Mar':(w1*rm).sum(),'total change':tot,'mix effect':mix,'rate effect':rate,'mix share of change':mix/tot}).to_string())
""")
md("""**Strong evidence:** payer mix by DPD, loan type, risk segment and account vintage does not differ across months (all p ≥ 0.09, none significant), and the mix term in the Feb-to-Mar decomposition is small relative to the rate term. A portfolio acquired in the period would show a vintage shift; none is visible. (`accounts` is a static snapshot, so exposure mix cannot change over time. A genuine portfolio-acquisition test needs dated balances; see the recommendation.)

**Simpson's paradox.** If the aggregate +11% hid opposing sub-group moves, the raw per-segment MoM would disagree in sign. Check it:""")
code("""
rows=[]
for col in ['dpd_bucket','loan_type','risk_segment']:
    t=q(f"select {col} g,month_ist m,sum(net_amount) s from golden.fact_payment where month_ist in ('2026-02','2026-03') group by 1,2").pivot(index='g',columns='m',values='s')
    raw=q(f"select {col} g,strftime(event_at_src,'%Y-%m') m,sum(amount) s from golden.fact_payment where payment_status='SUCCESS' and strftime(event_at_src,'%Y-%m') in ('2026-02','2026-03') group by 1,2").pivot(index='g',columns='m',values='s')
    for g in t.index: rows.append({'dim':col,'segment':g,'raw_MoM':raw.loc[g,'2026-03']/raw.loc[g,'2026-02']-1,'per_day_MoM':(t.loc[g,'2026-03']/31)/(t.loc[g,'2026-02']/28)-1})
sp=pd.DataFrame(rows);print(sp.groupby('dim')[['raw_MoM','per_day_MoM']].agg(['min','max']).to_string())
print('segments with raw MoM > 0:',(sp.raw_MoM>0).sum(),'of',len(sp),'| segments with per-day MoM > 0:',(sp.per_day_MoM>0).sum(),'of',len(sp))
""")
md("""The raw gain is positive in **all 14 of 14** segments (loan type +7% to +14%, risk segment +4% to +16%, DPD bucket +0.5% to +25%): the signature of a uniform calendar effect; a mix effect would be concentrated in a few segments. No Simpson reversal. Per day, only 9 of 14 segments are positive and they scatter around zero (-12% to +14%): noise.

### 3b. Denominator manipulation, survivorship and selection bias""")
code("""
st=q('''with e as (select acct_status_snapshot s,count(*) n,sum(outstanding_amount) ex from golden.dim_account group by 1),
p as (select acct_status_snapshot s,sum(net_amount) net,count(*) filter(where payment_status='SUCCESS') k from golden.fact_payment group by 1)
select s status,n accounts,ex/1e9 exposure_bn,net/1e6 net_rec_m,net/ex rec_rate,k successful_payments from e join p using(s)''');print(st.to_string(index=False))
print('share of successful payments landing on accounts whose snapshot status is NOT ACTIVE:',round(1-st.set_index('status').loc['ACTIVE','successful_payments']/st.successful_payments.sum(),3))
tg=q('''select t.status,count(*) n,avg((exists(select 1 from golden.fact_payment p where p.account_id=t.account_id and p.payment_status='SUCCESS' and p.event_ts_ist between t.target_date and t.target_date+interval 14 day))::int) paid_within_14d from raw.daily_targeting t group by 1 order by 1''');print(tg.to_string(index=False))
""")
md("""**Fact:** `accounts.status` is a current snapshot that is unrelated to payment behaviour. **75% of successful payments sit on accounts marked CLOSED, PAID or WRITEOFF** with identical rates across all four statuses. So a denominator of "ACTIVE accounts only" would silently drop 75% of paying accounts from the base: it is survivorship bias. We use *all accounts* as the denominator and never filter on snapshot status.

**Selection bias in targeting - Fact:** accounts the targeting engine `SKIPPED`/`EXPIRED` pay within 14 days at the same rate (≈3.6%) as those `CONTACTED`. Either targeting has no value or the status field is not a reliable record of what happened; either way "contacted accounts convert better" is not supported. Another way unsuccessful accounts vanish: **PTPs** (below).""")
md("""### 3c. PTP and other conversion metrics, reported vs independent""")
code("""
p=q("select status,count(*) n,avg(verified_paid::int) verified_rate,sum(promised_amount)/1e6 promised_m from golden.fact_ptp group by 1 order by 1");print(p.to_string(index=False))
k=p.set_index('status');print('Claimed PTP kept rate K/(K+B):',round(k.loc['KEPT','n']/(k.loc['KEPT','n']+k.loc['BROKEN','n']),3))
print('Verified (a SUCCESS payment on the account by promised_date+3d) among KEPT:',round(k.loc['KEPT','verified_rate'],3),'| among BROKEN:',round(k.loc['BROKEN','verified_rate'],3))
base=q("select avg(exists_pay::int) from (select (exists(select 1 from clean.payments pay where pay.account_id=a.account_id and pay.payment_status='SUCCESS' and pay.event_ts_ist between timestamp '2026-03-01' and timestamp '2026-03-18'))::int exists_pay from golden.dim_account a)").iloc[0,0];print('Random-account 18-day payment rate (coincidence baseline):',round(base,3))
t=stats.chi2_contingency(pd.crosstab(q("select status,verified_paid from golden.fact_ptp").status.isin(['KEPT']),q("select status,verified_paid from golden.fact_ptp").verified_paid))[1];print('chi2 p (KEPT vs rest verified):',round(t,3))
""")
md("""**Fact:** the claimed PTP kept rate (~50%) is not corroborated by payments: only ~4.8% of `KEPT` promises have a successful payment on that account by the promised date +3 days, which is no better than BROKEN promises (~4.1%) or coincidence. So PTP status is **not usable as a recovery proxy** and PTP kept rate is a vanity metric here until the status is reconciled to payment events.

### 3d. Drivers: do contact rates differ by anything? (with multiple-testing control)
We test 17 dimensions. Expect ~1 false positive at α = 0.05 by chance alone, so use Bonferroni (0.05/17 = 0.003).""")
code("""
fc=q("select f.*,c.channel camp_channel,c.campaign_name,c.strategy_version,c.target_definition,vt.vendor_name from golden.fact_call f left join raw.campaigns c using(campaign_id) left join raw.vendor_telephony vt on vt.vendor_id=f.vendor_id where direction='OUTBOUND' and month_ist>='2026-01'")
rows=[]
for col in ['month_ist','vendor_id','vendor_name','time_band_ist','hour_src','tenure_bucket','attempt_no','camp_channel','campaign_name','strategy_version','target_definition','dpd_bucket','loan_type','risk_segment','state','team','src_tz']:
    g=fc.groupby(col).is_answered.mean();p=stats.chi2_contingency(pd.crosstab(fc[col],fc.is_answered))[1]
    rows.append({'dimension':col,'groups':len(g),'min_contact_rate':g.min(),'max_contact_rate':g.max(),'chi2_p':p,'significant_after_Bonferroni':p<0.05/17})
dr=pd.DataFrame(rows).sort_values('chi2_p');dr.to_csv('outputs/tables/driver_scan.csv',index=False);dr
""")
code("""
a=q("select agent_id,count(*) n,sum(is_answered::int) k from golden.fact_call where direction='OUTBOUND' and agent_id is not null group by 1");pp=a.k.sum()/a.n.sum()
chi=(((a.k-a.n*pp)**2)/(a.n*pp*(1-pp))).sum();print(f'Agents: {len(a)}, ~{a.n.mean():.0f} calls each. Dispersion ratio = {chi/(len(a)-1):.3f} (1.0 = pure chance), p = {1-stats.chi2.cdf(chi,len(a)-1):.2f}')
r=a.assign(r=a.k/a.n).r;print('Best/worst decile of agents by contact rate:',round(r.quantile(.9),3),'/',round(r.quantile(.1),3),'-> exactly the spread binomial noise produces')
d=q('''with p as (select event_date_ist d,sum(net_amount)/1e6 net from golden.fact_payment group by 1),cl as (select event_date_ist d,count(*)/100.0 dials from golden.fact_call where direction='OUTBOUND' group by 1),
s as (select cast(login_ist as date) d,sum(hours)/100 hrs from clean.sessions group by 1),w as (select cast(event_at as date) d,count(*)/100.0 wa from raw.whatsapp_events group by 1),
m as (select cast(event_at as date) d,count(*)/100.0 sms from raw.sms_events group by 1),f as (select cast(event_at as date) d,count(*)/100.0 fv from raw.field_visits group by 1)
select * from p join cl using(d) join s using(d) join w using(d) join m using(d) join f using(d) where d between '2026-01-02' and '2026-07-31' ''');d['dow']=pd.to_datetime(d.d).dt.dayofweek
r=smf.ols('net~hrs+dials+wa+sms+fv+C(dow)',data=d).fit(cov_type='HAC',cov_kwds={'maxlags':3})
ci=r.conf_int().loc[['hrs','dials','wa','sms','fv']];ci.columns=['ci_low','ci_high'];ci['coef_Rs_M_per_100_units']=r.params[['hrs','dials','wa','sms','fv']];ci['p']=r.pvalues[['hrs','dials','wa','sms','fv']]
print('Daily recovery vs daily inputs (Rs M per +100 units), HAC SEs, n =',len(d),', R2 =',round(r.rsquared,3),', joint F p =',round(r.f_pvalue,2));ci.to_csv('outputs/tables/input_elasticity.csv')
ci
""")
md("""**Findings.** Fact-level: no dimension is significant after Bonferroni. The raw p-values for `state` (0.024), `vendor_name` (0.050) and `time_band` (0.057) are the 1-in-17 false positives you expect. Agent-to-agent variation is indistinguishable from binomial noise (dispersion 0.99), so there is no "top agent" signal to scale and no tenure effect (**Strong evidence** of absence, with tenure itself **Hypothesis**-level because of the joined_at conflicts). Daily recovery does not respond to daily agent-hours, dials, WhatsApp, SMS or field volume (joint p = 0.26, R² = 4%). **Language** is not in the data at all: `state` is the only proxy, and it shows no effect (**Hypothesis** at best).

### 3e. Time-series effects
Daily recovery has a mild weekday pattern (Saturday ~4% lower) and ~15% daily noise, but no trend and no change point. A 28-day February against a 31-day March is the single largest source of apparent movement.""")

md("""## 4. Independent metric definitions
Reported-style vs golden (details and rationale in `docs/metric_definitions.md`).""")
code("""
mm=q("select * from metrics.monthly where not is_partial_month")
cols=['month','success_amt','net_recovery','net_recovery_per_day','recovery_rate_30d_norm','contact_rate','account_contact_rate','agent_hours','recovery_per_agent_hour','assumed_cost_inr','cost_per_rupee_recovered']
t=mm[cols].copy();t.to_csv('outputs/tables/monthly_scorecard.csv',index=False);t
""")
code("""
rpc=q('''select count(*) answered, count(disposition_norm) with_disp, count(*) filter(where disposition_norm not in ('WRONG_NUMBER','NO_CONTACT')) rpc_disp from golden.fact_call where direction='OUTBOUND' and is_answered''')
ptp_calls=q("select count(*) filter(where disposition_norm='PROMISE_TO_PAY') ptp, count(*) filter(where disposition_norm is not null) disp from golden.fact_call where direction='OUTBOUND'")
print(rpc.T.to_string()); print('RPC rate (answered with a right-party disposition / answered):',round(rpc.rpc_disp[0]/rpc.answered[0],3),' <- only computable for the',round(rpc.with_disp[0]/rpc.answered[0],2),'of answered calls that have any disposition; the rest are missing, so RPC is a lower bound.')
print('PTP rate among dispositioned calls (PTP+PROMISE_TO_PAY):',round(ptp_calls.ptp[0]/ptp_calls.disp[0],3))
""")
md("""**What changes when definitions are rebuilt** (all verified above):
- *Recovery* = SUCCESS minus REVERSED, deduplicated by `payment_id`, IST months, normalised per calendar day. Reported MoM +11.0% → -0.1%.
- *Contact rate* = ANSWERED outbound / outbound dials, stable at 19.4-20.5% every month (no improvement). Account-level contact rate 22.3-23.8%.
- *RPC*, *PTP rate*, *PTP kept rate* are computable only for dispositioned calls (32%) and are unverifiable against payments. Report them with coverage; do not headline them.
- *Recovery per agent-hour* = net recovery / logged session hours. About ₹15-16k/h, flat. *Cost per ₹ recovered* is **assumption-driven** (no cost data exists): 1.7 paise per ₹ under `config/assumptions.json`; it is flat because every driver is flat.

## 5. Counterfactual: what if the targeting strategy had not changed? (Part 4)
**Design in `docs/counterfactual_design.md`.** The data contain no discrete switch date: `strategy_version` (legacy, v1, v2, v3) is mixed in every month. So we run the design on the in-data variation: accounts targeted by campaigns on strategy **v2/v3 (treated)** vs **legacy/v1 (control)**, with a pre/post DiD (14 days before vs after the target date), covariate adjustment and a permutation placebo.""")
code("""
t=q('''select t.account_id,t.target_date,cm.strategy_version sv,a.dpd_bucket,a.risk_segment,a.loan_type,
 (select count(*) from clean.payments p where p.account_id=t.account_id and p.payment_status='SUCCESS' and p.event_ts_ist>=t.target_date-interval 14 day and p.event_ts_ist<t.target_date)>0 pre,
 (select count(*) from clean.payments p where p.account_id=t.account_id and p.payment_status='SUCCESS' and p.event_ts_ist>=t.target_date and p.event_ts_ist<t.target_date+interval 14 day)>0 post
 from raw.daily_targeting t join raw.campaigns cm using(campaign_id) join golden.dim_account a using(account_id) where t.target_date between '2026-01-15' and '2026-07-20' ''')
t['pre']=t.pre.astype(int);t['post']=t.post.astype(int);t['treat']=t.sv.isin(['v2','v3']).astype(int)
print(t.groupby('treat')[['pre','post']].agg(['mean','count']).to_string())
L=pd.concat([t.assign(y=t.pre,period=0),t.assign(y=t.post,period=1)])
m=smf.ols('y~treat*period+C(dpd_bucket)+C(risk_segment)+C(loan_type)',data=L).fit(cov_type='cluster',cov_kwds={'groups':L.account_id.astype('category').cat.codes})
lo,hi=m.conf_int().loc['treat:period'];print(f"\\nDiD effect on 14-day payment probability: {m.params['treat:period']*100:+.2f} pp, 95% CI [{lo*100:+.2f}, {hi*100:+.2f}] pp, p = {m.pvalues['treat:period']:.2f}")
rng=np.random.default_rng(0);dd=(t.post-t.pre).values;est=[dd[(tt:=rng.permutation(t.treat.values))==1].mean()-dd[tt==0].mean() for _ in range(500)]
obs=dd[t.treat==1].mean()-dd[t.treat==0].mean();print(f'Placebo (500 random re-labellings): sd = {np.std(est)*100:.2f} pp, share |placebo| >= observed = {(np.abs(est)>=abs(obs)).mean():.2f}')
p0=t.post.mean();print(f'Baseline 14-day pay rate {p0:.3f}. Sample needed per arm to detect a +10% relative lift: {2*(1.96+.84)**2*p0*(1-p0)/(p0*.10)**2:,.0f}; +5%: {2*(1.96+.84)**2*p0*(1-p0)/(p0*.05)**2:,.0f}')
""")
md("""**Result (Strong evidence of no detectable effect, not evidence of zero):** the DiD is about -0.04 pp with a 95% CI of roughly ±0.5 pp on a 3.7% base, i.e. we can rule out lifts larger than ~+13% relative and the placebo distribution is just as wide. The counterfactual answer is therefore: *recovery would have looked the same.* Key assumptions are listed in the design doc: parallel trends (checked via the pre-period, which is balanced: 3.4-3.9%), no spillovers between accounts, and that `strategy_version` on the campaign is what actually drove targeting (unverifiable here: **Hypothesis**).

## 6. Where should ₹10 Cr go? (Part 4 question 4)
### 6a. What the data say about each lever
Incremental value of a touch = payment probability in the 7 days after the touch minus the probability for random account-days with no regard to touches.""")
code("""
tl=q('''with t as (select account_id,touch_ts,channel,engaged from golden.fact_touch where touch_ts<'2026-08-01'),
x as (select channel,engaged,(exists(select 1 from golden.fact_payment p where p.account_id=t.account_id and p.payment_status='SUCCESS' and p.event_ts_ist>t.touch_ts and p.event_ts_ist<=t.touch_ts+interval 7 day))::int y from t)
select channel,engaged,count(*) n,avg(y) rate from x group by 1,2 order by 1,2''')
bs=q('''with s as (select a.account_id,(date '2026-01-01'+(floor(random()*200))::int*interval 1 day) d from golden.dim_account a,range(10))
select count(*) n,avg((exists(select 1 from golden.fact_payment p where p.account_id=s.account_id and p.payment_status='SUCCESS' and p.event_ts_ist>s.d and p.event_ts_ist<=s.d+interval 7 day))::int) r from s''').iloc[0]
tl['baseline']=bs.r;tl['lift_pp']=(tl.rate-bs.r)*100;se=np.sqrt(tl.rate*(1-tl.rate)/tl.n+bs.r*(1-bs.r)/bs.n);tl['ci_low_pp']=tl.lift_pp-1.96*se*100;tl['ci_high_pp']=tl.lift_pp+1.96*se*100
tl['lift_significant']=(tl.ci_low_pp>0)|(tl.ci_high_pp<0);tl.to_csv('outputs/tables/touch_lift.csv',index=False);tl
""")
md("""**Strong evidence:** after any touch (engaged or not, on any channel) the 7-day payment probability is 1.6-1.9%, statistically the same as the 1.87% you get for an arbitrary account-day. No channel shows significant positive lift. (Field-engaged shows a slightly *negative* point estimate: treat that as noise.) Nothing observed supports scaling any input. Caveat: touches on the same account are not independent, so these intervals are too narrow, and one of eight comparisons crossing 5% is what chance produces.

### 6b. Recommendation: **Option 4, better borrower targeting, released in stages**
**Why this and not the others.** Options 1, 2, 3, 5, 6 all buy *more touches*, and measured lift per touch is ~0 (6a). Their cost scales linearly with volume. Vendor effect is also nil (contact rate 19.2-21.1% across 15 vendors, p = 0.45), agents are indistinguishable (dispersion 0.99), and 54% of calls are already outside permitted hours, so more calling or AI-voice capacity amplifies a compliance problem. Option 4 is the only one whose cost does not scale with touches, and it carries the thing the business lacks: a **randomized holdout** that finally measures incremental recovery.

**What the data can't support:** the current features (DPD, risk segment, loan type, balance, state) have **no predictive signal for payment** (logit pseudo-R² = 0.0003, p = 0.45). So the ₹10 Cr must buy new *signal* (bureau/alternative data, contactability and best-time data, payment-history features) and the experiment infrastructure, not just a re-ranking of existing columns.""")
code("""
base_annual=q("select avg(net) from (select event_date_ist d,sum(net_amount) net from golden.fact_payment where event_date_ist<'2026-08-01' group by 1)").iloc[0,0]*365
inv=10e7;scen=pd.DataFrame({'scenario':['Downside (data-consistent central case)','Base (assumption)','Upside (assumption)'],'lift_on_annual_recovery':[0.0,0.03,0.08],'probability':[0.50,0.35,0.15]})
scen['incremental_recovery_12m_Cr']=base_annual*scen.lift_on_annual_recovery/1e7
scen['ROI_12m']=scen.incremental_recovery_12m_Cr/10-1
scen['incremental_recovery_36m_Cr']=scen.incremental_recovery_12m_Cr*3
scen['ROI_36m']=scen.incremental_recovery_36m_Cr/10-1
ev12=(scen.probability*scen.incremental_recovery_12m_Cr).sum();ev36=ev12*3
print(f'Annualised baseline net recovery: Rs {base_annual/1e7:,.1f} Cr')
print(f'Break-even lift (value = gross recovered Rs): 12m {inv/base_annual*100:.1f}% of annual recovery ; 36m {inv/3/base_annual*100:.1f}%')
print(f'Probability-weighted incremental recovery: 12m Rs {ev12:.1f} Cr (ROI {ev12/10-1:+.0%}); 36m Rs {ev36:.1f} Cr (ROI {ev36/10-1:+.0%})')
print('Staged plan: release Rs 1.5 Cr for a 90-day holdout; release the remaining Rs 8.5 Cr only if measured lift >= break-even.')
g=0.5;cost=1.5+g*8.5;ev_inc=g*(0.7*scen.incremental_recovery_12m_Cr[1]+0.3*scen.incremental_recovery_12m_Cr[2]);print(f'Staged, 12m: expected spend Rs {cost:.2f} Cr, expected incremental Rs {ev_inc:.2f} Cr, ROI {ev_inc/cost-1:+.0%}; worst-case loss capped at Rs 1.5 Cr instead of Rs 10 Cr')
scen.to_csv('outputs/tables/investment_scenarios.csv',index=False);scen
""")
md("""**Read this honestly.** Expected incremental recovery, ROI and break-even above come from **assumed** lift scenarios, because the data contain no measurable lift to anchor on. Treat the numbers as a decision frame, not a forecast. Confidence is **low**. The estimates would need to be replaced by the holdout result: ~40,000 accounts per arm detect a +10% relative lift on a 3.7% 14-day payment rate (80% power), ~160,000 for +5%. At 30,000 accounts total, a 90-day rolling account-day randomization (not account-level) is needed. Valuing recovered rupees at 100% is generous: at a 10% commission the revenue break-even is ten times higher, which is why the spend must be gated.

## 7. Evidence classification
| # | Conclusion | Class |
|---|---|---|
| 1 | Reported +11% = raw SUCCESS rows, March vs February | **Fact** (reproduced to 10.99%) |
| 2 | ~10.7 pts of it is 31 vs 28 days; per-day change ≈ -0.1% (p=0.98) | **Fact** |
| 3 | 500 duplicate payment rows (₹3.8 Cr, of which ₹2.6 Cr SUCCESS) inflate gross SUCCESS recovery by ~2.0%, spread evenly across months | **Fact** |
| 4 | Dedupe on `payment_reference` would wrongly delete ~3.8k genuine payments | **Fact** |
| 5 | No portfolio mix shift (DPD, loan, risk, vintage) | **Strong evidence** |
| 6 | No Simpson reversal; uplift appears uniformly in all segments (calendar signature) | **Strong evidence** |
| 7 | `accounts.status` is not a valid filter; 75% of payers are on non-ACTIVE accounts | **Fact** |
| 8 | PTP "kept" rate (~50%) not corroborated by payments (~4.8% verified) | **Fact** |
| 9 | No contact-rate driver survives multiple-testing control; agents indistinguishable | **Strong evidence** |
| 10 | No channel touch lifts 7-day payment probability above baseline | **Strong evidence** |
| 11 | Targeting strategy v2/v3 vs legacy/v1: no detectable effect (CI ±0.5 pp) | **Strong evidence** (of no *large* effect) |
| 12 | 54% of outbound calls are outside 08:00-19:00 IST | **Fact** if timestamps are right |
| 13 | Tenure, language, telephony vendor effects | **Hypothesis** (tenure data conflicted, language absent, vendor tz assumed) |
| 14 | Option 4 ROI and break-even | **Hypothesis** (assumption-driven; low confidence) |
""")
nb['cells'] = C
nb['metadata']['kernelspec'] = {'name':'python3','display_name':'Python 3','language':'python'}
nbf.write(nb,'notebooks/analysis.ipynb')
print('notebook written')
