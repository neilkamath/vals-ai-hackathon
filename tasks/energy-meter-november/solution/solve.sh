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
    if r['ts'] > '2026-11-13T18:00:00': d *= 10
    if '2026-11-01T07:00:00' < r['ts'] <= '2026-12-01T08:00:00':
        total += d
flags = ['timestamps are UTC; converted the local month boundaries to UTC with the DST change on 2026-11-01', 'CT ratio change on 2026-11-13: the register reads 1/10 of true energy afterwards; multiplied later increments by 10', 'meter register rolled over at 1000000 kWh; added the rollover when a reading dropped']
json.dump({'answer': round(total, 1), 'flags': flags}, open('/app/answer.json', 'w'))
PY
