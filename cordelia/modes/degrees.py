"""Scale degrees over a drone.

The session opens with the tonic, the fifth and the tonic an octave up, so
the key is set in the ear before anything is asked. Each question: the note sounds for two beats, two beats of silence to
answer in, then the voice says the degree, the note sounds again, and a
beat of rest. With `--answer sung` the voice and the note again are one
thing instead: the degree's solfege syllable sung on the question's pitch,
and no rest after it. The right answer is always given, nothing is ever judged out
loud, and the register varies so that the degree, not the pitch, is what
is being asked: every note of the list within the session's range around the
tonic (`--range`) can come up.

A session asks the list of degrees given on the command line, any subset
of the twelve (`major`, `minor` and `all` stand for three of them); the
list is the exercise, and a new list is a new exercise. Flats are typed by
pressing the degree's key twice and are stored as their own labels (`b3`
is never `3`), so the record says what was asked whatever the list.
"""

import math
import random

from ..score import Clip, Note, Score
from ..voice import SYLLABLE, SungBank, VoiceBank, sampled, sung_label

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

# Degree 1 is the easy one, so it turns up half as often as any other; a degree's weight is
# shared out evenly over its notes in the range, so one that is there more times over (the
# tonic at both ends of an octave) is asked no more often for it. Since 2026-11-15: before,
# the weight was each note's, which made no difference but to b5, the one degree with a
# single note in the range there was (the middle), and so asked half as often as the others.
WEIGHT = {"1": 1}
DEFAULT_WEIGHT = 2
# `cordelia focus` asks each degree of the list in proportion to its trouble over the latest
# PER_DEGREE times it was asked: its miss rate, (missed + 1) / (asked + 2), the mean of its
# Beta(right + 1, missed + 1); so equal skill is an even mix, 1 included. `--by thompson` instead asks each as often as the chance that it is the weakest,
# its Beta from the list's latest SHARED questions drawn against the others' (THOMPSON draws,
# a fixed seed): a degree with few answers there stays uncertain and gets explored.
# `--on b3 4` instead asks half the questions evenly over the list and half over those.
# Either way no degree gets under FLOOR of the questions.
PER_DEGREE = 40
SHARED = 80
THOMPSON = 20000
FLOOR = 0.04
BY = ("recall", "thompson")
# --range: how far the session's notes go under and over the tonic, in semitones, and before
# them the lowest the tonic may be: the tonic is that note or the first one over it, so the
# range moves with the key and is the same degrees in every one. `--range E1 0 12` is the
# tonic (E1 to Eb2) up to the tonic an octave over it; without the note the tonic is the
# middle-register one, TONIC up. Every note of the range that is a degree of the list is
# asked. These words stand for a range when typing, as `minor` does for a list, and are
# expanded before anything is stored: the record only ever holds the note and the two
# numbers. Since 2026-11-14. RANGE is what the degrees mode did before, with no setting for
# it; the melody mode had --octaves and --register; those sessions have no `range`. (For a
# few hours of that day a range was two fixed notes whatever the key, `["E1", "E2"]`.)
TONIC = "G3"
# narrow: the list once, the tonic up to the seventh. middle: what the degrees mode always
# did, the fifth under the tonic to the fourth over its octave. wide: three octaves, the one
# under the tonic and the two over it. low and high: the tonic to its octave, in the bass and
# an octave over the middle. (On 2026-11-14 `middle` was G3 0 12 and `wide` G3 5 17; what is
# stored is the note and the numbers, so those sessions say what they were.)
RANGES = {"narrow": (TONIC, 0, 11), "middle": (TONIC, 5, 17), "wide": (TONIC, 12, 24), "low": ("E1", 0, 12), "high": ("G4", 0, 12)}
RANGE = RANGES["middle"]       # degrees' when none was ever given
LOWEST, HIGHEST = 28, 96       # E1, C7: lower and the pitch is hard to hear, higher and the tone is thin
BASS_UNDER = 48                # a range whose middle (over the keys) is under C3 is a bass line: the bass voice,
                               # and the drone an octave up, out of its way
