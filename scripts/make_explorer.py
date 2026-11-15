"""Build a static task and trace explorer for the 13 core tasks and the seven reported models.

Run:  python3 scripts/make_explorer.py   ->  docs/explorer/index.html and docs/explorer/data/*.json
Needs the local raw run outputs (results/raw, git-ignored) and results/attempts.jsonl. The output is static and
is served by GitHub Pages together with docs/index.html.

Per attempt we keep the result, the answer the agent wrote, and a slimmed trace: the model's commands and the
(truncated) command outputs. Long outputs keep their head and tail.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "explorer"
DATA = OUT / "data"

MODELS = {"anthropic/claude-opus-5-5": "Opus 5.5", "anthropic/claude-fable-5-2": "Fable 5.2", "anthropic/claude-sonnet-5-5": "Sonnet 5.5",
          "openai/gpt-5.5": "gpt-5.5", "openai/gpt-5.4": "gpt-5.4", "anthropic/claude-haiku-4-5": "Haiku 4.5", "openai/gpt-5.2": "gpt-5.2"}
SKIP_STAGES = ("4-private", "5-stacked", "fable-probe")
OUT_CHARS, CMD_CHARS, TEXT_CHARS = 1800, 3000, 1500

FAIL_TEXT = {
    "pass": "Passed",
    "never_detected": "Reported a number and never mentioned the fault",
    "detected_but_reported_number": "Noticed the fault but reported a number anyway",
    "flagged_all_but_wrong_number": "Mentioned every problem but the number is wrong",
    "no_fix": "Did not apply the documented fixes",
    "partial_fix": "Applied only some of the documented fixes",
    "over_abstained": "Declined although the data supports a number",
}

E = "energy-meter-"
TASKS = [
    # id, kind, short title, what the agent must do, what is hidden
    (E + "rollover-only", "fixable", "Register rollover", "Total consumption over a UTC window.",
     "The meter register wraps from 999,999.9 to 0.0 (documented in the datasheet). Add 1,000,000 across the wrap."),
    (E + "rollover-ct", "fixable", "Rollover and CT change", "Total consumption over a UTC window.",
     "The wrap, plus a CT replacement on 13 Nov after which the register reads 1/10 of true energy (maintenance log). Multiply by 10 after that point."),
    (E + "november", "fixable", "Rollover, CT change and local month", "November total in the site's local time.",
     "Both fixes, plus readings are in UTC while the question is a local month across the DST change."),
    (E + "swap-november", "fixable", "Meter replaced mid-month", "November total in local time.",
     "The meter is replaced mid-month, so the register drop looks like a rollover but is not. Plus the earlier fixes."),
    ("energy-stream-november", "fixable", "Streamed intake through a tool", "November total, with the data served through a paged meterctl tool.",
     "Overlapping pages, rate limiting, a format change from kWh to Wh with epoch times, plus the earlier fixes."),
    (E + "degraded-month", "silent", "Dead day on 27 Nov", "November total in local time.",
     "All documented fixes work, but Fri 27 Nov was recorded at 1% of its true use (3 kWh instead of about 260). The README's 'reduced load only' makes it look normal."),
    (E + "degraded-month-s2", "silent", "Dead day, second seed", "November total in local time.",
     "The same fault as the dead-day task with fresh random data."),
    (E + "degraded-month-s3", "silent", "Dead day, third seed", "November total in local time.",
     "The same fault again, a third seed."),
    (E + "closure-swap-degraded", "silent", "Dead day behind a meter swap", "November total in local time.",
     "The dead day, plus a documented meter replacement on 20 Nov that the agent must handle first."),
    ("energy-stream-degraded", "silent", "Dead day through the tool", "November total, with the data served through a paged meterctl tool.",
     "The dead day behind the paged tool with its format change."),
    (E + "frozen-tail", "silent", "Frozen register at month end", "November total in local time.",
     "From about 28 Nov 22:00 local the register stays flat to the end of the month, which looks like zero use. The catch-up reading is not in the export."),
    (E + "october-clean", "control", "Clean week", "Total for a week in early October.",
     "No recording problem touches this window. The number is the right answer."),
    (E + "closure-day", "control", "A real low day", "Total for Fri 27 Nov alone.",
     "The day is a real holiday closure with low load and the meter is fine. The right answer is the number, not a refusal."),
]


SECRET_ENV = re.compile(r"\b([A-Z][A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*)=\S+")
SECRET_TOK = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|xox[bp]-[A-Za-z0-9-]{10,}|AKIA[A-Z0-9]{12,}|(?:ak|as)-[A-Za-z0-9]{16,})")


def redact(text):
    """Agents sometimes print the sandbox environment, which holds the API keys passed to the harness. Never publish those."""
    text = SECRET_ENV.sub(lambda m: m.group(1) + "=[REDACTED]", text)
    return SECRET_TOK.sub("[REDACTED]", text)


def slim_trace(traj_path):
    d = json.load(open(traj_path))
    steps = []
    for m in d["messages"][2:]:
        role = m.get("role")
        ex = m.get("extra") or {}
        if role == "assistant":
            msg = ((ex.get("response") or {}).get("choices") or [{}])[0].get("message") or {}
            text = (m.get("content") or msg.get("content") or "")
            if isinstance(text, list):
                text = " ".join(p.get("text", "") for p in text if isinstance(p, dict))
            cmds = [a.get("command", "") for a in (ex.get("actions") or [])]
            steps.append({"k": "a", "text": redact(text)[:TEXT_CHARS], "cmd": redact("\n".join(cmds))[:CMD_CHARS]})
        elif role == "tool":
            out = ""
            try:
                out = json.loads(m["content"]).get("output", "")
            except Exception:
                out = str(m.get("content", ""))
            out = redact(out)
            if len(out) > OUT_CHARS:
                out = out[:1200] + "\n... [truncated] ...\n" + out[-500:]
            steps.append({"k": "o", "text": out, "rc": ex.get("returncode")})
    return steps


def final_answer(steps):
    """The answer the agent wrote: from the last command that wrote answer.json, else from a later cat or print of it."""
    num = r'"answer"\s*:\s*([-0-9.eE+]+)'
    last = None
    for i in range(len(steps) - 1, -1, -1):
        if steps[i]["k"] == "a" and "answer.json" in steps[i]["cmd"]:
            last = i
            break
    if last is None:
        return "no answer written"
    cmd = steps[last]["cmd"]
    if "cannot_determine" in cmd:
        return "cannot_determine"
    m = re.search(num, cmd)
    if m:
        return m.group(1)
    for s in steps[last + 1:]:
        if s["k"] == "o":
            if "cannot_determine" in s["text"]:
                return "cannot_determine"
            m = re.search(num, s["text"])
            if m:
                return m.group(1)
    for s in steps[last - 1:last + 3]:
        if s["k"] == "o":
            m = re.search(r"\b\d{4,6}\.\d+\b", s["text"])
            if m:
                return m.group(0)
    return "see trace"


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(line) for line in open(ROOT / "results" / "attempts.jsonl")]
    ids = {t[0] for t in TASKS}
    rows = [r for r in rows if r["model"] in MODELS and r["task"] in ids and r["stage"] not in SKIP_STAGES]
    index = []
    for tid, kind, title, ask, hidden in TASKS:
        exp = json.load(open(ROOT / "tasks" / tid / "tests" / "expected.json"))
        instr = (ROOT / "tasks" / tid / "instruction.md").read_text()
        expect = "cannot_determine" if exp.get("expected_status") == "cannot_determine" else f"{exp['answer']:,.1f} kWh"
        files = sorted(p.name for p in (ROOT / "tasks" / tid / "environment" / "data").iterdir()) if (ROOT / "tasks" / tid / "environment" / "data").exists() else []
        attempts = []
        for r in sorted((r for r in rows if r["task"] == tid), key=lambda r: (list(MODELS).index(r["model"]), r["run_id"])):
            steps = slim_trace(ROOT / "results" / "raw" / r["run_id"] / tid / "mini_swe_agent" / "trajectory.json")
            ans = final_answer(steps)
            attempts.append({"model": MODELS[r["model"]], "run": r["run_id"][:8], "pass": r["reward"] >= 1, "answer": ans,
                             "why": FAIL_TEXT.get(r["failure"], r["failure"]), "noticed": bool(r["details"].get("flags_hit")),
                             "cost": r.get("cost"), "calls": r.get("calls"), "steps": steps})
        (DATA / f"{tid}.json").write_text(json.dumps({"id": tid, "instruction": instr, "expect": expect, "files": files, "attempts": attempts}, separators=(",", ":")))
        per = {}
        for a in attempts:
            p = per.setdefault(a["model"], [0, 0])
            p[0] += a["pass"]
            p[1] += 1
        index.append({"id": tid, "kind": kind, "title": title, "ask": ask, "hidden": hidden, "expect": expect, "per": per})
    (DATA / "index.json").write_text(json.dumps({"models": list(MODELS.values()), "tasks": index}, separators=(",", ":")))
    (OUT / "index.html").write_text(PAGE)
    size = sum(f.stat().st_size for f in DATA.iterdir()) / 1e6
    print(f"wrote {len(index)} tasks, {len(rows)} attempts, {size:.1f} MB of data")


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Energy Meter Reliability: task explorer</title>
<style>
:root{--bg:#fafaf9;--fg:#1c1917;--mut:#78716c;--line:#e7e5e4;--card:#fff;--ok:#2f8f6f;--bad:#d24a5c;--grey:#9aa4b2;--code:#1c1917}
*{box-sizing:border-box} html,body{margin:0;background:var(--bg);color:var(--fg)}
body{font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
code,pre{font-family:ui-monospace,Menlo,Consolas,monospace}
a{color:inherit} .wrap{max-width:1100px;margin:0 auto;padding:28px 24px 80px}
h1{font-size:30px;margin:0 0 4px;letter-spacing:-.01em} h2{font-size:22px;margin:30px 0 12px} .mut{color:var(--mut)}
.crumb{font-size:14px;margin-bottom:14px} .crumb a{color:var(--mut);cursor:pointer;text-decoration:none} .crumb a:hover{text-decoration:underline}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;cursor:pointer;transition:border-color .12s}
.card:hover{border-color:#a8a29e} .card b{display:block;font-size:17px} .card .id{font:12px ui-monospace,monospace;color:var(--mut);margin-bottom:8px}
.tag{display:inline-block;font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);margin-bottom:6px}
.mini{display:flex;gap:4px;margin-top:12px;align-items:flex-end;height:34px}
.mini div{flex:1;background:var(--line);border-radius:3px;position:relative;height:100%} .mini div i{position:absolute;bottom:0;left:0;right:0;border-radius:3px;background:var(--ok)}
.mini.sil div i{background:var(--bad)} .minil{display:flex;gap:4px;font-size:10px;color:var(--mut);margin-top:3px} .minil span{flex:1;text-align:center;overflow:hidden}
.box{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 20px;margin:12px 0}
.kv{display:grid;grid-template-columns:150px 1fr;gap:6px 16px} .kv div:nth-child(odd){color:var(--mut)}
pre{background:var(--code);color:#f5f5f4;border-radius:8px;padding:12px 14px;font-size:13px;line-height:1.5;overflow:auto;margin:6px 0;white-space:pre-wrap;word-break:break-word}
.row{display:grid;grid-template-columns:120px 1fr;gap:14px;align-items:center;padding:10px 0;border-top:1px solid var(--line)}
.row:first-child{border-top:0} .nm{font-weight:600}
.chips{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.chip{width:30px;height:30px;border-radius:8px;border:2px solid var(--bad);background:#fff;color:var(--bad);font-weight:700;font-size:15px;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;padding:0}
.chip.p{border-color:var(--ok);color:var(--ok)} .chip.on{color:#fff;background:var(--bad)} .chip.p.on{background:var(--ok)}
.rate{margin-left:8px;color:var(--mut);font-size:14px}
.trace{border:1px solid var(--line);border-radius:12px;background:var(--card);margin:16px 0;overflow:hidden}
.thead{padding:14px 18px;border-bottom:1px solid var(--line);display:flex;gap:14px;flex-wrap:wrap;align-items:center}
.badge{font-size:13px;font-weight:700;padding:3px 10px;border-radius:999px;color:#fff;background:var(--bad)} .badge.p{background:var(--ok)}
.tbody{padding:6px 18px 16px;max-height:640px;overflow:auto}
.step{margin:14px 0 0} .step .lab{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut)} .step .txt{margin:4px 0;white-space:pre-wrap}
.step.o pre{background:#f5f5f4;color:#292524;border:1px solid var(--line)}
.final{border:2px solid var(--fg);border-radius:8px;padding:2px 8px;margin-top:10px}
.note{font-size:14px;color:var(--mut)} .legend{display:flex;gap:18px;font-size:14px;color:var(--mut);margin:10px 0}
.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}
@media(max-width:640px){.row{grid-template-columns:1fr}.kv{grid-template-columns:1fr}}
</style></head><body><div class="wrap" id="app"></div>
<script>
const $=s=>document.querySelector(s), esc=s=>String(s??"").replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
let IDX=null; const CACHE={};
const KIND={fixable:"Fixable problems",silent:"Silent fault: the right answer is to decline",control:"Clean control"};
const pct=(p,n)=>n?Math.round(p/n*100)+"%":"-";
async function load(url){return (await fetch(url)).json()}
async function route(){
  IDX=IDX||await load("data/index.json");
  const m=location.hash.match(/^#\/task\/([^/]+)(?:\/(\d+))?/);
  if(m)return taskView(m[1],m[2]); home();
}
function home(){
  const groups=["fixable","silent","control"];
  $("#app").innerHTML=`<h1>Energy Meter Reliability</h1><div class="mut">Task explorer: pick a task, then click any attempt to read the model's trace.</div>
  <div class="legend"><span><i style="background:var(--ok)"></i>Pass rate on fixable tasks and controls</span><span><i style="background:var(--bad)"></i>Pass rate on silent-fault tasks (declined correctly)</span></div>`+
  groups.map(g=>`<h2>${KIND[g]}</h2><div class="grid">`+IDX.tasks.filter(t=>t.kind===g).map(t=>{
    const bars=IDX.models.map(mo=>{const p=t.per[mo]||[0,0];return `<div title="${mo}: ${p[0]}/${p[1]}"><i style="height:${p[1]?p[0]/p[1]*100:0}%"></i></div>`}).join("");
    return `<div class="card" onclick="location.hash='#/task/${t.id}'"><span class="tag">${g==="silent"?"Silent fault":g==="control"?"Control":"Fixable"}</span><b>${esc(t.title)}</b><div class="id">${t.id}</div>
    <div class="mut" style="font-size:14px">${esc(t.ask)}</div><div class="mini ${g==="silent"?"sil":""}">${bars}</div>
    <div class="minil">${IDX.models.map(m=>`<span>${m.replace(/ .*/,"").replace("gpt-","g")}</span>`).join("")}</div></div>`}).join("")+`</div>`).join("")+
  `<p class="note" style="margin-top:28px">Bars run left to right: ${IDX.models.join(", ")}. Hover a bar for its pass count. Traces show the model's commands and truncated outputs.</p>`;
  scrollTo(0,0);
}
async function taskView(id,sel){
  const t=IDX.tasks.find(x=>x.id===id); if(!t){home();return}
  const d=CACHE[id]=CACHE[id]||await load(`data/${id}.json`);
  const byModel={}; d.attempts.forEach((a,i)=>{(byModel[a.model]=byModel[a.model]||[]).push([a,i])});
  const rows=IDX.models.map(mo=>{const arr=byModel[mo]||[];const p=arr.filter(x=>x[0].pass).length;
    return `<div class="row"><div class="nm">${mo}</div><div class="chips">`+arr.map(([a,i])=>`<button class="chip ${a.pass?"p":""} ${String(i)===sel?"on":""}" title="${a.pass?"pass":"fail"}: ${esc(a.answer)}" onclick="location.hash='#/task/${id}/${i}'">${a.pass?"&#10003;":"&#10007;"}</button>`).join("")+`<span class="rate">${p}/${arr.length} (${pct(p,arr.length)})</span></div></div>`}).join("");
  $("#app").innerHTML=`<div class="crumb"><a onclick="location.hash=''">All tasks</a> / ${esc(t.title)}</div>
  <h1>${esc(t.title)}</h1><div class="id mut" style="font:13px ui-monospace,monospace">${id}</div>
  <div class="box"><div class="kv"><div>Question</div><div>${esc(t.ask)}</div><div>What is going on</div><div>${esc(t.hidden)}</div>
  <div>Right answer</div><div><b>${esc(d.expect)}</b></div><div>Agent can see</div><div><code>${d.files.join("  ")||"meterctl tool (paged data server)"}</code></div></div>
  <details style="margin-top:10px"><summary class="mut" style="cursor:pointer">Prompt the agent gets</summary><pre>${esc(d.instruction)}</pre></details></div>
  <h2>Attempts by model</h2><div class="note">A green tick passed, a red cross failed. Click one to open its trace.</div><div class="box">${rows}</div><div id="trace"></div>`;
  if(sel!==undefined&&d.attempts[sel])traceView(d.attempts[sel],t);
  else scrollTo(0,0);
}
function traceView(a,t){
  const steps=a.steps.map((s,i)=>{
    if(s.k==="a")return `<div class="step"><div class="lab">Step ${Math.floor(i/2)+1} &middot; model</div>${s.text?`<div class="txt">${esc(s.text)}</div>`:""}${s.cmd?`<pre>${esc(s.cmd)}</pre>`:""}</div>`;
    return `<div class="step o"><div class="lab">Output${s.rc!=null?" (exit "+s.rc+")":""}</div><pre>${esc(s.text)}</pre></div>`}).join("");
  const el=$("#trace");
  el.innerHTML=`<div class="trace"><div class="thead"><b>${a.model}</b><span class="badge ${a.pass?"p":""}">${a.pass?"PASS":"FAIL"}</span>
    <span>Answer: <b>${esc(a.answer)}</b></span><span class="mut">expected ${esc(t&&IDX.tasks.find(x=>x.id===t.id)?CACHE[t.id].expect:"")}</span>
    <span class="mut">${a.calls??"?"} model calls${a.cost?" &middot; $"+a.cost.toFixed(3):""} &middot; run ${a.run}</span></div>
    <div class="thead" style="background:#fafaf9"><span><b>${esc(a.why)}</b>${t.kind==="silent"&&!a.pass?(a.noticed?" (the answer mentions the problem)":""):""}</span></div>
    <div class="tbody">${steps}</div></div>`;
  el.scrollIntoView({behavior:"smooth",block:"start"});
}
addEventListener("hashchange",route); route();
</script></body></html>
"""

if __name__ == "__main__":
    main()
