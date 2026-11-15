"""Build the results tables and charts for the 13-task energy core from results/attempts.jsonl.

Run:  uv run --with pandas --with matplotlib --with seaborn scripts/make_report.py

Inputs : results/attempts.jsonl (written by scripts/collect_results.py; local, git-ignored)
         results/curated/failure_labels.json (reader labels for failed decline attempts; key = run id[:8] + "|" + task)
Outputs: results/curated/*.csv and *.png

Accuracy = mean over the 13 core tasks of each task's pass rate (a task passes when the agent gives the correct number,
or correctly declines on a decline task). Standard errors are over tasks. Private held-out tasks are reported separately.
"""
import json
from pathlib import Path

import matplotlib
import matplotlib.ticker  # noqa: F401

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "curated"
OUT.mkdir(parents=True, exist_ok=True)

E, S = "energy-meter-", "energy-stream-"
ANSWERABLE = [E + "rollover-only", E + "rollover-ct", E + "november", E + "swap-november", S + "november"]
CONTROLS = [E + "october-clean", E + "closure-day"]
DECLINE = [E + "degraded-month", E + "degraded-month-s2", E + "degraded-month-s3", E + "closure-swap-degraded", S + "degraded",
           E + "frozen-tail"]
CORE = ANSWERABLE + CONTROLS + DECLINE
CATEGORIES = {
    "Scaling & units": [E + "rollover-only", E + "rollover-ct"],
    "Time & calendar": [E + "november"],
    "Meter continuity": [E + "swap-november"],
    "Data intake (streamed)": [S + "november"],
    "Silent sensor faults (decline)": DECLINE,
}
LADDER = [(1, E + "rollover-only"), (2, E + "rollover-ct"), (3, E + "november"), (4, E + "swap-november")]
PRIVATE_MAP = {E + "degraded-month-p1": E + "degraded-month", E + "degraded-month-p2": E + "degraded-month",
               E + "closure-swap-degraded-p1": E + "closure-swap-degraded", E + "swap-november-p1": E + "swap-november"}
SKIP_STAGES = ("5-stacked", "fable-probe")

MODEL = {"anthropic/claude-opus-5-5": "Opus 5.5", "anthropic/claude-sonnet-5-5": "Sonnet 5.5", "openai/gpt-5.4": "gpt-5.4",
         "openai/gpt-5.2": "gpt-5.2", "anthropic/claude-haiku-4-5": "Haiku 4.5",
         "anthropic/claude-fable-5-2": "Fable 5.2", "openai/gpt-5.5": "gpt-5.5"}
ORDER = ["Haiku 4.5", "gpt-5.2", "gpt-5.4", "gpt-5.5", "Sonnet 5.5", "Opus 5.5", "Fable 5.2"]
FRONTIER = ["gpt-5.5", "Sonnet 5.5", "Opus 5.5", "Fable 5.2"]
LAB = {"Haiku 4.5": "Anthropic", "Sonnet 5.5": "Anthropic", "Opus 5.5": "Anthropic", "gpt-5.2": "OpenAI", "gpt-5.4": "OpenAI",
       "Fable 5.2": "Anthropic", "gpt-5.5": "OpenAI"}
LAB_COLOR = {"Anthropic": "#c4623a", "OpenAI": "#2f8f6f"}
MARK = {"Haiku 4.5": "o", "gpt-5.2": "o", "Sonnet 5.5": "s", "gpt-5.4": "s", "Opus 5.5": "D", "Fable 5.2": "D", "gpt-5.5": "D"}
AUTO = {"detected_but_reported_number": "noticed_but_computed_anyway", "never_detected": "never_noticed"}