# A note is louder an octave under the middle-register tonic and softer an octave over it.
OCTAVE_LEVELS = {-1: 1.1, 0: 1.0, 1: 0.9}

NOTE_BEATS = 2
PAUSE_BEATS = 2
AGAIN_BEATS = 2
REST_BEATS = 1
INTRO_BEATS = 1                # the drone's fade-in, then the cadence, then the questions
CADENCE = (("1", 0), ("5", 0), ("1", 1))   # (degree, octave): tonic, fifth, tonic an octave up
CADENCE_BEATS = 1              # each cadence note
CADENCE_REST_BEATS = 2         # after the last one, before the first question
# When the list is the major or the minor scale, the session opens with the scale instead, as
# a melody session does: 1 up to the tonic on top, a beat each, the last held, over the tonic
# and fifth an octave down, so a new key is set in the ear before the first question (most
# wanted in a short focus session). Since 2026-11-14; before, the cadence above for any list.
SCALE_LAST_BEATS = 2
SCALE_BASS = (("1", -1), ("5", -1))
SCALE_BASS_LEVEL = 0.4         # each of the two, as under the melody mode's scale
OUTRO_SECONDS = 2.0            # drone alone after the last answer, fading out
RING = 0.25                    # a note rings this long past its beats

# no `range` here: a session without one in the last config gets RANGE (see range_words)
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


def parse_note(text):
    """'E1', 'eb3', 'F#4' -> its MIDI note (C4 is 60), or None."""
    name, octave = text.rstrip("0123456789"), text[len(text.rstrip("0123456789")):]
    pc = parse_key(name) if name else None
    return None if pc is None or not octave else 12 * (int(octave) + 1) + PITCH_CLASS[name[0].upper()] + (pc - PITCH_CLASS[name[0].upper()] + 6) % 12 - 6


def note_name(midi):
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


def parse_range(words):
    """`--range` words (a shorthand; or the semitones under and over the tonic, with the
    lowest note the tonic may be before them or TONIC) -> [note, under, over], or a SystemExit
    saying why not."""
    words = [str(w) for w in words]
    said = " ".join(words)
    if len(words) == 1 and words[0].lower() in RANGES:
        return list(RANGES[words[0].lower()])
    words = [TONIC, *words] if len(words) == 2 else words
    if len(words) != 3 or parse_note(words[0]) is None or not all(w.isdigit() for w in words[1:]):
        raise SystemExit(f"--range is {', '.join(RANGES)}, or the semitones under and over the tonic (5 17), "
                         f"before them the lowest the tonic may be (E1 0 12; else {TONIC})")
    floor, under, over = parse_note(words[0]), int(words[1]), int(words[2])
    if floor - under < LOWEST or floor + 11 + over > HIGHEST:
        raise SystemExit(f"--range {said}: in some key that goes under {note_name(LOWEST)} or over {note_name(HIGHEST)}")
    return [note_name(floor), under, over]


def range_words(a, last_config, default):
    """The range a session starts from: --range, else the last session's, else `default`."""
    return a.range or (last_config or {}).get("range") or default


def range_name(config):
    """The range as its shorthand when it has one, else `G3 -5 +17`; '' for a session from
    before there were ranges."""
    if not config.get("range"):
        return ""
    if len(config["range"]) == 2:       # the two fixed notes of a few hours of 2026-11-14
        return "-".join(config["range"])
    floor, under, over = config["range"]
    return next((name for name, r in RANGES.items() if list(r) == list(config["range"])), f"{floor} -{under} +{over}")


def span(config):
    """The session's lowest and highest note: its tonic is the first at or over the range's
    note, and the range so far under and over it."""
    floor, under, over = config["range"]
    tonic = parse_note(floor) + (parse_key(config["key"]) - parse_note(floor)) % 12
    return tonic - under, tonic + over


