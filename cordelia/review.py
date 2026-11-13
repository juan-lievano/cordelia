"""`cordelia review b3 4 b7`: a listening track for the degrees you mix up, over the degrees
drone, in a fresh key each time. Nothing is asked or recorded, and the audio is deleted after.

The parts, in order (each one that isn't a fixed length lasts --minutes):
  cadence      i iv V i, then i VI VII i, in chords (I IV V I when the list has 3 and no b3)
  scale        the scale up and down, in the middle octave and then the low one
  held         the same, the listed degrees held or repeated
  tonic        1 then a degree, above or below it
  pairs        two listed degrees under an octave apart
  one way      three notes going only up or only down, 1 sometimes among them
  free         three notes in any order, no step over a fifth, 1 sometimes
  singles      each degree in all three octaves
The scales are only played: counting from 1 says what each note is. A group in the later
parts is played, its names said, and played again, the whole of it --repeat times. The screen
shows it on a staff as it plays (cordelia/staff.py).
"""

import math

from .modes.degrees import (INTRO_BEATS, NOTE_NAMES, OCTAVE_LEVELS, OUTRO_SECONDS, PAUSE_BEATS, REST_BEATS,
                            RING, SEMITONES, SHORTHANDS, Builder, spoken)
from .score import Clip, Note
from .voice import VoiceBank

OCTAVES = (-1, 0, 1)
TONIC_SHARE = 0.25        # how often a note of a triple may be 1
MAX_STEP = 7              # semitones, between neighbours in a free triple
SPAN = 12                 # a pair, or a one-way triple, spans less than this
WORD_GAP = 0.15           # seconds between one said name and the next
CHORD_BEATS = 2
CHORD_LEVEL = 0.55        # each of a chord's notes
HOLD_BEATS = 3            # a listed degree held in the `held` scales, or played this many times
DEFAULT = ("b3", "4", "b7")
CELLS = 16                # columns of notes on the screen's staff; a longer excerpt scrolls


def minor(degrees):
    return not ("3" in degrees and "b3" not in degrees)


