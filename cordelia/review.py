"""`cordelia review b3 4 b7`: a listening track for the degrees you mix up, over the degrees
drone, in a fresh key each time. Nothing is asked or recorded, and the audio is deleted after.

The parts, in order (each one that isn't a fixed length lasts --minutes):
  cadence      i iv V i chords (I IV V I when the list has 3 and no b3)
  scale        the scale up and down, in the middle octave and then the low one
  held         the scale up and down in each octave, the listed degrees held or repeated
  tonic        1 then a degree, above or below it
  pairs        two listed degrees under an octave apart
  one way      three notes going only up or only down, 1 sometimes among them
  free         three notes in any order, no step over a fifth, 1 sometimes
  singles      each degree in all three octaves
The scales are only played: counting from 1 says what each note is. A group in the later
parts is played, then sung in solfege on its own notes, then played again.
"""

from .modes.degrees import (INTRO_BEATS, NOTE_NAMES, OCTAVE_LEVELS, OUTRO_SECONDS, PAUSE_BEATS, REST_BEATS,
                            RING, SEMITONES, SHORTHANDS, SINGER, SUNG_LEVEL, Builder)
from .score import Clip, Note
from .voice import SungBank, sung_label

OCTAVES = (-1, 0, 1)
TONIC_SHARE = 0.25        # how often a note of a triple may be 1
MAX_STEP = 7              # semitones, between neighbours in a free triple
SPAN = 12                 # a pair, or a one-way triple, spans less than this
SUNG_OVERLAP = 0.06       # a sung note holds this far past the next one's vowel
SUNG_RING = 1.5           # the last sung note of a group rings this long at most
CHORD_BEATS = 2
CHORD_LEVEL = 0.55        # each of a chord's notes
HOLD_BEATS = 3            # a listed degree held in the `held` scales, or played this many times
DEFAULT = ("b3", "4", "b7")


def minor(degrees):
    return not ("3" in degrees and "b3" not in degrees)


class Track(Builder):
    def __init__(self, degrees, key, bpm, minutes, rng):
        super().__init__(dict(key=key, bpm=bpm, answer="sung"), _NoBank())   # the bank comes per call
        self.degrees, self.rng, self.seconds = list(degrees), rng, minutes * 60
        self.scale = sorted(set(SHORTHANDS["minor" if minor(degrees) else "major"]) | set(degrees), key=lambda d: SEMITONES[d])

    # --- sounds -------------------------------------------------------------------------
    def note(self, t, d, o, beats=1):
        self.score.notes.append(Note(t, beats * self.beat + RING, self.midi(d, o), OCTAVE_LEVELS.get(o, 0.9)))
        return t + beats * self.beat

    def sing(self, t, notes, bank):
        for i, (d, o) in enumerate(notes):
            label = sung_label(d, self.midi(d, o))
            lead = bank.lead(label)
            dur = lead + (SUNG_RING if i == len(notes) - 1 else self.beat + SUNG_OVERLAP)
            self.score.clips.append(Clip(t - lead, label, SUNG_LEVEL, dur))
            t += self.beat
        return t + self.beat

    def group(self, t, notes, bank):
        """Played a beat each, a pause, sung, played again."""
        beats = 2 if len(notes) == 1 else 1
        for q in notes:
            t = self.note(t, *q, beats)
        t = self.sing(t + PAUSE_BEATS * self.beat, notes, bank)
        for q in notes:
            t = self.note(t, *q, beats)
        return t + REST_BEATS * self.beat

    # --- parts --------------------------------------------------------------------------
    def cadence_chords(self, t):
        third, sixth = ("b3", "b6") if minor(self.degrees) else ("3", "6")
        chords = [(("1", -1), ("1", 0), (third, 0), ("5", 0)),
                  (("4", -1), ("1", 0), ("4", 0), (sixth, 0)),
                  (("5", -1), ("7", -1), ("2", 0), ("5", 0)),
                  (("1", -1), ("1", 0), (third, 0), ("5", 0))]
        for i, chord in enumerate(chords):
            beats = 2 * CHORD_BEATS if i == len(chords) - 1 else CHORD_BEATS
            for d, o in chord:
                self.score.notes.append(Note(t, beats * self.beat + RING, self.midi(d, o), CHORD_LEVEL, voice="chord"))
            t += beats * self.beat
        return t + 2 * self.beat

    def updown(self, o):
        up = [(d, o) for d in self.scale] + [("1", o + 1)]
        return up + up[-2::-1]

    def scales(self, t):
        for o in (0, -1):
            for q in self.updown(o):
                t = self.note(t, *q)
            t += 2 * self.beat
        return t

    def held(self, t):
        for o in (0, -1, 1):
            for d, oo in self.updown(o):
                if d in self.degrees and d != "1":
                    if self.rng.random() < 0.5:
                        t = self.note(t, d, oo, HOLD_BEATS)
                    else:
                        for _ in range(HOLD_BEATS):
                            t = self.note(t, d, oo)
                else:
                    t = self.note(t, d, oo)
            t += 2 * self.beat
        return t

    def fill(self, t, make, bank):
        """Groups from make() until the part's time is used, none twice in a row."""
        end, last = t + self.seconds, None
        while t < end:
            g = make()
            if g != last:
                t, last = self.group(t, g, bank), g
        return t


