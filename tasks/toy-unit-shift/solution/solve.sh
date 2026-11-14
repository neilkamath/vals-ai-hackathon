#!/bin/bash
python3 - <<'PY'
import csv, json
tot = 0.0
for r in csv.DictReader(open('/app/orders.csv')):
    r['amount'] = float(r['amount'])
    if r['order_date'] >= '2026-08-15': r['amount'] = r['amount'] / 100
    tot += r['amount']
flags = ["'amount' switched from EUR to cents (unit change) on 2026-08-15"]
json.dump({'answer': round(tot, 2), 'flags': flags}, open('/app/answer.json', 'w'))
PY
