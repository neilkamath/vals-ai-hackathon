#!/bin/bash
python3 - <<'PY'
import csv, json
rows = list(csv.DictReader(open('/app/readings.csv')))  # file order is chronological
total, prev = 0.0, None
for r in rows:
    reg = float(r['register_kwh'])
    if prev is None:
        prev = reg
        continue
    d = reg - prev
    prev = reg
    if d < 0: d += 1000000.0
    if '2026-11-01T00:00:00' < r['ts'] <= '2026-12-01T00:00:00':
        total += d
flags = ['meter register rolled over at 1000000 kWh; added the rollover when a reading dropped']
json.dump({'answer': round(total, 1), 'flags': flags}, open('/app/answer.json', 'w'))
PY
