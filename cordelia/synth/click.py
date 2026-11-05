"""A metronome click, as in play_metronome.py: a sine that starts at full
level and dies away."""

import math

from .base import SAMPLE_RATE, cached

CLICK_FREQ = 1000.0
CLICK_SECONDS = 0.03
CLICK_DECAY = 0.005          # seconds to fall to 1/e


def segment(level):
    return cached(("click", round(level, 4)), lambda: [
        level * math.exp(-i / (SAMPLE_RATE * CLICK_DECAY)) * math.sin(2 * math.pi * CLICK_FREQ * i / SAMPLE_RATE)
        for i in range(int(SAMPLE_RATE * CLICK_SECONDS))])
