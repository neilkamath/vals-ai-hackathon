#!/bin/bash
# Local check: run each task's solution/solve.sh against its grader, no containers.
# Fails loudly if any task does not pass. Layout is emulated with temp dirs.
set -u
root="$(cd "$(dirname "$0")/.." && pwd)"
fail=0
for t in "$root"/tasks/*/; do
  id=$(basename "$t"); w=$(mktemp -d)
  mkdir -p "$w/app" "$w/logs/verifier" "$w/tests"
  cp -r "$t"environment/data/. "$w/app/"; cp -r "$t"tests/. "$w/tests/"
  # rewrite absolute container paths to the temp sandbox
  sed "s#/app#$w/app#g" "$t"solution/solve.sh | bash
  sed "s#/app#$w/app#g; s#/tests#$w/tests#g; s#/logs#$w/logs#g" "$t"tests/test.sh > "$w/test_local.sh"
  sed "s#/logs#$w/logs#g" "$t"tests/grade.py > "$w/tests/grade.py"
  bash "$w/test_local.sh" >/dev/null
  r=$(cat "$w/logs/verifier/reward.txt" 2>/dev/null)
  if [ "$r" = "1" ]; then echo "PASS $id"; else echo "FAIL $id (reward=$r)"; fail=1; fi
  rm -rf "$w"
done
exit $fail
