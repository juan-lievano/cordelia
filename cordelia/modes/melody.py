"""Short melodies over a drone, sung back by a voice.

The session opens with the asked degrees sung up to the octave over the
tonic and fifth, so the key is set before anything is asked. Each question
is one melody of a few quarter notes, played a few times with a bar of
clicks between, then a bar of clicks to think, then sung back in solfege on
its own pitches. You type the degrees, one key per note; a note past the
last starts the answer over, backspace clears it, and what stands when the
singing starts is the answer.

The exercise is described on the command line, as in the degrees mode:
which degrees a melody may use (any of the twelve), how far under and over the tonic,
how many notes, how far a move tends to go, and how many times a melody is
played. There is no level table; these together are the exercise, and every answer is stored the same way (the degrees as a
space-separated string), so the stats read across them.
"""

import functools
import random

from ..score import Clip, Note, Score
from ..staff import spell
from ..voice import MAX_SHIFT, SINGERS, SYLLABLE, Choir, sampled, shift, sung_label
from .degrees import keymap as degrees_keymap
from .degrees import (ANSWERS, FLAT_ROW, GAP, KEYS, NOTE_NAMES, RANGES, SEMITONES, SPOKEN, bass, both_ways, check_range, draw_key, flat_hint, in_range,
                      key_pool, key_text, sung_hint, parse_degrees, parse_key, parse_range, range_name, range_words, short, span_text, tonic_midi)

NAME = "melody"

# The twelve degrees and the tonic on top, with their semitones above the tonic.
DEGREES = dict(SEMITONES, **{"8": 12})
LABEL = {semitones: d for d, semitones in SEMITONES.items()}

# The notes a melody is drawn from: every note of the session's range around the tonic
# (`--range`, as in the degrees mode, whose shorthands and rules these are) that is a degree
# of the list. A range whose middle is under C3 is a bass line: its notes are the
# bass voice, its drone an octave up, out of the line's way, and its answers spoken.
# Since 2026-11-14. Before, the list ran up from a tonic `octaves` times over (1, 2 or 3; with
# 8 in the list, the tonic on top of the last), that tonic the one putting the middle of the
# octaves nearest the `register`'s centre; those sessions have no `range`.
RANGE = RANGES["narrow"]       # what a melody session had before there were ranges, without an 8

# degrees: what a melody may use; length: how many notes;
# spread: how far a move tends to go, the weight of a move of d positions along the
# notes (the list, octave after octave) being spread ** (d - 1), so 0 is steps only
# and 1 is uniform over the other notes (never the same note twice running; the
# first note is uniform);
# hearings: how many times a melody is played before the answer;
# think: the beats of clicks between the last hearing and the answer.
DEFAULTS = dict(minutes=5.0, key_pool=["all"], bpm=55.0, degrees=("1", "2", "3", "4", "5"), length=4, spread=0.2,
                hearings=3, think=4, singer="jennifer", shape="none", answer="sung")

# --shape: under the sung melody, a mark under each note as high as the note is above the
# melody's lowest, a level per scale step; the levels a character has, low to high. A row of
# them is added for every that many steps the session's notes span. The slabs' middle six
# are Unicode 13 (U+1FB76 on), which not every terminal draws.
SHAPES = dict(none="", slabs="▁🭻🭺🭹🭸🭷🭶▔", braille="⣀⠤⠒⠉")

# A question, in beats: the melody, then two clicks and the melody again
# for each further hearing, a bar of clicks to think, the answer sung a
# note a beat (or spoken a degree a beat, then the melody once more; or only the melody once more), and a beat of rest.
CLICK_BEATS = 2                # between hearings; since 2026-11-08, 4 before
ANSWER_CLICK_BEATS = DEFAULTS["think"]   # between the last hearing and the answer, unless --think says (since 2026-11-18)
REST_BEATS = 1                 # after the answer; 2 until 2026-11-14
INTRO_BEATS = 1                # the drone's fade-in, then the cadence, then the questions
CADENCE_REST_BEATS = 2         # after the cadence, before the first question
OUTRO_SECONDS = 2.0            # drone alone after the last answer, fading out
RING = 0.25                    # a melody note rings this long past its beat
CLICK_LEVEL = 0.5
CHORD_LEVEL = 0.4              # each chord tone under the cadence scale
SUNG_LEVEL = 1.3
SUNG_OVERLAP = 0.06            # a sung note holds this far past the next one's vowel
SUNG_RING = 1.5                # the last sung note rings this long at most

