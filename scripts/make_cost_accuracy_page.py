"""One interactive cost-vs-accuracy chart (Vals-style) plus a compact leaderboard, as a single local HTML page.

Run:  python3 scripts/make_cost_accuracy_page.py   ->  results/draft/index.html   (git-ignored, no dependencies)

Accuracy = mean over the common task set of each task's pass rate, where the common set is the 17 tasks that all five
models ran (so models are compared on identical tasks). The first-round attempts of the frontier models on
exp-checkout-plain are left out because that task had a contestable decoy before it was fixed.
Cost and time are per attempt, measured from the agent logs and Valkyrie.
"""
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
    html = TEMPLATE.replace("__DATA__", json.dumps(data)).replace("__ROWS__", rows_html).replace("__NTASKS__", str(len(COMMON)))
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
.banner{background:#fff4cc;color:#5c4a00;padding:8px 20px;font-size:13px;border-bottom:1px solid var(--line)}
</style></head><body>
<div class="card">
  <div class="head"><div><h1>Energy Meter Reliability</h1><span class="sub">Can agents tell when a meter total can be trusted?</span></div>
  <div class="date mono">Draft &bull; synthetic data &bull; __NTASKS__ common tasks</div></div>
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
