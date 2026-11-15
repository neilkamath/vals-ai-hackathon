#!/bin/bash
python3 - <<'PY'
import csv, json
assign_rows = list(csv.DictReader(open('/app/assignments.csv')))
event_rows = list(csv.DictReader(open('/app/events.csv')))

W = None
arm_of = {r['user_id']: r['arm'] for r in assign_rows if not W or r['assigned_at'] <= W}
n = {'control': 0, 'treatment': 0}
for a in arm_of.values():
    n[a] += 1
rev = {'control': 0.0, 'treatment': 0.0}
for r in event_rows:
    if r['event_type'] != 'checkout_complete' or (W and r['ts'][:10] > W):
        continue
    a = arm_of.get(r['user_id'])
    if a:
        rev[a] += float(r['amount'])
lift = rev['treatment'] / n['treatment'] - rev['control'] / n['control']
flags = []
json.dump({'answer': round(lift, 4), 'flags': flags}, open('/app/answer.json', 'w'))
PY
