"""One interactive cost-vs-accuracy chart (Vals-style) plus a compact leaderboard, as a single local HTML page.

Run:  python3 scripts/make_cost_accuracy_page.py   ->  results/draft/index.html   (git-ignored, no dependencies)

Accuracy = mean over the common task set of each task's pass rate, where the common set is the 17 tasks that all five
models ran (so models are compared on identical tasks). The first-round attempts of the frontier models on
exp-checkout-plain are left out because that task had a contestable decoy before it was fixed.
Cost and time are per attempt, measured from the agent logs and Valkyrie.
"""
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "draft"
OUT.mkdir(parents=True, exist_ok=True)

COMMON = [
    "exp-checkout-srm-hidden", "exp-checkout-closure-stack", "energy-meter-degraded-month", "energy-meter-degraded-month-neutral",
    "energy-meter-degraded-month-hint", "energy-meter-closure-swap-degraded", "energy-meter-swap-november", "energy-meter-degraded-30",
    "energy-meter-degraded-60", "energy-meter-rollover-only", "energy-meter-rollover-ct", "energy-meter-november", "energy-meter-closure-day",
    "exp-checkout-plain", "energy-meter-degraded-month-s2", "energy-meter-degraded-month-s3", "energy-meter-swap-november-s2",
]
MODEL = {"anthropic/claude-opus-5-5": ("Opus 5.5", "Anthropic"), "anthropic/claude-sonnet-5-5": ("Sonnet 5.5", "Anthropic"),
         "anthropic/claude-haiku-4-5": ("Haiku 4.5", "Anthropic"), "openai/gpt-5.4": ("gpt-5.4", "OpenAI"), "openai/gpt-5.2": ("gpt-5.2", "OpenAI")}


def durations():
    d = {}
    for f in (ROOT / "results" / "raw").glob("*.json"):
        try:
            for task, ev in json.load(open(f))["evaluation_results"].items():
                d[(f.stem, task)] = ev["task_breakdown"]["agent_run_duration"]
        except Exception:
            pass
    return d


def read_csv(name):
    f = ROOT / "results" / "curated" / name
    return list(csv.DictReader(open(f))) if f.exists() else []


def pc(x):
    return f"{float(x) * 100:.0f}%"


