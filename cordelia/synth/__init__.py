"""Render a Score to a WAV. One file per voice: `tone` (the sustained note
of degrees and melody), `chord` (the struck note of chords), `click` (the
metronome) and `drone`; `mix` lays them and the voice bank's clips on the
timeline and streams the file out. A Note's `voice` picks its file.
"""

from .base import SAMPLE_RATE, midi_to_freq  # noqa: F401
from .mix import render  # noqa: F401
