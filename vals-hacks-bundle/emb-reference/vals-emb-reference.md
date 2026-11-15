# Reference: Vals AI "Excel Modeling Benchmark" (EMB) v1.1

Source: https://www.vals.ai/benchmarks/emb-v1-1 (page dated Nov 11, 2026; captured Nov 14, 2026 via browser).
Why this file exists: it is a Vals-built benchmark, so it shows how Vals presents and justifies a benchmark. Use it as a model for *our* README, results, and demo. It is NOT the thing we are building.

Data files (same folder as this doc, under `data/`):
- `emb_v1_1_leaderboard.csv`: rank, model, slug, accuracy, cost/test, tokens/test, duration/test, template accuracy, scratch accuracy, avg turns
- `emb_v1_1_category_scores.csv`: per-model score in each of 7 categories
- `emb_v1_1_scratch_rubric.csv`: per-model numerical / formula / presentation scores

Everything below is paraphrased from the page (not verbatim), apart from numbers.

## What EMB is

A benchmark of whether agents can build complete Excel financial models of the kind junior investment-banking / private-equity analysts make. Each task gives a written business scenario plus source files and asks for the whole workbook (tabs, structure, formulas, formatting). Requirements include: opens cleanly in Excel, circular references handled, one-input case toggles (base/bull/bear) that flip the whole model, and input changes propagating end to end. Vals states each model would take a human expert at least 5 hours from scratch.

## Dataset and splits

- 103 expert-authored, peer-reviewed questions, each with a gold-standard Excel model and a detailed rubric.
- Splits: Public (1 task open-sourced), Private Validation (51, licensable), Test (51). **All reported results use only the held-out Test set** to prevent overfitting.
- Seven categories: LBO, DCF, M&A, Operating models, Comps spreads, Dataroom summaries, Misc (13-week cash flow, equity waterfall returns, project finance, multi-tranche returns). Overall accuracy = mean within category, then the seven categories weighted equally.
- No code repo or downloadable dataset is linked; the dataset is proprietary.

## Two evaluation modes (a design pattern worth copying)

- **Template mode:** agent fills a provided skeleton workbook. Graded by exact cell match against the gold model. Objective, no judge.
- **Scratch mode:** agent builds from nothing. Graded by a partial-credit rubric with three check types: numerical (values match truth), formula (cells wired to correct inputs), presentation (banking conventions: color coding, number formats, source citations). An agentic LLM judge (GPT-6 Luna) evaluates each check and returns reasoning plus pass/fail.
- Both modes recalculate all formulas through a real Excel engine before grading. A subset of tasks must be correct across all case toggles.

## Harness / methodology

- Shared harness. Nearly all work goes through two tools: `bash` (read inputs, write workbook) and `execute` (open and recalculate to verify). Other tools exist (web search, SEC filing search, price history, retrieve/parse) but are used sparingly because tasks ship their own data. A `submit` tool finalizes the workbook.
- Wall-clock cap per run is 3.5 hours, described as intentionally generous; most runs finish far earlier.
- Authoring process: an expert writes the Gold model first; the Template is made by stripping all values and formulas from the Gold.

## Headline results (Test set)

- Top: Claude Fable 5.2 at 77.38%, then Claude Fable 5.1 at 76.73%, Gemini 4 Carbon at 76.47%, Claude Sonnet 5.5 at 75.90%, Claude Opus 5.5 at 75.84%. 42 models listed; the lowest is 40.82%. Cost per test ranges from $0.09 to $15.93 (one model has no cost listed).
- Vals cautions that partial credit means high scores are substantial but incomplete work, not client-ready deliverables.
- Categories: nearly every model is strongest on Dataroom Summaries (mean about 83) and weakest on LBO (mean about 57). Vals's explanation: LBO and DCF are long chains of linked calculations so errors propagate; dataroom tasks are more summarization so errors stay local.
- Scratch rubric: formula and presentation checks pass far more often than numerical checks. Reason given: a formula can point at the right cells and still compute a wrong value if an upstream input is wrong.
- Template vs Scratch: 37 of 42 models score higher in Template than Scratch (computed from the data file). Scratch beats Template only for Qwen 3.8 Max, DeepSeek V4 Pro 0813, Mercury 3, Inkling, and Inkling Small.
- Generation is front-loaded: models write most of the workbook early, then taper to small edits and checks.
- v1.1 vs v1.0: Scratch judge changed from GPT 5.4 Mini to GPT-6 Luna plus a Template cell-matching fix across sheet names; v1.1 scores are not comparable to v1.0.