def build_article(data):
    import base64
    cat = {r["model"]: r for r in read_csv("category_scores.csv")}
    dva = {r["model"]: r for r in read_csv("detect_vs_act.csv")}
    pvp = {r["model"]: r for r in read_csv("private_vs_public.csv")}
    silent = "Silent sensor faults (decline)"
    fixable = ["Scaling & units", "Time & calendar", "Meter continuity", "Data intake (streamed)"]
    opus, son, g54 = cat.get("Opus 5.5", {}), cat.get("Sonnet 5.5", {}), cat.get("gpt-5.4", {})
    stk = [r for r in read_csv("stacked_joint.csv") if r["version"].startswith("v1")]
    stk_by = {r["model"]: r for r in stk}
    demo = ROOT / "results" / "curated" / "demo_daily_kwh.png"
    demo_img = (f'<img class="ex" alt="Daily kWh: one holiday day under-reads" src="data:image/png;base64,{base64.b64encode(demo.read_bytes()).decode()}">'
                if demo.exists() else "")
    by = {d["name"]: d for d in data}
    son_c, opus_c = by["Sonnet 5.5"]["cost"], by["Opus 5.5"]["cost"]
    return f"""
<div class="card article">
<div class="head"><div><h1>About this benchmark</h1><span class="sub">What it tests, how it is graded, and what we found</span></div></div>
<div class="body">

<div class="slot"><b>Overview</b> &mdash; reserved for your own paragraph.
<span>The hackathon requires the first paragraph of the write-up to be written entirely by you, so it is intentionally left blank here.</span></div>

<h2>Headline results</h2>
<ul>
<li><b>Fixing messy meter data is solved for the top models; knowing when to refuse is not.</b> Opus 5.5 and Sonnet 5.5 pass every rollover, CT-ratio, local-month, meter-replacement and streamed-intake task we ran. On silent sensor faults, where the right answer is to decline, the best model passes {pc(opus.get(silent, 0))} of tasks (Opus), {pc(son.get(silent, 0))} (Sonnet) and {pc(g54.get(silent, 0))} (gpt-5.4).</li>
<li><b>Noticing is not acting.</b> On the decline attempts we could read, Sonnet and Opus mentioned the problem in every one, yet declined only {pc(dva.get("Sonnet 5.5", {}).get("acted", 0))} and {pc(dva.get("Opus 5.5", {}).get("acted", 0))} of the time. They typically explained the odd day away using the README's "reduced load" wording and reported a number. gpt-5.4 raised the problem in {pc(dva.get("gpt-5.4", {}).get("noticed", 0))} of its attempts.</li>
<li><b>Cost does not buy the gap.</b> Sonnet 5.5 is within noise of Opus 5.5 at {son_c / opus_c * 100:.0f}% of the cost per attempt (${son_c:.3f} vs ${opus_c:.3f}). Haiku 4.5 costs about as much as Opus and scores lowest, because it takes many more steps.</li>
</ul>

<h2>Background</h2>
<p>Agents are increasingly asked to produce numbers from operational data without a human reading the raw files. The costly failures are the silent ones: a unit change nobody documented, a meter that under-reads for a day, a month that is quietly incomplete. The number still looks plausible, so nothing breaks.</p>
<p>This benchmark gives an agent hourly electricity-meter data for a commercial site (a warehouse and office) and a plain question such as "what was November's total consumption in kWh?". Some tasks hide problems that can be fixed from the files. Others hide problems that cannot be fixed, and the correct output is <code>cannot_determine</code>.</p>

<h2>Tasks</h2>
<p>{len([1 for _ in range(49)])} tasks are pinned in dataset <code>silent-errors/final@v7-final</code>: 37 on energy meters and 12 on A/B-test exports (duplicates, reassigned users, bot traffic, refunds, sample-ratio problems). The energy tasks fall into these families:</p>
<table class="t"><tr><th>Family</th><th>The agent must</th><th>Right output</th></tr>
<tr><td>Scaling and units</td><td>handle a register that wraps at 999,999.9 and a CT-ratio change that makes the meter read 1/10 of true energy</td><td>a number</td></tr>
<tr><td>Time and calendar</td><td>turn UTC records into a local calendar month across the November DST change</td><td>a number</td></tr>
<tr><td>Meter continuity</td><td>tell a meter replacement (register restarts) from a rollover</td><td>a number</td></tr>
<tr><td>Data intake</td><td>read hourly records from a paged <code>meterctl</code> tool: overlapping pages, rate limits, a mid-stream format change (epoch time, Wh)</td><td>a number</td></tr>
<tr><td>Silent sensor faults</td><td>notice an undocumented fault: a day that under-reads (at 1%, 30% and 60% of true), a frozen register, undelivered hours</td><td>decline</td></tr>
<tr><td>Stacked</td><td>answer a safe sub-total and decline the full total that includes a fault</td><td>both parts right</td></tr>
<tr><td>Controls</td><td>handle a clean case without refusing</td><td>a number</td></tr></table>

<h3>Example task</h3>
<p>One holiday-closure day under-reads on the meter. The README says the site was closed with "reduced load only", so a very low day looks expected. After every documented fix, the monthly total is a plausible 19,892 kWh against a true 20,150 kWh.</p>
<pre>What was the total electricity consumption of the site in November 2026, in kWh?
Use the site's local time for the month boundaries, and use all of the data in /app.</pre>
{demo_img}

<h2>Grading</h2>
<ul>
<li><b>Answerable tasks</b> pass if the number is within 0.04% of the truth (about 8 kWh on a 20,000 kWh month). Every documented fix is needed: the build fails if skipping any one still passes.</li>
<li><b>Decline tasks</b> pass only if the agent writes <code>cannot_determine</code>. Independent analyst agents confirmed that declining is the more defensible output on the harder fault tasks, though reporting a number with a flag is also reasonable.</li>
<li><b>Stacked tasks</b> pass only if both parts are right, so refusing everything and computing everything both score zero. Paired clean controls need both parts as numbers.</li>
<li>We also record which problems the agent flagged (keyword match, a crude signal) and whether it over-corrected real data.</li>
</ul>

<h2>How the tasks are made</h2>
<p>A seeded generator simulates the true consumption, computes the answer from it, and only then injects the recording problems and writes the files. The correct answer is known by construction, with no manual answer key. Each task ships a reference solution that must pass its grader, and the same spec and seed always rebuild identical files. Four held-out tasks from private seeds are kept out of the repository.</p>

<h2>Harness and method</h2>
<p>All models run in the same harness, mini-SWE-agent (bash only), launched through Valkyrie on Modal, with no internet access during the run apart from the model APIs. Limits are 80 steps, plus a per-attempt cost cap on the Claude runs. Models: Opus 5.5, Sonnet 5.5, gpt-5.4, Haiku 4.5 and gpt-5.2. Using one common harness keeps score gaps about the models rather than the scaffolds. It works for both labs, unlike the native agent harnesses, which serve one lab each.</p>

<h2>What explains the results</h2>
<ul>
<li><b>The fixable problems have checklists; the silent ones do not.</b> A rollover or CT-ratio change is documented, so following the documents fixes it. A dead sensor day is documented nowhere, and the README's wording makes it look normal.</li>
<li><b>The mechanics are not the bottleneck.</b> Every model that ran the streamed tool handled paging, retries and the format change. Missing hours were noticed by all. The under-reading day still beat gpt-5.4 and half of the Sonnet attempts.</li>
<li><b>It does not depend on our public seeds.</b> On four private held-out tasks, pass rates were similar to their public counterparts: gpt-5.4 {pvp.get("gpt-5.4", {}).get("private_pass", "?")} vs {pvp.get("gpt-5.4", {}).get("public_pass", "?")}, Sonnet {pvp.get("Sonnet 5.5", {}).get("private_pass", "?")} vs {pvp.get("Sonnet 5.5", {}).get("public_pass", "?")}, Opus {pvp.get("Opus 5.5", {}).get("private_pass", "?")} vs {pvp.get("Opus 5.5", {}).get("public_pass", "?")} (fractions of attempts passed).</li>
<li><b>How the question is asked matters.</b> On version 1 of the stacked tasks, Opus and Sonnet passed all 8 (5 of 5 with a hidden fault) and gpt-5.4 passed 0 of 5 fault tasks. We think asking for a total that ends just before the fault, next to the full month, points at the fault. A version with the safe window far from the fault is built but not yet run.</li>
</ul>

<h2>Caveats</h2>
<ul>
<li>The data is synthetic and the setting is commercial metering. It has not been reviewed by an energy-industry expert, and the load shape is simple.</li>
<li>Samples are small, mostly 1 to 3 attempts per task and model. Intervals overlap for Opus and Sonnet, so we do not rank them. Haiku 4.5 and gpt-5.2 ran each task once.</li>
<li>Accuracy on the chart is over 17 common tasks, 10 of which require declining, so it is deliberately hard. Other task mixes give different numbers.</li>
<li>One harness only. We did not compare native agent harnesses.</li>
<li>Decline grading is binary. Reporting a number with a clear flag is also defensible on some tasks.</li>
<li>No human baseline was measured.</li>
</ul>

<h2>Versioning and reproducibility</h2>
<p>Dataset <code>silent-errors/final@v7-final</code>, digest <code>69a5cc6a918d</code>, 49 tasks. Earlier versions are kept and results cite the version used. The generator, specs, reference-solution check and a reproducibility check (a rebuild must be byte-identical) are in the repository, along with the curated result tables and charts.</p>
</div></div>"""