class _NoBank:
    name = "none"


def build(degrees, key, bpm, minutes, rng, data_dir):
    """(score, the sung bank, [(part name, start seconds)])."""
    tr = Track(degrees, key, bpm, minutes, rng)
    bank = SungBank(SINGER, data_dir)
    tr.score.voice = bank.name
    pitch = lambda q: tr.midi(*q)
    targets = [d for d in degrees if d != "1"] or list(degrees)
    notes = [(d, o) for d in targets for o in OCTAVES]
    tonics = [("1", o) for o in OCTAVES]
    pick = lambda: rng.choice(tonics) if rng.random() < TONIC_SHARE else rng.choice(notes)
    enough = lambda g: len({d for d, _ in g if d in targets}) > min(1, len(targets) - 1)
    bank.ensure({sung_label(d, tr.midi(d, o)) for d in set(targets) | {"1"} for o in OCTAVES})

    def tonic():
        d = rng.choice(targets)
        start = rng.choice(OCTAVES)
        o = rng.choice([x for x in (start - 1, start) if x in OCTAVES and abs(SEMITONES[d] + 12 * (x - start)) < 12])
        return (("1", start), (d, o))

    def pair():
        while True:
            x, y = rng.sample(notes, 2)
            if (x[0] != y[0] or len(targets) == 1) and abs(pitch(x) - pitch(y)) < SPAN:
                return (x, y)

    def one_way():
        while True:
            g = sorted({pick() for _ in range(3)}, key=pitch, reverse=rng.random() < 0.5)
            if len(g) == 3 and enough(g) and abs(pitch(g[0]) - pitch(g[-1])) < SPAN:
                return tuple(g)

    def free():
        while True:
            g = (pick(), pick(), pick())
            steps = [abs(pitch(x) - pitch(y)) for x, y in zip(g, g[1:])]
            if min(steps) > 0 and max(steps) <= MAX_STEP and enough(g):
                return g

    order = []
    def single():
        if not order:                       # every note once, shuffled, before any comes again
            order.extend(rng.sample(notes, len(notes)))
        return (order.pop(),)

    parts, t = [], INTRO_BEATS * tr.beat
    for name, run in (("cadence", tr.cadence_chords), ("scale", tr.scales), ("held", tr.held),
                      ("tonic", lambda t: tr.fill(t, tonic, bank)), ("pairs", lambda t: tr.fill(t, pair, bank)),
                      ("one way", lambda t: tr.fill(t, one_way, bank)), ("free", lambda t: tr.fill(t, free, bank)),
                      ("singles", lambda t: tr.fill(t, single, bank))):
        parts.append((name, t))
        t = run(t)
    tr.score.seconds = t + OUTRO_SECONDS
    return tr.score, bank, parts


def draw_key(rng, keys):
    return rng.choice(keys or NOTE_NAMES)
