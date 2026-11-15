"""Streamed meter world: the readings are not a file. A `meterctl` tool serves hourly records in pages.

Serving quirks (documented in `meterctl --help` / `meterctl docs`): pages repeat the last record of the previous page,
every Nth call is rate limited, and firmware 2 meters send a different record format.
"""
import base64
import json
from datetime import datetime, timedelta, timezone

from ..core.meter_events import FMT, to_utc
from .meter import TZ, MeterWorld

PAGE_MAX, RATE_EVERY = 100, 6

METERCTL = r'''#!/usr/bin/env python3
import base64, json, os, sys

D = os.environ.get("METER_DIR", "/opt/meter")
STATE = os.environ.get("METER_STATE", "/tmp/meterctl.state")
CFG = json.load(open(os.path.join(D, "config.json")))
HELP = """meterctl: read hourly energy records from the meter server

usage:
  meterctl meters
  meterctl readings --meter ID [--cursor C] [--limit N]    (N up to %d, default %d)
  meterctl docs

readings prints one JSON object per call: {"records": [...], "next_cursor": C or null, "has_more": true/false}
Pass next_cursor back with --cursor to get the next page. Each page repeats the last record of the previous page.
The server limits the request rate: a rate-limited call prints {"error": "rate_limited", "retry_after_s": 1}
and exits with status 3. Call again.
Run `meterctl docs` for the record format.""" % (CFG["page_max"], CFG["page_max"])
DOCS = """Record formats
  v1: {"ts": "<UTC time at the end of the hour, ISO 8601>", "kwh": <energy for that hour in kWh>, "v": 1}
  v2: {"ts": <UTC epoch milliseconds at the end of the hour>, "wh": <energy for that hour in Wh>, "v": 2}
Meters on firmware 2.x report v2 records. Records are ordered by time."""


def out(obj, code=0):
    print(json.dumps(obj))
    sys.exit(code)


def main(a):
    if len(a) < 1 or a[0] in ("-h", "--help", "help"):
        print(HELP); return
    if a[0] == "docs":
        print(DOCS); return
    if a[0] == "meters":
        out([{"meter": "M-1001", "site": "main building", "timezone": "America/Los_Angeles"}])
    if a[0] != "readings":
        print(HELP); sys.exit(2)
    opt = {}
    i = 1
    while i < len(a):
        opt[a[i].lstrip("-")] = a[i + 1] if i + 1 < len(a) else ""
        i += 2
    if opt.get("meter") != "M-1001":
        out({"error": "unknown_meter"}, 2)
    n = int(open(STATE).read()) if os.path.exists(STATE) else 0
    n += 1
    open(STATE, "w").write(str(n))
    if CFG["rate_limit_every"] and n % CFG["rate_limit_every"] == 0:
        out({"error": "rate_limited", "retry_after_s": 1}, 3)
    stream = json.load(open(os.path.join(D, "stream.json")))
    limit = min(int(opt.get("limit", CFG["page_max"])), CFG["page_max"])
    off = int(base64.b64decode(opt["cursor"]).decode()) if opt.get("cursor") else 0
    recs = stream[off:off + limit]
    if off > 0:
        recs = [stream[off - 1]] + recs
    more = off + limit < len(stream)
    out({"records": recs, "next_cursor": base64.b64encode(str(off + limit).encode()).decode() if more else None,
         "has_more": more})


main(sys.argv[1:])
'''

FETCH = '''import subprocess, json, time, datetime
recs, cursor = [], None
while True:
    cmd = ['meterctl', 'readings', '--meter', 'M-1001', '--limit', '100'] + (['--cursor', cursor] if cursor else [])
    p = subprocess.run(cmd, capture_output=True, text=True)
    try:
        d = json.loads(p.stdout)
    except Exception:
        time.sleep(1); continue
    if 'error' in d:
        time.sleep(d.get('retry_after_s', 1)); continue
    recs += d['records']
    if not d['has_more']:
        break
    cursor = d['next_cursor']
seen, rows = set(), []
for r in recs:
    if r['v'] == 1:
        ts, kwh = r['ts'], r['kwh']
    else:
        ts = datetime.datetime.fromtimestamp(r['ts'] / 1000, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
        kwh = r['wh'] / 1000
    if ts in seen:
        continue
    seen.add(ts)
    rows.append((ts, kwh))
'''


