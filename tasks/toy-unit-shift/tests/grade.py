import json, sys
ans_path, exp_path = sys.argv[1:3]
exp = json.load(open(exp_path))
reward, details = 0, {"correct": 0, "flags_hit": [], "flags_missed": []}
try:
    ans = json.load(open(ans_path))
    a = float(ans["answer"])
    reward = int(abs(a - exp["answer"]) <= exp["tolerance_rel"] * abs(exp["answer"]))
    details.update(correct=reward, answer=a)
    text = " ".join(str(f) for f in ans.get("flags", [])).lower()
    for t in exp.get("traps", []):
        hit = any(k in text for k in t["keywords"])
        details["flags_hit" if hit else "flags_missed"].append(t["id"])
except Exception as e:
    details["error"] = repr(e)
print(json.dumps(details))
open("/logs/verifier/reward.txt", "w").write(str(reward))
open("/logs/verifier/details.json", "w").write(json.dumps(details))
