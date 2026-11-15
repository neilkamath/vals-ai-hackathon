#!/bin/bash
python3 - <<'PY'
import collections, csv, json
ev = collections.Counter(r['user_id'] for r in csv.DictReader(open('/app/events.csv')))
rows = [r for r in csv.DictReader(open('/app/assignments.csv')) if ev[r['user_id']] < 100]
n = {'control': 0, 'treatment': 0}
for r in rows:
    n[r['arm']] += 1
chi2 = (n['treatment'] - n['control']) ** 2 / (n['treatment'] + n['control'])
assert chi2 > 10.83, 'no sample ratio mismatch'
json.dump({'status': 'cannot_determine', 'reason': f'sample ratio mismatch among real customers: {n} vs a 50/50 design (chi2={chi2:.0f}); the split is not random, so the lift is not reliable', 'flags': ['sample ratio mismatch: uneven split vs the documented 50/50 design', 'bot-like users with extreme event volume (6 or more events a day) excluded']}, open('/app/answer.json', 'w'))
PY
