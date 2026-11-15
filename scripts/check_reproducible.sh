#!/bin/bash
# Rebuild every task from its spec in a temp dir, under two hash seeds, and require tasks/ to be byte-identical.
set -e
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
tmp=$(mktemp -d)
for seed in 0 1; do
  rm -rf "$tmp/out"
  PYTHONHASHSEED=$seed python3 -m generator.build --out "$tmp/out" --no-check > /dev/null
  if ! diff -r -q tasks "$tmp/out" > "$tmp/diff.txt"; then
    echo "NOT REPRODUCIBLE (PYTHONHASHSEED=$seed):"; head "$tmp/diff.txt"; rm -rf "$tmp"; exit 1
  fi
done
rm -rf "$tmp"
echo "reproducible: tasks/ is identical to a fresh build (2 hash seeds)"
