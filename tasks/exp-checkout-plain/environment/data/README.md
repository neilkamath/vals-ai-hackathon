# Checkout experiment export

Test of a new checkout flow. Users are randomly assigned to `control` or `treatment`, 50/50.

## assignments.csv
- `user_id`, `arm`, `assigned_at` (date of assignment)

## events.csv
- `event_id`: unique id of the logged event
- `request_id`: id of the originating request
- `user_id`, `ts` (UTC)
- `event_type`: `add_to_cart` or `checkout_complete` (a completed purchase)
- `amount`: purchase value in USD (0 for non-purchase events)

Large orders (over $1,500) come from verified wholesale accounts and are valid.
