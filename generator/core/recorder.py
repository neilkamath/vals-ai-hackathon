"""Recorder: turns the true world into the files an agent sees, applying change events."""
import copy


class Recorder:
    def __init__(self, world, events):
        self.world, self.events = world, events

    def record(self):
        rows = copy.deepcopy(self.world.rows)
        for e in self.events:
            e.apply(rows)
        return rows, self.world.render(rows)  # recorded rows, {filename: text}
