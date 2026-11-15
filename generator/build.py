"""Build all tasks from generator/specs/*.toml into tasks/. Fails loudly on any check.

Usage: python3 -m generator.build [--out tasks] [--specs generator/specs] [--no-check]

Specs in generator/specs/*.toml are the frozen benchmark; generator/specs/dev/ holds development-only specs.
"""
import subprocess
import sys
import tomllib
from pathlib import Path

from .core import change_events, clue_placer, task_writer
from .core.recorder import Recorder
from .worlds.experiment import ExperimentWorld
from .worlds.meter import MeterWorld
from .worlds.meter_api import MeterApiWorld
from .worlds.toy_orders import ToyOrdersWorld

WORLDS = {"toy_orders": ToyOrdersWorld, "experiment": ExperimentWorld, "meter": MeterWorld, "meter_api": MeterApiWorld}
ROOT = Path(__file__).resolve().parent.parent


MERGE = """python3 - <<'PY'
import json
a = json.load(open('/app/.part_a.json'))
b = json.load(open('/app/.part_b.json'))
def val(x):
    return {'status': x['status'], 'reason': x['reason']} if 'status' in x else x['answer']
json.dump({'a': val(a), 'b': val(b), 'flags': a.get('flags', []) + b.get('flags', [])}, open('/app/answer.json', 'w'))
PY
"""


def build_stacked(spec, out_root):
    """A task with several parts (a, b, ...). Each part is checked like a standalone task; the reward needs all parts right."""
    wp = dict(spec["world_params"])
    first = spec["parts"][0]
    wp.update(window_start=first["window_start"], window_end=first["window_end"])
    world = WORLDS[spec["world"]](spec["seed"], wp)
    events = [change_events.build_event(e) for e in spec["change_events"]]
    tables, files = Recorder(world, events, spec["seed"]).record()
    files.update(clue_placer.place(events, world.filler_files()))
    tol_rel = spec.get("tolerance_rel", 0.0004)
    expected_parts, sols, notes = {}, {}, []
    for part in spec["parts"]:
        world.params.update(window_start=part["window_start"], window_end=part["window_end"])
        for k in ("expected_status", "status_kind"):
            world.params.pop(k, None)
        truth = world.truth()
        tol = tol_rel * abs(truth)
        if part.get("expected_status"):
            world.params.update(expected_status=part["expected_status"], status_kind=spec["status_kind"])
            notes.append(f"{part['key']}: " + world.status_check(tables, events, truth, world.naive_answer(tables), tol))
            expected_parts[part["key"]] = {"expected_status": part["expected_status"]}
        else:
            full = world.compute(tables, events)
            assert abs(full - truth) <= tol, f"{spec['id']}.{part['key']}: reference {full} disagrees with truth {truth}"
            for name, val in world.ablations(tables, events).items():
                if part.get("ablate") is not None and name not in part["ablate"]:
                    continue
                assert abs(val - truth) > tol, f"{spec['id']}.{part['key']}: skipping '{name}' still passes ({val} vs {truth})"
            if hasattr(world, "clean_check_answer") or not spec.get("controls"):
                assert abs(world.naive_answer(tables) - truth) > tol or spec.get("controls"), f"{spec['id']}.{part['key']}: naive passes"
            expected_parts[part["key"]] = {"answer": truth, "tolerance_rel": tol_rel}
            notes.append(f"{part['key']}: truth={truth}")
        sols[part["key"]] = world.solve_code(events)
    scored = spec.get("scored_traps")
    expected = {"parts": expected_parts,
                "traps": [] if spec.get("controls") else [{"id": e.trap_id, "keywords": e.keywords} for e in events if not scored or e.trap_id in scored]}
    sa = sols["a"].replace("/app/answer.json", "/app/.part_a.json").replace("#!/bin/bash\n", "", 1)
    sb = sols["b"].replace("/app/answer.json", "/app/.part_b.json").replace("#!/bin/bash\n", "", 1)
    task_writer.write(spec, files, expected, "#!/bin/bash\n" + sa + sb + MERGE, out_root)
    print(f"built {spec['id']} (stacked): " + "; ".join(notes))


