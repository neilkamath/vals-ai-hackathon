# Energy Meter Reliability

> **Overview: to be written by the author.**
> The hackathon requires this first paragraph to be entirely human-written, so it is intentionally left empty.

**Frontier models fix the data, then fail to refuse.**
On tasks where the honest answer is to decline, the best model (Opus 5.5) passes 42%.

## What it tests

Each task gives an agent the hourly readings from one commercial site's electricity meter and one plain question, usually "what was November's total consumption in kWh?".
Some tasks hide recording problems that the site's documents explain and that the agent can fix.
Others hide a fault that nothing documents and that cannot be repaired, such as a day where the sensor under-reads.
There the correct output is `cannot_determine`, because any number would be silently wrong.

| Group | Tasks | What the agent must do | Right output |
|---|---|---|---|
| Fixable problems | 5 | handle register rollover, a CT-ratio change, UTC records for a local month across DST, a meter replacement, and a paged `meterctl` data tool (a ladder from 1 to 4 problems) | the corrected total |
| Silent faults | 6 | the same fixes, plus an undocumented fault: a holiday day that under-reads (three seeds, behind a meter swap, through the tool) or a frozen register at month end | `cannot_determine` |
| Clean controls | 2 | answer when the data fully supports it, including a genuinely low holiday day | the total |

The truth is known by construction: a seeded generator simulates the site's real consumption, computes the answer, and only then corrupts the recorded data.
Every task ships a reference solution that must pass its grader.

## Results (13 core tasks, mini-SWE-agent through Valkyrie on Modal)

| Model | Accuracy (±SE) | Fixable | Decline | Controls | Cost / attempt | Attempts |
|---|---|---|---|---|---|---|
| Opus 5.5 | 73.1% (±12.2) | 100% | 42% | 100% | $0.104 | 16 |
| Sonnet 5.5 | 69.2% (±12.1) | 100% | 33% | 100% | $0.059 | 18 |
| gpt-5.4 | 42.3% (±13.7) | 70% | 17% | 50% | $0.076 | 18 |
| gpt-5.2 | 15.4% (±10.4) | 20% | 0% | 50% | $0.064 | 13 |
| Haiku 4.5 | 7.7% (±7.7) | 20% | 0% | 0% | $0.120 | 13 |

Accuracy is the mean pass rate over the 13 tasks, with 1 to 3 attempts per task and model.
Opus and Sonnet overlap within noise, so we do not rank them against each other.

Findings in brief:

- Fixing documented problems is easy for frontier models; declining on an undocumented fault is not.
- Noticing is not acting: on readable failed decline attempts, Sonnet and Opus usually mentioned the odd day, then explained it away with the README's "reduced load" wording and reported a number.
- The difficulty holds on fresh public seeds and on four private held-out tasks, which are kept out of this repository.

The full results page (cost vs accuracy chart, leaderboard, example walkthrough, method and caveats) is built locally with `python3 scripts/make_cost_accuracy_page.py`, which writes `results/draft/index.html`.
Curated tables and charts are in `results/curated/`.

## How to run

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), and the Valkyrie CLI (`uv tool install valkyrie-cli`, then `valkyrie login`).

```bash
# Rebuild the 13 tasks from their specs and check every reference solution passes
python3 -m generator.build

# Confirm a fresh build is byte-identical to tasks/
./scripts/check_reproducible.sh

# Publish the tasks as a dataset and run an agent on them
valkyrie dataset push my-benchmark/energy-core ./tasks --tag v1
valkyrie run start --agent mini_swe_agent --dataset my-benchmark/energy-core@v1 \
  --model anthropic/claude-sonnet-5-5 --provider modal \
  -s ANTHROPIC_API_KEY anthropic-api-key -k step_limit 80 --concurrency 4

# Free sanity check: run every task's reference solution in the sandbox
valkyrie run start --agent oracle --dataset my-benchmark/energy-core@v1 --provider modal
```

The pinned dataset used for the results is `silent-errors/energy-core@v1` (digest `f6cfc94e1c4f`).
Some results were recorded on earlier pinned versions containing the same task data.

## Repository layout

- `generator/`: the seeded task generator (`core/` events, grading and task writer; `worlds/` meter simulations; `specs/` the 13 core task specs; `specs/dev/` exploratory tasks not in the core set).
- `tasks/`: the generated tasks in Harbor format (`instruction.md`, `environment/`, `tests/`, `solution/`).
- `scripts/`: reference-solution and reproducibility checks, result collection, and report and page builders.
- `results/curated/`: result tables and charts.

## Run IDs

Valkyrie run IDs behind the core results:

- Opus 5.5: `79e782c2-c232-48d5-9cec-cd790cb91e06`, `b3189fb9-4583-47f5-966d-be1574e82178`, `d1067a8e-ad62-4f4b-be51-292a47e628aa`, `e9c02e8c-0bc3-4f5e-81b7-3b498453e691`, `ebb29180-c9e3-4da0-96ef-f16c6f3a091b`
- Sonnet 5.5: `1615704a-f4fc-46d2-86a9-1ddd6106e7c8`, `4a7ce789-a78f-4b20-9025-bcf4e8f37170`, `5ad65fc9-4e00-415b-8c94-264311eb2947`, `8eab20ef-3802-4a22-ae06-18360184bf01`, `9b84402e-aee5-4706-a15c-78239edd8de0`, `e88a099b-95be-4bb0-a987-64ca61ae5e4a`
- gpt-5.4: `505bad60-720a-4aa2-8892-516d07595464`, `5b9566fb-d52c-4953-943b-d4fce25ef340`, `6c02adf0-796a-48bc-bde7-64fb2bcbbe03`, `9491eed5-465a-45b7-87a5-1b6257651085`, `e9eef9bb-0490-4ef6-b4f9-0980e0dbbf44`, `fed63f77-7ff4-482d-a7f8-9ed6be7c0d59`
- gpt-5.2: `35c3af12-4919-4051-99bf-c3c320187b64`, `e4e5d610-bc02-4418-a3ac-eaa21b86bb95`
- Haiku 4.5: `49003a28-b221-4f99-86e0-d7d35833dc24`, `e4b7d61c-27b6-4280-9736-ecd8136c91c8`

Some of these runs also include tasks outside the core set; only core-task attempts count toward the table above.

## Caveats

- The data is synthetic and modeled on commercial metering; it has not been reviewed by someone from the energy industry.
- Samples are small, and decline grading is binary even though a number with a clear warning is sometimes defensible.
- One harness only, and no human baseline was measured.
