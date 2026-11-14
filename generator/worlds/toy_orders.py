"""Toy world: a year of EUR orders. Used to validate the core."""
import csv
import io

from ..core.world import World


class ToyOrdersWorld(World):
    def simulate(self):
        rows = []
        for i in range(self.params["n_orders"]):
            month = self.rng.choice([7, 8, 9])
            day = self.rng.randint(1, 28)
            rows.append({"order_id": f"ORD{i:04d}", "order_date": f"2026-{month:02d}-{day:02d}",
                         "amount": round(self.rng.uniform(10, 500), 2)})
        return {"orders": rows}

    def truth(self):
        return round(sum(r["amount"] for r in self.tables["orders"]), 2)

    def render(self, tables):
        rows = sorted(tables["orders"], key=lambda r: r["order_date"])
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["order_id", "order_date", "amount"])
        w.writerows([r["order_id"], r["order_date"], r["amount"]] for r in rows)
        return {"orders.csv": buf.getvalue(),
                "README.md": "# Orders export\n\n`orders.csv`: one row per order. `amount` is the order value in EUR.\n"}

    def naive_answer(self, tables):
        return round(sum(r["amount"] for r in tables["orders"]), 2)

    def solve_code(self, events):
        undo = "\n        ".join(e.undo_code() for e in events)
        return (
            "#!/bin/bash\npython3 - <<'PY'\nimport csv, json\ntot = 0.0\n"
            "for r in csv.DictReader(open('/app/orders.csv')):\n"
            "    r['amount'] = float(r['amount'])\n"
            f"    {undo}\n"
            "    tot += r['amount']\n"
            "flags = " + repr([e.flag_text() for e in events]) + "\n"
            "json.dump({'answer': round(tot, 2), 'flags': flags}, open('/app/answer.json', 'w'))\nPY\n"
        )