def build_one(spec_path, out_root):
    spec = tomllib.loads(spec_path.read_text())
    if spec.get("parts"):
        return build_stacked(spec, out_root)
    wp = dict(spec["world_params"])
    if "window_end" in spec:
        wp["window_end"] = spec["window_end"]
    if "window_start" in spec:
        wp["window_start"] = spec["window_start"]
    if "window_tz" in spec:
        wp["window_tz"] = spec["window_tz"]
    if "expected_status" in spec:
        wp["expected_status"] = spec["expected_status"]
    if "low_ratio" in spec:
        wp["low_ratio"] = spec["low_ratio"]
    if "status_kind" in spec:
        wp["status_kind"] = spec["status_kind"]
    world = WORLDS[spec["world"]](spec["seed"], wp)
    events = [change_events.build_event(e) for e in spec["change_events"]]
    tables, files = Recorder(world, events, spec["seed"]).record()
    files.update(clue_placer.place(events, world.filler_files()))
    truth_pre = world.truth()
    if "events" in tables:  # id integrity: documented unique ids must really be unique
        eids = [e["event_id"] for e in tables["events"]]
        rids = [e["request_id"] for e in tables["events"]]
        assert len(set(eids)) == len(eids), f"{spec['id']}: duplicate event_id"
        if not any(e.trap_id == "duplicate_retries" for e in events):
            assert len(set(rids)) == len(rids), f"{spec['id']}: duplicate request_id without a retries event"
    if "assignments" in tables and not any(e.trap_id == "reassignment" for e in events):
        uids = [a["user_id"] for a in tables["assignments"]]
        assert len(set(uids)) == len(uids), f"{spec['id']}: duplicate assignment rows without a reassignment event"
    scored = spec.get("scored_traps")  # restrict which trap ids are scored via flags
    if hasattr(world, "ablations") and spec.get("expected_traps") != [] and not spec.get("expected_status"):
        full = world.compute(tables, events)
        assert abs(full - truth_pre) <= max(spec.get("tolerance_rel", 0) * abs(truth_pre), spec.get("tolerance_abs", 0)), \
            f"{spec['id']}: reference computation {full} disagrees with truth {truth_pre}"
        tol_pre = max(spec.get("tolerance_rel", 0) * abs(truth_pre), spec.get("tolerance_abs", 0))
        for name, val in world.ablations(tables, events).items():
            if spec.get("ablate") is not None and name not in spec["ablate"]:
                continue
            assert abs(val - truth_pre) > tol_pre, f"{spec['id']}: skipping '{name}' still passes ({val} vs {truth_pre})"
    if hasattr(world, "validate") and spec.get("validate", True) and not spec.get("expected_status"):
        world.validate(tables, events, clean=spec.get("expected_traps") == [])
    truth, naive = world.truth(), world.naive_answer(tables)
    tol_rel, tol_abs = spec.get("tolerance_rel", 0), spec.get("tolerance_abs", 0)
    tol = max(tol_rel * abs(truth), tol_abs)
    clean = spec.get("expected_traps") == []  # trap-free question (paired clean task)
    status = spec.get("expected_status")
    if status and hasattr(world, "status_check"):
        msg = world.status_check(tables, events, truth, naive, tol)
        traps = [{"id": e.trap_id, "keywords": e.keywords} for e in events if not scored or e.trap_id in scored]
        task_writer.write(spec, files, {"expected_status": status, "traps": traps}, world.solve_code(events), out_root)
        print(f"built {spec['id']}: expected_status={status} {msg}")
        return
    if status:
        def chi(rows):
            n = {"control": 0, "treatment": 0}
            for a in rows:
                n[a["arm"]] += 1
            return n, (n["treatment"] - n["control"]) ** 2 / (n["treatment"] + n["control"])
        n, chi2 = chi(tables["assignments"])
        if spec.get("raw_balanced"):  # skew is hidden until the bots are removed
            assert chi2 < 6, f"{spec['id']}: raw split is not balanced (chi2={chi2:.1f})"
        bots = set().union(*[getattr(e, "bot_ids", set()) for e in events])
        first = {}
        for a in sorted(tables["assignments"], key=lambda r: r["assigned_at"]):
            first.setdefault(a["user_id"], a)
        n, chi2 = chi([a for u, a in first.items() if u not in bots])
        assert chi2 > 30, f"{spec['id']}: split is not skewed enough (chi2={chi2:.1f})"
        assert abs(naive - truth) > tol, f"{spec['id']}: biased lift {naive} is close to the clean lift {truth}"
        expected = {"expected_status": status, "traps": [{"id": e.trap_id, "keywords": e.keywords} for e in events]}
        task_writer.write(spec, files, expected, world.solve_code(events), out_root)
        print(f"built {spec['id']}: expected_status={status} split={n} chi2={chi2:.0f} biased_lift={naive} clean_lift={truth}")
        return
    if clean:
        chk = world.clean_check_answer(tables, events) if hasattr(world, "clean_check_answer") else naive
        assert abs(chk - truth) <= tol, f"{spec['id']}: window is not clean (check={chk} truth={truth})"
    else:
        assert abs(naive - truth) > tol, f"{spec['id']}: naive answer passes, trap is not real"
    expected = {"answer": truth, "tolerance_rel": tol_rel, "tolerance_abs": tol_abs,
                "traps": [] if clean else [{"id": e.trap_id, "keywords": e.keywords} for e in events if not scored or e.trap_id in scored]}
    msg = f"truth={truth} naive={naive}"
    if hasattr(world, "overcorrect_answer") and spec.get("decoy", True):
        oc = world.overcorrect_answer(tables)
        assert abs(oc - truth) > tol, f"{spec['id']}: decoy does not bite (overcorrect={oc} truth={truth})"
        expected["overcorrect_answer"] = oc
        msg += f" overcorrect={oc}"
    task_writer.write(spec, files, expected, world.solve_code(events), out_root)
    print(f"built {spec['id']}: {msg}")


def main():
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else ROOT / "tasks"
    specs = Path(sys.argv[sys.argv.index("--specs") + 1]) if "--specs" in sys.argv else ROOT / "generator/specs"
    for p in sorted(specs.glob("*.toml")):
        build_one(p, out)
    if "--no-check" in sys.argv:
        return
    sys.exit(subprocess.call([str(ROOT / "scripts/check_solutions.sh")]))


if __name__ == "__main__":
    main()
