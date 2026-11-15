"""Change events: hidden changes in the recording process.

Each event can (1) corrupt recorded tables, (2) write its buried clue, (3) emit the code that
undoes it (reference solution), (4) give the flag text and keywords the grader looks for.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

TS = "%Y-%m-%dT%H:%M:%S"


def new_id(rng, used, prefix="evt-"):
    while True:
        i = f"{prefix}{rng.randrange(10**7, 10**8)}"
        if i not in used:
            used.add(i)
            return i


@dataclass
class UnitChange:
    """From `cutover` on, `field` is stored multiplied by `factor` (e.g. EUR -> cents)."""
    cutover: str
    factor: float
    field: str = "amount"
    date_field: str = "order_date"
    table: str = "orders"
    clue: str = "changelog"
    trap_id = "unit_change"
    keywords = ["cents", "unit", "scale", "eur"]

    def apply(self, tables, rng):
        for r in tables[self.table]:
            if r[self.date_field] >= self.cutover:
                r[self.field] = int(round(r[self.field] * self.factor))

    def clue_files(self, kind):
        return {"CHANGELOG.txt": (
            f"{self.cutover}  Billing export v2 deployed. '{self.field}' is now stored in cents "
            f"(integer) for all rows dated on or after {self.cutover}. Earlier rows are unchanged (EUR).\n")}

    def flag_text(self):
        return f"'{self.field}' switched from EUR to cents (unit change) on {self.cutover}"

    def undo_code(self):
        return (f"if r['{self.date_field}'] >= '{self.cutover}': "
                f"r['{self.field}'] = r['{self.field}'] / {self.factor}")


@dataclass
class StickyReassignment:
    """After an incident, a bucketing job re-rolled some users into the other arm; the old row stays."""
    incident: str
    frac: float
    clue: str = "chat_export"
    trap_id = "reassignment"
    keywords = ["reassign", "re-assign", "re-roll", "reroll", "both arms", "assigned twice",
                "multiple assignment", "more than one assignment", "first assignment", "duplicate assignment"]
    n_rerolled = 0

    def apply(self, tables, rng):
        add = []
        for a in tables["assignments"]:
            if a["assigned_at"] < self.incident and rng.random() < self.frac:
                add.append({"user_id": a["user_id"], "assigned_at": self.incident,
                            "arm": "control" if a["arm"] == "treatment" else "treatment"})
        tables["assignments"].extend(add)
        self.n_rerolled = len(add)

    def clue_files(self, kind):
        d = self.incident
        return {"exports/slack_data-eng_2026-03.txt": (
            "#data-eng  export 2026-03\n\n"
            "[Mar 02 10:12] marco: reminder, warehouse backfill finishes tonight\n"
            "[Mar 03 09:30] dev: who owns the dashboard refresh cron? it skipped twice\n"
            f"[{d[5:7]}/{d[8:10]} 16:40] priya: ok the config incident is sorted. I re-ran the bucketing job and it "
            f"re-rolled {self.n_rerolled} users who were already in the test.\n"
            "[same day 16:41] priya: I left the old rows in the assignments table for audit, so those users have two rows now\n"
            "[same day 16:43] priya: the first assignment is the one they actually experienced, the re-rolled ones never saw the other arm\n"
            "[Mar 06 11:05] marco: lunch?\n")}

    def flag_text(self):
        return (f"{self.n_rerolled} users were re-assigned to the other arm on {self.incident} "
                "(assigned twice, in both arms); the first assignment is the one that counts")

    def undo_code(self):
        return ("_first = {}\n"
                "for r in sorted(assign_rows, key=lambda r: r['assigned_at']):\n"
                "    _first.setdefault(r['user_id'], r)\n"
                "assign_rows = list(_first.values())")


@dataclass
class DuplicateRetries:
    """From `from_date`, a producer re-sends purchase events on ack timeout: new event_id, same request_id."""
    from_date: str
    rate: float
    clue: str = "etl_script"
    trap_id = "duplicate_retries"
    keywords = ["retry", "retries", "request_id", "re-sent", "resent", "duplicate purchase", "duplicate event",
                "duplicate checkout", "duplicate order", "duplicated purchase", "duplicated event"]

    def apply(self, tables, rng):
        ev = tables["events"]
        used = {e["event_id"] for e in ev}
        add = []
        for e in ev:
            if e["event_type"] == "checkout_complete" and e["ts"][:10] >= self.from_date and rng.random() < self.rate:
                d = dict(e)
                d["event_id"] = new_id(rng, used)
                d["ts"] = (datetime.strptime(e["ts"], TS) + timedelta(seconds=rng.randint(1, 9))).strftime(TS)
                add.append(d)
        ev.extend(add)

    def clue_files(self, kind):
        y, m, d = self.from_date.split("-")
        return {"pipeline/ingest_events.py": (
            '"""Ingest worker: reads raw checkout events from the queue and writes them to the events export."""\n'
            "import datetime\nimport json\nimport uuid\n\n"
            f"RETRY_EMIT_FROM = datetime.date({int(y)}, {int(m)}, {int(d)})  # flag: resend when the sink did not ack\n"
            "BATCH_SIZE = 500\n\n\n"
            "def parse(raw):\n    e = json.loads(raw)\n    e['amount'] = round(float(e.get('amount', 0)), 2)\n    return e\n\n\n"
            "def emit(sink, event, now):\n"
            "    sink.write(event)\n"
            "    if now.date() >= RETRY_EMIT_FROM and event.get('ack_timeout'):\n"
            "        retry = dict(event, event_id=str(uuid.uuid4()), ts=now.isoformat())\n"
            "        sink.write(retry)\n\n\n"
            "def run(queue, sink):\n"
            "    for raw in queue.poll(BATCH_SIZE):\n"
            "        emit(sink, parse(raw), datetime.datetime.utcnow())\n")}

    def flag_text(self):
        return (f"duplicate purchase events from {self.from_date} (retries re-sent with the same request_id); "
                "deduplicated by request_id")

    def undo_code(self):
        return ("_seen, _out = set(), []\n"
                "for r in sorted(event_rows, key=lambda r: r['ts']):\n"
                "    if r['request_id'] in _seen:\n        continue\n"
                "    _seen.add(r['request_id']); _out.append(r)\n"
                "event_rows = _out")


@dataclass
class EventRename:
    """From `cutover`, the purchase event is written under a new name."""
    cutover: str
    old: str = "checkout_complete"
    new: str = "order_placed"
    clue: str = "migration_sql"
    trap_id = "event_rename"
    keywords = ["renamed", "order_placed", "event name", "event type was", "event_type was", "new event name"]

    def apply(self, tables, rng):
        for e in tables["events"]:
            if e["ts"][:10] >= self.cutover and e["event_type"] == self.old:
                e["event_type"] = self.new

    def clue_files(self, kind):
        return {
            "migrations/0040_create_events_ts_index.sql": "CREATE INDEX idx_events_ts ON events (ts);\n",
            "migrations/0042_rename_checkout_event.sql": (
                "-- analytics v3: align event names with the product taxonomy\n"
                f"-- applies to events written on or after {self.cutover}\n"
                f"UPDATE event_type_map SET name = '{self.new}' WHERE name = '{self.old}';\n"),
            "migrations/0043_drop_legacy_sessions.sql": "DROP TABLE IF EXISTS legacy_sessions;\n",
        }

    def flag_text(self):
        return (f"event_type '{self.old}' was renamed to '{self.new}' from {self.cutover}; "
                "counted both names as purchases")

    def undo_code(self):
        return (f"for r in event_rows:\n    if r['event_type'] == '{self.new}':\n"
                f"        r['event_type'] = '{self.old}'")


REGISTRY = {"unit_change": UnitChange, "sticky_reassignment": StickyReassignment,
            "duplicate_retries": DuplicateRetries, "event_rename": EventRename}


def build_event(d):
    d = dict(d)
    return REGISTRY[d.pop("type")](**d)