# The cadence: 1, the asked degrees and 8, a beat each, the last held, over
# the tonic and fifth an octave down. No third, so the list says what the key
# is and nothing else does.
CADENCE_LAST_BEATS = 2
CADENCE_BASS = (("1", -1), ("5", -1))


# A melody has repeats, so a key twice must stay two notes: the flat is the
# home-row key shifted instead (> is b3). A degree is typed the same in any
# octave (the scorer folds 8 to 1), and the 8 key (u, next along the row) is
# another 1 for the hand that reaches for it, as 9 (y) is another 2; before 2026-11-08, 8 and u were the tonic above.


def keymap(degrees=()):
    """Digits and home-row keys name the naturals, the shifted home-row key
    the flat under it; a degree the list asks only flat, or only natural, is that by either
    key (degrees.keymap, since 2026-11-16)."""
    return {k: label for k, label in degrees_keymap(degrees).items() if len(k) == 1}


def notes(config):
    """The MIDI notes a melody is drawn from, low to high."""
    return [m for _, m in in_range(config)]


def near(config, midi):
    """The singers with a sample of the note's syllable near enough to pitch to it."""
    return [s for s in SINGERS if shift(s, SYLLABLE[label(config, midi)], midi) <= MAX_SHIFT]


def able(config, midi):
    """The singers who can sing the note as themselves: it is within what they recorded and
    sing well (voice.SINGS), and a sample of its syllable is near. Since 2026-11-14; before, near was enough,
    and a note up to six semitones past a singer's range was still sung. Nobody on a bass
    line (since 2026-11-14, later that day): its answers are all spoken, where before those
    of its melodies that stayed at G2 or over were sung, and it was silly to have only some."""
    if bass(config) or config.get("answer") in ("spoken", "visual"):      # --answer spoken, since 2026-11-15; visual, since 2026-11-20
        return []
    return [s for s in near(config, midi) if sampled(s, midi)]


def singers(config, midis):
    """Who sings each note of a melody: the session's singer if she can all of it, else the
    other if they can, else each note by whoever can (the session's singer first). None when
    some note is nobody's: the melody is then spoken."""
    order = sorted(SINGERS, key=lambda s: s != config.get("singer"))
    whole = [s for s in order if all(s in able(config, m) for m in midis)]
    if whole:
        return [whole[0]] * len(midis)
    each = [[s for s in order if s in able(config, m)] for m in midis]
    return [who[0] for who in each] if all(each) else None


def label(config, midi):
    """The degree a note is in the session's key, in any octave."""
    return LABEL[(midi - parse_key(config["key"])) % 12]


def recipe(config, brief=False):
    """The exercise as words: the list (`brief`: by its scale's name), then the rest, the range
    first unless it is RANGE. Sessions before 2026-11-14 had a register and octaves instead
    of a range; before 2026-11-08 `step`, the share of moves to a neighbour, the rest uniform
    with repeats; the first (2026-11-03) drew every move uniformly."""
    if "spread" in config:
        moves = f"spread {config['spread']:g}"
    else:
        moves = "any move" if config["step"] is None else f"step {config['step']:g}"
    if "range" in config:
        where = [range_name(config)] if list(config["range"]) != list(RANGE) else []
    else:
        where = [*([config["register"]] if config.get("register", "middle") != "middle" else []),
                 *([f"{config['octaves']} octaves"] if config.get("octaves", 1) > 1 else [])]
    return ((short if brief else " ".join)(config["degrees"]),
            ", ".join([*where, f"{config['length']} notes", moves, f"heard {config['hearings']}x"]))


