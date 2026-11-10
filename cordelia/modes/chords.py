"""Chord qualities, one chord at a time, the answer spoken.

No drone: the question is the quality of the chord relative to its own
root, and a key under it would give the ear something else to hear it
against. The root changes every question and is always the lowest note, so
the bass tells you the root and the quality is all that is asked. The chord
sounds for two beats; in levels 1-3 it then comes back one note at a time
from the root up and holds, so the intervals inside it can be heard before
answering; then two beats of clicks to answer in, the voice names it, and
the chord sounds again. Levels 4-6 are the same chords with the arpeggio
only after the voice. An answer counts anywhere before the voice, arpeggio
heard or not.

The ten qualities and the three sets follow Joe Luegers' "The 10 Best
Chords" (Epic Ear Training): the triads and the bare fifth first, the
sevenths next, then all ten in open voicing with the root an octave down.
A level is a row of LEVELS; every level's answers are stored as the same
quality labels, so the stats read across them.
"""

import math
import random

from ..score import Clip, Note, Score
from ..voice import VoiceBank
from .degrees import NOTE_NAMES

NAME = "chords"

# label: (semitones above the root, the word the voice says, the key that answers it,
#         the spelling against the major scale)
QUALITIES = {
    "maj": ((0, 4, 7), "major", "M", "1 3 5"),
    "min": ((0, 3, 7), "minor", "m", "1 ♭3 5"),
    "sus4": ((0, 5, 7), "sus four", "s", "1 4 5"),
    "aug": ((0, 4, 8), "augmented", "a", "1 3 ♯5"),
    "5": ((0, 7), "five", "5", "1 5"),
    "min7": ((0, 3, 7, 10), "minor seven", "n", "1 ♭3 5 ♭7"),
    "maj7": ((0, 4, 7, 11), "major seven", "j", "1 3 5 7"),
    "m7b5": ((0, 3, 6, 10), "half diminished", "h", "1 ♭3 ♭5 ♭7"),
    "dom7": ((0, 4, 7, 10), "dominant seven", "d", "1 3 5 ♭7"),
    "dim7": ((0, 3, 6, 9), "diminished seven", "o", "1 ♭3 ♭5 ♭♭7"),
}
LABELS = tuple(QUALITIES)        # the order the stats list the qualities in
TRIADS = ("maj", "min", "sus4", "aug", "5")
# Sevenths least to most tense, Luegers' ranking; the cheat sheet shows them in this order.
SEVENTHS = ("min7", "maj7", "m7b5", "dom7", "dim7")

# qualities: what may be asked; open: the root an octave under the rest;
# arpeggio: "before" the answer window (levels 1-3) or only "after" the voice.
SETS = (
    (TRIADS, False, "major, minor, sus4, augmented and bare fifth, close voicing"),
    (SEVENTHS, False, "the five seventh chords, close voicing"),
    (TRIADS + SEVENTHS, True, "all ten, the root an octave under the rest"),
)
LEVELS = {}
for _n, (_q, _open, _about) in enumerate(SETS, 1):
    LEVELS[_n] = dict(qualities=_q, open=_open, arpeggio="before", about=_about + ", arpeggiated before you answer")
for _n, (_q, _open, _about) in enumerate(SETS, 4):
    LEVELS[_n] = dict(qualities=_q, open=_open, arpeggio="after", about=_about + ", arpeggiated after the answer")

# The root in close position lies in this octave (F3 to E4), so the widest
# chord tops out around D5; open voicing drops the root an octave.
ROOT_LOW, ROOT_HIGH = 53, 64

CHORD_BEATS = 2
PAUSE_BEATS = 2                # the answer window, a click a beat
AGAIN_BEATS = 2                # the chord after the voice
ARPEGGIO_BEATS = 0.5           # between the notes of the arpeggio
ARPEGGIO_HOLD_BEATS = 1        # the whole chord held after the last note enters, at least;
                               # the arpeggio is rounded up to whole beats so the clicks stay on the beat
REST_BEATS = 1
INTRO_BEATS = 2                # silence before the first question
OUTRO_SECONDS = 0.0            # no drone to fade, so nothing after the last rest
RING = 0.25
CHORD_LEVEL = 0.8              # per note in the block: 0.55 sat 4-5 dB under a melody note once the strike decayed
ARPEGGIO_LEVEL = 1.0
CLICK_LEVEL = 0.5

DEFAULTS = dict(minutes=4.0, bpm=50.0, level=1, voice="default")


def keymap(level):
    return {QUALITIES[q][2]: q for q in LEVELS[level]["qualities"]}


def spoken(level):
    return {q: QUALITIES[q][1] for q in LEVELS[level]["qualities"]}


def exercise(config, brief=False):
    """What the session drilled, after the mode name in the stats: its level."""
    return (str(config["level"]),)


def settings(config):
    """The session's settings for its box, as (name, value) rows."""
    return [("level", f"{config['level']}: {LEVELS[config['level']]['about']}"), ("tempo", f"{config['bpm']:g} BPM"),
            ("voice", config.get("voice", "default"))]


def bank(config, data_dir):
    b = VoiceBank(config.get("voice", "default"), data_dir)
    b.ensure(spoken(config["level"]))
    return b


