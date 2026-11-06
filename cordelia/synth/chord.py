"""The struck tone of the chords drill.

The sustained tone, stacked three or four deep at the same instant with
nothing moving, sounds like an organ patch. This voice is struck instead:
a quick attack, then every partial dies away on its own, the higher the
faster, so the chord blooms and darkens as it rings the way a plucked or
hammered string does. Same harmonic series idea as the tone, no 5th or
7th harmonic, so the chord's own third decides major or minor.

Each partial is a complex rotation that shrinks a little every sample,
run through itertools.accumulate, so the per-sample work is C and a
chord note costs milliseconds, not seconds.
"""

import itertools
import math
import operator

from .base import SAMPLE_RATE, cached

# (harmonic, level): the series at the attack; the roll-off with pitch is
# done by the decay times below, since a high partial dies sooner anyway.
HARMONICS = ((1, 1.00), (2, 0.55), (3, 0.30), (4, 0.18), (6, 0.08), (8, 0.04))
DECAY = 1.1                  # seconds for the fundamental to fall to 1/e; 1.4 rang a little too long
DECAY_SLOPE = 0.8            # partial h decays in DECAY / h ** SLOPE
ATTACK = 0.006               # seconds, raised cosine: struck, not bowed
RELEASE = 0.05               # seconds: the tail is cut with a short fade, no click
TILT = 0.5                   # level falls as (ANCHOR / f) ** TILT above the anchor
ANCHOR = 174.6               # F3, the lowest close-position root, keeps full level


def segment(freq, n, level):
    """A struck note of n samples as a list."""
    def make():
        gain = level * min(1.0, (ANCHOR / freq) ** TILT) / sum(a for _, a in HARMONICS)
        out = [0.0] * n
        for h, amp in HARMONICS:
            if h * freq >= SAMPLE_RATE / 2:
                continue
            tau = DECAY / h ** DECAY_SLOPE
            r = math.exp(-1.0 / (SAMPLE_RATE * tau)) * complex(math.cos(2 * math.pi * h * freq / SAMPLE_RATE),
                                                              math.sin(2 * math.pi * h * freq / SAMPLE_RATE))
            spiral = itertools.accumulate(itertools.repeat(r, n - 1), operator.mul, initial=complex(gain * amp, 0.0))
            out = list(map(operator.add, out, map(operator.attrgetter("imag"), spiral)))
        attack = min(n, max(1, int(SAMPLE_RATE * ATTACK)))
        for i in range(attack):
            out[i] *= 0.5 - 0.5 * math.cos(math.pi * i / attack)
        release = min(n, max(1, int(SAMPLE_RATE * RELEASE)))
        for i in range(release):
            out[n - 1 - i] *= 0.5 - 0.5 * math.cos(math.pi * i / release)
        return out
    return cached(("chord", round(freq, 2), n, round(level, 4)), make)
