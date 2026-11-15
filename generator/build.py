"""Build all tasks from generator/specs/*.toml into tasks/. Fails loudly on any check.

Usage: python3 -m generator.build [--out tasks]
"""
import subprocess
import sys
import tomllib
from pathlib import Path

from .core import change_events, clue_placer, task_writer
from .core.recorder import Recorder
from .worlds.experiment import ExperimentWorld
from .worlds.toy_orders import ToyOrdersWorld

WORLDS = {"toy_orders": ToyOrdersWorld, "experiment": ExperimentWorld}
ROOT = Path(__file__).resolve().parent.parent


def build_one(spec_path, out_root):
    spec = tomllib.loads(spec_path.read_text())
    wp = dict(spec["world_params"])
    if "window_end" in spec:
        wp["window_end"] = spec["window_end"]
    if "expected_status" in spec:
        wp["expected_status"] = spec["expected_status"]
    world = WORLDS[spec["world"]](spec["seed"], wp)
    events = [change_events.build_event(e) for e in spec["change_events"]]
    tables, files = Recorder(world, events, spec["seed"]).record()
    files.update(clue_placer.place(events, world.filler_files()))
    if "events" in tables:  # id integrity: documented unique ids must really be unique
        eids = [e["event_id"] for e in tables["events"]]
        rids = [e["request_id"] for e in tables["events"]]
        assert len(set(eids)) == len(eids), f"{spec['id']}: duplicate event_id"
        if not any(e.trap_id == "duplicate_retries" for e in events):
            assert len(set(rids)) == len(rids), f"{spec['id']}: duplicate request_id without a retries event"
    truth, naive = world.truth(), world.naive_answer(tables)
    tol_rel, tol_abs = spec.get("tolerance_rel", 0), spec.get("tolerance_abs", 0)
    tol = max(tol_rel * abs(truth), tol_abs)
    clean = spec.get("expected_traps") == []  # trap-free question (paired clean task)
    status = spec.get("expected_status")
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
            n, chi2 = chi([a for a in tables["assignments"] if a["user_id"] not in bots])
        assert chi2 > 30, f"{spec['id']}: split is not skewed enough (chi2={chi2:.1f})"
        assert abs(naive - truth) > tol, f"{spec['id']}: biased lift {naive} is close to the clean lift {truth}"
        expected = {"expected_status": status, "traps": [{"id": e.trap_id, "keywords": e.keywords} for e in events]}
        task_writer.write(spec, files, expected, world.solve_code(events), out_root)
        print(f"built {spec['id']}: expected_status={status} split={n} chi2={chi2:.0f} biased_lift={naive} clean_lift={truth}")
        return
    if clean:
        assert abs(naive - truth) <= tol, f"{spec['id']}: window is not clean (naive={naive} truth={truth})"
    else:
        assert abs(naive - truth) > tol, f"{spec['id']}: naive answer passes, trap is not real"
    expected = {"answer": truth, "tolerance_rel": tol_rel, "tolerance_abs": tol_abs,
                "traps": [] if clean else [{"id": e.trap_id, "keywords": e.keywords} for e in events]}
    msg = f"truth={truth} naive={naive}"
    if hasattr(world, "overcorrect_answer"):
        oc = world.overcorrect_answer(tables)
        assert abs(oc - truth) > tol, f"{spec['id']}: decoy does not bite (overcorrect={oc} truth={truth})"
        expected["overcorrect_answer"] = oc
        msg += f" overcorrect={oc}"
    task_writer.write(spec, files, expected, world.solve_code(events), out_root)
    print(f"built {spec['id']}: {msg}")


def main():
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else ROOT / "tasks"
    for p in sorted((ROOT / "generator/specs").glob("*.toml")):
        build_one(p, out)
    sys.exit(subprocess.call([str(ROOT / "scripts/check_solutions.sh")]))


if __name__ == "__main__":
    main()
