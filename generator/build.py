"""Build all tasks from generator/specs/*.toml into tasks/. Fails loudly on any check.

Usage: python3 -m generator.build [--out tasks]
"""
import subprocess
import sys
import tomllib
from pathlib import Path

from .core import change_events, clue_placer, task_writer
from .core.recorder import Recorder
from .worlds.toy_orders import ToyOrdersWorld

WORLDS = {"toy_orders": ToyOrdersWorld}
ROOT = Path(__file__).resolve().parent.parent


def build_one(spec_path, out_root):
    spec = tomllib.loads(spec_path.read_text())
    world = WORLDS[spec["world"]](spec["seed"], spec["world_params"])
    events = [change_events.build_event(e) for e in spec["change_events"]]
    rows, files = Recorder(world, events).record()
    files.update(clue_placer.place(spec["clue"], events))
    truth = world.truth()
    naive = world.naive_answer(rows)
    tol = spec["tolerance_rel"]
    assert abs(naive - truth) > tol * abs(truth), f"{spec['id']}: naive answer passes, trap is not real"
    expected = {"answer": truth, "tolerance_rel": tol, "traps": spec["traps"]}
    task_writer.write(spec, files, expected, world.solve_code(events), out_root)
    print(f"built {spec['id']}: truth={truth} naive={naive}")


def main():
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else ROOT / "tasks"
    for p in sorted((ROOT / "generator/specs").glob("*.toml")):
        build_one(p, out)
    sys.exit(subprocess.call([str(ROOT / "scripts/check_solutions.sh")]))


if __name__ == "__main__":
    main()
