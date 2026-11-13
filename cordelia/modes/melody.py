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
from .degrees import FLAT_ROW, HOME_ROW, SEMITONES, draw_key, key_pool, key_text, parse_degrees, parse_key, short, tonic_midi

NAME = "melody"

# The twelve degrees and the tonic above, with their semitones above the tonic.
DEGREES = dict(SEMITONES, **{"8": 12})

# degrees: what a melody may use; length: how many notes; spread: how far a
# move tends to go, the weight of a move of d positions along the list being
# spread ** (d - 1), so 0 is steps only and 1 is uniform over the other
# degrees (never the same degree twice running; the first note is uniform);
# hearings: how many times a melody is played before the answer.
DEFAULTS = dict(minutes=5.0, key_pool=["all"], bpm=55.0, degrees=("1", "2", "3", "4", "5"), length=4, spread=0.2,
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
# another 1 for the hand that reaches for it, as 9 (y) is another 2; before 2026-11-08, 8 and u were the tonic above.


def keymap():
    """Digits and home-row keys name the naturals, the shifted home-row key
    the flat under it."""
    km = {}
    for d in range(1, 8):
        km[str(d)] = km[HOME_ROW[d - 1]] = str(d)
        if f"b{d}" in SEMITONES:
            km[FLAT_ROW[d - 1]] = f"b{d}"
    km["8"] = km["u"] = "1"
    km["9"] = km["y"] = "2"
    km["Y"] = "b2"
    return km


def recipe(config, brief=False):
    """The exercise as words: the list (`brief`: by its scale's name), then the rest. Sessions before
    2026-11-08 had `step`, the share of moves to a neighbour, the rest uniform
    with repeats; the first (2026-11-03) drew every move uniformly."""
    if "spread" in config:
        moves = f"spread {config['spread']:g}"
    else:
        moves = "any move" if config["step"] is None else f"step {config['step']:g}"
    return ((short if brief else " ".join)(config["degrees"]), f"{config['length']} notes, {moves}, heard {config['hearings']}x")


def exercise(config, brief=False):
    """What the session drilled, after the mode name in the stats."""
    return recipe(config, brief)


def settings(config):
    """The session's settings for its box, as (name, value) rows."""
    moves = (("spread", f"{config['spread']:g}") if "spread" in config else
             ("step", "any move" if config["step"] is None else f"{config['step']:g}"))
    return [("key", key_text(config)), ("degrees", " ".join(config["degrees"])),
            ("length", f"{config['length']} notes"), moves, ("hearings", f"{config['hearings']}"),
            ("bpm", f"{config['bpm']:g}"), ("singer", config.get("singer", "jennifer"))]


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
    pool = key_pool(a.key_pool)
    degrees, length, spread, hearings, bpm = parse_degrees(a.degrees, DEGREES), a.length, a.spread, a.hearings, a.bpm
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
    return dict(minutes=a.minutes, key=draw_key(pool, rng, last_config), key_pool=pool, bpm=bpm, degrees=list(degrees), length=length, spread=spread,
                hearings=hearings, singer=a.singer, keys=length)


def hint(config, width):
    """The keys and the flats' syllables."""
    flats = ", ".join(f"{d} {SYLLABLE[d]}" for d in config["degrees"] if d.startswith("b"))
    return (f"keys 1-9 or {HOME_ROW}uy (8 is 1, 9 is 2); flat: shifted, {FLAT_ROW}Y (> is b3)"
            + (f"\nflats sung: {flats}" if flats else ""))


def status(current, n, typed, config, answer=None):
    """The question, the degrees typed, and two lines under them the melody once its singing
    has started, as in degrees: the syllables are not always clear."""
    slots = ["_"] * config["keys"]
    for i, k in enumerate(typed):
        slots[i] = k
    head = f"{current} / {n}   "
    return f"{head}[{' '.join(slots)}]" + ("\n\n" + " " * (len(head) + 1) + answer if answer else "")


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

