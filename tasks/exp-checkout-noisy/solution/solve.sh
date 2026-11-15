#!/bin/bash
python3 - <<'PY'
import csv, json
assign_rows = list(csv.DictReader(open('/app/assignments.csv')))
event_rows = list(csv.DictReader(open('/app/events.csv')))
_first = {}
for r in sorted(assign_rows, key=lambda r: r['assigned_at']):
    _first.setdefault(r['user_id'], r)
assign_rows = list(_first.values())
_seen, _out = set(), []
for r in sorted(event_rows, key=lambda r: r['ts']):
    if r['request_id'] in _seen:
        continue
    _seen.add(r['request_id']); _out.append(r)
event_rows = _out
for r in event_rows:
    if r['event_type'] == 'order_placed':
        r['event_type'] = 'checkout_complete'
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
flags = ['222 users were re-assigned to the other arm on 2026-03-05 (assigned twice, in both arms); the first assignment is the one that counts', 'duplicate purchase events from 2026-03-09 (retries re-sent with the same request_id); deduplicated by request_id', "event_type 'checkout_complete' was renamed to 'order_placed' from 2026-03-12; counted both names as purchases"]
json.dump({'answer': round(lift, 4), 'flags': flags}, open('/app/answer.json', 'w'))
PY
