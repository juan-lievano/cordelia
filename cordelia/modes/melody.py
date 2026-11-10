"""Short melodies over a drone, sung back by a voice.

The session opens with the asked degrees sung up to the octave over the
tonic and fifth, so the key is set before anything is asked. Each question
is one melody of a few quarter notes, played a few times with a bar of
clicks between, then a bar of clicks to think, then sung back in solfege on
its own pitches. You type the degrees, one key per note; a note past the
last starts the answer over, backspace clears it, and what stands when the
singing starts is the answer.

The exercise is described on the command line, as in the degrees mode:
which degrees a melody may use (any of the twelve, and 8 for the tonic
above), how many notes, how far a move tends to go, and how many times a
melody is played. There is no level table; the four together are the
exercise, and every answer is stored the same way (the degrees as a
space-separated string), so the stats read across them.
"""

import random

from ..score import Clip, Note, Score
from ..voice import SYLLABLE, SungBank, sung_label
from .degrees import HOME_ROW, NOTE_NAMES, SEMITONES, parse_degrees, parse_key, random_key, tonic_midi

NAME = "melody"

# The twelve degrees and the tonic above, with their semitones above the tonic.
DEGREES = dict(SEMITONES, **{"8": 12})

# degrees: what a melody may use; length: how many notes; spread: how far a
# move tends to go, the weight of a move of d positions along the list being
# spread ** (d - 1), so 0 is steps only and 1 is uniform over the other
# degrees (never the same degree twice running; the first note is uniform);
# hearings: how many times a melody is played before the answer.
DEFAULTS = dict(minutes=5.0, key=None, bpm=55.0, degrees=("1", "2", "3", "4", "5"), length=4, spread=0.2,
                hearings=3, singer="jennifer")

# A question, in beats: the melody, then two clicks and the melody again
# for each further hearing, a bar of clicks to think, the answer sung a
# note a beat, and a rest.
CLICK_BEATS = 2                # between hearings; since 2026-11-08, 4 before
ANSWER_CLICK_BEATS = 4         # between the last hearing and the answer
REST_BEATS = 2
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
# another 1 for the hand that reaches for it; before 2026-11-08, 8 and u were the tonic above.
FLAT_ROW = "H<>NEIL"


def keymap():
    """Digits and home-row keys name the naturals, the shifted home-row key
    the flat under it."""
    km = {}
    for d in range(1, 8):
        km[str(d)] = km[HOME_ROW[d - 1]] = str(d)
        if f"b{d}" in SEMITONES:
            km[FLAT_ROW[d - 1]] = f"b{d}"
    km["8"] = km["u"] = "1"
    return km


def recipe(config):
    """The exercise as words: the list, then the rest. Sessions before
    2026-11-08 had `step`, the share of moves to a neighbour, the rest uniform
    with repeats; the first (2026-11-03) drew every move uniformly."""
    if "spread" in config:
        moves = f"spread {config['spread']:g}"
    else:
        moves = "any move" if config["step"] is None else f"step {config['step']:g}"
    return (" ".join(config["degrees"]), f"{config['length']} notes, {moves}, heard {config['hearings']}x")


def exercise(config):
    """What the session drilled, after the mode name in the stats."""
    return recipe(config)


def describe(config):
    return f"{NOTE_NAMES[parse_key(config['key'])]} · {' · '.join(recipe(config))} · {config['bpm']:g} BPM"


class Builder:
    def __init__(self, config, bank):
        self.config = config
        self.bank = bank
        self.beat = 60.0 / config["bpm"]
        self.pc = parse_key(config["key"])
        self.score = Score(drone={"midi": 36 + self.pc}, voice=bank.name)

    def midi(self, degree, octave=0):
        return tonic_midi(self.pc) + DEGREES[degree] + 12 * octave

    def sung(self, degree):
        return sung_label(degree, self.midi(degree))

    def melody(self, t, degrees):
        """The notes a beat each from t. Returns next_t."""
        for d in degrees:
            self.score.notes.append(Note(t, self.beat + RING, self.midi(d)))
            t += self.beat
        return t

    def clicks(self, t, beats=CLICK_BEATS):
        for _ in range(beats):
            self.score.notes.append(Note(t, 0.03, 84, CLICK_LEVEL, voice="click"))
            t += self.beat
        return t

    def sing(self, t, degrees):
        """The answer, a note a beat on its own pitch; each sung note's vowel
        lands on the beat and holds a little under the next. Returns next_t."""
        for i, d in enumerate(degrees):
            label = self.sung(d)
            lead = self.bank.lead(label)
            last = i == len(degrees) - 1
            dur = lead + (SUNG_RING if last else self.beat + SUNG_OVERLAP)
            self.score.clips.append(Clip(t - lead, label, SUNG_LEVEL, dur))
            t += self.beat
        return t

    def phrase(self, t, degrees):
        """Question at t. Returns (window_end, next_t)."""
        for i in range(self.config["hearings"]):
            if i:
                t = self.clicks(t)
            t = self.melody(t, degrees)
        t = self.clicks(t, ANSWER_CLICK_BEATS)
        window_end = t
        t = self.sing(t, degrees)
        return window_end, t + REST_BEATS * self.beat

    def cadence(self, t):
        """1, the asked degrees and 8 up the octave, a beat each, the last held,
        over the tonic and fifth, starting at t. Returns next_t."""
        steps = list(dict.fromkeys(["1", *self.config["degrees"], "8"]))
        beats = len(steps) - 1 + CADENCE_LAST_BEATS
        for degree, octave in CADENCE_BASS:
            self.score.notes.append(Note(t, beats * self.beat + RING, self.midi(degree, octave), CHORD_LEVEL))
        for i, degree in enumerate(steps):
            held = CADENCE_LAST_BEATS if i == len(steps) - 1 else 1
            self.score.notes.append(Note(t, held * self.beat + RING, self.midi(degree)))
            t += held * self.beat
        return t + CADENCE_REST_BEATS * self.beat

    def phrase_beats(self, notes):
        hearings = self.config["hearings"]
        return hearings * notes + (hearings - 1) * CLICK_BEATS + ANSWER_CLICK_BEATS + notes + REST_BEATS


