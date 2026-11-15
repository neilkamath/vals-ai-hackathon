#!/bin/bash
# Local check: run each task's solution/solve.sh against its grader, no containers.
# Fails loudly if any task does not pass. Layout is emulated with temp dirs.
set -u
root="$(cd "$(dirname "$0")/.." && pwd)"
fail=0
tasks_dir="${TASKS_DIR:-$root/tasks}"
for t in "$tasks_dir"/*/; do
  id=$(basename "$t"); w=$(mktemp -d)
  mkdir -p "$w/app" "$w/logs/verifier" "$w/tests"
  cp -r "$t"environment/data/. "$w/app/"; cp -r "$t"tests/. "$w/tests/"
  # tasks served through a tool: install it into a temp bin dir
  if [ -d "$t"environment/service ]; then
    mkdir -p "$w/service" "$w/bin"; cp -r "$t"environment/service/. "$w/service/"
    cp "$w/service/meterctl" "$w/bin/meterctl"; chmod +x "$w/bin/meterctl"
    export METER_DIR="$w/service" METER_STATE="$w/meter.state" PATH="$w/bin:$PATH"
  fi
  # rewrite absolute container paths to the temp sandbox
  sed "s#/app#$w/app#g" "$t"solution/solve.sh | bash
  sed "s#/app#$w/app#g; s#/tests#$w/tests#g; s#/logs#$w/logs#g" "$t"tests/test.sh > "$w/test_local.sh"
  sed "s#/logs#$w/logs#g" "$t"tests/grade.py > "$w/tests/grade.py"
  bash "$w/test_local.sh" >/dev/null
  r=$(cat "$w/logs/verifier/reward.txt" 2>/dev/null)
  missed=$(python3 -I -c "import json,sys;print(len(json.load(open(sys.argv[1]))['flags_missed']))" "$w/logs/verifier/details.json" 2>/dev/null)
  if [ "$r" = "1" ] && [ "$missed" = "0" ]; then echo "PASS $id"; else echo "FAIL $id (reward=$r, traps unflagged=$missed)"; fail=1; fi
  rm -rf "$w"
done
exit $fail
