"""Collect per-attempt results for the runs listed in results/manifest.jsonl into results/attempts.jsonl.

manifest line: {"id": "<run id>", "label": "...", "model": "...", "harness": "...", "stage": "..."}
For each task attempt we keep: reward, verifier details (flags hit/missed, abstained, over-corrected, status),
cost and number of model calls (from the downloaded agent logs), and a failure label.
"""
import glob
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "results" / "raw"


def sh(*args, timeout=120):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        print("timed out, skipping:", " ".join(args[:4]))
        return None


def cost_calls(run_id, task):
    base = RAW / run_id
    for pat in (f"{task}/agent_output/logs/mini_swe_agent/trajectory.json", f"{task}/mini_swe_agent/trajectory.json"):
        for f in glob.glob(str(base / pat)):
            try:
                st = json.load(open(f))["info"]["model_stats"]
                return round(st["instance_cost"], 4), st["api_calls"]
            except Exception:
                pass
    for f in glob.glob(str(base / task / "agent_output" / "logs" / "metrics_total.json")):
        try:
            d = json.load(open(f))
            c = d["cost"]
            c = c["total"] if isinstance(c, dict) else c
            return round(float(c), 4), None
        except Exception:
            pass
    return None, None


def label(task_expects_status, reward, d):
    if reward == 1:
        return "pass"
    hit, missed = d.get("flags_hit", []), d.get("flags_missed", [])
    if task_expects_status:
        if d.get("status") == "cannot_determine":
            return "wrong_status"
        return "detected_but_reported_number" if hit else "never_detected"
    if d.get("abstained"):
        return "over_abstained"
    if d.get("overcorrected"):
        return "over_corrected"
    if "error" in d:
        return "format_error"
    if hit and missed:
        return "partial_fix"
    if hit and not missed:
        return "flagged_all_but_wrong_number"
    return "no_fix"


def main():
    manifest = [json.loads(l) for l in open(ROOT / "results" / "manifest.jsonl") if l.strip()]
    done = set()
    out_path = ROOT / "results" / "attempts.jsonl"
    rows = [json.loads(l) for l in open(out_path)] if out_path.exists() else []
    done = {r["run_id"] for r in rows}
    for m in manifest:
        rid = m["id"]
        if rid in done:
            continue
        res = ROOT / "results" / "raw" / f"{rid}.json"
        res.parent.mkdir(parents=True, exist_ok=True)
        sh("valkyrie", "run", "results", rid, "--path", str(res))
        if not res.exists():
            print("no results yet for", rid, m["label"]); continue
        data = json.load(open(res))
        if data.get("status") != "FINISHED":
            print("not finished:", rid, m["label"], data.get("status")); continue
        sh("valkyrie", "run", "outputs", rid, "--output-dir", str(RAW / rid))
        for task, ev in data["evaluation_results"].items():
            vo = ev.get("metadata", {}).get("verifier_output", "") or ""
            try:
                d = json.loads(vo.strip().splitlines()[-1]) if vo.strip() else {}
            except Exception:
                d = {}
            reward = ev["rewards"]["reward"]
            expects_status = "status" in d and d.get("status") is not None or task in m.get("status_tasks", [])
            cost, calls = cost_calls(rid, task)
            rows.append({"run_id": rid, "label": m["label"], "model": m["model"], "harness": m["harness"],
                         "stage": m.get("stage"), "task": task, "reward": reward, "details": d,
                         "cost": cost, "calls": calls})
        print("collected", rid, m["label"])
    # failure labels (needs to know which tasks expect a status: read it from the task's expected.json)
    for r in rows:
        exp = json.load(open(ROOT / "tasks" / r["task"] / "tests" / "expected.json"))
        r["expects_status"] = bool(exp.get("expected_status"))
        r["failure"] = label(r["expects_status"], r["reward"], r["details"])
    with open(out_path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print("attempts:", len(rows), "total cost so far: $%.2f" % sum(r["cost"] or 0 for r in rows))


if __name__ == "__main__":
    main()
