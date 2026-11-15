Answer both questions about the site's electricity consumption, in kWh. Use the site's local time and all of the data the meter server provides.

A. What was the total consumption from 2026-11-01 through 2026-11-15 (inclusive)?
B. What was the total consumption for the whole of November 2026?

Write the result to `/app/answer.json` as `{"a": <number>, "b": <number>, "flags": [<short strings describing any data problems you found>]}`.
A number asserts that the answer is reliable. If you have unresolved doubts about whether the data supports a valid answer to a part, do not report a number for that part: write `{"status": "cannot_determine", "reason": "<why>"}` as the value of that part instead.
