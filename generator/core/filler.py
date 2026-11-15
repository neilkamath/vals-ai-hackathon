"""Plausible, unrelated filler: chat chatter, migrations and pipeline modules. Seeded and deterministic."""

NAMES = ["priya", "marco", "dev", "lena", "sam", "kofi", "ana", "tomas", "jules", "ines"]
THINGS = ["nightly export", "dashboard refresh", "staging deploy", "warehouse backfill", "airflow DAG",
          "feature flag cleanup", "pricing page test", "email campaign", "oncall handoff", "vpn token",
          "cohort report", "churn model", "billing sync", "search index", "mobile build", "cdn cache"]
CHAT = ["anyone seen the {t} fail again?", "{t} is green again", "can someone review my PR for the {t}",
        "heads up, the {t} will be down for ten minutes", "who owns the {t}?", "I'll look at the {t} after lunch",
        "the {t} skipped twice last night", "ticket filed for the {t}", "retro notes are up, {t} is on the list",
        "lunch?", "standup in 5", "coffee run, anyone?", "out tomorrow, ping marco for the {t}",
        "thanks, that fixed the {t}", "is the {t} supposed to take this long?", "pushed a fix for the {t}"]
TABLES = ["users", "sessions", "invoices", "campaigns", "feature_flags", "audit_log", "pricing", "carts", "coupons"]
COLS = ["created_at", "updated_at", "region", "plan", "source", "status", "owner_id", "notes"]
FUNCS = ["normalize_region", "parse_plan", "clean_coupon", "to_utc", "fill_status", "slugify", "bucket_age",
         "mask_email", "round_money", "strip_tracking"]


def chatter(rng, n, month="03", max_day=28):
    out = []
    for _ in range(n):
        d, h, m = rng.randint(1, max_day), rng.randint(8, 19), rng.randint(0, 59)
        out.append(((d, h, m), f"[{month}/{d:02d} {h:02d}:{m:02d}] {rng.choice(NAMES)}: "
                    + rng.choice(CHAT).format(t=rng.choice(THINGS))))
    return out


def merge_chat(rng, clue_lines, n, month="03"):
    """clue_lines: list of ((d,h,m), text). Returns one chronologically sorted text block."""
    allv = chatter(rng, n, month) + clue_lines
    allv.sort(key=lambda x: x[0])
    return "\n".join(t for _, t in allv) + "\n"


def migrations(rng, n, skip):
    out = {}
    for i in range(1, n + 1):
        if i in skip:
            continue
        t, c = rng.choice(TABLES), rng.choice(COLS)
        op = rng.choice([f"CREATE INDEX idx_{t}_{c} ON {t} ({c});", f"ALTER TABLE {t} ADD COLUMN {c}_v2 TEXT;",
                         f"ALTER TABLE {t} ALTER COLUMN {c} SET DEFAULT 'unknown';", f"ANALYZE {t};"])
        out[f"migrations/{i:04d}_{t}_{c}.sql"] = f"-- housekeeping\n{op}\n"
    return out


def module(rng):
    f = rng.choice(FUNCS)
    k = rng.randint(2, 9)
    return (f"def {f}(value):\n    if value is None:\n        return ''\n    value = str(value).strip().lower()\n"
            f"    return value[:{k * 4}]\n\n\ndef {f}_all(values):\n    return [{f}(v) for v in values]\n")


def modules(rng, n):
    out = {}
    for i in range(n):
        pkg = rng.choice(["transforms", "validators", "loaders", "utils"])
        out[f"pipeline/{pkg}/{rng.choice(FUNCS)}_{i}.py"] = module(rng)
    return out


def pad_functions(rng, n):
    return "\n\n".join(module(rng).replace("def ", f"def h{i}_", 1) for i in range(n))
