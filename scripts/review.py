"""A listening track for the degrees you mix up (default b3 4 b7), over the degrees drone.

Five parts, each about --minutes long:
  1. single notes, every degree in three octaves, as in the degrees drill
     (the note, a pause, its name, the note again);
  2. random pairs, under an octave apart;
  3. triples going one way, up or down, sometimes with 1 in them;
  4. triples in any order, no step over a fifth, sometimes with 1;
  5. single notes again.
A group plays its notes one beat each, pauses, then names each one followed by its note.
Nothing is asked or recorded: it is for listening. The WAV goes to review/ (git-ignored).

    python scripts/review.py [b3 4 b7] [--key C] [--bpm 60] [--minutes 1] [--play]
"""

import argparse
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cordelia import store                                         # noqa: E402
from cordelia.modes.degrees import (INTRO_BEATS, NOTE_NAMES, OCTAVE_LEVELS,  # noqa: E402
                                    OUTRO_SECONDS, PAUSE_BEATS, REST_BEATS, RING, SEMITONES, Builder,
                                    parse_key, spoken)
from cordelia.score import Clip, Note                              # noqa: E402
from cordelia.synth import render                                  # noqa: E402
from cordelia.voice import VoiceBank                               # noqa: E402

OCTAVES = (-1, 0, 1)
TONIC_SHARE = 0.25        # how often a triple's note may be 1
MAX_STEP = 7              # semitones, between neighbours in a free triple
SPAN = 12                 # a pair, or a one-way triple, spans less than this


class Review(Builder):
    def note(self, t, d, o, beats):
        self.score.notes.append(Note(t, beats * self.beat + RING, self.midi(d, o), OCTAVE_LEVELS[o]))

    def single(self, t, d, o):
        return self.phrase(t, d, o)[1]

    def group(self, t, notes):
        """Each note a beat, a pause, then each name followed by its note again."""
        for d, o in notes:
            self.note(t, d, o, 1)
            t += self.beat
        t += PAUSE_BEATS * self.beat
        for d, o in notes:
            self.score.clips.append(Clip(t, d))
            t += self.answer_beats(d) * self.beat
            self.note(t, d, o, 1)
            t += self.beat
        return t + REST_BEATS * self.beat


def section(b, t, seconds, make):
    """Groups from make() until the section's time is used; no group twice in a row."""
    end, last = t + seconds, None
    while t < end:
        g = make()
        if g == last:
            continue
        t, last = g(b, t) if callable(g) else b.group(t, g), g
    return t


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("degrees", nargs="*", default=["b3", "4", "b7"])
    p.add_argument("--key", default=None, help="the tonic (default: a random one)")
    p.add_argument("--bpm", type=float, default=60)
    p.add_argument("--minutes", type=float, default=1.0, help="each of the five parts")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--play", action="store_true", help="play it when it is made")
    a = p.parse_args()
    bad = [d for d in a.degrees if d not in SEMITONES]
    if bad:
        raise SystemExit(f"not degrees: {' '.join(bad)}")
    rng = random.Random(a.seed)
    key = NOTE_NAMES[parse_key(a.key)] if a.key else rng.choice(NOTE_NAMES)
    degs = list(dict.fromkeys(a.degrees))
    with_one = degs + (["1"] if "1" not in degs else [])

    bank = VoiceBank("default", store.data_dir())
    bank.ensure(spoken(with_one))
    b = Review(dict(key=key, bpm=a.bpm, answer="spoken"), bank)
    pitch = lambda q: b.midi(*q)
    notes = [(d, o) for d in degs for o in OCTAVES]
    tonics = [("1", o) for o in OCTAVES]
    pick = lambda: rng.choice(tonics) if "1" not in degs and rng.random() < TONIC_SHARE else rng.choice(notes)

    def pair():
        while True:
            x, y = rng.sample(notes, 2)
            if x[0] != y[0] and abs(pitch(x) - pitch(y)) < SPAN:
                return (x, y)

    def one_way():
        while True:
            g = sorted({pick() for _ in range(3)}, key=pitch, reverse=rng.random() < 0.5)
            if len(g) == 3 and len({d for d, _ in g if d in degs}) > 1 and abs(pitch(g[0]) - pitch(g[-1])) < SPAN:
                return tuple(g)

    def free():
        while True:
            g = (pick(), pick(), pick())
            steps = [abs(pitch(x) - pitch(y)) for x, y in zip(g, g[1:])]
            if 0 < min(steps) and max(steps) <= MAX_STEP and len({d for d, _ in g if d in degs}) > 1:
                return g

    def singles(order=[]):
        if not order:                       # every note once, shuffled, before any comes again
            order.extend(rng.sample(notes, len(notes)))
        q = order.pop()
        return lambda b, t: b.single(t, *q)

    s = a.minutes * 60
    t = b.cadence(INTRO_BEATS * b.beat)
    for make in (singles, pair, one_way, free, singles):
        t = section(b, t, s, make)
    b.score.seconds = t + OUTRO_SECONDS

    out = ROOT / "review" / f"{'-'.join(degs)}-{key}-{a.bpm:g}bpm.wav"
    out.parent.mkdir(exist_ok=True)
    render(b.score, str(out), bank, lambda f: print(f"\rrendering {f:4.0%}", end="", flush=True))
    print(f"\r{out.relative_to(ROOT)} · key {key} · {t / 60:.1f} min")
    if a.play:
        subprocess.run(["afplay", str(out)])


if __name__ == "__main__":
    main()