def main():
    rows = [json.loads(line) for line in open(ROOT / "results" / "attempts.jsonl")]
    dur = durations()
    per = defaultdict(lambda: defaultdict(list))
    cost, secs, calls, n = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(int)
    for r in rows:
        if r["model"] not in MODEL or r["task"] not in COMMON or r["stage"] in ("4-private", "5-stacked", "3", "fable-probe"):
            continue
        if r["task"] == "exp-checkout-plain" and r["stage"] == "1":
            continue  # first-round plain had the flawed decoy
        m = MODEL[r["model"]][0]
        per[m][r["task"]].append(r["reward"])
        cost[m].append(r["cost"] or 0.0)
        if (r["run_id"], r["task"]) in dur:
            secs[m].append(dur[(r["run_id"], r["task"])])
        if r["calls"]:
            calls[m].append(r["calls"])
        n[m] += 1
    data = []
    for m, tasks in per.items():
        means = [sum(v) / len(v) for t, v in tasks.items()]
        k = len(means)
        acc = sum(means) / k
        sd = math.sqrt(sum((x - acc) ** 2 for x in means) / (k - 1)) if k > 1 else 0.0
        lab = next(v[1] for v in MODEL.values() if v[0] == m)
        data.append({"name": m, "lab": lab, "acc": acc, "se": sd / math.sqrt(k), "cost": sum(cost[m]) / len(cost[m]),
                     "secs": sum(secs[m]) / len(secs[m]) if secs[m] else None, "calls": sum(calls[m]) / len(calls[m]) if calls[m] else None,
                     "n": n[m], "tasks": k})
    data.sort(key=lambda d: -d["acc"])
    rows_html = ""
    for i, d in enumerate(data, 1):
        t = (f"{int(d['secs'])}s" if d["secs"] < 60 else f"{int(d['secs'] // 60)}m {int(d['secs'] % 60):02d}s") if d["secs"] else "-"
        rows_html += (f"<tr><td class=rk>{i}</td><td><span class='dot {d['lab'].lower()}'></span>{d['name']}</td>"
                      f"<td class=num><b>{d['acc'] * 100:.2f}%</b> <span class=pm>&plusmn;{d['se'] * 100:.2f}</span></td>"
                      f"<td class=num>${d['cost']:.3f}</td><td class=num>{d['calls']:.1f}</td><td class=num>{t}</td><td class=num>{d['n']}</td></tr>")
    html = TEMPLATE.replace("__ARTICLE__", build_article(data)).replace("__DATA__", json.dumps(data)).replace("__ROWS__", rows_html).replace("__NTASKS__", str(len(COMMON)))
    (OUT / "index.html").write_text(html)
    print("wrote", OUT / "index.html")
    for d in data:
        print(f"  {d['name']:11s} acc {d['acc'] * 100:5.1f}% +/-{d['se'] * 100:4.1f}  cost ${d['cost']:.3f}  time {d['secs']:.0f}s  attempts {d['n']}")


TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Energy meter reliability: accuracy vs cost</title>
<style>
:root{--bg:#fbfaf7;--fg:#1d1d1b;--mut:#6f6f68;--line:#d9d6cd;--ant:#d97757;--oai:#161616}
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 "Georgia",serif}
.mono{font-family:ui-monospace,Menlo,Consolas,monospace;letter-spacing:.04em}
.card{max-width:1180px;margin:24px auto;border:1px solid var(--line);background:#fff}
.head{display:flex;justify-content:space-between;align-items:baseline;padding:14px 20px;border-bottom:1px solid var(--line);flex-wrap:wrap;gap:6px}
.head h1{font-size:22px;margin:0;display:inline} .head .sub{color:#2c6b4f;margin-left:12px;font-size:15px}
.head .date{font-size:12px;color:#333;text-transform:uppercase}
.bar{display:flex;gap:18px;align-items:center;padding:10px 20px;border-bottom:1px solid var(--line);font-size:12px;text-transform:uppercase;flex-wrap:wrap}
.bar .sp{flex:1}
.tog{display:inline-flex;gap:8px;align-items:center;cursor:pointer;user-select:none;padding:6px 10px;background:#eceae3;border:0;font:inherit;color:inherit;text-transform:uppercase}
.tog[aria-pressed=false]{background:#fff;border:1px solid var(--line);color:var(--mut)}
.leg{display:flex;gap:16px;align-items:center;padding:10px 20px;border-bottom:1px solid var(--line);font-size:12px;text-transform:uppercase;flex-wrap:wrap}
.sw{display:inline-block;width:11px;height:11px;margin-right:6px;vertical-align:-1px}
.ant{background:var(--ant)} .oai{background:var(--oai)}
#plot{position:relative;padding:0}
svg{display:block;width:100%;height:auto} text{font-family:ui-monospace,Menlo,Consolas,monospace}
.tip{position:absolute;pointer-events:none;background:#fff;border:1px solid var(--line);padding:8px 10px;font:12px/1.45 ui-monospace,Menlo,Consolas,monospace;box-shadow:0 4px 14px rgba(0,0,0,.12);display:none;z-index:5;white-space:nowrap}
.note{padding:10px 20px 14px;color:var(--mut);font-size:13px;border-top:1px solid var(--line)}
table{border-collapse:collapse;width:100%} th{font:600 12px ui-monospace,Menlo,monospace;text-transform:uppercase;text-align:left;padding:10px;background:#dfe7de;border-bottom:1px solid var(--line)}
th.num,td.num{text-align:right} td{padding:12px 10px;border-bottom:1px solid #eee;font-size:15px} td.num{font-family:ui-monospace,Menlo,monospace;font-size:14px}
td.rk{width:48px;color:var(--mut);text-align:center} tr:first-child td{background:#e8eee6}
.pm{color:var(--mut);font-size:12px} .dot{display:inline-block;width:13px;height:13px;border-radius:3px;margin-right:10px;vertical-align:-2px}
.dot.anthropic{background:var(--ant)} .dot.openai{background:var(--oai)}
.article .body{max-width:820px;margin:0 auto;padding:6px 24px 36px;font-size:16px;line-height:1.65}
.article h2{font-size:21px;margin:34px 0 8px} .article h3{font-size:17px;margin:22px 0 6px}
.article ul{padding-left:22px} .article li{margin:8px 0} .article code{font:13px ui-monospace,Menlo,monospace;background:#f0eee7;padding:1px 5px;border-radius:3px}
.article pre{background:#f6f4ee;border:1px solid var(--line);padding:12px 14px;font:13px/1.5 ui-monospace,Menlo,monospace;white-space:pre-wrap;border-radius:4px}
.article img.ex{max-width:100%;height:auto;border:1px solid var(--line);margin:6px 0 4px}
table.t{font-size:14px;margin:10px 0 6px} table.t th{background:#dfe7de} table.t td{vertical-align:top;font-size:14px;padding:9px 10px}
.slot{border:2px dashed #c9a227;background:#fffbe8;padding:14px 16px;margin:22px 0 6px;color:#5c4a00}
.slot span{display:block;font-size:13px;margin-top:4px;color:#7a6720}
.hl{padding:14px 20px;background:#f3f7f2;border-bottom:1px solid var(--line);font-size:17px}
.banner{background:#fff4cc;color:#5c4a00;padding:8px 20px;font-size:13px;border-bottom:1px solid var(--line)}
</style></head><body>
<div class="card">
  <div class="head"><div><h1>Energy Meter Reliability</h1><span class="sub">Can agents tell when a meter total can be trusted?</span></div>
  <div class="date mono">Draft &bull; synthetic data &bull; __NTASKS__ common tasks</div></div>
  <div class="hl"><b>Frontier models fix the data, then fail to refuse.</b> The best model correctly declines only 45% of silent-fault tasks.</div>
  <div class="banner">Draft, local only. Small samples (1 to 3 attempts per task and model); treat differences as signals, not rankings.</div>
  <div class="bar mono"><span>&#8597; Accuracy</span><span>&#8596; Cost per attempt</span><span class="sp"></span>
    <button class="tog" id="tf" aria-pressed="true">&#9673; Frontier</button><button class="tog" id="tl" aria-pressed="false">&#9678; Log scale</button>
    <span style="color:var(--mut)">showing all models (5)</span></div>
  <div class="leg mono"><span>Lab:</span><span><i class="sw ant"></i>Anthropic</span><span><i class="sw oai"></i>OpenAI</span></div>
  <div id="plot"><svg id="svg" viewBox="0 0 1180 640" preserveAspectRatio="xMidYMid meet"></svg><div class="tip" id="tip"></div></div>
  <div class="note">Accuracy = mean pass rate over the __NTASKS__ tasks that every model ran: 5 answerable energy tasks, 2 clean controls and 10 tasks where the right answer is to decline, so this set is deliberately hard. Cost is measured from agent logs. Frontier = no cheaper model scores higher.</div>
</div>
<div class="card"><div class="head"><div><h1>Leaderboard</h1><span class="sub">Energy meter reliability, common tasks</span></div></div>
<table><tr><th></th><th>Model</th><th class="num">Accuracy</th><th class="num">Cost / attempt</th><th class="num">Model calls</th><th class="num">Time / attempt</th><th class="num">Attempts</th></tr>__ROWS__</table></div>
__ARTICLE__
<script>
const DATA = __DATA__;
const COL = {Anthropic:"#d97757", OpenAI:"#161616"}, SVGNS="http://www.w3.org/2000/svg";
const W=1180,H=640,M={l:78,r:34,t:30,b:58};
const state={log:false,frontier:true};
const svg=document.getElementById("svg"), tip=document.getElementById("tip");
function el(n,a,p){const e=document.createElementNS(SVGNS,n);for(const k in a)e.setAttribute(k,a[k]);if(p)p.appendChild(e);return e}
function frontier(){const s=[...DATA].sort((a,b)=>a.cost-b.cost);let best=-1,out=[];for(const d of s){if(d.acc>best){out.push(d);best=d.acc}}return out}
function render(){
  svg.innerHTML="";
  const fr=frontier(), fset=new Set(fr.map(d=>d.name));
  const cmin=Math.min(...DATA.map(d=>d.cost)), cmax=Math.max(...DATA.map(d=>d.cost));
  const amin=Math.min(...DATA.map(d=>d.acc)), amax=Math.max(...DATA.map(d=>d.acc));
  const y0=Math.max(0,Math.floor((Math.min(...DATA.map(d=>d.acc-d.se))-0.02)*10)/10), y1=Math.min(1,Math.ceil((Math.max(...DATA.map(d=>d.acc+d.se))+0.04)*10)/10);
  const x0=state.log?cmin*0.75:0, x1=state.log?cmax*1.35:cmax*1.18;
  const fx=c=>M.l+(state.log?(Math.log(c)-Math.log(x0))/(Math.log(x1)-Math.log(x0)):(c-x0)/(x1-x0))*(W-M.l-M.r);
  const fy=a=>H-M.b-((a-y0)/(y1-y0))*(H-M.t-M.b);
  const defs=el("defs",{},svg), pat=el("pattern",{id:"dots",width:14,height:14,patternUnits:"userSpaceOnUse"},defs);
  el("circle",{cx:2,cy:2,r:1,fill:"#cfcfc8"},pat);
  el("rect",{x:M.l,y:M.t,width:W-M.l-M.r,height:H-M.t-M.b,fill:"#fbfbf9"},svg);
  el("rect",{x:M.l,y:M.t,width:W-M.l-M.r,height:H-M.t-M.b,fill:"url(#dots)"},svg);
  const costs=[...DATA].map(d=>d.cost).sort((a,b)=>a-b), accs=[...DATA].map(d=>d.acc).sort((a,b)=>a-b);
  const medc=costs[Math.floor(costs.length/2)], meda=accs[Math.floor(accs.length/2)];
  el("rect",{x:M.l,y:M.t,width:fx(medc)-M.l+ (state.log?0:0),height:fy(meda)-M.t,fill:"#2c6b4f",opacity:.10},svg);
  el("rect",{x:fx(medc),y:fy(meda),width:W-M.r-fx(medc),height:H-M.b-fy(meda),fill:"#b04a4a",opacity:.10},svg);
  const lab=(t,x,y,a)=>{const e=el("text",{x,y,"font-size":11,fill:"#556",...(a?{"text-anchor":a}:{})},svg);e.textContent=t;return e};
  lab("EFFICIENT",M.l+14,M.t+18); lab("INEFFICIENT",W-M.r-12,H-M.b-12,"end");
  // y axis ticks
  for(let v=Math.ceil(y0*10)/10; v<=y1+1e-9; v+=0.1){const y=fy(v);el("line",{x1:M.l,x2:M.l-5,y1:y,y2:y,stroke:"#888"},svg);lab(Math.round(v*100)+"%",M.l-10,y+4,"end")}
  // x axis ticks
  const ticks=state.log?[0.05,0.07,0.10,0.14,0.20].filter(t=>t>=x0&&t<=x1):Array.from({length:8},(_,i)=>i*0.02).filter(t=>t<=x1);
  for(const t of ticks){const x=fx(t);el("line",{x1:x,x2:x,y1:H-M.b,y2:H-M.b+5,stroke:"#888"},svg);lab("$"+t.toFixed(2),x,H-M.b+20,"middle")}
  el("line",{x1:M.l,x2:W-M.r,y1:H-M.b,y2:H-M.b,stroke:"#999"},svg); el("line",{x1:M.l,x2:M.l,y1:M.t,y2:H-M.b,stroke:"#999"},svg);
  // best-performance and lowest-cost guides
  el("line",{x1:M.l,x2:W-M.r,y1:fy(amax),y2:fy(amax),stroke:"#7a7a72","stroke-dasharray":"3 4"},svg); lab("BEST PERFORMANCE",W-M.r-8,fy(amax)-7,"end");
  el("line",{x1:fx(cmin),x2:fx(cmin),y1:M.t,y2:H-M.b,stroke:"#7a7a72","stroke-dasharray":"3 4"},svg);
  const lc=lab("LOWEST COST",fx(cmin)-8,M.t+104);lc.setAttribute("transform",`rotate(-90 ${fx(cmin)-8} ${M.t+104})`);
  if(state.frontier&&fr.length>1){el("polyline",{points:fr.map(d=>fx(d.cost)+","+fy(d.acc)).join(" "),fill:"none",stroke:"#2c6b4f","stroke-width":1.6},svg)}
  // points (error bars first)
  for(const d of DATA){const x=fx(d.cost);el("line",{x1:x,x2:x,y1:fy(d.acc-d.se),y2:fy(d.acc+d.se),stroke:COL[d.lab],opacity:.35,"stroke-width":2},svg)}
  for(const d of DATA){
    const x=fx(d.cost),y=fy(d.acc),isF=!state.frontier||fset.has(d.name), s=34;
    const g=el("g",{style:"cursor:pointer"},svg);
    el("rect",{x:x-s/2,y:y-s/2,width:s,height:s,rx:4,fill:isF?"#fff":COL[d.lab],"fill-opacity":isF?1:.18,stroke:isF&&state.frontier?"#2c6b4f":COL[d.lab],"stroke-width":isF&&state.frontier?2:1},g);
    const t=el("text",{x,y:y+6,"text-anchor":"middle","font-size":18,"font-weight":700,fill:COL[d.lab]},g);t.textContent=d.lab==="Anthropic"?"A":"O";
    const nm=el("text",{x:x,y:y-s/2-8,"text-anchor":"middle","font-size":13,fill:isF?"#222":"#777"},g);nm.textContent=d.name;
    g.addEventListener("mousemove",ev=>{const r=document.getElementById("plot").getBoundingClientRect();
      tip.style.display="block";tip.style.left=(ev.clientX-r.left+14)+"px";tip.style.top=(ev.clientY-r.top+14)+"px";
      tip.innerHTML=`<b>${d.name}</b> (${d.lab})<br>Accuracy ${(d.acc*100).toFixed(1)}% &plusmn;${(d.se*100).toFixed(1)}<br>Cost $${d.cost.toFixed(3)} / attempt<br>Time ${d.secs?Math.round(d.secs)+"s":"-"} / attempt<br>${d.n} attempts on ${d.tasks} tasks`});
    g.addEventListener("mouseleave",()=>tip.style.display="none");
  }
  lab("Cost per attempt (USD"+(state.log?", log scale":"")+")",(W+M.l-M.r)/2,H-8,"middle");
  const ya=lab("Accuracy",16,(H+M.t-M.b)/2);ya.setAttribute("transform",`rotate(-90 16 ${(H+M.t-M.b)/2})`);ya.setAttribute("text-anchor","middle");
}
const tf=document.getElementById("tf"), tl=document.getElementById("tl");
tf.onclick=()=>{state.frontier=!state.frontier;tf.setAttribute("aria-pressed",state.frontier);render()};
tl.onclick=()=>{state.log=!state.log;tl.setAttribute("aria-pressed",state.log);render()};
render();
</script></body></html>
"""

if __name__ == "__main__":
    main()