def load():
    df = pd.DataFrame([json.loads(line) for line in open(ROOT / "results" / "attempts.jsonl")])
    df = df[df.model.isin(MODEL) & ~df.stage.isin(SKIP_STAGES)].copy()
    df["model"] = df.model.map(MODEL)
    df["cost"] = df.cost.fillna(0.0)
    dur = {}
    for rid in df.run_id.unique():
        f = ROOT / "results" / "raw" / f"{rid}.json"
        if f.exists():
            try:
                for task, ev in json.load(open(f))["evaluation_results"].items():
                    dur[(rid, task)] = ev["task_breakdown"]["agent_run_duration"]
            except Exception:
                pass
    df["duration_s"] = [dur.get((r, t), np.nan) for r, t in zip(df.run_id, df.task)]
    lp = OUT / "failure_labels.json"
    labels = {x["key"]: x["label"] for x in json.load(open(lp))} if lp.exists() else {}
    df["key"] = df.run_id.str[:8] + "|" + df.task
    df["label"] = df.key.map(labels).fillna(df.failure.map(AUTO))  # reader label, else the automatic one
    return df


def task_rates(df, model, tasks):
    """Per-task pass rate (mean over that task's attempts) for the tasks the model ran."""
    return df[(df.model == model) & df.task.isin(tasks)].groupby("task").reward.mean()


def mean_se(r):
    if len(r) == 0:
        return np.nan, np.nan
    return r.mean(), (r.std(ddof=1) / np.sqrt(len(r)) if len(r) > 1 else np.nan)