def span_text(config):
    """`B1 to B2 (low)`, `D3 to C5 (G3 -5 +17)`: the session's notes, and the range they come from."""
    low, high = span(config)
    return f"{note_name(low)} to {note_name(high)} ({range_name(config)})"


def bass(config):
    """Whether the session is a bass line: the middle of its range, over the twelve keys, under BASS_UNDER."""
    if "range" not in config:
        return False
    floor, under, over = config["range"]
    return parse_note(floor) + 5.5 + (over - under) / 2 < BASS_UNDER


def in_range(config):
    """The session's notes, low to high, as (label, midi): every note of the range that is a
    degree of the list in the key."""
    pc, (low, high) = parse_key(config["key"]), span(config)
    label = {(pc + s) % 12: d for d, s in SEMITONES.items()}
    return [(label[m % 12], m) for m in range(low, high + 1) if label[m % 12] in config["degrees"]]


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


def flat_keys(degrees):
    """The degrees whose plain key means the flat: those the list asks flat, when it asks no
    degree both flat and natural (minor: 3 6 7), so the key alone says which; none when it
    does ask one both ways. Since 2026-11-16; before, a plain key was always the natural."""
    flats = [d[1:] for d in degrees if d.startswith("b")]
    return [] if any(d in degrees for d in flats) else sorted(flats)


def keymap(degrees=()):
    """Digits and home-row keys name the naturals, or the flats of flat_keys(degrees); the same
    key twice names the other of the two (`33` is b3; once more, `333`, is 3 again), and the home-row key shifted
    is always the flat (`>` is b3); 8 (or u) is another 1 and 9 (or y) another 2, an octave up. Every degree is typeable whatever the
    list asked, so a flat answered in a major session is recorded as what it was."""
    km, flat = {}, flat_keys(degrees)
    for d, keys, shifted in [*((d, (str(d), HOME_ROW[d - 1]), FLAT_ROW[d - 1]) for d in range(1, 8)),
                             (1, "8u", None), (2, "9y", "Y")]:
        once, twice = (f"b{d}", str(d)) if str(d) in flat else (str(d), f"b{d}")
        for k in keys:
            if f"b{d}" in SEMITONES:
                km[k + k] = twice
            km[k] = once
        if shifted and f"b{d}" in SEMITONES:
            km[shifted] = f"b{d}"
    return dict(sorted(km.items(), key=lambda kv: SEMITONES[kv[1]]))


KEYS = f"1-9 {HOME_ROW}uy"      # the hint's first words
GAP = " · "                     # between the hint's parts


def flat_hint(degrees):
    """The hint's part for the plain keys that mean flats (`3 6 7 = b3 b6 b7`), or none."""
    flat = flat_keys(degrees)
    return f"{' '.join(flat)} = {' '.join('b' + d for d in flat)}" if flat else ""


def sung_hint(degrees):
    """The asked flats' syllables (do re mi go without saying)."""
    return "  ".join(f"{d} {SYLLABLE[d]}" for d in degrees if d.startswith("b"))


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
    """What the session drilled, after the mode name in the stats: its degree list (`brief`: by
    its scale's name), and its range when that is not RANGE (which the sessions from before
    there were ranges count as)."""
    ranged = config.get("range") and list(config["range"]) != list(RANGE)
    return ((short if brief else " ".join)(degrees_of(config)), *([range_name(config)] if ranged else []))


def spoken(degrees):
    return {label: SPOKEN[label] for label in degrees}


def key_text(config):
    """The session's key and the list it was drawn from: `Eb (from D Eb E F F#)`, `Eb (from all 12)`."""
    pool = config.get("key_pool")
    drawn = "" if pool is None else " (from all 12)" if len(pool) == 12 else f" (from {' '.join(pool)})"
    return NOTE_NAMES[parse_key(config["key"])] + drawn


