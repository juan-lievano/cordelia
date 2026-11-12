"""The breathing drone that holds for the whole score."""

import itertools
import math
import operator

from .base import SAMPLE_RATE, midi_to_freq

DRONE_LEVEL = 0.288          # down from 0.40 with the root an octave up: the
                             # same energy sits where the ear is more sensitive;
                             # then a further dB off, the ears felt pressed after a session (0.24);
                             # then up with the sub-octave and the core (2026-11-12) so the
                             # other partials stay exactly as loud

# Drone partials as harmonics of the root, which sits two octaves under the
# middle-register tonic (C2 for C, 65 Hz: the old C1 root was mostly below
# what laptop speakers reproduce, and a weight on the ears in headphones).
# (harmonic, level, floor, slowest breath, quickest breath): each partial
# swells on its own LFO, a cosine between floor and 1, with a period drawn
# once from that range. The core (2 and 4) and the sub-octave breathe over
# tens of seconds and never drop below their floor, so the key never
# wavers; the fifths and the shimmer above move a little quicker, for some
# colour, but still over several seconds: faster than that, and with more
# partials, the drone stopped sounding like one thing. No 5th harmonic (a
# major third would fight the minor scales) and no 7th.
PARTIALS = (
    (1, 0.65, 0.50, 22.0, 45.0),    # sub-octave (0.55 until 2026-11-12: +1.4 dB, a touch more bass)
    (2, 1.40, 0.60, 18.0, 40.0),    # core (1.00 until 2026-11-12: +2.9 dB, the octave clearer)
    (3, 0.24, 0.15, 11.0, 22.0),    # fifth
    (4, 0.35, 0.35, 18.0, 40.0),    # core, octave up: the mid-register tonic
    (6, 0.14, 0.05, 9.0, 18.0),     # fifth
    (8, 0.14, 0.05, 9.0, 18.0),     # two octaves up
    (12, 0.06, 0.00, 7.0, 15.0),    # shimmer
    (16, 0.03, 0.00, 7.0, 15.0),    # shimmer, octave up
)


class Drone:
    """One period of each partial, tabulated once, and an LFO per partial."""

    def __init__(self, midi, rng):
        self.period = max(2, round(SAMPLE_RATE / midi_to_freq(midi)))
        p = self.period
        self.tables = [[math.sin(2 * math.pi * h * i / p) for i in range(p)] for h, *_ in PARTIALS]
        self.lfos = [(level, floor, rng.uniform(slow, quick), rng.uniform(0, 2 * math.pi))
                     for _, level, floor, slow, quick in PARTIALS]
        self.scale = DRONE_LEVEL / sum(level for _, level, *_ in PARTIALS)

    def amps(self, seconds):
        out = []
        for level, floor, period, phase in self.lfos:
            breath = 0.5 - 0.5 * math.cos(2 * math.pi * seconds / period + phase)
            out.append(self.scale * level * (floor + (1.0 - floor) * breath))
        return out

    def block(self, start, n):
        """n samples from sample `start`, which must be a multiple of the period."""
        out = []
        pos = 0
        while pos < n:
            # the amplitudes hold for one period (a few ms), then each table is
            # scaled and summed at C speed: no per-sample Python
            one = [0.0] * self.period
            for a, table in zip(self.amps((start + pos) / SAMPLE_RATE), self.tables):
                one = list(map(operator.add, one, map(operator.mul, table, itertools.repeat(a))))
            out.extend(one[: n - pos])
            pos += self.period
        return out
