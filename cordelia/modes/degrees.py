"""Scale degrees over a drone.

The session opens with the tonic, the fifth and the tonic an octave up, so
the key is set in the ear before anything is asked. Each question: the note sounds for two beats, two beats of silence to
answer in, then the voice says the degree, the note sounds again, and a
beat of rest. With `--answer sung` the voice and the note again are one
thing instead: the degree's solfege syllable sung on the question's pitch,
and no rest after it. The right answer is always given, nothing is ever judged out
loud, and the register varies so that the degree, not the pitch, is what
is being asked.

A session asks the list of degrees given on the command line, any subset
of the twelve (`major`, `minor` and `all` stand for three of them); the
list is the exercise, and a new list is a new exercise. Flats are typed by
pressing the degree's key twice and are stored as their own labels (`b3`
is never `3`), so the record says what was asked whatever the list.
"""

import math
import random

from ..score import Clip, Note, Score
from ..voice import SYLLABLE, SungBank, VoiceBank, sung_label

NAME = "degrees"

PITCH_CLASS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
NOTE_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]

# Every degree there is, in order up the octave, with its semitones above
# the tonic. A label is what is asked, typed, spoken and stored; the number
# only tells the synth which note to play.
SEMITONES = {"1": 0, "b2": 1, "2": 2, "b3": 3, "3": 4, "4": 5, "b5": 6, "5": 7, "b6": 8, "6": 9, "b7": 10, "7": 11}
SPOKEN = {"1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven",
          "b2": "flat two", "b3": "flat three", "b5": "flat five", "b6": "flat six", "b7": "flat seven"}

# A session asks a list of degrees, any subset of the twelve, given on the
# command line; the list is the exercise, there is no level table. These
# words stand for a list when typing, and are expanded before anything is
# stored, so the record only ever holds the list.
SHORTHANDS = {
    "major": ("1", "2", "3", "4", "5", "6", "7"),
    "minor": ("1", "2", "b3", "4", "5", "b6", "b7"),
    "all": tuple(SEMITONES),
}

# Degree 1 is the easy one, so it turns up half as often as any other.
WEIGHT = {"1": 1}
DEFAULT_WEIGHT = 2
# Questions reach half an octave past the middle register either way: the
# low octave asks the upper half of the scale, the high octave the lower half.
OCTAVES = (-1, 0, 1)
REGISTER = {-1: lambda semis: semis >= 7, 0: lambda semis: True, 1: lambda semis: semis <= 5}
OCTAVE_LEVELS = {-1: 1.1, 0: 1.0, 1: 0.9}
OCTAVE_NAMES = {-1: "low", 0: "mid", 1: "high"}

NOTE_BEATS = 2
PAUSE_BEATS = 2
AGAIN_BEATS = 2
REST_BEATS = 1
INTRO_BEATS = 1                # the drone's fade-in, then the cadence, then the questions
CADENCE = (("1", 0), ("5", 0), ("1", 1))   # (degree, octave): tonic, fifth, tonic an octave up
CADENCE_BEATS = 1              # each cadence note
CADENCE_REST_BEATS = 2         # after the last one, before the first question
OUTRO_SECONDS = 2.0            # drone alone after the last answer, fading out
RING = 0.25                    # a note rings this long past its beats

DEFAULTS = dict(minutes=4.0, key_pool=["all"], bpm=50.0, degrees=SHORTHANDS["major"], voice="default", answer="spoken")
ANSWERS = ("spoken", "sung")   # the word then the note again, or the syllable sung on the note
SINGER = "jennifer"            # the sung answer's voice, the melody mode's default singer
SUNG_LEVEL = 1.3               # as loud as the melody mode's sung answers
MIN_BPM, MAX_BPM = 20, 240

# Sessions before 2026-11-05 had a scale instead of a list and stored a degree
# as its position in that scale; the scale's labels turn those into labels.
OLD_SCALES = {"major": ("1", "2", "3", "4", "5", "6", "7"),
              "natural-minor": ("1", "2", "b3", "4", "5", "b6", "b7"),
              "harmonic-minor": ("1", "2", "b3", "4", "5", "b6", "7")}


def key_pool(words):
    """`--key` words -> the keys a session is drawn from, as note names; `all` is the twelve.
    A SystemExit when a word is not a note name."""
    pool = []
    for w in words:
        if w.lower() == "all":
            pool += NOTE_NAMES
            continue
        pc = parse_key(w)
        if pc is None:
            raise SystemExit(f"--key {w!r} is not a note name (or all)")
        pool.append(NOTE_NAMES[pc])
    return list(dict.fromkeys(pool))


def draw_key(pool, rng, last_config):
    """A key from the pool, not the last session's when the pool has another."""
    last = last_config and last_config.get("key")
    return rng.choice([k for k in pool if k != last] or pool)


def tonic_midi(pc):
    """The middle-register tonic: G3 to F#4, the octave that puts the exercise
    where sung melodies sit (most questions then fall in G3-G5), and in the
    melody mode keeps every sung note within six semitones of a sample."""
    return 60 + pc if pc <= 6 else 48 + pc


