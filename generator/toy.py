"""Toy task generator: validates the pipeline end to end. Not part of the final benchmark.

Clean data -> true answer -> corrupt (unit change to cents after a cutover date).
"""
import csv, json, random, sys
from pathlib import Path

TASK_ID = "toy-unit-shift"


def build(seed: int, out_root: Path) -> None:
    rng = random.Random(seed)
    task = out_root / TASK_ID
    (task / "environment" / "data").mkdir(parents=True, exist_ok=True)
    (task / "tests").mkdir(exist_ok=True)
    (task / "solution").mkdir(exist_ok=True)

    cutover = "2026-08-15"
    rows, truth = [], 0.0
    for i in range(60):
        month = rng.choice([7, 8, 9])
        day = rng.randint(1, 28)
        date = f"2026-{month:02d}-{day:02d}"
        eur = round(rng.uniform(10, 500), 2)
        truth += eur
        shown = int(round(eur * 100)) if date >= cutover else eur
        rows.append((f"ORD{i:04d}", date, shown))
    rows.sort(key=lambda r: r[1])
    truth = round(truth, 2)

    with open(task / "environment/data/orders.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["order_id", "order_date", "amount"])
        w.writerows(rows)
    (task / "environment/data/CHANGELOG.txt").write_text(
        f"2026-08-15  Billing export v2 deployed. 'amount' is now stored in cents (integer) for\n"
        f"            all rows dated on or after {cutover}. Earlier rows are unchanged (EUR).\n"
    )
    (task / "environment/data/README.md").write_text(
        "# Orders export\n\n`orders.csv`: one row per order. `amount` is the order value in EUR.\n"
    )
    (task / "environment/Dockerfile").write_text(
        "FROM python:3.12-slim\n"
        "RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates "
        "&& rm -rf /var/lib/apt/lists/*\n"
        "WORKDIR /app\nCOPY data/ /app/\n"
    )
    (task / "instruction.md").write_text(
        "What was total Q3 2026 (July-September) revenue in EUR, from the orders export in `/app`?\n\n"
        'Write the result to `/app/answer.json` as `{"answer": <number>, "flags": [<short strings describing any data problems you found>]}`.\n'
    )
    (task / "task.toml").write_text(
        'version = "1.0"\n\n[task]\nname = "silent-errors/toy-unit-shift"\n'
        'description = "Pipeline smoke test: unit change documented only in a changelog."\n\n'
        '[metadata]\ndifficulty = "toy"\ncategory = "data-analysis"\n\n'
        "[verifier]\ntimeout_sec = 120.0\n\n[agent]\ntimeout_sec = 600.0\n"
        "network_mode = \"allowlist\"\nallowed_hosts = [\"api.anthropic.com\", \"api.openai.com\"]\n\n"
        "[environment]\nbuild_timeout_sec = 600.0\ncpus = 1\nmemory_mb = 2048\nstorage_mb = 10240\n"
    )
    (task / "tests/expected.json").write_text(json.dumps({"answer": truth, "tolerance_rel": 0.001}))
    (task / "tests/grade.py").write_text(GRADE)
    (task / "tests/test.sh").write_text(
        "#!/bin/bash\nmkdir -p /logs/verifier\npython3 /tests/grade.py /app/answer.json /tests/expected.json\n"
    )
    (task / "solution/solve.sh").write_text(SOLVE)
    for p in ("tests/test.sh", "solution/solve.sh"):
        (task / p).chmod(0o755)


GRADE = '''import json, sys
ans_path, exp_path = sys.argv[1:3]
exp = json.load(open(exp_path))
reward = 0
try:
    a = float(json.load(open(ans_path))["answer"])
    reward = int(abs(a - exp["answer"]) <= exp["tolerance_rel"] * abs(exp["answer"]))
    print(f"answer={a} expected={exp['answer']} reward={reward}")
except Exception as e:
    print(f"grading error: {e!r}")
open("/logs/verifier/reward.txt", "w").write(str(reward))
'''

SOLVE = '''#!/bin/bash
python3 - <<'PY'
import csv, json
tot = 0.0
for r in csv.DictReader(open("/app/orders.csv")):
    v = float(r["amount"])
    tot += v / 100 if r["order_date"] >= "2026-08-15" else v
json.dump({"answer": round(tot, 2), "flags": ["amount switched to cents on 2026-08-15"]}, open("/app/answer.json", "w"))
PY
'''

if __name__ == "__main__":
    build(int(sys.argv[1]) if len(sys.argv) > 1 else 0, Path(sys.argv[2]) if len(sys.argv) > 2 else Path("tasks"))