def exercise(config, brief=False):
    """What the session drilled, after the mode name in the stats."""
    return recipe(config, brief)


def settings(config):
    """The session's settings for its box, as (name, value) rows."""
    moves = (("spread", f"{config['spread']:g}") if "spread" in config else
             ("step", "any move" if config["step"] is None else f"{config['step']:g}"))
    return [("key", key_text(config)), ("degrees", " ".join(config["degrees"])), ("range", span_text(config)),
            ("length", f"{config['length']} notes"), moves, ("hearings", f"{config['hearings']}"), ("think", f"{think(config)} beats"),
            ("bpm", f"{config['bpm']:g}"), ("answer", config.get("answer", "sung")), ("singer", config.get("singer", "jennifer"))]


def think(config):
    """The beats of clicks before the answer; sessions before 2026-11-18 had no setting for it."""
    return config.get("think", ANSWER_CLICK_BEATS)


class Builder:
    def __init__(self, config, bank):
        self.config = config
        self.bank = bank
        self.beat = 60.0 / config["bpm"]
        self.pc = parse_key(config["key"])
        self.low = bass(config)
        self.score = Score(drone={"midi": (48 if self.low else 36) + self.pc}, voice=bank.name)

    def midi(self, degree, octave=0):
        return tonic_midi(self.pc) + DEGREES[degree] + 12 * octave

    def sung(self, midi, singer):
        return f"{singer}/{sung_label(label(self.config, midi), midi)}"

    def melody(self, t, midis):
        """The notes a beat each from t. Returns next_t."""
        for m in midis:
            self.score.notes.append(Note(t, self.beat + RING, m, voice="bass" if self.low else "tone"))
            t += self.beat
        return t

    def clicks(self, t, beats=CLICK_BEATS):
        for _ in range(beats):
            self.score.notes.append(Note(t, 0.03, 84, CLICK_LEVEL, voice="click"))
            t += self.beat
        return t

    def sing(self, t, midis):
        """The answer, a note a beat on its own pitch; each sung note's vowel
        lands on the beat and holds a little under the next. A melody with a note nobody
        can sing is spoken instead, a degree a beat, and then played once more (since
        2026-11-16: the words have no pitch to check the answer against). With --answer visual
        no voice at all: the melody is played once more as its degrees show. Returns next_t."""
        who = singers(self.config, midis)
        if who is None:
            for m in [] if self.config.get("answer") == "visual" else midis:
                self.score.clips.append(Clip(t, f"spoken/{label(self.config, m)}"))
                t += self.beat
            return self.melody(t, midis)
        for i, (m, singer) in enumerate(zip(midis, who)):
            clip = self.sung(m, singer)
            lead = self.bank.lead(clip)
            last = i == len(midis) - 1
            dur = lead + (SUNG_RING if last else self.beat + SUNG_OVERLAP)
            self.score.clips.append(Clip(t - lead, clip, SUNG_LEVEL, dur))
            t += self.beat
        return t

    def phrase(self, t, midis):
        """Question at t. Returns (window_end, next_t)."""
        for i in range(self.config["hearings"]):
            if i:
                t = self.clicks(t)
            t = self.melody(t, midis)
        t = self.clicks(t, think(self.config))
        window_end = t
        t = self.sing(t, midis)
        return window_end, t + REST_BEATS * self.beat

    def cadence(self, t):
        """1, the asked degrees and 8 up the octave from the middle-register tonic, a beat
        each, the last held, over the tonic and fifth, starting at t. Returns next_t."""
        steps = list(dict.fromkeys(["1", *self.config["degrees"], "8"]))
        beats = len(steps) - 1 + CADENCE_LAST_BEATS
        for degree, octave in CADENCE_BASS:
            self.score.notes.append(Note(t, beats * self.beat + RING, self.midi(degree, octave), CHORD_LEVEL))
        for i, degree in enumerate(steps):
            held = CADENCE_LAST_BEATS if i == len(steps) - 1 else 1
            self.score.notes.append(Note(t, held * self.beat + RING, self.midi(degree)))
            t += held * self.beat
        return t + CADENCE_REST_BEATS * self.beat

    def phrase_beats(self, midis):
        """How long the melody's question is: a spoken answer is the degrees, then the melody again."""
        hearings, notes = self.config["hearings"], len(midis)
        answer = notes if singers(self.config, midis) or self.config.get("answer") == "visual" else 2 * notes
        return hearings * notes + (hearings - 1) * CLICK_BEATS + think(self.config) + answer + REST_BEATS


