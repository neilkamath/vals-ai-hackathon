"""Change events: hidden changes in the recording process.

Each event knows how to (1) corrupt recorded rows, (2) describe itself for the buried clue,
(3) emit the code that undoes it, used to build the reference solution.
"""
from dataclasses import dataclass


@dataclass
class UnitChange:
    """From `cutover` on, `field` is stored multiplied by `factor` (e.g. EUR -> cents)."""
    cutover: str
    factor: float
    field: str = "amount"
    date_field: str = "order_date"
    trap_id: str = "unit_change"

    def apply(self, rows):
        for r in rows:
            if r[self.date_field] >= self.cutover:
                r[self.field] = int(round(r[self.field] * self.factor))

    def clue_text(self):
        return (
            f"{self.cutover}  Billing export v2 deployed. '{self.field}' is now stored in cents "
            f"(integer) for all rows dated on or after {self.cutover}. Earlier rows are unchanged (EUR)."
        )

    def flag_text(self):
        return f"'{self.field}' switched from EUR to cents (unit change) on {self.cutover}"

    def undo_code(self):
        return (f"if r['{self.date_field}'] >= '{self.cutover}': "
                f"r['{self.field}'] = r['{self.field}'] / {self.factor}")


REGISTRY = {"unit_change": UnitChange}


def build_event(d):
    d = dict(d)
    return REGISTRY[d.pop("type")](**d)