def configure(a, last_config, rng):
    """A session config from the parsed flags, or a SystemExit saying why not."""
    level = a.level
    if level not in LEVELS:
        raise SystemExit(f"level {level}: choose from {', '.join(map(str, LEVELS))}")
    if a.minutes <= 0:
        raise SystemExit("--minutes must be positive")
    return dict(minutes=a.minutes, bpm=a.bpm, level=level, voice=a.voice, keys=1)


def hint(config, width):
    """A cheat sheet: key (chord symbol) spelling against the major scale,
    in as many equal columns as fit in `width`."""
    entries = [f"{QUALITIES[q][2]} ({q}){' ' * (5 - len(q))}{QUALITIES[q][3]}" for q in LEVELS[config["level"]]["qualities"]]
    cell = max(map(len, entries)) + 3
    per_line = max(1, (width + 4) // cell)
    rows = [entries[i:i + per_line] for i in range(0, len(entries), per_line)]
    return "\n".join("".join(e.ljust(cell) for e in row).rstrip() for row in rows)


def status(current, n, typed, config):
    answer = f"{QUALITIES[typed[-1]][2]} ({typed[-1]})" if typed else " "
    return f"{current} / {n}   [{answer}]"


def voicing(root, quality, open_):
    """MIDI notes, root lowest."""
    notes = [root + i for i in QUALITIES[quality][0]]
    if open_:
        notes[0] -= 12
    return notes


class Builder:
    def __init__(self, config, bank):
        self.config = config
        self.bank = bank
        self.beat = 60.0 / config["bpm"]
        self.open = LEVELS[config["level"]]["open"]
        self.arpeggio_when = LEVELS[config["level"]]["arpeggio"]
        self.score = Score(voice=bank.name)

    def block(self, t, midis, beats, level=CHORD_LEVEL):
        for m in midis:
            self.score.notes.append(Note(t, beats * self.beat + RING, m, level, voice="chord"))
        return t + beats * self.beat

    def clicks(self, t, beats=PAUSE_BEATS):
        for _ in range(beats):
            self.score.notes.append(Note(t, 0.03, 84, CLICK_LEVEL, voice="click"))
            t += self.beat
        return t

    @staticmethod
    def arpeggio_beats(n):
        return math.ceil(ARPEGGIO_BEATS * (n - 1) + ARPEGGIO_HOLD_BEATS)

    def arpeggio(self, t, midis):
        """From the root up, each note entering half a beat after the last and
        holding until the section ends. Returns next_t."""
        end = t + self.arpeggio_beats(len(midis)) * self.beat
        for i, m in enumerate(midis):
            start = t + i * ARPEGGIO_BEATS * self.beat
            self.score.notes.append(Note(start, end - start + RING, m, ARPEGGIO_LEVEL, voice="chord"))
        return end

    def phrase(self, t, root, quality):
        """Question at t. Returns (window_end, next_t)."""
        beat = self.beat
        midis = voicing(root, quality, self.open)
        t = self.block(t, midis, CHORD_BEATS)
        if self.arpeggio_when == "before":
            t = self.arpeggio(t, midis)
        voice_t = self.clicks(t)
        self.score.clips.append(Clip(voice_t, quality))
        t = voice_t + max(1, math.ceil(self.bank.seconds(quality) / beat)) * beat
        t = self.arpeggio(t, midis) if self.arpeggio_when == "after" else self.block(t, midis, AGAIN_BEATS)
        return voice_t, t + REST_BEATS * beat

    def max_phrase(self):
        spec = LEVELS[self.config["level"]]
        longest = max(self.bank.seconds(q) for q in spec["qualities"])
        widest = max(len(QUALITIES[q][0]) for q in spec["qualities"])
        again = self.arpeggio_beats(widest) if self.arpeggio_when == "after" else AGAIN_BEATS
        before = self.arpeggio_beats(widest) if self.arpeggio_when == "before" else 0
        return (CHORD_BEATS + before + PAUSE_BEATS + max(1, math.ceil(longest / self.beat))
                + again + REST_BEATS) * self.beat


def draw(rng, level, count):
    """(root midi, quality) pairs: never the exact same chord twice in a row."""
    questions = [(r, q) for r in range(ROOT_LOW, ROOT_HIGH + 1) for q in LEVELS[level]["qualities"]]
    out = []
    for _ in range(count):
        q = rng.choice(questions)
        while out and q == out[-1]:
            q = rng.choice(questions)
        out.append(q)
    return out


def build_session(config, bank, rng=None):
    """Score + key items for a fresh session of config['minutes']."""
    rng = rng or random.Random()
    b = Builder(config, bank)
    level = config["level"]
    limit = config["minutes"] * 60
    t = INTRO_BEATS * b.beat
    count = max(1, int((limit - t) // b.max_phrase()))
    items = []
    for idx, (root, quality) in enumerate(draw(rng, level, count)):
        window_end, nxt = b.phrase(t, root, quality)
        items.append(dict(idx=idx, truth=quality, ask_s=t, window_end_s=window_end,
                          meta=dict(level=level, quality=quality, root=NOTE_NAMES[root % 12], root_midi=root,
                                    midis=voicing(root, quality, b.open))))
        t = nxt
    b.score.seconds = t + OUTRO_SECONDS
    return b.score, items, keymap(level)

