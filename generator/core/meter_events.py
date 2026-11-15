"""Change events for meter worlds. Rows have a hidden `utc` key; the visible columns are ts and register."""
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

FMT = "%Y-%m-%dT%H:%M:%S"


def local_str(utc_str, tz):
    t = datetime.strptime(utc_str, FMT).replace(tzinfo=timezone.utc).astimezone(ZoneInfo(tz))
    return t.strftime(FMT)


def to_utc(local_naive, tz):
    t = datetime.strptime(local_naive, FMT).replace(tzinfo=ZoneInfo(tz)).astimezone(timezone.utc)
    return t.strftime(FMT)


@dataclass
class UtcTimestamps:
    """Timestamps are UTC (stated in the README) but the question is about a local calendar month.

    The offset changes on the DST end date inside the month, so a fixed-offset conversion is off by an hour.
    """
    tz: str = "America/Los_Angeles"
    clue: str = "none"
    trap_id = "utc_boundary"
    keywords = ["utc", "time zone", "timezone", "dst", "daylight", "local time", "offset", "boundary", "boundaries"]

    def apply(self, tables, rng):
        pass  # timestamps are already UTC in the clean world

    def clue_files(self, kind):
        return {}

    def flag_text(self):
        return "timestamps are UTC; converted the local month boundaries to UTC with the DST change on 2026-11-01"

    def undo_code(self):
        return "pass  # month bounds converted to UTC below"


@dataclass
class MultiplierChange:
    """From `cutover` (site-local), a CT-ratio change makes the register read 1/factor of the true energy."""
    cutover: str
    factor: float
    tz: str = "America/Los_Angeles"
    clue: str = "maintenance_log"
    trap_id = "multiplier_change"
    keywords = ["ct ratio", "multiplier", "scale", "x10", "10x", "1/10", "tenth", "ct change", "recalibrat"]

    def apply(self, tables, rng):
        rows = tables["readings"]
        base = None
        for r in rows:
            if local_str(r["utc"], self.tz) <= self.cutover:
                base = r["register"]
            elif base is not None:
                r["register"] = base + (r["register"] - base) / self.factor

    def clue_files(self, kind):
        d = self.cutover[:10]
        return {"docs/maintenance_log.txt": (
            "Site maintenance log\n\n"
            "2026-09-02  Replaced hallway lighting ballasts (building 2).\n"
            "2026-10-05  Roof unit 3 filter change.\n"
            f"{d}  Electrician replaced the CT set on the main meter. New CT ratio is {int(self.factor)}x the old one, so the "
            f"register now displays 1/{int(self.factor)} of the true energy. Multiply energy "
            f"measured after {self.cutover.replace('T', ' ')} (site local time) by {int(self.factor)}.\n"
            "2026-11-20  Quarterly inspection, no findings.\n")}

    def flag_text(self):
        return (f"CT ratio change on {self.cutover[:10]}: the register reads 1/{int(self.factor)} of true energy afterwards; "
                f"multiplied later increments by {int(self.factor)}")

    def undo_code(self):
        return f"if r['ts'] > '{to_utc(self.cutover, self.tz)}': d *= {self.factor}"


@dataclass
class RegisterRollover:
    """The register has a fixed number of digits and wraps to zero."""
    modulus: float = 1_000_000.0
    clue: str = "datasheet"
    trap_id = "register_rollover"
    keywords = ["rollover", "roll over", "rolled over", "wrap", "odometer", "overflow", "register reset", "6-digit", "6 digit"]

    def apply(self, tables, rng):
        for r in tables["readings"]:
            r["register"] = round(r["register"] % self.modulus, 1)

    def clue_files(self, kind):
        return {"docs/meter_datasheet.txt": (
            "Electronic energy meter, model EM-300\n\n"
            "Interval: one reading per hour, taken at the end of the hour.\n"
            "Register: 6 digits and one decimal (0.0 to 999999.9 kWh).\n"
            "After 999999.9 the register rolls over to 0.0 and keeps counting.\n"
            "Accuracy class 0.5S.\n")}

    def flag_text(self):
        return f"meter register rolled over at {int(self.modulus)} kWh; added the rollover when a reading dropped"

    def undo_code(self):
        return f"if d < 0: d += {self.modulus}"


REGISTRY = {"utc_timestamps": UtcTimestamps, "multiplier_change": MultiplierChange,
            "register_rollover": RegisterRollover}