# To do (noted 2026-11-20): a second way of drawing the next note, nearer how tunes move, to choose beside this one.
# What `spread` cannot do at any value: the same note again (about a fifth of a tune's moves; never dealt here);
# fourths, fifths and octaves more often than a steady falloff gives, sixths and sevenths less; after a leap, a
# step back the other way (this draw has no memory of the move before). Of a tune's moves that change note about
# 60-70 % are steps, 15-20 % thirds, 10 % fourths and fifths, a few % wider: a spread of 0.3 to 0.4 by the steps
# alone. Those shares are from memory of folk-song and classical counts: check them against a corpus first.
# A run's count in `stats --full` (full.possible) leaves out a note twice in a row, and would have to let it in.
def next_note(rng, config, among, last):
    """Any other note, weighted spread ** (positions away - 1)."""
    i = among.index(last)
    others = [(m, abs(j - i)) for j, m in enumerate(among) if j != i]
    return rng.choices([m for m, _ in others], [config["spread"] ** (away - 1) for _, away in others])[0]


def draw(rng, config, count):
    """`count` melodies for the config as MIDI notes, never the same one twice in a row."""
    out, previous, among = [], None, notes(config)
    # the first note: every degree as likely, whichever of its notes (so not the tonic twice
    # as often where the range has it at both ends; since 2026-11-15, any note equally before)
    first = [1 / sum(1 for other in among if (other - m) % 12 == 0) for m in among]
    while len(out) < count:
        melody = [rng.choices(among, first)[0]]
        while len(melody) < config["length"]:
            melody.append(next_note(rng, config, among, melody[-1]))
        if melody != previous:
            out.append(melody)
            previous = melody
    return out


def sung_labels(config):
    """Every sung clip a session at this config could need."""
    b = Builder(config, _NoBank())
    return [b.sung(m, s) for m in notes(config) for s in able(config, m)]


class _NoBank:
    name = "none"


def bank(config, data_dir):
    """The singers' banks, with every clip the session can ask for."""
    b = Choir(data_dir)
    b.ensure(sung_labels(config))
    among = notes(config)
    if config.get("answer") != "visual" and not all(able(config, m) for m in among):
        b.spoken.ensure({d: SPOKEN[d] for d in {label(config, m) for m in among}})
    return b


def configure(a, last_config, rng):
    """A session config from the parsed flags, or a SystemExit saying why not."""
    pool = key_pool(a.key_pool)
    degrees, length, spread, hearings, bpm = parse_degrees(a.degrees), a.length, a.spread, a.hearings, a.bpm
    if length < 1:
        raise SystemExit("--length must be at least 1")
    if hearings < 1:
        raise SystemExit("--hearings must be at least 1")
    if a.think < 0:
        raise SystemExit("--think is 0 beats or more")
    if not 0 <= spread <= 1:
        raise SystemExit("--spread is 0 (steps only) to 1 (any other degree, equally)")
    if a.minutes <= 0:
        raise SystemExit("--minutes must be positive")
    if a.answer not in ANSWERS:
        raise SystemExit(f"--answer is {' or '.join(ANSWERS)}")
    if a.shape not in SHAPES:
        raise SystemExit(f"--shape is {', '.join(SHAPES)}")
    config = dict(minutes=a.minutes, key=draw_key(pool, rng, last_config), key_pool=pool, bpm=bpm, degrees=list(degrees),
                  range=parse_range(range_words(a, last_config, RANGE)),
                  length=length, spread=spread, hearings=hearings, think=a.think, singer=a.singer, shape=a.shape, answer=a.answer, keys=length)
    if a.singer not in SINGERS:
        raise SystemExit(f"singer {a.singer!r}: choose from {', '.join(SINGERS)}")
    check_range(config, 2)      # two notes to move between
    return config


