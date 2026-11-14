"""Base World: a seeded simulation of the true events, as a dict of tables (lists of row dicts).

truth() is computed from the clean tables, before any recording imperfection.
"""
import random


class World:
    def __init__(self, seed, params):
        self.rng = random.Random(seed)
        self.params = params
        self.tables = self.simulate()  # clean, true tables

    def simulate(self):
        raise NotImplementedError

    def truth(self):
        raise NotImplementedError

    def render(self, tables):
        """-> {filename: text} for the files the agent sees."""
        raise NotImplementedError

    def naive_answer(self, tables):
        """What a careless analyst computes from the recorded tables."""
        raise NotImplementedError

    def solve_code(self, events):
        """Reference solution (bash script text). Uses only files in environment/data."""
        raise NotImplementedError

    def filler_files(self):
        return {}
