#!/bin/bash
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
json.dump({'status': 'cannot_determine', 'reason': f'consumption on {low} is implausibly low ({daily[low]:.1f} kWh against about {mean_o:.0f} on the other holiday closure days), so the meter looks faulty that day and the requested total cannot be relied on', 'flags': ["one day's consumption is implausibly low compared with comparable days; the meter looks faulty that day, so the true consumption is unknown"]}, open('/app/answer.json', 'w'))
PY
