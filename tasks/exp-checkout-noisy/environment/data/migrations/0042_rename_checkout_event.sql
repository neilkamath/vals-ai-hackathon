-- analytics v3: align event names with the product taxonomy
-- applies to events written on or after 2026-03-12
UPDATE event_type_map SET name = 'order_placed' WHERE name = 'checkout_complete';