def hint(config, width):
    """The keys and the flats' syllables."""
    flats = sung_hint(config["degrees"])
    both = both_ways(config["degrees"])
    return GAP.join([KEYS, *filter(None, [flat_hint(config["degrees"]), both and f"flat {FLAT_ROW[int(both) - 1]}"])]) + (
        "\n" + flats if flats else "")


def step(config, midi):
    """The note's height in scale steps, spelt from its degree (b3 is on the third's line)."""
    return spell(NOTE_NAMES[parse_key(config["key"])], label(config, midi), midi)[0]


@functools.lru_cache
def reach(key, degrees, *among):
    """How many scale steps the session's notes span, both ends counted."""
    config = dict(key=key, degrees=degrees, range=among)
    steps = [step(config, m) for m in notes(config)]
    return max(steps) - min(steps) + 1


def shape(config, midis, width):
    """The --shape rows, top first: under each note (`width` columns, one between) its mark, in
    as few rows as the melody takes, right under it; then blank rows, as many as the widest
    melody of the session would need, so the panel is as tall for every question (and all of
    them blank without `midis`, before the answer)."""
    levels = SHAPES[config.get("shape", "none")]
    if not levels:
        return []
    rows = -(-reach(config["key"], tuple(config["degrees"]), *config["range"]) // len(levels))
    steps = [step(config, m) for m in midis or []]
    high = [s - min(steps) for s in steps]
    used = max(high, default=-1) // len(levels) + 1
    return [" ".join((levels[h % len(levels)] if h // len(levels) == r else " ") * width for h in high)
            for r in range(used - 1, -1, -1)] + [""] * (rows - used)


def status(current, n, typed, config, item=None):
    """The question, the degrees typed, and two lines under them the melody once its singing
    has started, as in degrees: the syllables are not always clear. Every degree as wide as
    the list's widest, so the notes are evenly spaced; under them the --shape rows."""
    width = max(map(len, config["degrees"]))
    slots = ["_"] * config["keys"]
    for i, k in enumerate(typed):
        slots[i] = k
    head = f"{current} / {n}   "
    under = lambda text: " " * (len(head) + 1) + text      # noqa: E731
    row = lambda labels: " ".join(l.rjust(width) for l in labels)      # noqa: E731
    return "\n".join([f"{head}[{row(slots)}]", "", under(row(item["truth"].split())) if item else "",
                      *map(under, shape(config, item and item["meta"].get("midis"), width))]).rstrip("\n")


def build_session(config, bank, rng=None):
    """Score + key items for a fresh session of config['minutes']."""
    rng = rng or random.Random()
    b = Builder(config, bank)
    limit = config["minutes"] * 60
    t = b.cadence(INTRO_BEATS * b.beat)
    count = max(1, int((limit - t) // ((b.phrase_beats([]) + (config["hearings"] + 1) * config["length"]) * b.beat)))   # were all of them sung
    items = []
    for idx, midis in enumerate(draw(rng, config, count)):
        if items and t + b.phrase_beats(midis) * b.beat > limit + 1e-6:      # the spoken ones are longer
            break
        window_end, nxt = b.phrase(t, midis)
        degrees = [label(config, m) for m in midis]
        items.append(dict(idx=idx, truth=" ".join(degrees), ask_s=t, window_end_s=window_end,
                          meta=dict(degrees=degrees, midis=midis, answer="sung" if singers(config, midis) else "visual" if config.get("answer") == "visual" else "spoken")))
        t = nxt
    b.score.seconds = t + OUTRO_SECONDS
    return b.score, items, keymap(config["degrees"])

