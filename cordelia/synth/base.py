"""What every voice shares: the sample rate, pitch, and a cache of rendered segments."""

SAMPLE_RATE = 22050

_segments = {}


def midi_to_freq(midi):
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


def cached(key, make):
    """The segment for `key`, made once by `make()`: identical notes are rendered once."""
    seg = _segments.get(key)
    if seg is None:
        seg = _segments[key] = make()
    return seg