## The page's charts and tables (what each one shows)

The charts are interactive and have no downloadable images. Data captured where marked.
1. **Pareto chart:** accuracy vs cost (and latency), log scale, 20 models shown (latest, top, and frontier), filterable by lab. Underlying numbers: leaderboard CSV.
2. **Leaderboard table:** accuracy, cost, tokens, duration per test. In the leaderboard CSV.
3. **Reasoning-effort chart:** accuracy at three reasoning settings for 8 models, with +/-1 standard error bars. **Not captured** (data not in the main data file).
4. **Category table:** heat-mapped scores for 7 categories. In the category CSV.
5. **Scratch rubric table:** numerical / formula / presentation. In the rubric CSV (transcribed from the page text; not cross-checked against a data file).
6. **Template vs Scratch bar chart:** in the leaderboard CSV (template and scratch columns, from the page data file).
7. **Tokens-per-turn table with sparklines:** per-turn output volume over a run. Only the averages shown on the page; sparkline data **not captured**.
8. **Tool-calls chart:** average turns, tool calls, and tool-call errors per task. Avg turns are in the leaderboard CSV; tool call and error counts **not captured**.

## The example task (structure only)

The page shows one public Dataroom Summaries task: an associate at a PE firm receives a SaaS company's customer data cube and must build a customer-retention workbook with four named tabs. The prompt is long and highly specific: it names exact tabs, exact metric definitions (e.g. how gross and net retention are computed), cohort rules, checks that tie out to other tabs, and a detailed formatting spec (color conventions, number formats, prefixes). Sample rubric checks shown are one numerical (a specific dollar value for a cohort), one formula (a retention formula), and two presentation checks. Takeaway: the task text defines every metric precisely so rubric checks are objective.

## Patterns to borrow for our README, results, and demo

1. **Justify difficulty with a human-effort statement** (their "5+ hours for an expert").
2. **Report only on a held-out split** and say so; mention a public sample task.
3. **Two grading modes**: one exact/objective, one partial-credit. For us: exact-match answer vs flags found.
4. **Break results down by category** and explain *why* categories differ.
5. **Report cost, tokens, and duration** next to accuracy, plus an accuracy-vs-cost chart.
6. **Show a reasoning-effort ablation** with error bars. For us: hinted vs un-hinted runs.
7. **Show tool usage / error stats**, and explain the harness and why it was chosen.
8. **Define every metric precisely in the task text** so grading is objective.
9. **Version the benchmark** and note when scores are not comparable across versions.
10. **State honest caveats** (partial credit is not "done").
11. **Use a rubric split into check types** to show *where* models fail (numbers vs wiring vs presentation); this maps to our detect-vs-fix gap.

## Caveats about this capture

- Figures are from the page as of Nov 11, 2026 and may change.
- The leaderboard, category, and Template/Scratch numbers were cross-checked against the page's own data file; the scratch-rubric table was transcribed from page text only.
- Display names: "Qwen 3.8 Max 0902" corresponds to slug `alibaba/qwen3.8-max-internal`; "Mistral Large 4 Preview" to `mistralai/mistral-large-4`; "Mistral Large 4" to `mistralai/mistral-large-4-oss` (matched by accuracy values).