class Track(Builder):
    """The score, and what the screen shows along with it: `excerpts`, each a list of columns
    (notes [(label, midi)], held, name), and `events` (t, excerpt, column sounding, named)."""

    def __init__(self, degrees, key, bpm, minutes, rng, repeat):
        super().__init__(dict(key=key, bpm=bpm, answer="spoken"), _NoBank())   # the bank comes per call
        self.degrees, self.rng, self.seconds, self.repeat = list(degrees), rng, minutes * 60, repeat
        self.scale = sorted(set(SHORTHANDS["minor" if minor(degrees) else "major"]) | set(degrees), key=lambda d: SEMITONES[d])
        self.excerpts, self.events = [], []

    def excerpt(self, columns):
        self.excerpts.append(columns)
        return len(self.excerpts) - 1

    def column(self, notes, held=False, name=None):
        return ([(d, self.midi(d, o)) for d, o in notes], held, notes[0][0] if name is None else name)

    # --- sounds -------------------------------------------------------------------------
    def note(self, t, d, o, beats=1, mark=None):
        if mark:
            self.events.append((t, *mark))
        self.score.notes.append(Note(t, beats * self.beat + RING, self.midi(d, o), OCTAVE_LEVELS.get(o, 0.9)))
        return t + beats * self.beat

    def say(self, t, notes, bank, x):
        """The names one after another, then on to the next beat."""
        start = t
        for i, (d, _) in enumerate(notes):
            self.score.clips.append(Clip(t, d))
            self.events.append((t, x, i, True))
            t += bank.seconds(d) + WORD_GAP
        return start + math.ceil((t - start) / self.beat) * self.beat

    def group(self, t, notes, bank):
        """Played a beat each, a pause, the names said, played again; `repeat` times."""
        x = self.excerpt([self.column([q]) for q in notes])
        beats = 2 if len(notes) == 1 else 1
        for n in range(self.repeat):
            for i, q in enumerate(notes):
                t = self.note(t, *q, beats, mark=(x, i, n > 0))     # named once it has been said
            self.events.append((t, x, None, n > 0))
            t = self.say(t + PAUSE_BEATS * self.beat, notes, bank, x)
            for i, q in enumerate(notes):
                t = self.note(t, *q, beats, mark=(x, i, True))
            self.events.append((t, x, None, True))
            t += REST_BEATS * self.beat
        return t

    # --- parts --------------------------------------------------------------------------
    def cadence_chords(self, t):
        """i iv V i, then i VI VII i, the natural minor's own (I IV V I alone in major)."""
        if minor(self.degrees):
            tonic = (("1", -1), ("1", 0), ("b3", 0), ("5", 0))
            cadences = [[("i", tonic), ("iv", (("4", -1), ("1", 0), ("4", 0), ("b6", 0))),
                         ("V", (("5", -1), ("7", -1), ("2", 0), ("5", 0))), ("i", tonic)],
                        [("i", tonic), ("VI", (("b6", -2), ("1", 0), ("b3", 0), ("b6", 0))),
                         ("VII", (("b7", -2), ("2", 0), ("4", 0), ("b7", 0))), ("i", tonic)]]
        else:
            tonic = (("1", -1), ("1", 0), ("3", 0), ("5", 0))
            cadences = [[("I", tonic), ("IV", (("4", -1), ("1", 0), ("4", 0), ("6", 0))),
                         ("V", (("5", -1), ("7", -1), ("2", 0), ("5", 0))), ("I", tonic)]]
        for chords in cadences:
            x = self.excerpt([self.column(c, name=n) for n, c in chords])
            for i, (_, chord) in enumerate(chords):
                self.events.append((t, x, i, True))
                beats = 2 * CHORD_BEATS if i == len(chords) - 1 else CHORD_BEATS
                for d, o in chord:
                    self.score.notes.append(Note(t, beats * self.beat + RING, self.midi(d, o), CHORD_LEVEL, voice="chord"))
                t += beats * self.beat
            t += self.beat
        return t + self.beat

    def updown(self, o):
        up = [(d, o) for d in self.scale] + [("1", o + 1)]
        return up + up[-2::-1]

    def run(self, t, steps):
        """steps: [((d, o), beats)], a column each; a step of more than a beat is held."""
        x = self.excerpt([self.column([q], held=b > 1) for q, b in steps])
        for i, (q, b) in enumerate(steps):
            t = self.note(t, *q, b, mark=(x, i, True))
        return t + 2 * self.beat

    def scales(self, t):
        for o in (0, -1):
            t = self.run(t, [(q, 1) for q in self.updown(o)])
        return t

    def held(self, t):
        for o in (0, -1):
            steps = []
            for q in self.updown(o):
                if q[0] in self.degrees and q[0] != "1":
                    steps += [(q, HOLD_BEATS)] if self.rng.random() < 0.5 else [(q, 1)] * HOLD_BEATS
                else:
                    steps.append((q, 1))
            t = self.run(t, steps)
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


def build(degrees, key, bpm, minutes, rng, data_dir, repeat=2, voice="default"):
    """(the Track, its voice bank, [(part name, start seconds)])."""
    tr = Track(degrees, key, bpm, minutes, rng, repeat)
    bank = VoiceBank(voice, data_dir)
    tr.score.voice = bank.name
    pitch = lambda q: tr.midi(*q)
    targets = [d for d in degrees if d != "1"] or list(degrees)
    notes = [(d, o) for d in targets for o in OCTAVES]
    tonics = [("1", o) for o in OCTAVES]
    pick = lambda: rng.choice(tonics) if rng.random() < TONIC_SHARE else rng.choice(notes)
    enough = lambda g: len({d for d, _ in g if d in targets}) > min(1, len(targets) - 1)
    bank.ensure(spoken(sorted(set(targets) | {"1"}, key=lambda d: SEMITONES[d])))

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
    tr.events.sort(key=lambda e: e[0])
    return tr, bank, parts


def draw_key(rng, keys):
    return rng.choice(keys or NOTE_NAMES)
