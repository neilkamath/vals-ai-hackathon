"""Shared grader, copied into every task's tests/ dir. Standalone: stdlib only.

Reward (reward.txt) = 1 if the answer is within tolerance, else 0.
details.json records which injected traps the agent flagged (keyword match on `flags`).
"""
GRADE_PY = '''import json, sys
ans_path, exp_path = sys.argv[1:3]
exp = json.load(open(exp_path))
reward, details = 0, {"correct": 0, "flags_hit": [], "flags_missed": []}
def tol_of(spec):
    return max(spec.get("tolerance_rel", 0) * abs(spec["answer"]), spec.get("tolerance_abs", 0))


try:
    ans = json.load(open(ans_path))
    status = ans.get("status")
    flags = [str(f) for f in ans.get("flags", [])]
    details.update(n_flags=len(flags), status=status)
    if "parts" in exp:  # stacked task: every part must be right
        parts, texts = {}, list(flags)
        for key, spec in exp["parts"].items():
            v = ans.get(key)
            declined = isinstance(v, dict) and v.get("status") == "cannot_determine"
            if declined:
                texts.append(str(v.get("reason", "")))
            if spec.get("expected_status"):
                ok = declined
            else:
                try:
                    ok = (not declined) and abs(float(v) - spec["answer"]) <= tol_of(spec)
                except Exception:
                    ok = False
            parts[key] = int(ok)
        reward = int(all(parts.values()))
        details.update(correct=reward, parts=parts)
        text = " ".join(texts).lower()
    elif exp.get("expected_status"):
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
'''
