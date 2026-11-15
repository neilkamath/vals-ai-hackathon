"""Experiment world: an A/B test of a new checkout flow.

True tables: assignments (user, arm, date) and events (page/cart/purchase events).
Metric: lift in revenue per assigned user (treatment minus control), in USD.
Decoys that are real data: repeat same-day purchases (same user, day and amount, different
request_id) and a few large wholesale orders. Both are valid and must be kept.
"""
import csv
import io
import random
from datetime import date, datetime, timedelta

from ..core import filler
from ..core.change_events import TS, new_id
from ..core.world import World

PURCHASE = "checkout_complete"


def _csv(rows, cols):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    w.writerows([r[c] for c in cols] for r in rows)
    return buf.getvalue()


def _lift(arm_of, events, types, window):
    n = {"control": 0, "treatment": 0}
    for a in arm_of.values():
        n[a] += 1
    rev = {"control": 0.0, "treatment": 0.0}
    for e in events:
        if e["event_type"] not in types or (window and e["ts"][:10] > window):
            continue
        a = arm_of.get(e["user_id"])
        if a:
            rev[a] += float(e["amount"])
    return round(rev["treatment"] / n["treatment"] - rev["control"] / n["control"], 4)


class ExperimentWorld(World):
    def simulate(self):
        p, rng = self.params, self.rng
        start = date.fromisoformat(p["start"])
        used, assignments, events = set(), [], []
        for u in range(p["n_users"]):
            uid = f"u{u:05d}"
            day0 = rng.randrange(0, p["days"] - 7)
            arm = rng.choice(["control", "treatment"])
            assignments.append({"user_id": uid, "arm": arm,
                                "assigned_at": (start + timedelta(days=day0)).isoformat()})
            rate = p["base_rate"] * (p["lift"] if arm == "treatment" else 1.0)
            for d in range(day0, p["days"]):
                if rng.random() >= rate:
                    continue
                amount = round(rng.lognormvariate(3.6, 0.7), 2)
                if rng.random() < p["whale_rate"]:
                    amount = round(amount * 30, 2)
                day = start + timedelta(days=d)
                t = datetime(day.year, day.month, day.day, rng.randint(7, 21), rng.randint(0, 59), rng.randint(0, 59))
                orders = [(t, amount)]
                if rng.random() < p["repeat_rate"]:  # real repeat purchase, same day and amount
                    orders.append((t + timedelta(minutes=rng.randint(5, 90)), amount))
                for ot, amt in orders:
                    cart_t = ot - timedelta(minutes=rng.randint(2, 20))
                    for typ, tt, a in (("add_to_cart", cart_t, 0.0), (PURCHASE, ot, amt)):
                        events.append({"event_id": new_id(rng, used), "request_id": new_id(rng, used, "req-"),
                                       "user_id": uid, "ts": tt.strftime(TS), "event_type": typ, "amount": a})
        return {"assignments": assignments, "events": events}

    def _window(self):
        return self.params.get("window_end")

    def truth(self):
        w = self._window()
        arm_of = {a["user_id"]: a["arm"] for a in self.tables["assignments"] if not w or a["assigned_at"] <= w}
        return _lift(arm_of, self.tables["events"], {PURCHASE}, w)

    def render(self, tables):
        assigns = sorted(tables["assignments"], key=lambda r: (r["assigned_at"], r["user_id"]))
        events = sorted(tables["events"], key=lambda r: r["ts"])
        readme = (
            "# Checkout experiment export\n\n"
            "Test of a new checkout flow. Users are randomly assigned to `control` or `treatment`.\n\n"
            "## assignments.csv\n- `user_id`, `arm`, `assigned_at` (date of assignment)\n\n"
            "## events.csv\n- `event_id`: unique id of the logged event\n"
            "- `request_id`: id of the originating request\n- `user_id`, `ts` (UTC)\n"
            "- `event_type`: `add_to_cart` or `checkout_complete` (a completed purchase)\n"
            "- `amount`: purchase value in USD (0 for non-purchase events)\n\n"
            "Large orders (over $1,500) come from verified wholesale accounts and are valid.\n")
        files = {"assignments.csv": _csv(assigns, ["user_id", "arm", "assigned_at"]),
                 "events.csv": _csv(events, ["event_id", "request_id", "user_id", "ts", "event_type", "amount"]),
                 "README.md": readme}
        return files

    def filler_files(self):
        base = self._base_filler()
        n = self.params.get("noise", 0)
        if n:
            r = random.Random(f"filler-{self.seed}")
            base.update(filler.migrations(r, n, skip={40, 42, 43}))
            base.update(filler.modules(r, n // 2))
            for ch, mon in (("general", "02"), ("analytics", "03"), ("oncall", "03")):
                base[f"exports/slack_{ch}_2026-{mon}.txt"] = filler.merge_chat(r, [], 150, mon)
        return base

    def _base_filler(self):
        return {"pipeline/config.yaml": "queue: checkout-events\nsink: warehouse.events\nbatch_size: 500\nregion: us-west-2\n",
                "pipeline/requirements.txt": "boto3\npandas\npyyaml\n"}

    def naive_answer(self, tables):
        """Join assignments to events as-is (fan-out), count only the documented purchase event."""
        w = self._window()
        rows = [a for a in tables["assignments"] if not w or a["assigned_at"] <= w]
        by_user = {}
        for a in rows:
            by_user.setdefault(a["user_id"], []).append(a["arm"])
        n = {"control": 0, "treatment": 0}
        for a in rows:
            n[a["arm"]] += 1
        rev = {"control": 0.0, "treatment": 0.0}
        for e in tables["events"]:
            if e["event_type"] != PURCHASE or (w and e["ts"][:10] > w):
                continue
            for arm in by_user.get(e["user_id"], []):
                rev[arm] += float(e["amount"])
        return round(rev["treatment"] / n["treatment"] - rev["control"] / n["control"], 4)

    def overcorrect_answer(self, tables):
        """Fixes everything except dedupes with a heuristic (user, day, amount), which also drops real repeats."""
        w = self._window()
        first = {}
        for a in sorted(tables["assignments"], key=lambda r: r["assigned_at"]):
            first.setdefault(a["user_id"], a)
        arm_of = {u: a["arm"] for u, a in first.items() if not w or a["assigned_at"] <= w}
        seen, kept = set(), []
        for e in sorted(tables["events"], key=lambda r: r["ts"]):
            key = (e["user_id"], e["ts"][:10], e["amount"])
            if e["event_type"] in (PURCHASE, "order_placed"):
                if key in seen:
                    continue
                seen.add(key)
            kept.append(dict(e, event_type=PURCHASE if e["event_type"] == "order_placed" else e["event_type"]))
        return _lift(arm_of, kept, {PURCHASE}, w)

    def solve_code(self, events):
        w = self._window()
        undo = "\n".join(e.undo_code() for e in events)
        return (
            "#!/bin/bash\npython3 - <<'PY'\nimport csv, json\n"
            "assign_rows = list(csv.DictReader(open('/app/assignments.csv')))\n"
            "event_rows = list(csv.DictReader(open('/app/events.csv')))\n"
            f"{undo}\n"
            f"W = {w!r}\n"
            "arm_of = {r['user_id']: r['arm'] for r in assign_rows if not W or r['assigned_at'] <= W}\n"
            "n = {'control': 0, 'treatment': 0}\nfor a in arm_of.values():\n    n[a] += 1\n"
            "rev = {'control': 0.0, 'treatment': 0.0}\n"
            "for r in event_rows:\n"
            "    if r['event_type'] != 'checkout_complete' or (W and r['ts'][:10] > W):\n        continue\n"
            "    a = arm_of.get(r['user_id'])\n    if a:\n        rev[a] += float(r['amount'])\n"
            "lift = rev['treatment'] / n['treatment'] - rev['control'] / n['control']\n"
            f"flags = {[e.flag_text() for e in events] if not w else []!r}\n"
            "json.dump({'answer': round(lift, 4), 'flags': flags}, open('/app/answer.json', 'w'))\nPY\n")
