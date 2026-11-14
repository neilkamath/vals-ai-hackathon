#!/bin/bash
python3 - <<'PY'
import csv, json
tot = 0.0
for r in csv.DictReader(open("/app/orders.csv")):
    v = float(r["amount"])
    tot += v / 100 if r["order_date"] >= "2026-08-15" else v
json.dump({"answer": round(tot, 2), "flags": ["amount switched to cents on 2026-08-15"]}, open("/app/answer.json", "w"))
PY
