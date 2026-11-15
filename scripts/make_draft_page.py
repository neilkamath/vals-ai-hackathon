"""Build a single self-contained HTML page (leaderboard + charts) from results/curated for local viewing.

Run:  python3 scripts/make_draft_page.py     ->  results/draft/index.html  (git-ignored)
"""
import base64
import csv
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CUR = ROOT / "results" / "curated"
OUT = ROOT / "results" / "draft"
OUT.mkdir(parents=True, exist_ok=True)


def rows(name):
    return list(csv.DictReader(open(CUR / name)))


def f(x, nd=2):
    try:
        return f"{float(x):.{nd}f}"
    except (TypeError, ValueError):
        return "-"


def pct(x):
    try:
        return f"{float(x) * 100:.0f}%"
    except (TypeError, ValueError):
        return "-"


def img(name, caption):
    b = base64.b64encode((CUR / name).read_bytes()).decode()
    return f'<figure><img src="data:image/png;base64,{b}" alt="{html.escape(caption)}"><figcaption>{html.escape(caption)}</figcaption></figure>'


lb = sorted(rows("leaderboard.csv"), key=lambda r: -float(r["energy_reliability_score"] or 0))
da = {r["model"]: r for r in rows("detect_vs_act.csv")}
pv = rows("private_vs_public.csv") if (CUR / "private_vs_public.csv").exists() else []

trs = ""
for i, r in enumerate(lb, 1):
    ci = f"{f(r['ci_low'])} to {f(r['ci_high'])}"
    trs += (f"<tr><td>{i}</td><td><b>{html.escape(r['model'])}</b></td><td><b>{f(r['energy_reliability_score'])}</b> <span class=m>({ci})</span></td>"
            f"<td>{pct(r['fix_and_compute'])}</td><td>{pct(r['judge_reliability'])}</td><td>{pct(r['control_pass'])}</td>"
            f"<td>${f(r['avg_cost_per_attempt_usd'], 3)}</td><td>{f(r['avg_model_calls'], 1)}</td><td>{r['attempts']}</td></tr>")

dtr = ""
for m, r in da.items():
    dtr += (f"<tr><td>{html.escape(m)}</td><td>{r['n']}</td><td>{pct(r['noticed'])}</td><td>{pct(r['acted'])}</td>"
            f"<td>{r['unreadable_excluded']}</td></tr>")
ptr = "".join(f"<tr><td>{html.escape(r['model'])}</td><td>{pct(r['private_pass'])} ({r['private_n']})</td>"
              f"<td>{pct(r['public_pass'])} ({r['public_n']})</td></tr>" for r in pv)

page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Draft results</title><style>
:root{{--bg:#fff;--fg:#1d2430;--mut:#6b7280;--line:#e5e7eb;--card:#f8fafc}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0f1419;--fg:#e6e9ee;--mut:#9aa4b2;--line:#273041;--card:#171e28}}}}
body{{background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,sans-serif;margin:0}}
main{{max-width:980px;margin:0 auto;padding:24px 16px 64px}}
h1{{font-size:28px;margin:0 0 4px}} h2{{font-size:20px;margin:36px 0 8px}} .banner{{background:#fff4cc;color:#5c4a00;padding:8px 12px;border-radius:8px;font-size:14px;margin:12px 0}}
table{{border-collapse:collapse;width:100%;font-size:15px;background:var(--card);border-radius:8px;overflow:hidden}}
th,td{{padding:8px 10px;text-align:left;border-bottom:1px solid var(--line)}} th{{font-weight:600;font-size:13px;color:var(--mut)}}
.m{{color:var(--mut);font-size:13px}} figure{{margin:16px 0;background:#fff;border-radius:10px;padding:8px;border:1px solid var(--line)}}
img{{max-width:100%;height:auto;display:block;margin:auto}} figcaption{{font-size:13px;color:#555;text-align:center;padding-top:6px}}
.note{{color:var(--mut);font-size:14px}} .wrap{{overflow-x:auto}}
</style></head><body><main>
<h1>Do energy agents know when their number is wrong?</h1>
<div class="banner">DRAFT, local only. Numbers are from small samples (mostly 1 to 3 attempts per task and model); treat them as signals.</div>
<p class="note">Synthetic hourly meter data for a commercial site, plus a second domain of A/B test exports. Tasks are either
answerable (fix the data, report a number) or require declining (cannot_determine) because of an undocumented fault.
Reliability score = mean of two equal-weight modes: fix-and-compute and judge-reliability.</p>

<h2>Leaderboard</h2><div class="wrap"><table><tr><th>#</th><th>Model</th><th>Reliability score (95% CI)</th><th>Fix and compute</th><th>Judge reliability</th>
<th>Clean controls</th><th>Cost / attempt</th><th>Avg model calls</th><th>Attempts</th></tr>{trs}</table></div>
<p class="note">Haiku 4.5 and gpt-5.2 were run once per task and not on the streamed category, so their intervals are wide. Costs are measured from agent logs.</p>

{img('fig1_reliability_vs_cost.png','Reliability score against cost per attempt (95% bootstrap interval over tasks and attempts)')}
{img('fig2_category_heatmap.png','Pass rate by failure category: fixable problems saturate, silent faults do not')}
{img('fig3_answerable_vs_decline.png','Fix-and-compute against judge-reliability pass rates (all tasks, error bars are +/-1 SE)')}

<h2>Noticing is not acting</h2>
<div class="wrap"><table><tr><th>Model</th><th>Readable decline attempts</th><th>Noticed the problem</th><th>Declined</th><th>Unreadable (excluded)</th></tr>{dtr}</table></div>
{img('fig4_detect_vs_act.png','Share of decline attempts where the model noticed the problem versus declined')}
{img('demo_daily_kwh.png','The demo task: one holiday-closure day under-reads (3 kWh recorded vs about 296 on the other closure days)')}

<h2>Ablations and ladders</h2>
{img('fig5_ablations.png','Hint, wording and sensor-severity ablations (frontier models pooled)')}
{img('fig6_trap_ladder.png','Pass rate against number of recording problems to fix (answerable energy tasks)')}
{img('fig7_calls_per_attempt.png','Model calls per attempt: failures are not caused by running out of steps')}

<h2>Private held-out seeds</h2>
<div class="wrap"><table><tr><th>Model</th><th>Private seeds (n)</th><th>Public analogs (n)</th></tr>{ptr}</table></div>
<p class="note">The private tasks are not in the repository. Similar pass rates suggest results do not depend on the public seeds.</p>
</main></body></html>"""
(OUT / "index.html").write_text(page)
print("wrote", OUT / "index.html", f"({len(page) // 1024} KB)")
