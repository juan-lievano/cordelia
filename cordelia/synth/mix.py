"""Mix a Score down to a WAV: the voices' segments and the voice bank's
clips over the drone, in blocks of about a second, each block a whole
number of drone periods, so the drone tables never need rotating and the
file is streamed out as it is made.
"""

import math
import operator
import random
import struct
import wave

from . import chord, click, tone
from .base import SAMPLE_RATE, midi_to_freq
from .drone import Drone

MELODY_LEVEL = 0.38          # notes and clicks, on top of the drone's 0.317
VOICE_LEVEL = 0.22
FADE_IN_SECONDS = 1.0        # from silence
FADE_OUT_SECONDS = 2.0       # the drone alone, after the last note or clip
CLIP_ATTACK = 0.04           # seconds: every clip eases in over this
CLIP_RELEASE = 0.25          # and fades out over this, cut short or not

# A Note's `voice` names one of these; each makes a segment for one note.
VOICES = {
    "tone": lambda n: tone.segment(midi_to_freq(n.midi), int(SAMPLE_RATE * n.dur), MELODY_LEVEL * n.level),
    "bass": lambda n: tone.segment(midi_to_freq(n.midi), int(SAMPLE_RATE * n.dur), MELODY_LEVEL * n.level, bass=True),
    "chord": lambda n: chord.segment(midi_to_freq(n.midi), int(SAMPLE_RATE * n.dur), MELODY_LEVEL * n.level),
    "click": lambda n: click.segment(MELODY_LEVEL * n.level),
}


def shape(samples, seconds=None):
    """A clip, cut to `seconds` when given, eased in over CLIP_ATTACK and
    faded out over CLIP_RELEASE (raised cosines) so no edge is abrupt."""
    n = len(samples) if seconds is None else min(len(samples), int(SAMPLE_RATE * seconds))
    out = samples[:n]
    attack = min(n, int(SAMPLE_RATE * CLIP_ATTACK))
    for i in range(attack):
        out[i] *= 0.5 - 0.5 * math.cos(math.pi * i / attack)
    release = min(n, int(SAMPLE_RATE * CLIP_RELEASE))
    for i in range(release):
        out[n - 1 - i] *= 0.5 - 0.5 * math.cos(math.pi * i / release)
    return out


def render(score, path, bank=None, progress=None, seed=None):
    """Write `score` to the WAV at `path`. `bank` supplies the clips."""
    rng = random.Random(seed)
    total = int(SAMPLE_RATE * score.seconds)
    drone = Drone(score.drone["midi"], rng) if score.drone else None
    period = drone.period if drone else SAMPLE_RATE
    block = period * max(1, SAMPLE_RATE // period)

    pending = []
    for n in score.notes:
        if n.voice not in VOICES:
            raise ValueError(f"no voice {n.voice!r} in the synth: {', '.join(VOICES)}")
        pending.append((int(SAMPLE_RATE * n.t), VOICES[n.voice](n)))
    for c in score.clips:
        if bank is None:
            raise ValueError("the score has voice clips but no voice bank was given")
        seg = [VOICE_LEVEL * c.level * v for v in shape(bank.load(c.label), c.dur)]
        pending.append((int(SAMPLE_RATE * c.t), seg))
    # The fade-out never touches a note or a clip: it starts after the last one
    # ends, over whatever tail the score leaves, up to FADE_OUT_SECONDS.
    last_end = max((start + len(seg) for start, seg in pending), default=0)
    pending.sort(key=lambda e: e[0], reverse=True)   # pop() gives the earliest
    active = []
    fade = int(SAMPLE_RATE * FADE_IN_SECONDS)
    out_start = max(total - int(SAMPLE_RATE * FADE_OUT_SECONDS), last_end)
    out_len = max(1, total - out_start)

    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        for b0 in range(0, total, block):
            b1 = min(total, b0 + block)
            n = b1 - b0
            buf = drone.block(b0, n) if drone else [0.0] * n

            while pending and pending[-1][0] < b1:
                active.append(pending.pop())
            keep = []
            for start, seg in active:
                end = start + len(seg)
                if end <= b0:
                    continue
                keep.append((start, seg))
                lo, hi = max(start, b0), min(end, b1)
                s, so = lo - b0, lo - start
                buf[s:s + hi - lo] = map(operator.add, buf[s:s + hi - lo], seg[so:so + hi - lo])
            active = keep

            if b0 < fade or b1 > out_start:
                for i in range(n):
                    pos = b0 + i
                    g = max(0.0, min(1.0, pos / fade, (total - pos) / out_len))
                    buf[i] *= 0.5 - 0.5 * math.cos(math.pi * g)

            frames = [max(-32767, min(32767, int(32767 * x))) for x in buf]
            wf.writeframes(struct.pack(f"<{n}h", *frames))
            if progress:
                progress(b1 / total)
