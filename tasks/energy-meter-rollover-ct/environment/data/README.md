# Meter export

Hourly readings from the main electricity meter of one site.

## readings.csv
- `meter_id`
- `ts`: reading time in UTC
- `register_kwh`: the meter's cumulative energy register in kWh, taken at the end of each hour

The site is in the America/Los_Angeles time zone; billing months follow the site's local calendar.
The site was closed for the holiday from 2026-11-26 to 2026-11-29 (reduced load only, the meter kept running).
