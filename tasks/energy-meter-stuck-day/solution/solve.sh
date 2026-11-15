#!/bin/bash
python3 - <<'PY'
import csv, json
rows = list(csv.DictReader(open('/app/readings.csv')))
win = [r for r in rows if '2026-11-20T08:00:00' < r['ts'] <= '2026-11-21T08:00:00']
run = best = 1
for a, b in zip(win, win[1:]):
    run = run + 1 if a['register_kwh'] == b['register_kwh'] else 1
    best = max(best, run)
assert best >= 12, 'no frozen register'
json.dump({'status': 'cannot_determine', 'reason': f'the meter register is frozen for {best} consecutive hours inside the requested period, so consumption in that period was not recorded', 'flags': ['the meter register is frozen for many consecutive hours (identical readings), so consumption in that period was not recorded']}, open('/app/answer.json', 'w'))
PY