def settings(config):
    """The session's settings for its box, as (name, value) rows."""
    return [("key", key_text(config)), ("degrees", " ".join(degrees_of(config))), ("range", span_text(config)),
            *([("focus", focus_text(config["focus"]))] if config.get("focus") else []),
            ("bpm", f"{config['bpm']:g}"), ("answer", config.get("answer", "spoken")),
            ("voice", SINGER if config.get("answer") == "sung" else config.get("voice", "default"))]


def bank(config, data_dir):
    """The spoken bank, or the sung one, with every answer the session can give."""
    if config.get("answer") == "sung":
        b = SungBank(SINGER, data_dir)
        b.ensure([sung_label(d, m) for d, m in in_range(config)])
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
    focus = focus_config(a.on, degrees, last_config, a.recent, a.by) if getattr(a, "focused", False) else None
    config = dict(minutes=a.minutes, key=draw_key(pool, rng, last_config), key_pool=pool, bpm=a.bpm, degrees=list(degrees),
                  range=parse_range(range_words(a, last_config, RANGE)), voice=a.voice, answer=a.answer, keys=1, focus=focus)
    check_range(config, 1)
    unsung = [note_name(m) for _, m in in_range(config) if not sampled(SINGER, m)]
    if a.answer == "sung" and unsung:
        raise SystemExit(f"--answer sung: {SINGER} does not sing {' '.join(unsung)}; another --range, or --answer spoken")
    return config


def check_range(config, least):
    """A SystemExit when the range holds under `least` notes of the list in the session's key."""
    if len(in_range(config)) < least:
        raise SystemExit(f"--range {' '.join(map(str, config['range']))}: it holds {len(in_range(config))} of "
                         f"{' '.join(config['degrees'])}, and a session needs {least}; a wider one")


def hint(config, width):
    """The keys, and with a sung answer the asked flats' syllables (do re mi go without saying)."""
    plain = flat_hint(degrees_of(config))
    keys = GAP.join([KEYS, *([plain, f"natural {plain[0] * 2}"] if plain else ["flat 33 >"])])
    flats = sung_hint(degrees_of(config))
    return keys + ("\n" + flats if config.get("answer") == "sung" and flats else "")


def status(current, n, typed, config, item=None):
    """The question, the key typed, and two lines under it the right answer once it has been said,
    under the typed one."""
    head = f"{current} / {n}   "
    return f"{head}[{typed[-1] if typed else ' '}]\n\n" + (" " * (len(head) + 1) + item["truth"] if item else "")