def next_note(rng, config, last):
    """Any other degree in the list, weighted spread ** (positions away - 1)."""
    degrees = config["degrees"]
    i = degrees.index(last)
    others = [(d, abs(j - i)) for j, d in enumerate(degrees) if j != i]
    return rng.choices([d for d, _ in others], [config["spread"] ** (away - 1) for _, away in others])[0]


def draw(rng, config, count):
    """`count` melodies for the config, never the same one twice in a row."""
    out, previous = [], None
    while len(out) < count:
        melody = [rng.choice(config["degrees"])]
        while len(melody) < config["length"]:
            melody.append(next_note(rng, config, melody[-1]))
        if melody != previous:
            out.append(melody)
            previous = melody
    return out


def sung_labels(config):
    """Every sung clip a session at this config could need."""
    b = Builder(config, _NoBank())
    return [b.sung(d) for d in config["degrees"]]


class _NoBank:
    name = "none"


def bank(config, data_dir):
    """The singer's bank, with every clip the session can ask for."""
    b = SungBank(config["singer"], data_dir)
    b.ensure(sung_labels(config))
    return b


def configure(a, last_config, rng):
    """A session config from the parsed flags, or a SystemExit saying why not."""
    pc = parse_key(a.key or random_key(rng, last_config and last_config.get("key")))
    if pc is None:
        raise SystemExit(f"--key {a.key!r} is not a note name")
    last = last_config or DEFAULTS
    degrees = parse_degrees(a.degrees, DEGREES) if a.degrees else tuple(last["degrees"])
    length = a.length if a.length is not None else last["length"]
    spread = a.spread if a.spread is not None else last["spread"]
    hearings = a.hearings if a.hearings is not None else last["hearings"]
    bpm = a.bpm if a.bpm is not None else last["bpm"]
    if len(degrees) < 2:
        raise SystemExit("a melody needs at least two degrees to move between")
    if length < 1:
        raise SystemExit("--length must be at least 1")
    if hearings < 1:
        raise SystemExit("--hearings must be at least 1")
    if not 0 <= spread <= 1:
        raise SystemExit("--spread is 0 (steps only) to 1 (any other degree, equally)")
    if a.minutes <= 0:
        raise SystemExit("--minutes must be positive")
    return dict(minutes=a.minutes, key=NOTE_NAMES[pc], bpm=bpm, degrees=list(degrees), length=length, spread=spread,
                hearings=hearings, singer=a.singer, keys=length)


def hint(config, width):
    """What the title doesn't say: the keys and the flats' syllables."""
    return (f"keys 1-7 (or {HOME_ROW}), shifted ({FLAT_ROW}) for the flat (> = b3), 8 or u is 1. "
            + ", ".join(f"{d} {SYLLABLE[d]}" for d in config["degrees"] if d.startswith("b")))


def status(current, n, typed, config):
    slots = ["_"] * config["keys"]
    for i, k in enumerate(typed):
        slots[i] = k
    return f"question {current}/{n}   [{' '.join(slots)}]"


def build_session(config, bank, rng=None):
    """Score + key items for a fresh session of config['minutes']."""
    rng = rng or random.Random()
    b = Builder(config, bank)
    limit = config["minutes"] * 60
    t = b.cadence(INTRO_BEATS * b.beat)
    count = max(1, int((limit - t) // (b.phrase_beats(config["length"]) * b.beat)))
    items = []
    for idx, degrees in enumerate(draw(rng, config, count)):
        window_end, nxt = b.phrase(t, degrees)
        items.append(dict(idx=idx, truth=" ".join(degrees), ask_s=t, window_end_s=window_end,
                          meta=dict(degrees=degrees, midis=[b.midi(d) for d in degrees])))
        t = nxt
    b.score.seconds = t + OUTRO_SECONDS
    return b.score, items, keymap()