def _iso(r):
    if r["v"] == 1:
        return r["ts"]
    return datetime.fromtimestamp(r["ts"] / 1000, timezone.utc).strftime(FMT)


class MeterApiWorld(MeterWorld):
    def simulate(self):
        t = super().simulate()
        t["stream"] = [{"utc": r["utc"], "ts": r["utc"], "kwh": round(r["kwh"], 3), "v": 1}
                       for r in t["readings"][1:]]
        return t

    # -- serving, mirrored from meterctl ------------------------------------------------
    def served(self, tables):
        s, out, off = tables["stream"], [], 0
        while off < len(s):
            page = s[off:off + PAGE_MAX]
            out += ([s[off - 1]] if off else []) + page
            off += PAGE_MAX
        return out

    def render(self, tables):
        public = [{k: v for k, v in r.items() if k != "utc"} for r in tables["stream"]]
        cfg = {"page_max": PAGE_MAX, "rate_limit_every": RATE_EVERY}
        c = self.params
        readme = (
            "# Meter data\n\nHourly energy readings from the main electricity meter of one site (meter M-1001).\n\n"
            "There is no readings file. The readings are served by the `meterctl` tool; run `meterctl --help`.\n\n"
            "The site is in the America/Los_Angeles time zone; billing months follow the site's local calendar.\n"
            f"The site was closed for the holiday from {c['closure_start']} to {c['closure_end']} "
            "(reduced load only, the meter kept running).\n")
        return {"README.md": readme, "service/meterctl": METERCTL, "service/stream.json": json.dumps(public),
                "service/config.json": json.dumps(cfg)}

    # -- reference computation (mirrors what a solver does) -------------------------------
    def compute(self, tables, events, dedupe=True, schema=True, mult=True, bounds=None):
        lo, hi = bounds or self._utc_bounds()
        m = next((e for e in events if e.trap_id == "multiplier_change"), None)
        cut = to_utc(m.cutover, TZ) if (m and mult) else None
        seen, total = set(), 0.0
        for r in self.served(tables):
            ts = _iso(r)
            if dedupe:
                if ts in seen:
                    continue
                seen.add(ts)
            kwh = r["kwh"] if r["v"] == 1 else (r["wh"] / 1000 if schema else r["wh"])
            if cut and ts > cut:
                kwh *= m.factor
            if lo < ts <= hi:
                total += kwh
        return round(total, 1)

    def ablations(self, tables, events):
        ws, we = self.params["window_start"], self.params["window_end"]
        out = {
            "no_dedupe_of_page_overlap": self.compute(tables, events, dedupe=False),
            "no_schema_fix": self.compute(tables, events, schema=False),
            "no_multiplier_fix": self.compute(tables, events, mult=False),
            "bounds_read_as_utc": self.compute(tables, events, bounds=(ws, we)),
            "fixed_-8h_offset": self.compute(tables, events, bounds=tuple(
                (datetime.strptime(x, FMT) + timedelta(hours=8)).strftime(FMT) for x in (ws, we))),
        }
        return out

    def naive_answer(self, tables):
        """Concatenate the pages, read only v1 records, sum kWh in the window with the local strings read as UTC."""
        ws, we = self.params["window_start"], self.params["window_end"]
        return round(sum(r["kwh"] for r in self.served(tables)
                         if r["v"] == 1 and ws < r["ts"] <= we), 1)

    def clean_check_answer(self, tables, events):
        """A solver that handles the documented behaviour (overlap, retries) but applies no other fix."""
        return self.compute(tables, events, dedupe=True, schema=False, mult=False)

    def status_check(self, tables, events, truth, naive, tol):
        kind = self.params.get("status_kind")
        recorded = self.compute(tables, events)
        assert abs(recorded - truth) > tol, f"recorded total {recorded} is close to the true {truth}"
        if kind == "gap":
            lo, hi = self._utc_bounds()
            have = {_iso(r) for r in tables["stream"]}
            t, miss = datetime.strptime(lo, FMT) + timedelta(hours=1), 0
            while t <= datetime.strptime(hi, FMT):
                miss += t.strftime(FMT) not in have
                t += timedelta(hours=1)
            assert miss >= 3, "fewer than 3 missing hours inside the window"
            return f"missing_hours={miss} recorded_total={recorded} true_total={truth}"
        daily = self._closure_daily(tables, events)
        low = min(daily, key=daily.get)
        others = [v for d, v in daily.items() if d != low]
        mean_o = sum(others) / len(others)
        assert max(others) / min(others) < 1.2, f"other closure days inconsistent: {daily}"
        assert daily[low] < self.params.get("low_ratio", 0.1) * mean_o, f"degraded day not low enough: {daily}"
        return f"low_day={low} ({daily[low]} kWh vs {mean_o:.0f}) recorded_total={recorded} true_total={truth}"

    # -- reference solutions (use only the meterctl tool) ---------------------------------
    def solve_code(self, events):
        m = next((e for e in events if e.trap_id == "multiplier_change"), None)
        head = "#!/bin/bash\npython3 - <<'PY'\nimport json\n" + FETCH
        cut = f"cut = {to_utc(m.cutover, TZ) if m else None!r}\nfactor = {m.factor if m else 1}\n"
        fix = "rows = [(ts, kwh * factor if cut and ts > cut else kwh) for ts, kwh in rows]\n"
        if self.params.get("expected_status") and self.params.get("status_kind") == "gap":
            lo, hi = self._utc_bounds()
            return (head + f"import datetime as dt\nlo, hi = {lo!r}, {hi!r}\n"
                    "have = {ts for ts, _ in rows}\nt = dt.datetime.fromisoformat(lo) + dt.timedelta(hours=1)\nmiss = 0\n"
                    "while t <= dt.datetime.fromisoformat(hi):\n    miss += t.strftime('%Y-%m-%dT%H:%M:%S') not in have\n    t += dt.timedelta(hours=1)\n"
                    "assert miss >= 3\n"
                    "json.dump({'status': 'cannot_determine', 'reason': f'{miss} hourly records inside the requested period were "
                    "never delivered by the meter server, so the total is incomplete', "
                    f"'flags': {[e.flag_text() for e in events if e.trap_id == 'stream_gap']!r}}}, open('/app/answer.json', 'w'))\nPY\n")
        if self.params.get("expected_status"):
            thr = self.params.get("low_ratio", 0.1)
            return (head + cut + fix + f"days = {self._closure_days()!r}\n"
                    "daily = {d: sum(k for ts, k in rows if lo < ts <= hi) for d, lo, hi in days}\n"
                    "low = min(daily, key=daily.get)\nothers = [v for d, v in daily.items() if d != low]\nmean_o = sum(others) / len(others)\n"
                    f"assert daily[low] < {thr} * mean_o\n"
                    "json.dump({'status': 'cannot_determine', 'reason': f'consumption on {low} is implausibly low "
                    "({daily[low]:.1f} kWh against about {mean_o:.0f} on the other holiday closure days), so the meter looks "
                    "faulty that day and the requested total cannot be relied on', "
                    f"'flags': {[e.flag_text() for e in events if e.trap_id == 'degraded_meter']!r}}}, open('/app/answer.json', 'w'))\nPY\n")
        lo, hi = self._utc_bounds()
        return (head + cut + fix + f"lo, hi = {lo!r}, {hi!r}\ntotal = sum(k for ts, k in rows if lo < ts <= hi)\n"
                f"flags = {[e.flag_text() for e in events]!r}\n"
                "json.dump({'answer': round(total, 1), 'flags': flags}, open('/app/answer.json', 'w'))\nPY\n")
