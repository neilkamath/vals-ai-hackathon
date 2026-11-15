#!/bin/bash
python3 - <<'PY'
import json
import subprocess, json, time, datetime
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
import datetime as dt
lo, hi = '2026-11-01T07:00:00', '2026-12-01T08:00:00'
have = {ts for ts, _ in rows}
t = dt.datetime.fromisoformat(lo) + dt.timedelta(hours=1)
miss = 0
while t <= dt.datetime.fromisoformat(hi):
    miss += t.strftime('%Y-%m-%dT%H:%M:%S') not in have
    t += dt.timedelta(hours=1)
assert miss >= 3
json.dump({'status': 'cannot_determine', 'reason': f'{miss} hourly records inside the requested period were never delivered by the meter server, so the total is incomplete', 'flags': ['some hourly records are missing from the stream and cannot be recovered, so the total is incomplete']}, open('/app/answer.json', 'w'))
PY
