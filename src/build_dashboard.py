"""Builds dashboard/index.html (self-contained, no external requests) from the DuckDB metrics."""
import json, duckdb
c = duckdb.connect("outputs/collections.duckdb", read_only=True)
mom = c.execute("select month,reported_mom,golden_per_day_mom from metrics.mom where not is_partial_month order by month").fetchall()
daily = c.execute("select cast(event_date_ist as varchar),sum(net_amount)/1e6 from golden.fact_payment where event_date_ist<'2026-08-01' group by 1 order by 1").fetchall()
cr = c.execute("select min(contact_rate),max(contact_rate) from metrics.monthly where not is_partial_month").fetchall()[0]
data = {"mom": mom, "daily": daily, "cr": cr}
html = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Recovery: executive view</title><style>
:root{--bg:#fff;--fg:#102a43;--mut:#627d98;--card:#f0f4f8;--red:#c0392b;--blue:#1f6fb2;--grn:#1e8449;--amb:#b9770e}
@media(prefers-color-scheme:dark){:root{--bg:#0f1b2a;--fg:#e6edf5;--mut:#9fb3c8;--card:#18283b;--red:#ff7b6b;--blue:#6db3f2;--grn:#58d68d;--amb:#f5b041}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.4 system-ui,sans-serif;padding:16px;max-width:1100px;margin:auto}
h1{font-size:15px;margin:0 0 10px;color:var(--mut);font-weight:600;letter-spacing:.04em;text-transform:uppercase}
.hero{display:grid;grid-template-columns:1fr 1fr;gap:12px}.card{background:var(--card);border-radius:10px;padding:14px}
.big{font-size:44px;font-weight:700;line-height:1}.lbl{color:var(--mut);font-size:12px;margin-top:4px}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:12px}.grid .big{font-size:26px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}svg{width:100%;height:auto;display:block}
.dec{margin-top:12px;border-left:5px solid var(--amb)}.dec b{color:var(--amb)}
@media(max-width:760px){.hero,.two{grid-template-columns:1fr}.grid{grid-template-columns:1fr 1fr}}
</style></head><body>
<h1>Collections recovery, Jan to Jul 2026 · executive view</h1>
<div class="hero">
<div class="card"><div class="big" style="color:var(--red)">+11.0%</div><div class="lbl">Reported Mar vs Feb: raw SUCCESS rows by calendar month (reproduced exactly)</div></div>
<div class="card"><div class="big" style="color:var(--blue)">-0.1%</div><div class="lbl">Actual Mar vs Feb per calendar day, after dedupe and reversals · 95% CI -7% to +8% · p = 0.98<br><b>31 days vs 28 days explains the whole gap.</b></div></div></div>
<div class="two"><div class="card"><div class="lbl">Month-on-month change: reported vs per day</div><svg id="a" viewBox="0 0 480 220"></svg></div>
<div class="card"><div class="lbl">Daily net recovery (₹ M): flat all year · 14-day average</div><svg id="b" viewBox="0 0 480 220"></svg></div></div>
<div class="grid">
<div class="card"><div class="big">₹55 L</div><div class="lbl">net recovery per day, flat (₹202 Cr a year)</div></div>
<div class="card"><div class="big" id="cr"></div><div class="lbl">contact rate, every month. No improvement</div></div>
<div class="card"><div class="big" style="color:var(--red)">4.8%</div><div class="lbl">PTPs actually paid vs ~50% "kept" status</div></div>
<div class="card"><div class="big" style="color:var(--amb)">54%</div><div class="lbl">calls outside 08:00-19:00 IST (compliance)</div></div></div>
<div class="grid">
<div class="card"><div class="big">500</div><div class="lbl">duplicate payment rows (₹3.8 Cr): +2.0% on gross</div></div>
<div class="card"><div class="big">0 of 17</div><div class="lbl">drivers significant: vendor, agent, tenure, time, mix, campaign...</div></div>
<div class="card"><div class="big">≈ 0</div><div class="lbl">7-day payment lift after any channel touch vs baseline</div></div>
<div class="card"><div class="big">75%</div><div class="lbl">of payers sit on non-ACTIVE accounts; never filter on status</div></div></div>
<div class="card dec"><b>Decision.</b> Put the ₹10 Cr into <b>better borrower targeting</b>, in stages: ₹1.5 Cr for a 90-day randomized holdout; the other ₹8.5 Cr only if measured lift ≥ 4.9% of annual recovery (12-month break-even; 1.6% over 3 years). More touches (agents, telephony, AI voice, WhatsApp, field) show no measurable return today.
Expected incremental recovery ₹4.6 Cr in 12 months (probability-weighted, range ₹0 to ₹16 Cr). <b>Confidence: low</b>, because the lift scenarios are assumptions.</div>
<script>
const D=__DATA__,NS='http://www.w3.org/2000/svg';
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n);
function el(p,t,a,x){const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);if(x)e.textContent=x;p.appendChild(e);return e}
function bars(){const s=document.getElementById('a'),m=D.mom.slice(1),W=480,H=220,y0=110,sc=7;
 el(s,'line',{x1:30,x2:470,y1:y0,y2:y0,stroke:css('--mut')});
 m.forEach((r,i)=>{const x=45+i*72;[[r[1],css('--red'),0],[r[2],css('--blue'),30]].forEach(([v,c,o])=>{const h=Math.abs(v*100)*sc;
  el(s,'rect',{x:x+o,y:v>=0?y0-h:y0,width:26,height:Math.max(h,1),fill:c,rx:2});
  el(s,'text',{x:x+o+13,y:v>=0?y0-h-4:y0+h+11,'text-anchor':'middle','font-size':9,fill:css('--fg')},(v*100).toFixed(1));});
  el(s,'text',{x:x+28,y:212,'text-anchor':'middle','font-size':10,fill:css('--mut')},r[0].slice(5));});
 el(s,'rect',{x:300,y:6,width:9,height:9,fill:css('--red')});el(s,'text',{x:313,y:14,'font-size':9,fill:css('--fg')},'reported');
 el(s,'rect',{x:370,y:6,width:9,height:9,fill:css('--blue')});el(s,'text',{x:383,y:14,'font-size':9,fill:css('--fg')},'per day (actual)');}