def parse_key(text):
    """'G', 'f#', 'Bb' -> pitch class 0-11, or None."""
    key = text.strip().capitalize().replace("s", "#")
    root, accidental = key[:1], key[1:]
    if root not in PITCH_CLASS or accidental not in ("", "#", "b"):
        return None
    return (PITCH_CLASS[root] + {"": 0, "#": 1, "b": -1}[accidental]) % 12


# The digits, and the keys that sit under them on a layer, so one hand can
# answer without the layer key: h , . n e i l stand in for 1-7.
HOME_ROW = "h,.neil"
FLAT_ROW = "H<>NEIL"    # the home-row keys shifted: the flat under each


def keymap():
    """Digits and home-row keys name the naturals; the same key twice names
    the flat under it (`33` is b3; once more, `333`, is 3 again), and so does the home-row key shifted
    (`>` is b3); 8 (or u) is another 1 and 9 (or y) another 2, an octave up. Every degree is typeable whatever the
    list asked, so a flat answered in a major session is recorded as what it was."""
    km = {}
    for d in range(1, 8):
        for k in (str(d), HOME_ROW[d - 1]):
            if f"b{d}" in SEMITONES:
                km[k + k] = f"b{d}"
            km[k] = str(d)
        if f"b{d}" in SEMITONES:
            km[FLAT_ROW[d - 1]] = f"b{d}"
    km["8"] = km["u"] = "1"
    km["9"] = km["y"] = "2"
    km["99"] = km["yy"] = km["Y"] = "b2"
    return dict(sorted(km.items(), key=lambda kv: SEMITONES[kv[1]]))


LABELS = tuple(dict.fromkeys(keymap().values()))   # the order the stats list the degrees in


def parse_degrees(words, table=SEMITONES):
    """Labels and shorthands from the command line -> the list of degrees, in
    order up the octave and without repeats, or a SystemExit saying why not.
    `table` is the labels allowed, with their semitones."""
    labels = []
    for w in words:
        labels += SHORTHANDS.get(w.lower(), (w,))
    bad = [l for l in labels if l not in table]
    if bad:
        raise SystemExit(f"no such degree: {' '.join(bad)}. Use {' '.join(table)}, or {', '.join(SHORTHANDS)}.")
    return tuple(sorted(set(labels), key=table.get))


def degrees_of(config):
    """The degrees a session asked, for sessions from before the list too."""
    if "degrees" in config:
        return tuple(config["degrees"])
    return OLD_SCALES[config.get("scale", "major")]


def short(degrees):
    """A list as the scale it holds whole and whatever else it has (`minor 8`, `major b7`), the
    scale that leaves the least over; as it is when it holds neither whole. For a title: the
    stored list stays the full one."""
    whole = [(name, [d for d in degrees if d not in scale]) for name, scale in SHORTHANDS.items() if set(scale) <= set(degrees)]
    if not whole:
        return " ".join(degrees)
    name, rest = min(whole, key=lambda w: len(w[1]))
    return " ".join([name, *rest])


def exercise(config, brief=False):
    """What the session drilled, after the mode name in the stats: its degree list (`brief`: by its scale's name)."""
    return ((short if brief else " ".join)(degrees_of(config)),)


def spoken(degrees):
    return {label: SPOKEN[label] for label in degrees}


def key_text(config):
    """The session's key and the list it was drawn from: `Eb (from D Eb E F F#)`, `Eb (from all 12)`."""
    pool = config.get("key_pool")
    drawn = "" if pool is None else " (from all 12)" if len(pool) == 12 else f" (from {' '.join(pool)})"
    return NOTE_NAMES[parse_key(config["key"])] + drawn


def settings(config):
    """The session's settings for its box, as (name, value) rows."""
    return [("key", key_text(config)), ("degrees", " ".join(degrees_of(config))),
            ("tempo", f"{config['bpm']:g} BPM"),
            ("voice", SINGER + ", sung" if config.get("answer") == "sung" else config.get("voice", "default"))]


def bank(config, data_dir):
    """The spoken bank, or the sung one, with every answer the session can give."""
    if config.get("answer") == "sung":
        b = SungBank(SINGER, data_dir)
        b.ensure([sung_label(d, tonic_midi(parse_key(config["key"])) + SEMITONES[d] + 12 * o)
                  for (d, o), _ in pool(degrees_of(config))])
        return b
    b = VoiceBank(config.get("voice", "default"), data_dir)
    b.ensure(spoken(degrees_of(config)))
    return b


def configure(a, last_config, rng):
    """A session config from the parsed flags, or a SystemExit saying why not."""
    pool = key_pool(a.key_pool)
    degrees = parse_degrees(a.degrees)
    if a.minutes <= 0:
        raise SystemExit("--minutes must be positive")
    if a.answer not in ANSWERS:
        raise SystemExit(f"--answer is {' or '.join(ANSWERS)}")
    return dict(minutes=a.minutes, key=draw_key(pool, rng, last_config), key_pool=pool, bpm=a.bpm, degrees=list(degrees),
                voice=a.voice, answer=a.answer, keys=1)


