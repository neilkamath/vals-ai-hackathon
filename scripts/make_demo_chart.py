"""Demo chart: what the meter recorded vs what was really consumed, per local day, for one energy task.

Run:  uv run --with matplotlib scripts/make_demo_chart.py [spec-name]   (default: energy_meter_degraded_month)
Rebuilds the task's world from its spec (deterministic), so it needs no results data.
"""
import sys
import tomllib
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from generator.core import change_events  # noqa: E402
from generator.core.meter_events import FMT, to_utc  # noqa: E402
from generator.core.recorder import Recorder  # noqa: E402
from generator.worlds.meter import TZ, MeterWorld  # noqa: E402


def main(name="energy_meter_degraded_month"):
    spec = tomllib.loads((ROOT / "generator/specs" / f"{name}.toml").read_text())
    wp = dict(spec["world_params"])
    for k in ("window_start", "window_end"):
        wp[k] = spec[k]
    world = MeterWorld(spec["seed"], wp)
    events = [change_events.build_event(e) for e in spec["change_events"]]
    tables, _ = Recorder(world, events, spec["seed"]).record()

    days, rec, true = [], [], []
    d = datetime(2026, 11, 23)
    while d <= datetime(2026, 11, 30):
        lo, hi = to_utc(d.strftime(FMT), TZ), to_utc((d + timedelta(days=1)).strftime(FMT), TZ)
        days.append(d.strftime("%a %d"))
        rec.append(world.compute(tables, events, bounds=(lo, hi)))
        true.append(sum(r["kwh"] for r in world.tables["readings"] if lo < r["utc"] <= hi))
        d += timedelta(days=1)

    fig, ax = plt.subplots(figsize=(10, 5.8))
    x = list(range(len(days)))
    ax.bar([i - 0.2 for i in x], true, 0.4, label="What the site really used", color="#9aa5b1")
    ax.bar([i + 0.2 for i in x], rec, 0.4, label="What the meter recorded (after every documented fix)", color="#d1495b")
    low = min(x, key=lambda i: rec[i] - true[i])
    closure = [i for i, dd in enumerate(days) if dd.split()[1] in ("26", "27", "28", "29")]
    others = [rec[i] for i in closure if i != low]
    ax.axvspan(min(closure) - 0.5, max(closure) + 0.5, color="#f4e8c1", alpha=0.5, zorder=0)
    ax.text(sum(closure) / len(closure), max(true) * 1.12, "holiday closure (README: 'reduced load only')", ha="center", fontsize=11)
    ax.annotate(f"meter recorded {rec[low]:.0f} kWh\nthe other closure days: about {sum(others) / len(others):.0f}",
                (low + 0.2, rec[low] + 4), xytext=(low + 0.55, 455), arrowprops={"arrowstyle": "->"}, fontsize=11)
    ax.set_ylim(0, max(true) * 1.22)
    ax.set_xticks(x)
    ax.set_xticklabels(days)
    ax.set_ylabel("kWh per local day")
    ax.set_title("A plausible month total hides one dead day", pad=14)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=2, fontsize=10, frameon=False)
    fig.tight_layout()
    out = ROOT / "results" / "curated" / "demo_daily_kwh.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=160)
    print("wrote", out)
    print("recorded:", dict(zip(days, [round(v) for v in rec])))
    print("true:    ", dict(zip(days, [round(v) for v in true])))


if __name__ == "__main__":
    main(*sys.argv[1:])
