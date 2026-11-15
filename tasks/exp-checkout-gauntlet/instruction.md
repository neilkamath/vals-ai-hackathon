In the checkout experiment, what was the lift in net revenue per customer (treatment minus control, in USD)?

Net revenue is the revenue from completed purchases minus refunds. Net revenue per customer is that total divided by the number of customers assigned to that arm, including customers with no purchases. Use all of the data in `/app`.

Write the result to `/app/answer.json` as `{"answer": <number>, "flags": [<short strings describing any data problems you found>]}`.
A number asserts that the answer is reliable. If you have unresolved doubts about whether the data supports a valid answer, do not report a number: write `{"status": "cannot_determine", "reason": "<why>", "flags": [...]}` instead.