def hint(config, width):
    """The keys, and with a sung answer the asked flats' syllables (do re mi go without saying)."""
    keys = f"keys 1-9 or {HOME_ROW}uy\nflat: the key twice or shifted"
    flats = "  ".join(f"{d} {SYLLABLE[d]}" for d in degrees_of(config) if d.startswith("b"))
    if config.get("answer") != "sung" or not flats:
        return keys
    return keys + "\nflats sung: " + flats


def status(current, n, typed, config, answer=None):
    """The question, the key typed, and two lines under it the right answer once it has been said,
    under the typed one."""
    head = f"{current} / {n}   "
    return f"{head}[{typed[-1] if typed else ' '}]\n\n" + (" " * (len(head) + 1) + answer if answer else "")


class Builder:
    def __init__(self, config, bank):
        self.config = config
        self.bank = bank
        self.sung = config.get("answer") == "sung"
        self.beat = 60.0 / config["bpm"]
        self.tonic = tonic_midi(parse_key(config["key"]))
        self.score = Score(drone={"midi": self.tonic - 24}, voice=bank.name)   # the root two octaves under the tonic

    def midi(self, label, octave):
        return self.tonic + SEMITONES[label] + 12 * octave

    def answer_beats(self, clip):
        return max(1, math.ceil(self.bank.seconds(clip) / self.beat))

    def phrase(self, t, label, octave):
        """Question at t. Returns (window_end, next_t)."""
        beat = self.beat
        midi, level = self.midi(label, octave), OCTAVE_LEVELS[octave]
        self.score.notes.append(Note(t, NOTE_BEATS * beat + RING, midi, level))
        voice_t = t + (NOTE_BEATS + PAUSE_BEATS) * beat
        if self.sung:
            clip = sung_label(label, midi)
            self.score.clips.append(Clip(voice_t, clip, SUNG_LEVEL))
            return voice_t, voice_t + self.answer_beats(clip) * beat   # no rest: the sung note's fade is the gap
        self.score.clips.append(Clip(voice_t, label))
        voice_beats = self.answer_beats(label)
        again = voice_t + voice_beats * beat
        self.score.notes.append(Note(again, AGAIN_BEATS * beat + RING, midi, level))
        return voice_t, again + (AGAIN_BEATS + REST_BEATS) * beat

    def cadence(self, t):
        """Tonic, fifth, tonic an octave up, starting at t. Returns next_t."""
        beat = self.beat
        for label, octave in CADENCE:
            self.score.notes.append(Note(t, CADENCE_BEATS * beat + RING,
                                         self.midi(label, octave), OCTAVE_LEVELS[octave]))
            t += CADENCE_BEATS * beat
        return t + CADENCE_REST_BEATS * beat

    def max_phrase(self):
        if self.sung:
            longest = max(self.answer_beats(sung_label(d, self.midi(d, o))) for (d, o), _ in pool(degrees_of(self.config)))
            return (NOTE_BEATS + PAUSE_BEATS + longest) * self.beat
        longest = max(self.answer_beats(l) for l in degrees_of(self.config))
        return (NOTE_BEATS + PAUSE_BEATS + longest + AGAIN_BEATS + REST_BEATS) * self.beat


def pool(degrees):
    """((label, octave), weight) for every question the list can ask."""
    return [((d, o), WEIGHT.get(d, DEFAULT_WEIGHT))
            for o in OCTAVES for d in degrees if REGISTER[o](SEMITONES[d])]


def draw(rng, degrees, count):
    """(label, octave) pairs, never the exact same question twice in a row."""
    questions = [q for q, _ in pool(degrees)]
    weights = [w for _, w in pool(degrees)]
    out = []
    for _ in range(count):
        q = rng.choices(questions, weights)[0]
        while out and q == out[-1] and len(questions) > 1:
            q = rng.choices(questions, weights)[0]
        out.append(q)
    return out


def build_session(config, bank, rng=None):
    """Score + key items for a fresh session of config['minutes']."""
    rng = rng or random.Random()
    b = Builder(config, bank)
    limit = config["minutes"] * 60
    t = b.cadence(INTRO_BEATS * b.beat)
    count = max(1, int((limit - t) // b.max_phrase()))
    items = []
    for idx, (label, octave) in enumerate(draw(rng, config["degrees"], count)):
        window_end, nxt = b.phrase(t, label, octave)
        items.append(dict(idx=idx, truth=label, ask_s=t, window_end_s=window_end,
                          meta=dict(degree=label, octave=octave, register=OCTAVE_NAMES[octave],
                                    midi=b.midi(label, octave))))
        t = nxt
    b.score.seconds = t + OUTRO_SECONDS
    return b.score, items, keymap()

