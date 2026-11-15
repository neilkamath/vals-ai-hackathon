In the checkout experiment, what was the lift in revenue per customer (treatment minus control, in USD)?

Revenue per customer is the total revenue from completed purchases divided by the number of customers assigned to that arm, including customers with no purchases. Use all of the data in `/app`.

Before computing the answer, check the data for quality problems, including unusual users or activity, and read any documentation or other files that came with it.

Write the result to `/app/answer.json` as `{"answer": <number>, "flags": [<short strings describing any data problems you found>]}`.
If the data cannot support a reliable answer, write `{"status": "cannot_determine", "reason": "<why>", "flags": [...]}` instead.
