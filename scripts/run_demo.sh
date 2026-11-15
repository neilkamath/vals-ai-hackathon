#!/bin/bash
# Fresh run of all 13 core tasks on all five models, in parallel, for a live demo in `valkyrie tui`.
# Usage: ./scripts/run_demo.sh [repeats]      (default 1 repeat; each repeat is one run per model)
# Cost: about $5 to $6 per repeat. Run IDs are appended to results/demo_runs.txt (local, git-ignored).
set -e
cd "$(dirname "$0")/.."
REPEATS="${1:-1}"
COMMON="--agent mini_swe_agent --dataset silent-errors/energy-core@v1 --provider modal --concurrency 13 -k step_limit 80 --count $REPEATS -l demo"
mkdir -p results
start() {  # model, extra args...
  local model="$1"; shift
  echo "starting $model ..."
  valkyrie run start $COMMON --model "$model" "$@" 2>&1 | grep -E "Run ID|Error" | tee -a results/demo_runs.txt
}
start anthropic/claude-opus-5-5   -k cost_limit 0.5 -s ANTHROPIC_API_KEY anthropic-api-key
start anthropic/claude-sonnet-5-5 -k cost_limit 0.4 -s ANTHROPIC_API_KEY anthropic-api-key
start anthropic/claude-haiku-4-5  -k cost_limit 0.4 -s ANTHROPIC_API_KEY anthropic-api-key
start openai/gpt-5.4              -k cost_tracking ignore_errors -s OPENAI_API_KEY openai-api-key
start openai/gpt-5.2              -k cost_tracking ignore_errors -s OPENAI_API_KEY openai-api-key
echo "all started: watch them in 'valkyrie tui' (runs labelled 'demo')"
