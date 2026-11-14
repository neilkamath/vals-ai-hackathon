"""Recorder: turns the true world into the files an agent sees, applying change events."""
import copy
import random


class Recorder:
    def __init__(self, world, events, seed):
        self.world, self.events, self.seed = world, events, seed

    def record(self):
        tables = copy.deepcopy(self.world.tables)
        for i, e in enumerate(self.events):
            e.apply(tables, random.Random(f"{self.seed}-{i}-{e.trap_id}"))
        return tables, self.world.render(tables)
