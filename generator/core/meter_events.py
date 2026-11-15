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


@dataclass
class StuckMeter:
    """The meter keeps its register frozen between start and end (comms fault), then catches up.

    Consumption in that period is not recorded hour by hour. If `end` is past the export, the catch-up
    never appears in the data.
    """
    start: str
    end: str
    tz: str = "America/Los_Angeles"
    clue: str = "none"
    trap_id = "stuck_meter"
    keywords = ["stuck", "frozen", "freeze", "flat", "not updating", "stale", "no change", "constant register",
                "same reading", "identical reading", "not recorded", "gap", "catch-up", "catch up"]

    def apply(self, tables, rng):
        base = None
        for r in tables["readings"]:
            loc = local_str(r["utc"], self.tz)
            if loc <= self.start:
                base = r["register"]
            elif loc < self.end and base is not None:
                r["register"] = base

    def clue_files(self, kind):
        return {}

    def flag_text(self):
        return ("the meter register is frozen for many consecutive hours (identical readings), "
                "so consumption in that period was not recorded")

    def undo_code(self):
        return "pass"


@dataclass
class MeterSwap:
    """The meter is replaced at `at` (site local). The new meter has a new id and its register starts at 0.0.

    The reading drop looks like a register rollover but is not one; the paperwork says what happened.
    """
    at: str
    new_id: str = "M-1002"
    tz: str = "America/Los_Angeles"
    clue: str = "replacement_form"
    trap_id = "meter_swap"
    keywords = ["meter replace", "replaced", "new meter", "meter swap", "swap", "meter_id", "m-1002",
                "different meter", "register reset", "reset to 0", "reset to zero", "not a rollover"]

    def apply(self, tables, rng):
        base = None
        for r in tables["readings"]:
            if local_str(r["utc"], self.tz) <= self.at:
                base = r["register"]
            elif base is not None:
                r["meter_id"] = self.new_id
                r["register"] = round(r["register"] - base, 1)

    def clue_files(self, kind):
        return {"docs/meter_replacement_form.txt": (
            "Meter replacement form\n\n"
            f"Date and time: {self.at[:10]} {self.at[11:16]} (site local time)\n"
            "Reason: end of life, scheduled replacement\n"
            f"Old meter: M-1001. Its last hourly reading is its final reading.\n"
            f"New meter: {self.new_id}, installed at the time above with its register at 0.0 kWh.\n"
            "CT ratio unchanged.\n")}

    def flag_text(self):
        return (f"the meter was replaced on {self.at[:10]} (new meter {self.new_id}, register restarts at 0.0); "
                "the drop in the register is not a rollover")

    def undo_code(self):
        return "if r['meter_id'] != last_id:\n        prev = 0.0  # new meter starts at 0.0\n    last_id = r['meter_id']"


@dataclass
class DegradedMeter:
    """A failing sensor under-reads (reports `factor` of the true energy) between start and end, then recovers.

    The energy it missed never appears in the register. No file mentions it; the evidence is one implausibly low
    day compared with comparable days. There is no frozen run.
    """
    start: str
    end: str
    factor: float = 0.01
    tz: str = "America/Los_Angeles"
    clue: str = "none"
    trap_id = "degraded_meter"
    keywords = ["degraded", "faulty", "fault", "implausibly low", "implausible", "anomal", "outlier", "under-read",
                "under read", "underread", "sensor failure", "suspicious", "too low", "near zero", "near-zero",
                "unusually low", "dropout", "drop-out"]

    def apply(self, tables, rng):
        lost, prev = 0.0, None
        for r in tables["readings"]:
            true_reg = r["register"]
            loc = local_str(r["utc"], self.tz)
            if prev is not None and self.start < loc <= self.end:
                lost += (true_reg - prev) * (1 - self.factor)
            prev = true_reg
            r["register"] = true_reg - lost

    def clue_files(self, kind):
        return {}

    def flag_text(self):
        return ("one day's consumption is implausibly low compared with comparable days; the meter looks faulty "
                "that day, so the true consumption is unknown")

    def undo_code(self):
        return "pass"


REGISTRY = {"degraded_meter": DegradedMeter, "stuck_meter": StuckMeter, "meter_swap": MeterSwap, "utc_timestamps": UtcTimestamps, "multiplier_change": MultiplierChange,
            "register_rollover": RegisterRollover}
