"""Build the results tables and charts from results/attempts.jsonl (written by scripts/collect_results.py).

Run:  uv run --with pandas --with matplotlib --with seaborn scripts/make_report.py

Outputs go to results/curated/: CSV tables and PNG charts. Reader labels for failed "decline" attempts are read from
results/curated/failure_labels.json when present (key = first 8 chars of the run id + "|" + task).

Headline metric: the energy reliability score = mean of two equal-weight modes,
  (a) fix-and-compute: mean of the four fixable categories (scaling & units, time, meter continuity, streamed intake), and
  (b) judge-reliability: the silent-sensor-fault category, where the right output is to decline.
A task passes if the agent gives the correct number or correctly declines. Each category is the mean of its tasks' pass
rates. Models not run on a category are scored on the categories they cover. Controls and ablation tasks are reported
separately and never enter the headline.
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "curated"
OUT.mkdir(parents=True, exist_ok=True)

MODEL = {"anthropic/claude-opus-5-5": "Opus 5.5", "anthropic/claude-sonnet-5-5": "Sonnet 5.5", "openai/gpt-5.4": "gpt-5.4",
         "openai/gpt-5.2": "gpt-5.2", "anthropic/claude-haiku-4-5": "Haiku 4.5", "anthropic/claude-fable-5-2": "Fable 5.2"}
ORDER = ["Haiku 4.5", "gpt-5.2", "gpt-5.4", "Sonnet 5.5", "Opus 5.5"]
FRONTIER = ["gpt-5.4", "Sonnet 5.5", "Opus 5.5"]

E = "energy-meter-"
S = "energy-stream-"
CATEGORIES = {  # headline categories (equal weights)
    "Scaling & units": [E + "rollover-only", E + "rollover-ct"],
    "Time & calendar": [E + "november"],
    "Meter continuity": [E + "swap-november", E + "swap-november-s2"],
    "Data intake (streamed)": [S + "november"],
    "Silent sensor faults (decline)": [E + "degraded-month", E + "degraded-month-s2", E + "degraded-month-s3", E + "degraded-30",
                                       E + "degraded-60", E + "closure-swap-degraded", E + "stuck-day", E + "frozen-tail",
                                       S + "gap", S + "degraded"],
}
CONTROLS = [E + "october-clean", E + "closure-day", S + "clean-week", "exp-checkout-plain", "exp-checkout-clean-window"]
EXPERIMENT = ["exp-checkout-stacked", "exp-checkout-bots", "exp-checkout-gauntlet", "exp-checkout-srm", "exp-checkout-srm-hidden",
              "exp-checkout-closure-reassign", "exp-checkout-closure-stack"]
ABLATION = {
    "Hint (nudge to check data quality)": [("degraded sensor", E + "degraded-month", E + "degraded-month-hint"),
                                            ("stacked fixes", "exp-checkout-stacked", "exp-checkout-stacked-hint"),
                                            ("bot traffic", "exp-checkout-bots", "exp-checkout-bots-hint")],
    "Wording (explicit vs neutral decline rule)": [("degraded sensor", E + "degraded-month", E + "degraded-month-neutral"),
                                                   ("hidden skew", "exp-checkout-srm-hidden", "exp-checkout-srm-hidden-neutral")],
}
SEVERITY = [("1%", E + "degraded-month"), ("30%", E + "degraded-30"), ("60%", E + "degraded-60")]
TRAP_LADDER = [(1, E + "rollover-only"), (2, E + "rollover-ct"), (3, E + "november"), (4, E + "swap-november")]
DECLINE_TASKS = set(CATEGORIES["Silent sensor faults (decline)"]) | {"exp-checkout-srm", "exp-checkout-srm-hidden",
                                                                      "exp-checkout-closure-reassign", "exp-checkout-closure-stack"}


def load():
    rows = [json.loads(line) for line in open(ROOT / "results" / "attempts.jsonl")]
    df = pd.DataFrame(rows)
    df["model"] = df["model"].map(MODEL)
    df["cost"] = df["cost"].fillna(0.0)
    labels_path = OUT / "failure_labels.json"
    labels = {x["key"]: x["label"] for x in json.load(open(labels_path))} if labels_path.exists() else {}
    df["key"] = df["run_id"].str[:8] + "|" + df["task"]
    df["reader_label"] = df["key"].map(labels)
    return df


def se(p, n):
    return float(np.sqrt(p * (1 - p) / n)) if n else float("nan")


def task_rate(df, task, model):
    d = df[(df.task == task) & (df.model == model)]
    return (d.reward.mean(), len(d)) if len(d) else (np.nan, 0)


FIX_CATS = [c for c in CATEGORIES if not c.startswith("Silent")]
JUDGE_CAT = "Silent sensor faults (decline)"


def cat_score(df, model, tasks, rng=None):
    rates = []
    if rng is not None:  # bootstrap over tasks as well as attempts
        tasks = list(rng.choice(tasks, size=len(tasks), replace=True))
    for t in tasks:
        d = df[(df.task == t) & (df.model == model)]
        if len(d):
            r = d.reward.to_numpy()
            if rng is not None:
                r = rng.choice(r, size=len(r), replace=True)
            rates.append(r.mean())
    return float(np.mean(rates)) if rates else np.nan


def modes(df, model, rng=None):
    """-> (fix_and_compute, judge_reliability, headline)."""
    fix = [cat_score(df, model, CATEGORIES[c], rng) for c in FIX_CATS]
    fix = [x for x in fix if not np.isnan(x)]
    a = float(np.mean(fix)) if fix else np.nan
    b = cat_score(df, model, CATEGORIES[JUDGE_CAT], rng)
    return a, b, float(np.mean([a, b])) if not (np.isnan(a) or np.isnan(b)) else np.nan


def headline(df, model, rng=None):
    return modes(df, model, rng)[2]


def main():
    df = load()
    pub = df[df.stage != "4-private"].copy()
    rng = np.random.default_rng(0)

    # ---- category scores and headline with bootstrap CI --------------------------------------------------------
    cat_rows, head_rows = [], []
    for m in ORDER:
        row = {"model": m}
        for c, tasks in CATEGORIES.items():
            d = pub[(pub.model == m) & (pub.task.isin(tasks))]
            row[c] = d.groupby("task").reward.mean().mean() if len(d) else np.nan
        cat_rows.append(row)
        a, b, h = modes(pub, m)
        boots = [headline(pub, m, rng) for _ in range(1000)] if not np.isnan(h) else []
        lo, hi = (np.nanpercentile(boots, [2.5, 97.5]) if boots else (np.nan, np.nan))
        ncat = int(sum(not np.isnan(row[c]) for c in CATEGORIES))
        head_rows.append({"model": m, "energy_reliability_score": h, "ci_low": lo, "ci_high": hi,
                          "fix_and_compute": a, "judge_reliability": b, "categories_covered": ncat})
    cats = pd.DataFrame(cat_rows).set_index("model")
    head = pd.DataFrame(head_rows).set_index("model")
    cats.round(3).to_csv(OUT / "category_scores.csv")

    # ---- leaderboard ----------------------------------------------------------------------------------------
    lb = []
    for m in ORDER:
        d = pub[pub.model == m]
        ans = d[~d.task.isin(DECLINE_TASKS) & ~d.task.isin(CONTROLS)]
        dec = d[d.task.isin(DECLINE_TASKS)]
        ctl = d[d.task.isin(CONTROLS)]
        lb.append({"model": m, "attempts": len(d), "energy_reliability_score": head.loc[m, "energy_reliability_score"],
                   "ci_low": head.loc[m, "ci_low"], "ci_high": head.loc[m, "ci_high"],
                   "fix_and_compute": head.loc[m, "fix_and_compute"], "judge_reliability": head.loc[m, "judge_reliability"],
                   "categories_covered": head.loc[m, "categories_covered"],
                   "answerable_pass": ans.reward.mean() if len(ans) else np.nan, "decline_pass": dec.reward.mean() if len(dec) else np.nan,
                   "control_pass": ctl.reward.mean() if len(ctl) else np.nan, "avg_cost_per_attempt_usd": d.cost.mean(),
                   "avg_model_calls": d.calls.dropna().mean(), "total_cost_usd": d.cost.sum()})
    lb = pd.DataFrame(lb).set_index("model")
    lb.round(3).to_csv(OUT / "leaderboard.csv")

    # ---- per task table -------------------------------------------------------------------------------------
    pt = pub.groupby(["task", "model"]).reward.agg(["sum", "count"]).reset_index()
    pt["pass_rate"] = pt["sum"] / pt["count"]
    pt.pivot(index="task", columns="model", values="pass_rate").reindex(columns=ORDER).round(2).to_csv(OUT / "per_task_pass_rate.csv")

    # ---- ablations (pooled over frontier models) -------------------------------------------------------------
    abl = []
    fr = pub[pub.model.isin(FRONTIER)]
    for group, pairs in ABLATION.items():
        for name, base, var in pairs:
            for label, t in (("plain", base), ("variant", var)):
                d = fr[fr.task == t]
                if len(d):
                    p = d.reward.mean()
                    abl.append({"group": group, "case": name, "arm": label, "task": t, "pass_rate": p, "se": se(p, len(d)), "n": len(d)})
    for name, t in SEVERITY:
        d = fr[fr.task == t]
        if len(d):
            p = d.reward.mean()
            abl.append({"group": "Sensor severity (reads x% of true)", "case": name, "arm": name, "task": t, "pass_rate": p, "se": se(p, len(d)), "n": len(d)})
    abl = pd.DataFrame(abl)
    abl.round(3).to_csv(OUT / "ablations.csv", index=False)

    # ---- detect vs act (decline attempts, reader labels when present) -----------------------------------------
    dec_all = pub[pub.task.isin(DECLINE_TASKS)].copy()
    if dec_all.reader_label.notna().any():
        # attempts whose final answer text could not be read are excluded and counted separately
        unreadable = (dec_all.reward == 0) & (dec_all.reader_label.fillna("other") == "other")
        dec = dec_all[~unreadable].copy()
        dec["noticed"] = (dec.reward == 1) | dec.reader_label.isin(["noticed_rationalized", "noticed_but_computed_anyway"])
        n_unread = unreadable.groupby(dec_all.model).sum()
    else:
        dec = dec_all.copy()
        dec["noticed"] = (dec.reward == 1) | dec.failure.eq("detected_but_reported_number")
        n_unread = pd.Series(0, index=ORDER)
    da = dec.groupby("model").agg(n=("reward", "size"), noticed=("noticed", "mean"), acted=("reward", "mean")).reindex(ORDER).dropna()
    da["detect_act_gap"] = da["noticed"] - da["acted"]
    da["unreadable_excluded"] = n_unread.reindex(da.index).fillna(0).astype(int)
    da.round(3).to_csv(OUT / "detect_vs_act.csv")
    fm = dec_all[dec_all.reward == 0].groupby(["model", dec_all[dec_all.reward == 0].reader_label.fillna(dec_all[dec_all.reward == 0].failure)]).size().unstack(fill_value=0).reindex(ORDER).dropna(how="all")
    fm.to_csv(OUT / "failure_modes_decline.csv")

    # ---- over-abstention on answerable attempts -------------------------------------------------------------
    answ = pub[~pub.task.isin(DECLINE_TASKS)]
    oa = answ.groupby("model").apply(lambda g: g.details.apply(lambda d: bool(d.get("abstained"))).mean(), include_groups=False).reindex(ORDER).dropna()
    oa.rename("over_abstention_rate").round(3).to_csv(OUT / "over_abstention.csv")

    # ---- private held-out seeds vs their public counterparts ------------------------------------------------
    priv = df[df.stage == "4-private"]
    if len(priv):
        mapping = {E + "degraded-month-p1": E + "degraded-month", E + "degraded-month-p2": E + "degraded-month",
                   E + "closure-swap-degraded-p1": E + "closure-swap-degraded", E + "swap-november-p1": E + "swap-november"}
        pr = []
        for m in FRONTIER:
            p = priv[priv.model == m]
            pu = pub[(pub.model == m) & pub.task.isin(set(mapping.values()))]
            pr.append({"model": m, "private_pass": p.reward.mean(), "private_n": len(p), "public_pass": pu.reward.mean(), "public_n": len(pu)})
        pd.DataFrame(pr).round(3).to_csv(OUT / "private_vs_public.csv", index=False)

    # =================================== charts ==================================================================
    sns.set_theme(style="whitegrid", context="talk")
    colors = dict(zip(ORDER, sns.color_palette("viridis", len(ORDER))))

    # 1. Pareto: reliability vs cost
    fig, ax = plt.subplots(figsize=(8, 5.5))
    for m in ORDER:
        if m in lb.index and not np.isnan(lb.loc[m, "energy_reliability_score"]):
            x, y = lb.loc[m, "avg_cost_per_attempt_usd"], lb.loc[m, "energy_reliability_score"]
            ax.errorbar(x, y, yerr=[[y - lb.loc[m, "ci_low"]], [lb.loc[m, "ci_high"] - y]], fmt="o", color=colors[m], capsize=4, ms=10)
            ax.annotate(m, (x, y), textcoords="offset points", xytext=(8, 6), fontsize=12)
    ax.set_xscale("log")
    ax.set_xlabel("Cost per attempt (USD, log scale)")
    ax.set_ylabel("Energy reliability score")
    ax.set_ylim(0, 1)
    ax.set_title("Reliability vs cost (95% bootstrap CI)")
    fig.tight_layout()
    fig.savefig(OUT / "fig1_reliability_vs_cost.png", dpi=160)
    plt.close(fig)

    # 2. Category heat map
    fig, ax = plt.subplots(figsize=(10, 4.8))
    sns.heatmap(cats.dropna(how="all") * 100, annot=True, fmt=".0f", cmap="RdYlGn", vmin=0, vmax=100, cbar_kws={"label": "pass rate (%)"}, ax=ax)
    ax.set_ylabel("")
    ax.set_title("Pass rate by failure category")
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    fig.tight_layout()
    fig.savefig(OUT / "fig2_category_heatmap.png", dpi=160)
    plt.close(fig)

    # 3. Answerable vs decline
    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(lb))
    w = 0.38
    for i, (col, lab) in enumerate((("answerable_pass", "Fix and compute"), ("decline_pass", "Judge reliability (decline)"))):
        ns = [len(pub[(pub.model == m) & (pub.task.isin(DECLINE_TASKS) if col == "decline_pass" else ~pub.task.isin(DECLINE_TASKS | set(CONTROLS)))]) for m in lb.index]
        ses = [se(v, n) if n else 0 for v, n in zip(lb[col].fillna(0), ns)]
        ax.bar(x + (i - 0.5) * w, lb[col].fillna(0), w, yerr=ses, capsize=3, label=lab)
    ax.set_xticks(x)
    ax.set_xticklabels(lb.index, rotation=15)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Pass rate")
    ax.legend(loc="upper left", fontsize=11)
    ax.set_title("Mechanics vs judgment")
    fig.tight_layout()
    fig.savefig(OUT / "fig3_answerable_vs_decline.png", dpi=160)
    plt.close(fig)

    # 4. Detect vs act
    if len(da):
        fig, ax = plt.subplots(figsize=(8, 5))
        x = np.arange(len(da))
        ax.bar(x - 0.2, da["noticed"], 0.4, label="Noticed the problem")
        ax.bar(x + 0.2, da["acted"], 0.4, label="Acted (declined)")
        ax.set_xticks(x)
        ax.set_xticklabels(da.index, rotation=15)
        ax.set_ylim(0, 1.05)
        ax.set_ylabel("Share of decline attempts")
        ax.legend(fontsize=11)
        ax.set_title("Noticing is not acting")
        fig.tight_layout()
        fig.savefig(OUT / "fig4_detect_vs_act.png", dpi=160)
        plt.close(fig)

    # 5. Ablations
    if len(abl):
        groups = list(abl.group.unique())
        fig, axes = plt.subplots(1, len(groups), figsize=(5.2 * len(groups), 5), sharey=True)
        for ax, g in zip(np.atleast_1d(axes), groups):
            d = abl[abl.group == g]
            if g.startswith("Sensor"):
                ax.bar(d.arm, d.pass_rate, yerr=d.se, capsize=4, color=sns.color_palette("mako", len(d)))
            else:
                cases = list(d.case.unique())
                xs = np.arange(len(cases))
                for i, arm in enumerate(("plain", "variant")):
                    dd = d[d.arm == arm].set_index("case").reindex(cases)
                    ax.bar(xs + (i - 0.5) * 0.38, dd.pass_rate, 0.38, yerr=dd.se, capsize=3, label=arm)
                ax.set_xticks(xs)
                ax.set_xticklabels(cases, rotation=15)
                ax.legend(fontsize=10)
            ax.set_title(g, fontsize=12)
            ax.set_ylim(0, 1.05)
        np.atleast_1d(axes)[0].set_ylabel("Pass rate (frontier models pooled, +/-1 SE)")
        fig.tight_layout()
        fig.savefig(OUT / "fig5_ablations.png", dpi=160)
        plt.close(fig)

    # 6. Trap ladder
    fig, ax = plt.subplots(figsize=(7.5, 5))
    for m in ORDER:
        ys = [task_rate(pub, t, m)[0] for _, t in TRAP_LADDER]
        if not all(np.isnan(ys)):
            ax.plot([n for n, _ in TRAP_LADDER], ys, "o-", label=m, color=colors[m])
    ax.set_xticks([1, 2, 3, 4])
    ax.set_xlabel("Recording problems to fix")
    ax.set_ylabel("Pass rate")
    ax.set_ylim(-0.05, 1.05)
    ax.legend(fontsize=10)
    ax.set_title("Difficulty ladder (answerable energy tasks)")
    fig.tight_layout()
    fig.savefig(OUT / "fig6_trap_ladder.png", dpi=160)
    plt.close(fig)

    # 7. Calls per attempt, pass vs fail
    d = pub[pub.calls.notna() & pub.model.isin(ORDER)].copy()
    d["outcome"] = np.where(d.reward == 1, "pass", "fail")
    fig, ax = plt.subplots(figsize=(8.5, 5))
    sns.boxplot(data=d, x="model", y="calls", hue="outcome", order=[m for m in ORDER if m in set(d.model)], ax=ax)
    ax.set_ylabel("Model calls per attempt")
    ax.set_xlabel("")
    ax.set_title("Failures are not step-limit truncation")
    fig.tight_layout()
    fig.savefig(OUT / "fig7_calls_per_attempt.png", dpi=160)
    plt.close(fig)

    print(lb.round(3).to_string())
    print()
    print(cats.round(2).to_string())
    print("\nwrote:", ", ".join(sorted(p.name for p in OUT.iterdir())))


if __name__ == "__main__":
    main()
