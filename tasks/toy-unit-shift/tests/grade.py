import json, sys
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
