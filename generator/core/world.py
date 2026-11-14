"""Base World: a seeded simulation of the true events. truth() is computed from clean data."""
import random


class World:
    def __init__(self, seed, params):
        self.rng = random.Random(seed)
        self.params = params
        self.rows = self.simulate()  # clean, true events

    def simulate(self):
        raise NotImplementedError

    def truth(self):
        """Correct answer, from the clean world."""
        raise NotImplementedError
