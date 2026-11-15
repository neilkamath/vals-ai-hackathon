"""Build the interactive cost-vs-accuracy chart (dark, self-contained) from the committed leaderboard table.

Run:  python3 scripts/make_interactive_chart.py   ->  docs/index.html   (served by GitHub Pages)

Reads results/curated/leaderboard.csv, so it can be rebuilt from committed data. No dependencies.
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAB = {"Haiku 4.5": "Anthropic", "Sonnet 5.5": "Anthropic", "Opus 5.5": "Anthropic", "gpt-5.2": "OpenAI", "gpt-5.4": "OpenAI",
       "gpt-5.5": "OpenAI", "Fable 5.2": "Anthropic"}


def main():
    rows = list(csv.DictReader(open(ROOT / "results" / "curated" / "leaderboard.csv")))
    data = []
    for r in rows:
        data.append({"name": r["model"], "lab": LAB[r["model"]], "acc": float(r["accuracy"]), "se": float(r["se"] or 0),
                     "fix": float(r["fixable"]), "dec": float(r["decline"]), "ctl": float(r["controls"]),
                     "cost": float(r["avg_cost_per_attempt_usd"]), "secs": float(r["avg_duration_s"]), "calls": float(r["avg_model_calls"]),
                     "n": int(r["attempts"]), "tasks": int(r["tasks_covered"])})
    by = {d["name"]: d for d in data}
    best = max(data, key=lambda d: d["dec"])
    headline = (f"<b>Models fix the data, then often fail to refuse.</b> "
                f"On tasks where the honest answer is to decline, the best model ({best['name']}) passes {best['dec'] * 100:.0f}%, "
                f"while gpt-5.5 fixes every documented problem and passes {by['gpt-5.5']['dec'] * 100:.0f}%.")
    out = ROOT / "docs"
    out.mkdir(exist_ok=True)
    (out / "index.html").write_text(TEMPLATE.replace("__DATA__", json.dumps(data)).replace("__HEADLINE__", headline))
    print("wrote", out / "index.html")


TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Energy Meter Reliability: accuracy vs cost</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{--bg:#0d1117;--card:#161b22;--line:#30363d;--fg:#e6edf3;--mut:#8b949e;--ant:#f0865a;--oai:#34d399;--front:#58a6ff;--good:#3fb950;--bad:#f85149}
*{box-sizing:border-box} html,body{margin:0;background:var(--bg);color:var(--fg)}
body{font:15px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;padding:20px}
.mono{font-family:"JetBrains Mono",ui-monospace,Menlo,Consolas,monospace}
.card{max-width:1080px;margin:0 auto;background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}
.head{padding:18px 22px 4px;display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap}
.head h1{margin:0;font-size:21px;font-weight:650;letter-spacing:-.01em}
.head .sub{color:var(--mut);font-size:14px;margin-top:2px}
.tag{font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.08em}
.hl{margin:12px 22px 0;padding:10px 14px;border-left:3px solid var(--front);background:#10161f;border-radius:6px;font-size:15px}
.bar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:14px 22px 6px}
.chip{display:inline-flex;gap:8px;align-items:center;border:1px solid var(--line);background:transparent;color:var(--mut);
  padding:6px 12px;border-radius:999px;font:500 12.5px Inter,system-ui,sans-serif;cursor:pointer;transition:all .15s}
.chip[aria-pressed=true]{color:var(--fg);border-color:#484f58;background:#21262d}
.chip:hover{border-color:#6e7681}
.chip i{width:8px;height:8px;border-radius:50%;background:currentColor;display:inline-block}
.sp{flex:1}
.leg{display:flex;gap:16px;align-items:center;color:var(--mut);font-size:12.5px}
.dot{width:10px;height:10px;border-radius:3px;display:inline-block;margin-right:6px;vertical-align:-1px}
#plot{position:relative;padding:4px 10px 0}
svg{display:block;width:100%;height:auto} text{font-family:"JetBrains Mono",ui-monospace,Menlo,monospace}
.tip{position:absolute;pointer-events:none;background:#0d1117ee;border:1px solid #484f58;border-radius:10px;padding:10px 12px;
  font:12.5px/1.55 Inter,system-ui,sans-serif;box-shadow:0 8px 28px rgba(0,0,0,.5);display:none;z-index:5;min-width:210px;backdrop-filter:blur(4px)}
.tip b{font-size:14px} .tip .r{display:flex;justify-content:space-between;gap:18px;color:var(--mut)} .tip .r span:last-child{color:var(--fg);font-family:"JetBrains Mono",monospace;font-size:12px}
.tip hr{border:0;border-top:1px solid var(--line);margin:6px 0}
.note{padding:12px 22px 18px;color:var(--mut);font-size:12.5px;border-top:1px solid var(--line)}
.pt{transition:transform .12s ease;transform-box:fill-box;transform-origin:center} .pt:hover{transform:scale(1.14)}
</style></head><body>
<div class="card">
  <div class="head"><div><h1>Energy Meter Reliability</h1><div class="sub">Can agents tell when a meter total can be trusted?</div></div>
  <div class="tag mono">Synthetic data &middot; 13 core tasks</div></div>
  <div class="hl">__HEADLINE__</div>
  <div class="bar"><button class="chip" id="tf" aria-pressed="true"><i></i>Frontier</button><button class="chip" id="tl" aria-pressed="false"><i></i>Log scale</button>
    <span class="sp"></span><div class="leg"><span><i class="dot" style="background:var(--ant)"></i>Anthropic</span><span><i class="dot" style="background:var(--oai)"></i>OpenAI</span></div></div>
  <div id="plot"><svg id="svg" viewBox="0 0 1060 600" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Accuracy against cost per attempt for seven models"></svg><div class="tip" id="tip"></div></div>
  <div class="note">Hover a model for details. Accuracy = mean pass rate over the 13 core tasks (5 fixable, 2 clean controls, 6 where the honest answer is to decline); error bars are &plusmn;1 SE over tasks. Cost is measured per attempt from agent logs (Fable 5.2 is estimated from logged token usage at list price). Frontier = no cheaper model scores higher. Small samples: treat differences as signals, not rankings.</div>
</div>
<script>
const DATA = __DATA__;
const COL = {Anthropic:"#f0865a", OpenAI:"#34d399"}, NS="http://www.w3.org/2000/svg";
const W=1060,H=600,M={l:70,r:28,t:24,b:56}, state={log:false,frontier:true};
const svg=document.getElementById("svg"), tip=document.getElementById("tip");
function el(n,a,p){const e=document.createElementNS(NS,n);for(const k in a)e.setAttribute(k,a[k]);if(p)p.appendChild(e);return e}
function frontierSet(){const s=[...DATA].sort((a,b)=>a.cost-b.cost);let best=-1,out=[];for(const d of s){if(d.acc>best){out.push(d);best=d.acc}}return out}
function render(){
  svg.innerHTML="";
  const fr=frontierSet(), fset=new Set(fr.map(d=>d.name));
  const cmin=Math.min(...DATA.map(d=>d.cost)), cmax=Math.max(...DATA.map(d=>d.cost));
  const lo=Math.min(...DATA.map(d=>d.acc-d.se)), hi=Math.max(...DATA.map(d=>d.acc+d.se));
  const y0=Math.max(0,Math.floor((lo-0.02)*10)/10), y1=Math.min(1,Math.ceil((hi+0.04)*10)/10);
  const x0=state.log?cmin*0.75:0, x1=state.log?cmax*1.35:cmax*1.18;
  const fx=c=>M.l+(state.log?(Math.log(c)-Math.log(x0))/(Math.log(x1)-Math.log(x0)):(c-x0)/(x1-x0))*(W-M.l-M.r);
  const fy=a=>H-M.b-((a-y0)/(y1-y0))*(H-M.t-M.b);
  const defs=el("defs",{},svg), pat=el("pattern",{id:"dots",width:16,height:16,patternUnits:"userSpaceOnUse"},defs);
  el("circle",{cx:2,cy:2,r:.9,fill:"#2a313a"},pat);
  const pw=W-M.l-M.r, ph=H-M.t-M.b;
  el("rect",{x:M.l,y:M.t,width:pw,height:ph,fill:"#0f141b",rx:6},svg); el("rect",{x:M.l,y:M.t,width:pw,height:ph,fill:"url(#dots)",rx:6},svg);
  const cs=DATA.map(d=>d.cost).sort((a,b)=>a-b), as=DATA.map(d=>d.acc).sort((a,b)=>a-b);
  const medc=cs[Math.floor(cs.length/2)], meda=as[Math.floor(as.length/2)];
  el("rect",{x:M.l,y:M.t,width:fx(medc)-M.l,height:fy(meda)-M.t,fill:"#3fb950",opacity:.07},svg);
  el("rect",{x:fx(medc),y:fy(meda),width:W-M.r-fx(medc),height:H-M.b-fy(meda),fill:"#f85149",opacity:.07},svg);
  const lab=(t,x,y,a,fill,size)=>{const e=el("text",{x,y,"font-size":size||11,fill:fill||"#8b949e","text-anchor":a||"start"},svg);e.textContent=t;return e};
  lab("EFFICIENT",M.l+14,M.t+20,"start","#3fb95099"); lab("INEFFICIENT",W-M.r-14,H-M.b-14,"end","#f8514999");
  for(let v=Math.ceil(y0*10)/10; v<=y1+1e-9; v+=0.1){const y=fy(v);el("line",{x1:M.l,x2:W-M.r,y1:y,y2:y,stroke:"#21262d"},svg);lab(Math.round(v*100)+"%",M.l-10,y+4,"end")}
  const ticks=state.log?[0.05,0.07,0.10,0.14,0.20,0.30].filter(t=>t>=x0&&t<=x1):Array.from({length:30},(_,i)=>i*(x1>0.3?0.1:0.02)).filter(t=>t<=x1);
  for(const t of ticks){const x=fx(t);el("line",{x1:x,x2:x,y1:H-M.b,y2:H-M.b+5,stroke:"#484f58"},svg);lab("$"+t.toFixed(2),x,H-M.b+22,"middle")}
  el("line",{x1:M.l,x2:W-M.r,y1:H-M.b,y2:H-M.b,stroke:"#484f58"},svg);
  el("line",{x1:M.l,x2:W-M.r,y1:fy(Math.max(...DATA.map(d=>d.acc))),y2:fy(Math.max(...DATA.map(d=>d.acc))),stroke:"#6e7681","stroke-dasharray":"3 5"},svg);
  lab("BEST PERFORMANCE",W-M.r-10,fy(Math.max(...DATA.map(d=>d.acc)))-8,"end","#8b949e",10);
  el("line",{x1:fx(cmin),x2:fx(cmin),y1:M.t,y2:H-M.b,stroke:"#6e7681","stroke-dasharray":"3 5"},svg);
  const lc=lab("LOWEST COST",fx(cmin)-8,H-M.b-12,"start","#8b949e",10);lc.setAttribute("transform",`rotate(-90 ${fx(cmin)-8} ${H-M.b-12})`);
  if(state.frontier&&fr.length>1){
    el("polyline",{points:fr.map(d=>fx(d.cost)+","+fy(d.acc)).join(" "),fill:"none",stroke:"#58a6ff","stroke-width":2,"stroke-linejoin":"round",opacity:.9},svg)}
  for(const d of DATA){
    const x=fx(d.cost), ya=fy(d.acc+d.se), yb=fy(d.acc-d.se), cap=9;
    const st={stroke:COL[d.lab],opacity:.55,"stroke-width":2,"stroke-linecap":"round"};
    el("line",{x1:x,x2:x,y1:ya,y2:yb,...st},svg);          // range bar
    el("line",{x1:x-cap,x2:x+cap,y1:ya,y2:ya,...st},svg);  // upper cap
    el("line",{x1:x-cap,x2:x+cap,y1:yb,y2:yb,...st},svg);  // lower cap
  }
  for(const d of DATA){
    const x=fx(d.cost),y=fy(d.acc),isF=!state.frontier||fset.has(d.name);
    const g=el("g",{class:"pt",style:"cursor:pointer",tabindex:0},svg);
    el("circle",{cx:x,cy:y,r:17,fill:"#0d1117",stroke:COL[d.lab],"stroke-width":isF&&state.frontier?2.6:1.6,opacity:isF?1:.5},g);
    el("circle",{cx:x,cy:y,r:17,fill:COL[d.lab],opacity:isF?.16:.08},g);
    const t=el("text",{x,y:y+5,"text-anchor":"middle","font-size":14,"font-weight":600,fill:COL[d.lab],opacity:isF?1:.6},g);t.textContent=d.lab==="Anthropic"?"A":"O";
    const nm=el("text",{x,y:y-26,"text-anchor":"middle","font-size":12,fill:isF?"#e6edf3":"#8b949e","font-family":"Inter,system-ui,sans-serif"},g);nm.textContent=d.name;
    const show=ev=>{const r=document.getElementById("plot").getBoundingClientRect();
      tip.style.display="block";
      let lx=ev.clientX-r.left+16, ty=ev.clientY-r.top+16; if(lx>r.width-250) lx=ev.clientX-r.left-250;
      tip.style.left=lx+"px";tip.style.top=ty+"px";
      tip.innerHTML=`<b>${d.name}</b> <span style="color:${COL[d.lab]};font-size:12px">${d.lab}</span><hr>
      <div class="r"><span>Accuracy</span><span>${(d.acc*100).toFixed(1)}% &plusmn;${(d.se*100).toFixed(1)}</span></div>
      <div class="r"><span>Fix and compute</span><span>${(d.fix*100).toFixed(0)}%</span></div>
      <div class="r"><span>Decline</span><span>${(d.dec*100).toFixed(0)}%</span></div>
      <div class="r"><span>Clean controls</span><span>${(d.ctl*100).toFixed(0)}%</span></div><hr>
      <div class="r"><span>Cost / attempt</span><span>$${d.cost.toFixed(3)}</span></div>
      <div class="r"><span>Time / attempt</span><span>${Math.round(d.secs)}s</span></div>
      <div class="r"><span>Model calls</span><span>${d.calls.toFixed(1)}</span></div>
      <div class="r"><span>Attempts</span><span>${d.n} on ${d.tasks} tasks</span></div>`};
    g.addEventListener("mouseenter",show);g.addEventListener("mousemove",show);g.addEventListener("click",show);g.addEventListener("focus",()=>{});
    g.addEventListener("mouseleave",()=>tip.style.display="none");
  }
  lab("Cost per attempt (USD"+(state.log?", log scale":"")+")",(W+M.l-M.r)/2,H-10,"middle","#8b949e",11);
  const ya=lab("Accuracy",16,(H+M.t-M.b)/2,"middle","#8b949e",11);ya.setAttribute("transform",`rotate(-90 16 ${(H+M.t-M.b)/2})`);
}
const tf=document.getElementById("tf"), tl=document.getElementById("tl");
tf.onclick=()=>{state.frontier=!state.frontier;tf.setAttribute("aria-pressed",state.frontier);render()};
tl.onclick=()=>{state.log=!state.log;tl.setAttribute("aria-pressed",state.log);render()};
document.addEventListener("click",e=>{if(!e.target.closest(".pt"))tip.style.display="none"});
render();
</script></body></html>
"""

if __name__ == "__main__":
    main()
