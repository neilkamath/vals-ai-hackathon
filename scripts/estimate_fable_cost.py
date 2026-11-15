"""Fill in cost for Fable 5.2 attempts, whose runs had cost tracking off, from the logged token usage.

Assumed list price (third-party pages, not verified against Anthropic's own page): $8 / $40 per million input / output tokens,
cache writes at 1.25x input, cache reads at 0.1x input. The result is an estimate and is labelled as one in the README.
"""
import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IN, OUT, WRITE, READ = 8e-6, 40e-6, 8e-6 * 1.25, 8e-6 * 0.1


def attempt_cost(run_id, task):
    for f in glob.glob(str(ROOT / "results" / "raw" / run_id / task / "agent_output" / "logs" / "mini_swe_agent" / "trajectory.json")):
        total = 0.0
        for m in json.load(open(f))["messages"]:
            u = (m.get("extra") or {}).get("response", {}).get("usage")
            if m.get("role") != "assistant" or not u:
                continue
            d = u.get("prompt_tokens_details") or {}
            read, write = d.get("cached_tokens") or 0, d.get("cache_creation_tokens") or 0
            fresh = max(u["prompt_tokens"] - read - write, 0)
            total += fresh * IN + write * WRITE + read * READ + u["completion_tokens"] * OUT
        return round(total, 4)


def main():
    p = ROOT / "results" / "attempts.jsonl"
    rows = [json.loads(l) for l in open(p)]
    n = 0
    for r in rows:
        if r["model"] == "anthropic/claude-fable-5-2" and not r.get("cost"):
            c = attempt_cost(r["run_id"], r["task"])
            if c:
                r["cost"] = c
                n += 1
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    print("estimated cost for", n, "Fable attempts")


if __name__ == "__main__":
    main()