def main():
    df_all = load()
    pub = df_all[(df_all.stage != "4-private") & df_all.task.isin(CORE)].copy()

    # ---- leaderboard ---------------------------------------------------------------------------------------
    lb = []
    for m in ORDER:
        d = pub[pub.model == m]
        acc, se = mean_se(task_rates(pub, m, CORE))
        lb.append({"model": m, "accuracy": acc, "se": se, "fixable": task_rates(pub, m, ANSWERABLE).mean(),
                   "decline": task_rates(pub, m, DECLINE).mean(), "controls": task_rates(pub, m, CONTROLS).mean(),
                   "tasks_covered": d.task.nunique(), "attempts": len(d), "avg_cost_per_attempt_usd": d.cost.mean(),
                   "avg_model_calls": d.calls.dropna().mean(), "avg_duration_s": d.duration_s.mean(), "total_cost_usd": d.cost.sum()})
    lb = pd.DataFrame(lb).set_index("model")
    lb.round(3).to_csv(OUT / "leaderboard.csv")

    # ---- categories, per-task table, over-abstention ---------------------------------------------------------
    cats = pd.DataFrame({m: {c: task_rates(pub, m, ts).mean() for c, ts in CATEGORIES.items()} for m in ORDER}).T
    cats.round(3).to_csv(OUT / "category_scores.csv")
    pt = pub.groupby(["task", "model"]).reward.agg(["sum", "count"]).reset_index()
    pt["pass_rate"] = pt["sum"] / pt["count"]
    pt.pivot(index="task", columns="model", values="pass_rate").reindex(index=CORE, columns=ORDER).round(2).to_csv(OUT / "per_task_pass_rate.csv")
    ans = pub[pub.task.isin(ANSWERABLE + CONTROLS)]
    oa = ans.groupby("model").apply(lambda g: g.details.apply(lambda d: bool(d.get("abstained"))).mean(), include_groups=False)
    oa.reindex(ORDER).rename("over_abstention_rate").round(3).to_csv(OUT / "over_abstention.csv")

    # ---- noticing vs acting on decline tasks (unreadable answers excluded and counted) -----------------------
    dec = pub[pub.task.isin(DECLINE)].copy()
    unreadable = (dec.reward == 0) & dec.label.fillna("other").isin(["other"])
    readable = dec[~unreadable].copy()
    readable["noticed"] = (readable.reward == 1) | readable.label.isin(["noticed_rationalized", "noticed_but_computed_anyway"])
    da = readable.groupby("model").agg(readable_attempts=("reward", "size"), noticed=("noticed", "mean"), declined=("reward", "mean"))
    da["gap"] = da.noticed - da.declined
    da["unreadable_excluded"] = unreadable.groupby(dec.model).sum()
    da = da.reindex(ORDER).dropna(subset=["readable_attempts"])
    da.round(3).to_csv(OUT / "detect_vs_act.csv")
    dec[dec.reward == 0].groupby(["model", dec[dec.reward == 0].label.fillna("other")]).size().unstack(fill_value=0).reindex(ORDER).dropna(how="all").to_csv(OUT / "failure_modes_decline.csv")

    # ---- private held-out seeds vs their public counterparts ---------------------------------------------------
    priv = df_all[df_all.stage == "4-private"]
    rows = []
    for m in FRONTIER:
        p = priv[priv.model == m]
        pu = pub[(pub.model == m) & pub.task.isin(set(PRIVATE_MAP.values()))]
        rows.append({"model": m, "private_pass": p.reward.mean(), "private_attempts": len(p), "public_pass": pu.reward.mean(), "public_attempts": len(pu)})
    pd.DataFrame(rows).round(3).to_csv(OUT / "private_vs_public.csv", index=False)

    # =================================== charts =================================================================
    sns.set_theme(style="whitegrid", context="talk", rc={"axes.grid.axis": "y"})
    colors = {m: LAB_COLOR[LAB[m]] for m in ORDER}

    # 1. accuracy vs cost and vs time, with frontier
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.6))
    for ax, xc, xl, ticks, fmt in ((axes[0], "avg_cost_per_attempt_usd", "Cost per attempt (USD, log scale)", [0.06, 0.08, 0.10, 0.13], "${:.2f}"),
                                   (axes[1], "avg_duration_s", "Agent time per attempt (seconds, log scale)", [30, 40, 60, 100], "{:g}s")):
        pts = sorted((lb.loc[m, xc], lb.loc[m, "accuracy"], m) for m in ORDER if not np.isnan(lb.loc[m, "accuracy"]))
        front, best = [], -1
        for x_, y_, m in pts:
            if y_ > best:
                front.append((x_, y_))
                best = y_
        if len(front) > 1:
            fx, fy = zip(*front)
            ax.step(fx, fy, where="post", color="#888", lw=1.6, ls="--", zorder=1)
        for x_, y_, m in pts:
            se_ = lb.loc[m, "se"]
            ax.errorbar(x_, y_, yerr=0 if np.isnan(se_) else se_, fmt="none", ecolor=colors[m], alpha=0.5, capsize=4, zorder=2)
            ax.scatter(x_, y_, s=60 + 4 * lb.loc[m, "attempts"], marker=MARK[m], color=colors[m], edgecolor="white", linewidth=1.2, zorder=3)
            ax.annotate(m, (x_, y_), textcoords="offset points", xytext=(-10, 9) if m == "Sonnet 5.5" else (10, 8),
                        ha="right" if m == "Sonnet 5.5" else "left", fontsize=11)
        ax.set_xscale("log")
        ax.set_xticks(ticks)
        ax.set_xticklabels([fmt.format(t) for t in ticks])
        ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        ax.set_xlabel(xl, fontsize=12)
        ax.set_ylabel("Accuracy (13 core tasks)", fontsize=12)
        ax.set_ylim(-0.02, 1.0)
        ax.margins(x=0.15)
    handles = [plt.Line2D([], [], marker="o", ls="", color=c, label=l) for l, c in LAB_COLOR.items()]
    handles += [plt.Line2D([], [], color="#888", ls="--", label="Pareto frontier"), plt.Line2D([], [], marker="o", ls="", color="#bbb", label="marker size = attempts")]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, fontsize=11)
    fig.suptitle("Accuracy vs cost and time (error bars: +/-1 SE over tasks)", fontsize=15)
    fig.tight_layout(rect=(0, 0.07, 1, 0.95))
    fig.savefig(OUT / "fig1_accuracy_vs_cost.png", dpi=150)
    plt.close(fig)

    # 2. category heat map
    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    sns.heatmap(cats * 100, annot=True, fmt=".0f", cmap="RdYlGn", vmin=0, vmax=100, cbar_kws={"label": "pass rate (%)"}, ax=ax)
    ax.set_ylabel("")
    ax.set_title("Pass rate by failure category")
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    fig.tight_layout()
    fig.savefig(OUT / "fig2_category_heatmap.png", dpi=160)
    plt.close(fig)

    # 3. fixable vs decline vs controls
    fig, ax = plt.subplots(figsize=(9.5, 5))
    x = np.arange(len(ORDER))
    for i, (col, lab, tasks) in enumerate((("fixable", "Fix and compute (5 tasks)", ANSWERABLE), ("decline", "Judge reliability: decline (6 tasks)", DECLINE),
                                            ("controls", "Clean controls (2 tasks)", CONTROLS))):
        vals = [lb.loc[m, col] for m in ORDER]
        errs = [mean_se(task_rates(pub, m, tasks))[1] for m in ORDER]
        bars = ax.bar(x + (i - 1) * 0.27, np.nan_to_num(vals), 0.27, yerr=np.nan_to_num(errs), capsize=3, label=lab)
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.03, f"{b.get_height() * 100:.0f}%", ha="center", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(ORDER)
    ax.set_ylim(0, 1.2)
    ax.set_ylabel("Pass rate")
    ax.legend(fontsize=9, loc="upper left")
    ax.set_title("Mechanics vs judgment")
    fig.tight_layout()
    fig.savefig(OUT / "fig3_fix_vs_decline.png", dpi=160)
    plt.close(fig)

    # 4. noticing vs acting
    d4 = da.reindex(FRONTIER).dropna(subset=["readable_attempts"])
    if len(d4):
        fig, ax = plt.subplots(figsize=(8, 5))
        x = np.arange(len(d4))
        for i, (col, lab) in enumerate((("noticed", "Noticed the problem"), ("declined", "Declined (correct)"))):
            bars = ax.bar(x + (i - 0.5) * 0.4, d4[col], 0.4, label=lab)
            for b in bars:
                ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.03, f"{b.get_height() * 100:.0f}%", ha="center", fontsize=10)
        ax.set_xticks(x)
        ax.set_xticklabels([f"{m}\n(n={int(d4.loc[m, 'readable_attempts'])})" for m in d4.index])
        ax.set_ylim(0, 1.15)
        ax.set_ylabel("Share of readable decline attempts")
        ax.legend(fontsize=10)
        ax.set_title("Noticing is not acting")
        fig.tight_layout()
        fig.savefig(OUT / "fig4_noticing_vs_acting.png", dpi=160)
        plt.close(fig)

    # 5. difficulty ladder
    fig, ax = plt.subplots(figsize=(7.8, 5))
    styles = {"Haiku 4.5": ":", "gpt-5.2": "--", "gpt-5.4": "-.", "gpt-5.5": "-.", "Sonnet 5.5": "-", "Opus 5.5": "-", "Fable 5.2": "--"}
    for k, m in enumerate(ORDER):
        ys = [task_rates(pub, m, [t]).mean() for _, t in LADDER]
        ax.plot([n + (k - 2) * 0.045 for n, _ in LADDER], ys, "o", linestyle=styles[m], label=m, color=colors[m], lw=2, ms=8)
    ax.set_xticks([1, 2, 3, 4])
    ax.set_xlabel("Recording problems to fix")
    ax.set_ylabel("Pass rate")
    ax.set_ylim(-0.05, 1.05)
    ax.legend(fontsize=10, loc="center left")
    ax.set_title("Difficulty ladder (answerable energy tasks)")
    fig.tight_layout()
    fig.savefig(OUT / "fig5_difficulty_ladder.png", dpi=160)
    plt.close(fig)

    # 6. model calls per attempt
    d6 = pub[pub.calls.notna()].copy()
    d6["outcome"] = np.where(d6.reward == 1, "pass", "fail")
    fig, ax = plt.subplots(figsize=(8.5, 5))
    sns.boxplot(data=d6, x="model", y="calls", hue="outcome", order=ORDER, ax=ax)
    ax.set_ylabel("Model calls per attempt")
    ax.set_xlabel("")
    ax.set_title("Failures are not step-limit truncation")
    fig.tight_layout()
    fig.savefig(OUT / "fig6_calls_per_attempt.png", dpi=160)
    plt.close(fig)

    print(lb.round(3).to_string())
    print()
    print(cats.round(2).to_string())
    print()
    print(da.round(2).to_string())
    print()
    print(pd.read_csv(OUT / "private_vs_public.csv").to_string(index=False))


if __name__ == "__main__":
    main()
