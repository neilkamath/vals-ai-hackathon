"""Meter world: one building, one electricity meter with a cumulative register.

True tables: readings with the cumulative true energy (unbounded, UTC). Recorded files show a
register (possibly wrapped / scaled) with site-local timestamps. Truth: total kWh in a local window.
"""
import csv
import io
import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ..core.meter_events import FMT, local_str, to_utc
from ..core.world import World

TZ = "America/Los_Angeles"


class MeterWorld(World):
    def simulate(self):
        p, rng = self.params, self.rng
        z = ZoneInfo(TZ)
        start = datetime.fromisoformat(p["start_local"]).replace(tzinfo=z).astimezone(timezone.utc)
        end = datetime.fromisoformat(p["end_local"]).replace(tzinfo=z).astimezone(timezone.utc)
        reg, t = float(p["start_register"]), start
        rows = [{"meter_id": "M-1001", "utc": t.strftime(FMT), "ts": t.strftime(FMT), "register": reg, "kwh": 0.0}]
        closure = (p["closure_start"], p["closure_end"])  # local dates, inclusive
        while t < end:
            t += timedelta(hours=1)
            loc = t.astimezone(z)
            h, wd, day = loc.hour, loc.weekday(), loc.date().isoformat()
            load = 22 + 30 * max(0.0, math.sin(math.pi * (h - 6) / 14)) if 6 <= h <= 20 else 22
            load *= 0.7 if wd >= 5 else 1.0
            if closure[0] <= day <= closure[1]:
                load = 12.0  # holiday closure: reduced load only
            kwh = max(1.0, rng.gauss(load, 2.5))
            reg += kwh
            rows.append({"meter_id": "M-1001", "utc": t.strftime(FMT), "ts": t.strftime(FMT),
                         "register": reg, "kwh": kwh})
        return {"readings": rows}

    # -- helpers -------------------------------------------------------------
    def _utc_bounds(self):
        ws, we = self.params["window_start"], self.params["window_end"]
        if self.params.get("window_tz", "local") == "utc":
            return ws, we
        return to_utc(ws, TZ), to_utc(we, TZ)

    def _in_window(self, utc):
        lo, hi = self._utc_bounds()
        return lo < utc <= hi

    def truth(self):
        return round(sum(r["kwh"] for r in self.tables["readings"] if self._in_window(r["utc"])), 1)

    def render(self, tables):
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["meter_id", "ts", "register_kwh"])
        w.writerows([r["meter_id"], r["ts"], r["register"]] for r in tables["readings"])
        c = self.params
        readme = (
            "# Meter export\n\nHourly readings from the main electricity meter of one site.\n\n"
            "## readings.csv\n- `meter_id`\n- `ts`: reading time in UTC\n"
            "- `register_kwh`: the meter's cumulative energy register in kWh, taken at the end of each hour\n\n"
            "The site is in the America/Los_Angeles time zone; billing months follow the site's local calendar.\n"
            f"The site was closed for the holiday from {c['closure_start']} to {c['closure_end']} "
            "(reduced load only, the meter kept running).\n")
        return {"readings.csv": buf.getvalue(), "README.md": readme}

    def filler_files(self):
        return {"docs/billing_rates.txt": "Tariff E-19: energy charge by season and time of use. Rates updated each January.\n",
                "docs/site_notes.txt": "Site: warehouse and office, 2 floors. Main meter in the electrical room.\n"}

    def _recorded_increments(self, tables):
        """Correct increments in file order, using only information a solver has."""
        return tables["readings"]

    def naive_answer(self, tables):
        """End register minus start register inside the window, file order, no corrections."""
        ws, we = self.params["window_start"], self.params["window_end"]  # compared directly with the UTC strings
        allr = tables["readings"]
        idx = [i for i, r in enumerate(allr) if ws < r["ts"] <= we]
        return round(allr[idx[-1]]["register"] - allr[idx[0] - 1]["register"], 1)

    def overcorrect_answer(self, tables):
        """Fixes everything, but treats low-load hours (under 15 kWh) as sensor dropouts and fills them with the median."""
        true_inc = [r["kwh"] for r in tables["readings"] if self._in_window(r["utc"])]
        normal = sorted(x for x in true_inc if x >= 15)
        median = normal[len(normal) // 2]
        return round(sum(x if x >= 15 else median for x in true_inc), 1)

    def validate(self, tables, events, clean):
        """Each recording problem must really occur inside the question window (unless the window is the clean one)."""
        rows = tables["readings"]
        lo, hi = self._utc_bounds()
        win = [r for r in rows if lo < r["ts"] <= hi]
        kinds = {e.trap_id for e in events}
        if clean:
            return
        if "register_rollover" in kinds:
            assert any(b["register"] < a["register"] - 500_000 for a, b in zip(win, win[1:])), "no rollover inside the window"
        if "multiplier_change" in kinds:
            cut = to_utc(next(e for e in events if e.trap_id == "multiplier_change").cutover, TZ)
            assert any(r["ts"] > cut for r in win), "multiplier cutover is outside the window"

    def compute(self, tables, events, roll=True, mult=True, bounds=None):
        """Reference computation in Python, with individual fixes switchable for ablation checks."""
        lo, hi = bounds or self._utc_bounds()
        m = next((e for e in events if e.trap_id == "multiplier_change"), None)
        cut = to_utc(m.cutover, TZ) if (m and mult) else None
        total, prev = 0.0, None
        for r in tables["readings"]:
            if prev is None:
                prev = r["register"]
                continue
            d = r["register"] - prev
            prev = r["register"]
            if roll and d < 0:
                d += 1_000_000.0
            if cut and r["ts"] > cut:
                d *= m.factor
            if lo < r["ts"] <= hi:
                total += d
        return round(total, 1)

    def ablations(self, tables, events):
        ws, we = self.params["window_start"], self.params["window_end"]
        return {
            "no_rollover_fix": self.compute(tables, events, roll=False),
            "no_multiplier_fix": self.compute(tables, events, mult=False),
            "bounds_read_as_utc": self.compute(tables, events, bounds=(ws, we)),
            "fixed_-8h_offset": self.compute(tables, events, bounds=tuple(
                (datetime.strptime(x, FMT) + timedelta(hours=8)).strftime(FMT) for x in (ws, we))),
        }

    def solve_code(self, events):
        mult = next((e for e in events if e.trap_id == "multiplier_change"), None)
        roll = next((e for e in events if e.trap_id == "register_rollover"), None)
        c = self.params
        lo, hi = self._utc_bounds()
        lines = [
            "#!/bin/bash\npython3 - <<'PY'\nimport csv, json\n",
            "rows = list(csv.DictReader(open('/app/readings.csv')))  # file order is chronological\n",
            "total, prev = 0.0, None\nfor r in rows:\n",
            "    reg = float(r['register_kwh'])\n    if prev is None:\n        prev = reg\n        continue\n",
            "    d = reg - prev\n    prev = reg\n",
        ]
        if roll:
            lines.append(f"    {roll.undo_code()}\n")
        if mult:
            lines.append(f"    {mult.undo_code()}\n")
        lines.append(f"    if '{lo}' < r['ts'] <= '{hi}':\n        total += d\n")
        lines.append("flags = " + repr([e.flag_text() for e in events]) + "\n")
        lines.append("json.dump({'answer': round(total, 1), 'flags': flags}, open('/app/answer.json', 'w'))\nPY\n")
        return "".join(lines)