function line(){const s=document.getElementById('b'),d=D.daily,n=d.length,x=i=>30+i*440/(n-1),y=v=>200-(v-3)*(180/5);
 [4,5,6,7].forEach(g=>{el(s,'line',{x1:30,x2:470,y1:y(g),y2:y(g),stroke:css('--mut'),'stroke-opacity':.25});el(s,'text',{x:26,y:y(g)+3,'text-anchor':'end','font-size':9,fill:css('--mut')},g)});
 el(s,'polyline',{points:d.map((r,i)=>x(i)+','+y(r[1])).join(' '),fill:'none',stroke:css('--mut'),'stroke-width':.8,'stroke-opacity':.6});
 const ma=d.map((r,i)=>{const a=d.slice(Math.max(0,i-13),i+1);return a.reduce((t,q)=>t+q[1],0)/a.length});
 el(s,'polyline',{points:ma.map((v,i)=>i>12?x(i)+','+y(v):null).filter(Boolean).join(' '),fill:'none',stroke:css('--blue'),'stroke-width':2.4});
 [['Jan',0],['Feb',31],['Mar',59],['Apr',90],['May',120],['Jun',151],['Jul',181]].forEach(([t,i])=>el(s,'text',{x:x(i),y:214,'font-size':10,fill:css('--mut')},t));}
bars();line();document.getElementById('cr').textContent=(D.cr[0]*100).toFixed(1)+'-'+(D.cr[1]*100).toFixed(1)+'%';
</script></body></html>"""
open("dashboard/index.html", "w", encoding="utf-8").write(html.replace("__DATA__", json.dumps(data, ensure_ascii=False)))
print("dashboard written")
