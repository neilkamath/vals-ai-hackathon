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
    if prev is None:
        prev = reg
        continue
    if r['meter_id'] != last_id:
        prev = 0.0
    last_id = r['meter_id']
    if d < 0: d += 1000000.0
    if r['ts'] > '2026-11-13T18:00:00': d *= 10
    if '2026-11-01T07:00:00' < r['ts'] <= '2026-12-01T08:00:00':
        total += d
flags = ['timestamps are UTC; converted the local month boundaries to UTC with the DST change on 2026-11-01', 'CT ratio change on 2026-11-13: the register reads 1/10 of true energy afterwards; multiplied later increments by 10', 'meter register rolled over at 1000000 kWh; added the rollover when a reading dropped', 'the meter was replaced on 2026-11-20 (new meter M-1002, register restarts at 0.0); the drop in the register is not a rollover']
json.dump({'answer': round(total, 1), 'flags': flags}, open('/app/answer.json', 'w'))
PY
