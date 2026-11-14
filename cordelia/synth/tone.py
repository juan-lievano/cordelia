"""The sustained additive tone of the degrees and melody drills."""

import math

from .base import SAMPLE_RATE, cached

# The note's harmonics, as in play_ambient_drone.py: no 5th (a major third
# would fight the minor scales), each rolled off the higher it sits so a low
# note keeps its warmth and a high one thins towards a sine.
HARMONICS = ((1, 1.00), (2, 0.30), (3, 0.12), (4, 0.06))
# The bass voice: the ear hears 50 Hz some 20 dB fainter than the same level at 200 Hz, and
# small speakers give little of it, so a low note is heard mostly from its overtones: there
# are more of them (still no 5th or 7th), under a fundamental that stays the strongest so
# the note is not heard an octave up, and the whole note is BASS_GAIN louder, about what the
# mix has room for over the drone. (2026-11-14: fundamental strongest and no gain was "quite
# faint" on closed headphones; the octave at 1.00 over a fundamental at 0.60 was too strong.)
BASS_HARMONICS = ((1, 1.00), (2, 0.55), (3, 0.45), (4, 0.25), (6, 0.12), (8, 0.06))
BASS_GAIN = 1.9
TONE_DAMPING = 1000.0        # Hz: a partial here is at half strength
TONE_TILT = 0.6              # level falls as (TONE_ANCHOR / f) ** TILT, ~3.6 dB an octave
TONE_ANCHOR = 196.0          # G3: the lowest question note keeps full level
ATTACK = 0.08                # seconds, raised cosine
RELEASE_SHARE = 0.35         # of the note, spent fading out


def partials(freq, harmonics=HARMONICS):
    out = [(h, level / (1.0 + (h * freq / TONE_DAMPING) ** 2)) for h, level in harmonics]
    total = sum(level for _, level in out)
    return [(h, level / total) for h, level in out]


def tone(t, f, parts):
    return sum(level * math.sin(2 * math.pi * h * f * t) for h, level in parts)


def segment(freq, n, level, bass=False):
    """A whole note of n samples as a list."""
    def make():
        attack = max(1, int(SAMPLE_RATE * ATTACK))
        release = max(1, int(n * RELEASE_SHARE))
        parts = partials(freq, BASS_HARMONICS if bass else HARMONICS)
        gain = level * min(1.0, (TONE_ANCHOR / freq) ** TONE_TILT) * (BASS_GAIN if bass else 1.0)
        seg = []
        for i in range(n):
            t = i / SAMPLE_RATE
            env = 1.0 if i >= attack else 0.5 - 0.5 * math.cos(math.pi * i / attack)
            remaining = n - i
            if remaining < release:
                env *= 0.5 - 0.5 * math.cos(math.pi * remaining / release)
            seg.append(gain * env * tone(t, freq, parts))
        return seg
    return cached(("bass" if bass else "tone", round(freq, 2), n, round(level, 4)), make)
