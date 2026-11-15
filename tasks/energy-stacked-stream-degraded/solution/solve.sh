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
cut = '2026-11-13T18:00:00'
factor = 10
rows = [(ts, kwh * factor if cut and ts > cut else kwh) for ts, kwh in rows]
lo, hi = '2026-11-01T07:00:00', '2026-11-26T08:00:00'
total = sum(k for ts, k in rows if lo < ts <= hi)
flags = ['timestamps are UTC; converted the local month boundaries to UTC with the DST change on 2026-11-01', 'CT ratio change on 2026-11-13: the meter reports 1/10 of true energy afterwards; multiplied later energy by 10', "one day's consumption is implausibly low compared with comparable days; the meter looks faulty that day, so the true consumption is unknown", 'from 2026-11-09 the meter sends v2 records (epoch milliseconds, energy in Wh); converted to UTC time and kWh']
json.dump({'answer': round(total, 1), 'flags': flags}, open('/app/.part_a.json', 'w'))
PY
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
cut = '2026-11-13T18:00:00'
factor = 10
rows = [(ts, kwh * factor if cut and ts > cut else kwh) for ts, kwh in rows]
days = [('2026-11-26', '2026-11-26T08:00:00', '2026-11-27T08:00:00'), ('2026-11-27', '2026-11-27T08:00:00', '2026-11-28T08:00:00'), ('2026-11-28', '2026-11-28T08:00:00', '2026-11-29T08:00:00'), ('2026-11-29', '2026-11-29T08:00:00', '2026-11-30T08:00:00')]
daily = {d: sum(k for ts, k in rows if lo < ts <= hi) for d, lo, hi in days}
low = min(daily, key=daily.get)
others = [v for d, v in daily.items() if d != low]
mean_o = sum(others) / len(others)
assert daily[low] < 0.1 * mean_o
json.dump({'status': 'cannot_determine', 'reason': f'consumption on {low} is implausibly low ({daily[low]:.1f} kWh against about {mean_o:.0f} on the other holiday closure days), so the meter looks faulty that day and the requested total cannot be relied on', 'flags': ["one day's consumption is implausibly low compared with comparable days; the meter looks faulty that day, so the true consumption is unknown"]}, open('/app/.part_b.json', 'w'))
PY
python3 - <<'PY'
import json
a = json.load(open('/app/.part_a.json'))
b = json.load(open('/app/.part_b.json'))
def val(x):
    return {'status': x['status'], 'reason': x['reason']} if 'status' in x else x['answer']
json.dump({'a': val(a), 'b': val(b), 'flags': a.get('flags', []) + b.get('flags', [])}, open('/app/answer.json', 'w'))
PY
