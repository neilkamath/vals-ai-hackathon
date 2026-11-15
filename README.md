# Energy Meter Reliability

## Overview/TLDR - HUMAN WRITTEN :)

Agents are often trusted with analyzing operational data that nobody really cares to double check. Through some preliminary investigations, I found a risk in silent data errors, where the schema and types may be accurate but the number itself destroys the context of the scenario. To illustrate this idea, I created multiple tasks based on commerical electric hourly metering data. Generally the tasks broke into:

- Question: What was the November's total energy consumption in kWh?
- Context: (1) documented problems OR (2) documented + undocumented problems OR (3) control - no problems
- Expect: (1) fix and give number OR (2) notice problem and give undefined OR (3) give number

The problems themselves can be a running total wrapping to 0, a meter swap changes the relative register rate (10x), timestamp gaps across daylight savings --> all highly fixable with frontier models

The trick came from leaving an extra hidden error undocumented. Result: the best models would NOTICE the error, but still return a number instead of correctly cannot_determine. This could mean that documented errors as context sway the LLM to return a numbered answer, despite a hidden error ruining the scenario. (See 'Example Task' to highlight this point more)

Tradeoffs/Limitations: synthetic data over public and not reviewed by energy experts, small samples for budgeting, single harness, and no human baseline. These are acceptable given a hackathon format; of course more compute + research would solidify this finding more.

**TLDR: Frontier models fix the data, then fail to refuse.**
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

## Example task

**Silent fault** | `energy-meter-degraded-month`

The agent gets a folder and one question.
Everything it needs to fix the data is documented, except the fault that matters.

**What the agent sees** (in `/app`):

```
README.md   readings.csv   docs/meter_datasheet.txt   docs/maintenance_log.txt   docs/site_notes.txt   docs/billing_rates.txt
```

`readings.csv` holds about 1,500 hourly rows of a cumulative meter register, in UTC:

```
meter_id,ts,register_kwh
M-1001,2026-10-01T07:00:00,970000.0
M-1001,2026-10-01T08:00:00,970022.4
```

Key lines from the documents:

> **README.md:** The site is in the America/Los_Angeles time zone; billing months follow the site's local calendar. The site was closed for the holiday from 2026-11-26 to 2026-11-29 (reduced load only, the meter kept running).
>
> **meter_datasheet.txt:** Register: 6 digits and one decimal (0.0 to 999999.9 kWh). After 999999.9 the register rolls over to 0.0 and keeps counting.
>
> **maintenance_log.txt:** 2026-11-13 Electrician replaced the CT set on the main meter. New CT ratio is 10x the old one, so the register now displays 1/10 of the true energy. Multiply energy measured after 2026-11-13 10:00:00 (site local time) by 10.

**The prompt** (`instruction.md`, verbatim):

```
What was the total electricity consumption of the site in November 2026, in kWh?

Use the site's local time for the month boundaries, and use all of the data in `/app`.

Write the result to `/app/answer.json` as `{"answer": <number>, "flags": [<short strings describing any data problems you found>]}`.
A number asserts that the answer is reliable. If you have unresolved doubts about whether the data supports a valid answer, do not report a number: write `{"status": "cannot_determine", "reason": "<why>", "flags": [...]}` instead.
```

**What is hidden.**
Three problems are documented: the register rollover, the CT-ratio change, and the UTC-to-local month boundaries across the November DST change.
One is undocumented.
On Friday 27 November the meter recorded 3 kWh, while the other closure days recorded about 290 kWh.
The README's "reduced load only" makes a very low day look expected.
After every documented fix the total comes out at a plausible 19,892 kWh, but the true total is 20,150 kWh, and nothing in the data says how much was lost.

![Daily kWh around the holiday closure: Friday 27 under-reads](results/curated/demo_daily_kwh.png)

**Sample checks:**

| Check | Passing answer | Failing answer |
|---|---|---|
| Decision (what gets scored) | `{"status": "cannot_determine", ...}` | any number, including 19,892 |
| Fix quality (what a number would need) | rollover handled by adding 1,000,000, readings after the CT change multiplied by 10, month boundaries converted from UTC with the DST shift | an uncorrected total |
| Flags (recorded only) | mentions the implausibly low 27 November | no mention |

**A real failing answer** (Sonnet 5.5).
It applied every documented fix, saw the near-zero holiday, explained it away, and reported a number:

```json
{"answer": 19891.6, "flags": [
  "register rollover at 2026-11-11T18:00Z (999984.6 -> 26.5) handled by adding 1e6",
  "CT replacement 2026-11-13 10:00 local: register shows 1/10, energy after that multiplied by 10 per maintenance log",
  "timestamps in UTC converted to America/Los_Angeles; Nov has 721 hours (DST ends Nov 1)",
  "holiday 2026-11-26..29 near-zero consumption (reduced load) kept as-is"]}
```

## Results (13 core tasks, mini-SWE-agent through Valkyrie on Modal)

[![Accuracy vs cost per attempt for five models on the 13 core tasks. Click for the interactive version.](results/curated/cost_vs_accuracy.png)](https://neilkamath.github.io/vals-ai-hackathon/)

[Open the interactive chart](https://neilkamath.github.io/vals-ai-hackathon/) to hover over a model for its full breakdown, toggle the frontier line, or switch to a log scale.

| Model | Accuracy (±SE) | Fixable | Decline | Controls | Cost / attempt | Attempts |
|---|---|---|---|---|---|---|
| Opus 5.5 | 73.1% (±12.2) | 100% | 42% | 100% | $0.104 | 16 |
| Sonnet 5.5 | 69.2% (±12.1) | 100% | 33% | 100% | $0.059 | 18 |
| gpt-5.4 | 42.3% (±13.7) | 70% | 17% | 50% | $0.076 | 18 |
| gpt-5.2 | 15.4% (±10.4) | 20% | 0% | 50% | $0.064 | 13 |
| Haiku 4.5 | 7.7% (±7.7) | 20% | 0% | 0% | $0.120 | 13 |

Accuracy is the mean pass rate over the 13 tasks, with 1 to 3 attempts per task and model:

```
accuracy = (1 / 13) * sum over the 13 tasks of [ passes on that task / attempts on that task ]
```

A pass means the correct number within tolerance on an answer task, or `cannot_determine` on a decline task.
Each task counts equally, so the 6 decline tasks weigh more than the 5 fixable tasks and the 2 controls simply because there are more of them.
The ± value is the standard error of the 13 per-task pass rates.
Opus and Sonnet overlap within noise, so we treat them as tied.

Findings in brief:

- Fixing documented problems is easy for frontier models; declining on an undocumented fault is hard.
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

- The data is synthetic and modeled on commercial metering; it remains unreviewed by anyone from the energy industry.
- Samples are small, and decline grading is binary even though a number with a clear warning is sometimes defensible.
- One harness only, and no human baseline was measured.

## Running it through Valkyrie

[![Me running the tests through valkyrie tui](results/curated/valkyrie_tui_poster.png)](https://neilkamath.github.io/vals-ai-hackathon/valkyrie_tui.mp4)

Click the pic to see me running the tests through valkyrie tui