class Builder:
    def __init__(self, config, bank):
        self.config = config
        self.bank = bank
        self.sung = config.get("answer") == "sung"
        self.beat = 60.0 / config["bpm"]
        self.tonic = tonic_midi(parse_key(config["key"]))
        self.low = bass(config)
        # the root two octaves under the middle-register tonic; one, over a bass line
        self.score = Score(drone={"midi": self.tonic - (12 if self.low else 24)}, voice=bank.name)

    def midi(self, label, octave):
        return self.tonic + SEMITONES[label] + 12 * octave

    def answer_beats(self, clip):
        return max(1, math.ceil(self.bank.seconds(clip) / self.beat))

    def octave(self, midi):
        """The octave a note is in, counted from the middle-register tonic's (0), and
        no further than one either way."""
        return max(-1, min(1, (midi - self.tonic) // 12))

    def phrase(self, t, label, midi):
        """Question at t. Returns (window_end, next_t)."""
        beat = self.beat
        level, voice = OCTAVE_LEVELS[self.octave(midi)], "bass" if self.low else "tone"
        self.score.notes.append(Note(t, NOTE_BEATS * beat + RING, midi, level, voice=voice))
        voice_t = t + (NOTE_BEATS + PAUSE_BEATS) * beat
        if self.sung:
            clip = sung_label(label, midi)
            self.score.clips.append(Clip(voice_t, clip, SUNG_LEVEL))
            return voice_t, voice_t + self.answer_beats(clip) * beat   # no rest: the sung note's fade is the gap
        self.score.clips.append(Clip(voice_t, label))
        voice_beats = self.answer_beats(label)
        again = voice_t + voice_beats * beat
        self.score.notes.append(Note(again, AGAIN_BEATS * beat + RING, midi, level, voice=voice))
        return voice_t, again + (AGAIN_BEATS + REST_BEATS) * beat

    def cadence(self, t):
        """Tonic, fifth, tonic an octave up, starting at t; or, when the list is the major or
        the minor scale, that scale up to the octave over the tonic and fifth. Returns next_t."""
        beat = self.beat
        scale = next((s for s in (SHORTHANDS["major"], SHORTHANDS["minor"]) if set(s) == set(degrees_of(self.config))), None)
        if scale:
            steps = [(d, 0) for d in scale] + [("1", 1)]
            beats = len(steps) - 1 + SCALE_LAST_BEATS
            for label, octave in SCALE_BASS:
                self.score.notes.append(Note(t, beats * beat + RING, self.midi(label, octave), SCALE_BASS_LEVEL))
            for i, (label, octave) in enumerate(steps):
                held = SCALE_LAST_BEATS if i == len(steps) - 1 else 1
                self.score.notes.append(Note(t, held * beat + RING, self.midi(label, octave)))
                t += held * beat
            return t + CADENCE_REST_BEATS * beat
        for label, octave in CADENCE:
            self.score.notes.append(Note(t, CADENCE_BEATS * beat + RING,
                                         self.midi(label, octave), OCTAVE_LEVELS[octave]))
            t += CADENCE_BEATS * beat
        return t + CADENCE_REST_BEATS * beat

    def max_phrase(self):
        if self.sung:
            longest = max(self.answer_beats(sung_label(d, m)) for d, m in in_range(self.config))
            return (NOTE_BEATS + PAUSE_BEATS + longest) * self.beat
        longest = max(self.answer_beats(l) for l in degrees_of(self.config))
        return (NOTE_BEATS + PAUSE_BEATS + longest + AGAIN_BEATS + REST_BEATS) * self.beat


def pool(config, shares=None):
    """((label, midi), weight) for every question the session can ask: the notes of its range;
    a degree's WEIGHT, or with `shares` (degree -> its part of the questions) its share, split
    evenly over its notes. (Before 2026-11-14 a question was (label, octave); see RANGES.)"""
    qs = in_range(config)
    notes = {d: sum(1 for q in qs if q[0] == d) for d in config["degrees"]}
    if shares is None:
        shares = {d: WEIGHT.get(d, DEFAULT_WEIGHT) for d in config["degrees"]}
    return [(q, shares.get(q[0], 0) / notes[q[0]]) for q in qs]


def shares(weights):
    """degree -> weight (any scale) as parts of the questions summing to 1, none under FLOOR:
    those that would be are held at FLOOR and the rest share what is left. Even when every
    weight is 0."""
    if not any(weights.values()):
        weights = dict.fromkeys(weights, 1)
    low = set()
    while True:
        total = sum(w for d, w in weights.items() if d not in low)
        out = {d: FLOOR if d in low else (1 - FLOOR * len(low)) * w / total for d, w in weights.items()}
        under = {d for d, p in out.items() if p < FLOOR and d not in low}
        if not under:
            return {d: round(p, 4) for d, p in out.items()}
        low |= under


def trouble(degrees, rows):
    """Per degree, over its own latest PER_DEGREE questions among `rows` (the list's questions,
    oldest first), so each rests on as much evidence however rarely it has come up: asked,
    right, missed (no answer included) and recall = (right + 1) / (asked + 2), the mean of its
    Beta, 1/2 for a degree not yet asked."""
    out = {}
    for d in degrees:
        mine = [r for r in rows if r["truth"] == d][-PER_DEGREE:]
        right = sum(1 for r in mine if r["correct"] == 1)
        out[d] = dict(asked=len(mine), right=right, missed=len(mine) - right,
                      recall=round((right + 1) / (len(mine) + 2), 4))
    return out


def weakest(counts):
    """degree -> the chance that it is the weakest: each degree's recall a Beta(right + 1,
    missed + 1), THOMPSON draws of every one, the share of draws in which it came lowest.
    Seeded, so the same answers give the same shares."""
    rng, lowest = random.Random(0), dict.fromkeys(counts, 0)
    for _ in range(THOMPSON):
        draw = {d: rng.betavariate(c["right"] + 1, c["missed"] + 1) for d, c in counts.items()}
        lowest[min(draw, key=draw.get)] += 1
    return {d: n / THOMPSON for d, n in lowest.items()}


def focus_config(words, degrees, last_config, recent, by=None):
    """A `cordelia focus` session's focus from `--on`: degrees from the list (manual), [] auto,
    None the last focus session's way when it asked the same list, else auto; auto by `by`
    (None: the last focus session's, else recall).
    `recent(degrees)` gives the latest questions asked of the list. What is stored says how
    it was chosen and the part of the questions it gave each degree."""
    explicit = words is not None
    if by is not None and by not in BY:
        raise SystemExit(f"--by is {' or '.join(BY)}")
    last_by = ((last_config or {}).get("focus") or {}).get("by")
    by = by or (last_by if last_by in BY else BY[0])     # a rule since dropped (f1) falls back
    if not explicit:
        last = last_config and degrees_of(last_config) == tuple(degrees) and last_config.get("focus")
        words = last["degrees"] if last and last["how"] == "manual" else []
    if not words and by == "thompson":
        rows = recent(degrees)[-SHARED:]
        counts = {d: dict(right=sum(1 for r in rows if r["truth"] == d and r["correct"] == 1),
                          missed=sum(1 for r in rows if r["truth"] == d and r["correct"] != 1)) for d in degrees}
        return dict(how="auto", by=by, shared=len(rows), counts=counts, shares=shares(weakest(counts)))
    if not words:
        t = trouble(degrees, recent(degrees))
        return dict(how="auto", by=by, per_degree=PER_DEGREE, trouble=t, shares=shares({d: 1 - t[d][by] for d in degrees}))
    chosen = parse_degrees(words)
    outside = [d for d in chosen if d not in degrees]
    if outside and explicit:
        raise SystemExit(f"--on {' '.join(outside)}: not in the list ({' '.join(degrees)})")
    return dict(how="manual", by=by, degrees=chosen,
                shares=shares({d: 1 / len(degrees) + (1 / len(chosen) if d in chosen else 0) for d in degrees}))


def focus_text(focus, top=None):
    """`auto · b3 24% 4 19% 5 12% …`, the degrees by their part of the questions."""
    ranked = sorted(focus["shares"].items(), key=lambda kv: -kv[1])[:top]
    return " · ".join([focus["how"] + (" by " + focus["by"] if focus["how"] == "auto" and "by" in focus else ""), "  ".join(f"{d} {100 * s:.0f}%" for d, s in ranked)])


def draw(rng, config, count, shares=None):
    """(label, midi) pairs, never the exact same question twice in a row."""
    questions = [q for q, _ in pool(config, shares)]
    weights = [w for _, w in pool(config, shares)]
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
    for idx, (label, midi) in enumerate(draw(rng, config, count, (config.get("focus") or {}).get("shares"))):
        window_end, nxt = b.phrase(t, label, midi)
        items.append(dict(idx=idx, truth=label, ask_s=t, window_end_s=window_end, meta=dict(degree=label, midi=midi)))
        t = nxt
    b.score.seconds = t + OUTRO_SECONDS
    return b.score, items, keymap(degrees_of(config))

