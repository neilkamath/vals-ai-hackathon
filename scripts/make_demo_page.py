"""Build a short slide page for the live demo from the committed result tables.

Run:  python3 scripts/make_demo_page.py   ->  results/draft/demo.html   (git-ignored)
Open it directly (file://) or serve the repo root with `python3 -m http.server 8000`
and visit http://localhost:8000/results/draft/demo.html
Keys: right / left arrows or space to move between slides. Click the right or left half of the page also works.
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "draft"
OUT.mkdir(parents=True, exist_ok=True)


def main():
    lb = list(csv.DictReader(open(ROOT / "results/curated/leaderboard.csv")))
    pt = {r["task"]: r for r in csv.DictReader(open(ROOT / "results/curated/per_task_pass_rate.csv"))}
    models = [{"name": r["model"], "acc": float(r["accuracy"]), "fix": float(r["fixable"]), "dec": float(r["decline"]),
               "ctl": float(r["controls"]), "n": int(r["attempts"])} for r in lb]
    ex = pt["energy-meter-degraded-month"]
    example = [{"name": k, "v": float(v)} for k, v in ex.items() if k != "task"]
    html = TEMPLATE.replace("__MODELS__", json.dumps(models)).replace("__EXAMPLE__", json.dumps(example))
    (OUT / "demo.html").write_text(html)
    print("wrote", OUT / "demo.html")


TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Energy Meter Reliability: demo</title>
<style>
:root{--bg:#fafaf9;--fg:#1c1917;--mut:#78716c;--line:#e7e5e4;--ant:#c4623a;--oai:#2f8f6f;--bad:#d24a5c;--grey:#9aa4b2;--card:#fff}
*{box-sizing:border-box} html,body{height:100%;margin:0;background:var(--bg);color:var(--fg)}
body{font:20px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;overflow:hidden}
.slide{position:absolute;inset:0;padding:48px 72px 56px;display:none;flex-direction:column;justify-content:center}
.slide.on{display:flex}
h1{font-size:52px;line-height:1.1;margin:0 0 14px;letter-spacing:-.02em} h2{font-size:34px;margin:0 0 22px;letter-spacing:-.01em}
.sub{color:var(--mut);font-size:24px;margin:0}
.big{font-size:72px;font-weight:700;letter-spacing:-.03em;line-height:1}
.mut{color:var(--mut)} .bad{color:var(--bad)} .good{color:var(--oai)}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-top:10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px 24px}
.card b{display:block;font-size:22px;margin-bottom:6px} .card .tag{font-size:14px;color:var(--mut);text-transform:uppercase;letter-spacing:.08em}
.card .out{margin-top:12px;padding-top:12px;border-top:1px solid var(--line);font-size:18px}
code,pre{font-family:ui-monospace,Menlo,Consolas,monospace} pre{background:#1c1917;color:#f5f5f4;border-radius:12px;padding:22px 26px;font-size:17px;line-height:1.5;margin:0;overflow:hidden}
pre .hl{background:#7a2e3a;border-radius:4px;padding:1px 4px}
.two{display:grid;grid-template-columns:1.5fr 1fr;gap:36px;align-items:center}
.stat{margin-bottom:20px} .stat .lab{font-size:16px;color:var(--mut);text-transform:uppercase;letter-spacing:.08em}
img.chart{width:100%;border:1px solid var(--line);border-radius:12px;background:#fff}
.bars{display:flex;flex-direction:column;gap:12px}
.row{display:grid;grid-template-columns:130px 1fr;align-items:center;gap:14px}
.row .nm{text-align:right;font-size:19px}
.pair{display:flex;flex-direction:column;gap:4px}
.b{height:20px;border-radius:4px;position:relative;min-width:2px} .b span{position:absolute;left:calc(100% + 8px);top:-1px;font-size:15px;color:var(--mut);white-space:nowrap;font-variant-numeric:tabular-nums}
.leg{display:flex;gap:22px;font-size:16px;color:var(--mut);margin-bottom:14px} .leg i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}
#s7{padding:0;align-items:center} #fw{width:1100px;height:900px;transform-origin:top center;margin-top:8px} #fw iframe{width:1100px;height:900px;border:0;background:#0d1117}
video{width:100%;max-height:calc(100vh - 200px);border-radius:12px;border:1px solid var(--line);background:#000}
.bg{display:grid;grid-template-columns:1.5fr 1fr;gap:48px;align-items:center}
ul.plain{list-style:none;padding:0;margin:0;font-size:28px} ul.plain li{margin:8px 0}
.chk{display:flex;flex-direction:column;gap:0;border-left:2px solid var(--line);padding-left:36px}
.ck{display:flex;align-items:center;gap:18px;font-size:26px;padding:18px 0;position:relative}
.ck i{font-style:normal;width:44px;height:44px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:22px;font-weight:700;color:#fff;flex:none}
.ck.ok i{background:var(--oai)} .ck.no i{background:var(--bad)} .ck.no{color:var(--bad);font-weight:700}
.ck span{font-size:16px;color:var(--mut);font-weight:400;margin-left:6px}
ul.bul{margin:0;padding-left:30px;font-size:30px} ul.bul li{margin:18px 0}
ul{margin:0;padding-left:26px} li{margin:10px 0}
.nav{position:fixed;bottom:16px;left:0;right:0;text-align:center;color:var(--mut);font-size:14px;pointer-events:none}
.dots span{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--line);margin:0 4px} .dots span.on{background:var(--fg)}
</style></head><body>

<section class="slide" id="s1">
  <p class="sub" style="margin-bottom:18px">Vals Hacks, Track 1</p>
  <h1>Energy Meter Reliability</h1>
  <p class="sub">Can agents tell when a number cannot be trusted?</p>
</section>

<section class="slide" id="s1b">
  <h2>Background: silent data errors</h2>
  <ul class="bul">
    <li>Agents analyze data that nobody double-checks</li>
    <li>The file parses and the number looks plausible</li>
    <li>But a hidden fault makes it wrong</li>
    <li>Reporting a number says "trust this"</li>
  </ul>
</section>

<section class="slide" id="s2">
  <h2>One question, three kinds of data</h2>
  <p class="sub" style="margin-bottom:22px">"What was November's total energy use in kWh?"</p>
  <div class="cards">
    <div class="card"><span class="tag">Fixable</span><b>Documented problems</b>Rollover, CT change, DST, meter swap<div class="out">Right answer: <b class="good" style="display:inline">the corrected number</b></div></div>
    <div class="card"><span class="tag">Silent fault</span><b>Plus one undocumented</b>A day where the sensor under-reads<div class="out">Right answer: <b class="bad" style="display:inline">cannot_determine</b></div></div>
    <div class="card"><span class="tag">Control</span><b>No problems</b>Even a really quiet holiday day<div class="out">Right answer: <b class="good" style="display:inline">the number</b></div></div>
  </div>
  <p class="mut" style="margin-top:26px;font-size:18px">13 tasks. Synthetic data, answer known by construction.</p>
</section>

<section class="slide" id="s3">
  <h2>The hidden fault</h2>
  <div class="two">
    <img class="chart" src="../curated/demo_daily_kwh.png" alt="Daily kWh around the holiday closure">
    <div>
      <div class="stat"><div class="lab">Fri 27 Nov, meter says</div><div class="big bad">3 kWh</div></div>
      <div class="stat"><div class="lab">Total after every documented fix</div><div class="big">19,892</div></div>
      <div class="stat"><div class="lab">True total</div><div class="big good">20,150</div></div>
      <div class="mut" style="font-size:18px">The README says "reduced load only", so a low day looks normal.</div>
    </div>
  </div>
</section>

<section class="slide" id="s4">
  <h2>What a frontier model did</h2>
  <p class="sub" style="margin-bottom:18px">Sonnet 5.5 fixed all three documented problems, saw the dead day, and still answered.</p>
<pre>{"answer": 19891.6, "flags": [
  "register rollover ... handled by adding 1e6",
  "CT replacement ... multiplied by 10",
  "timestamps in UTC converted to America/Los_Angeles",
  <span class="hl">"holiday near-zero consumption (reduced load) kept as-is"</span>]}</pre>
  <p style="margin-top:22px">Noticing is not acting. A number claims the data is reliable.</p>
</section>

<section class="slide" id="s5">
  <h2>Fixing is easy. Declining is not.</h2>
  <div class="leg"><span><i style="background:var(--grey)"></i>Fixable tasks passed</span><span><i style="background:var(--bad)"></i>Decline tasks passed</span></div>
  <div class="bars" id="bars"></div>
  <p class="mut" style="margin-top:18px;font-size:17px">5 to 7 attempts per task and model, mini-SWE-agent on Valkyrie.</p>
</section>

<section class="slide" id="s6">
  <h2>The example task, for every model</h2>
  <p class="sub" style="margin-bottom:20px">Pass rate on <code>energy-meter-degraded-month</code>. Each model was run 5 to 7 times. Sonnet passes 3 of 7, Opus 2 of 7.</p>
  <div class="bars" id="ex"></div>
</section>

<section class="slide" id="s7">
  <div id="fw"><iframe src="../../docs/index.html" title="Interactive chart" scrolling="no"></iframe></div>
</section>

<section class="slide" id="s9">
  <h2>Takeaways</h2>
  <ul>
    <li><b>Strong models fix the data.</b> Opus, Fable, Sonnet and gpt-5.5 pass every fixable task.</li>
    <li><b>Few of them refuse.</b> Decline rate: Opus 73%, Fable 53%, Sonnet 44%, gpt-5.5 10%.</li>
    <li><b>A fix is not a verdict.</b> Models notice the fault, explain it away, and report a number.</li>
  </ul>
  <p class="mut" style="margin-top:28px;font-size:18px">Limits: synthetic data, small samples, one harness, no human baseline.</p>
  <p class="mut" style="font-size:18px">github.com/neilkamath/vals-ai-hackathon</p>
</section>

<div class="nav"><div class="dots" id="dots"></div></div>
<script>
const M = __MODELS__, EX = __EXAMPLE__;
const pct = v => Math.round(v*100)+"%";
const order = [...M].sort((a,b)=>b.dec-a.dec||b.fix-a.fix);
document.getElementById("bars").innerHTML = order.map(m=>`<div class="row"><div class="nm">${m.name}</div><div class="pair">
  <div class="b" style="width:${m.fix*70}%;background:var(--grey)"><span>${pct(m.fix)}</span></div>
  <div class="b" style="width:${m.dec*70}%;background:var(--bad)"><span>${pct(m.dec)}</span></div></div></div>`).join("");
const ex = [...EX].sort((a,b)=>b.v-a.v);
document.getElementById("ex").innerHTML = ex.map(m=>`<div class="row"><div class="nm">${m.name}</div><div class="b" style="width:${Math.max(m.v,0.004)*70}%;background:var(--bad)"><span>${pct(m.v)}</span></div></div>`).join("");
const slides=[...document.querySelectorAll(".slide")], dots=document.getElementById("dots");
dots.innerHTML = slides.map(()=>"<span></span>").join("");
let i=0;
function show(n){i=Math.max(0,Math.min(slides.length-1,n));slides.forEach((s,k)=>s.classList.toggle("on",k===i));
  [...dots.children].forEach((d,k)=>d.classList.toggle("on",k===i));history.replaceState(null,"","#"+(i+1));
  const v=document.querySelector("video"); if(v){slides[i].contains(v)?v.play().catch(()=>{}):v.pause()}}
document.addEventListener("keydown",e=>{if(["ArrowRight"," ","PageDown"].includes(e.key))show(i+1);if(["ArrowLeft","PageUp"].includes(e.key))show(i-1)});
document.addEventListener("click",e=>{if(e.target.closest("iframe,video"))return;show(e.clientX>innerWidth/2?i+1:i-1)});
function fit(){const k=Math.min((innerHeight-40)/900,innerWidth/1100);document.getElementById("fw").style.transform="scale("+k+")";document.getElementById("fw").style.marginBottom=(900*k-900)+"px"}
addEventListener("resize",fit);fit();
show((parseInt(location.hash.slice(1))||1)-1);
</script></body></html>
"""

if __name__ == "__main__":
    main()
