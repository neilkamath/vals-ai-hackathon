"""Change events for streamed meter worlds. They act on tables["stream"]: records {utc, ts, kwh, v}."""
from dataclasses import dataclass
from datetime import datetime, timezone

from .meter_events import FMT, local_str, to_utc


def scale(r, f):
    """Scale a record's energy whichever format it is in."""
    if "kwh" in r:
        r["kwh"] = round(r["kwh"] * f, 3)
    else:
        r["wh"] = round(r["wh"] * f, 1)


def epoch_ms(utc_str):
    return int(datetime.strptime(utc_str, FMT).replace(tzinfo=timezone.utc).timestamp() * 1000)


@dataclass
class StreamMultiplier:
    """From `cutover` (site local), a CT-ratio change makes the meter report 1/factor of the true energy."""
    cutover: str
    factor: float
    tz: str = "America/Los_Angeles"
    clue: str = "maintenance_log"
    trap_id = "multiplier_change"
    keywords = ["ct ratio", "multiplier", "scale", "x10", "10x", "1/10", "tenth", "ct change", "recalibrat"]

    def apply(self, tables, rng):
        for r in tables["stream"]:
            if local_str(r["utc"], self.tz) > self.cutover:
                scale(r, 1 / self.factor)

    def clue_files(self, kind):
        d = self.cutover[:10]
        return {"docs/maintenance_log.txt": (
            "Site maintenance log\n\n"
            "2026-09-02  Replaced hallway lighting ballasts (building 2).\n"
            "2026-10-05  Roof unit 3 filter change.\n"
            f"{d}  Electrician replaced the CT set on the main meter. New CT ratio is {int(self.factor)}x the old one, so the "
            f"meter now reports 1/{int(self.factor)} of the true energy. Multiply energy "
            f"measured after {self.cutover.replace('T', ' ')} (site local time) by {int(self.factor)}.\n"
            "2026-11-20  Quarterly inspection, no findings.\n")}

    def flag_text(self):
        return (f"CT ratio change on {self.cutover[:10]}: the meter reports 1/{int(self.factor)} of true energy afterwards; "
                f"multiplied later energy by {int(self.factor)}")


@dataclass
class StreamSchemaSwitch:
    """From `at` (site local), the meter firmware reports v2 records: epoch-millisecond timestamps and Wh."""
    at: str
    tz: str = "America/Los_Angeles"
    clue: str = "none"
    trap_id = "schema_switch"
    keywords = ["schema", "v2", "wh", "watt-hour", "watt hour", "unit", "epoch", "millisecond", "format change", "firmware"]

    def apply(self, tables, rng):
        for r in tables["stream"]:
            if local_str(r["utc"], self.tz) > self.at:
                r["v"] = 2
                r["wh"] = round(r.pop("kwh") * 1000, 1)
                r["ts"] = epoch_ms(r["utc"])

    def clue_files(self, kind):
        return {}

    def flag_text(self):
        return f"from {self.at[:10]} the meter sends v2 records (epoch milliseconds, energy in Wh); converted to UTC time and kWh"


@dataclass
class StreamGap:
    """Records between start and end (site local) were never delivered. The server cannot return them."""
    start: str
    end: str
    tz: str = "America/Los_Angeles"
    clue: str = "none"
    trap_id = "stream_gap"
    keywords = ["gap", "missing", "dropped", "incomplete", "not delivered", "missing hours", "lost", "absent", "hole"]

    def apply(self, tables, rng):
        tables["stream"] = [r for r in tables["stream"]
                            if not (self.start < local_str(r["utc"], self.tz) <= self.end)]

    def clue_files(self, kind):
        return {}

    def flag_text(self):
        return "some hourly records are missing from the stream and cannot be recovered, so the total is incomplete"


@dataclass
class StreamDegraded:
    """The sensor under-reports (`factor` of the true energy) between start and end, with nothing recording it."""
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
        for r in tables["stream"]:
            if self.start < local_str(r["utc"], self.tz) <= self.end:
                scale(r, self.factor)

    def clue_files(self, kind):
        return {}

    def flag_text(self):
        return ("one day's consumption is implausibly low compared with comparable days; the meter looks faulty "
                "that day, so the true consumption is unknown")


REGISTRY = {"stream_multiplier": StreamMultiplier, "stream_schema_switch": StreamSchemaSwitch,
            "stream_gap": StreamGap, "stream_degraded": StreamDegraded}
