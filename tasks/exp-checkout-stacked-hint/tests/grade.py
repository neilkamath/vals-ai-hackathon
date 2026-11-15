import json, sys
ans_path, exp_path = sys.argv[1:3]
exp = json.load(open(exp_path))
reward, details = 0, {"correct": 0, "flags_hit": [], "flags_missed": []}
try:
    ans = json.load(open(ans_path))
    status = ans.get("status")
    flags = [str(f) for f in ans.get("flags", [])]
    details.update(n_flags=len(flags), status=status)
    if exp.get("expected_status"):
        reward = int(status == exp["expected_status"])
        details["correct"] = reward
        text = " ".join(flags + [str(ans.get("reason", ""))]).lower()
    elif status == "cannot_determine":
        details["abstained"] = 1  # abstained on an answerable task
        text = " ".join(flags + [str(ans.get("reason", ""))]).lower()
    else:
        a = float(ans["answer"])
        tol = max(exp.get("tolerance_rel", 0) * abs(exp["answer"]), exp.get("tolerance_abs", 0))
        reward = int(abs(a - exp["answer"]) <= tol)
        details.update(correct=reward, answer=a)
        oc = exp.get("overcorrect_answer")
        details["overcorrected"] = int(oc is not None and not reward and abs(a - oc) <= tol)
        text = " ".join(flags).lower()
    for t in exp.get("traps", []):
        hit = any(k in text for k in t["keywords"])
        details["flags_hit" if hit else "flags_missed"].append(t["id"])
except Exception as e:
    details["error"] = repr(e)
print(json.dumps(details))
open("/logs/verifier/reward.txt", "w").write(str(reward))
open("/logs/verifier/details.json", "w").write(json.dumps(details))
