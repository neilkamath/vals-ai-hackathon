#!/bin/bash
python3 - <<'PY'
import csv, json
rows = list(csv.DictReader(open('/app/readings.csv')))  # file order is chronological
total, prev, last_id = 0.0, None, rows[0]['meter_id']
for r in rows:
    reg = float(r['register_kwh'])
    if prev is None:
        prev = reg
        continue
    if r['meter_id'] != last_id:
        prev = 0.0  # the new meter starts at 0.0
    last_id = r['meter_id']
    d = reg - prev
    prev = reg
    if d < 0: d += 1000000.0
    if r['ts'] > '2026-11-13T18:00:00': d *= 10
    if '2026-11-01T07:00:00' < r['ts'] <= '2026-11-26T08:00:00':
        total += d
flags = ['timestamps are UTC; converted the local month boundaries to UTC with the DST change on 2026-11-01', 'CT ratio change on 2026-11-13: the register reads 1/10 of true energy afterwards; multiplied later increments by 10', "one day's consumption is implausibly low compared with comparable days; the meter looks faulty that day, so the true consumption is unknown", 'meter register rolled over at 1000000 kWh; added the rollover when a reading dropped', 'the meter was replaced on 2026-11-20 (new meter M-1002, register restarts at 0.0); the drop in the register is not a rollover']
json.dump({'answer': round(total, 1), 'flags': flags}, open('/app/.part_a.json', 'w'))
PY
python3 - <<'PY'
import csv, json
rows = list(csv.DictReader(open('/app/readings.csv')))
days = [('2026-11-26', '2026-11-26T08:00:00', '2026-11-27T08:00:00'), ('2026-11-27', '2026-11-27T08:00:00', '2026-11-28T08:00:00'), ('2026-11-28', '2026-11-28T08:00:00', '2026-11-29T08:00:00'), ('2026-11-29', '2026-11-29T08:00:00', '2026-11-30T08:00:00')]  # the holiday closure days named in the README
cut = '2026-11-13T18:00:00'
factor = 10
inc, prev, last_id = [], None, rows[0]['meter_id']
for r in rows:
    reg = float(r['register_kwh'])
    if prev is None:
        prev = reg
        continue
    if r['meter_id'] != last_id:
        prev = 0.0  # a replaced meter starts at 0.0
    last_id = r['meter_id']
    d = reg - prev
    prev = reg
    if d < 0: d += 1000000.0
    if cut and r['ts'] > cut: d *= factor
    inc.append((r['ts'], d))
daily = {day: sum(d for ts, d in inc if lo < ts <= hi) for day, lo, hi in days}
low = min(daily, key=daily.get)
others = [v for k, v in daily.items() if k != low]
mean_o = sum(others) / len(others)
assert daily[low] < 0.1 * mean_o, 'no implausible day'
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
