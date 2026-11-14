"""Short melodies over a drone, sung back by a voice.

The session opens with the asked degrees sung up to the octave over the
tonic and fifth, so the key is set before anything is asked. Each question
is one melody of a few quarter notes, played a few times with a bar of
clicks between, then a bar of clicks to think, then sung back in solfege on
its own pitches. You type the degrees, one key per note; a note past the
last starts the answer over, backspace clears it, and what stands when the
singing starts is the answer.

The exercise is described on the command line, as in the degrees mode:
which degrees a melody may use (any of the twelve, and 8 for the tonic on
top), over how many octaves and in which register,
how many notes, how far a move tends to go, and how many times a melody is
played. There is no level table; these together are the exercise, and every answer is stored the same way (the degrees as a
space-separated string), so the stats read across them.
"""

import functools
import random

from ..score import Clip, Note, Score
from ..staff import spell
from ..voice import MAX_SHIFT, SINGERS, SYLLABLE, Choir, sampled, shift, sung_label
from .degrees import FLAT_ROW, HOME_ROW, NOTE_NAMES, SEMITONES, SPOKEN, draw_key, key_pool, key_text, parse_degrees, parse_key, short, tonic_midi

NAME = "melody"

# The twelve degrees and the tonic on top, with their semitones above the tonic.
DEGREES = dict(SEMITONES, **{"8": 12})
LABEL = {semitones: d for d, semitones in SEMITONES.items()}

# The notes a melody is drawn from: the list up from a tonic, `octaves` times over, and with
# 8 in the list the tonic on top of the last. The tonic is the one that puts the middle of
# those octaves nearest G4: for one octave the middle-register tonic (G3 to F#4), for two
# C#3 to C4, for three G2 to F#3; an octave off that where some note would otherwise be
# further than a sample can be pitched from every singer's (the highest do sung is F#5).
CENTRE = 67
OCTAVES = (1, 2, 3)

# --register: where the octaves sit, as the note their middle is nearest. `middle` is the
# placement above, and what every session before there were registers had. `low` is a bass
# line (one octave: the tonic E1 to Eb2) and `high` an octave over middle (the tonic G4 to
# F#5); these two go where they are asked whatever the singers can reach, an octave nearer
# the middle only where a note would be under FLOOR or over CEILING. A low session's notes
# are the bass voice, and its drone an octave up, out of the line's way.
REGISTERS = dict(low=40, middle=CENTRE, high=79)
FLOOR, CEILING = 28, 96        # E1, C7: lower and the pitch is hard to hear, higher and the tone is thin

# degrees: what a melody may use; octaves: over how many; length: how many notes;
# spread: how far a move tends to go, the weight of a move of d positions along the
# notes (the list, octave after octave) being spread ** (d - 1), so 0 is steps only
# and 1 is uniform over the other notes (never the same note twice running; the
# first note is uniform);
# hearings: how many times a melody is played before the answer.
DEFAULTS = dict(minutes=5.0, key_pool=["all"], bpm=55.0, degrees=("1", "2", "3", "4", "5"), octaves=1, length=4, spread=0.2,
                hearings=3, singer="jennifer", shape="none", register="middle")

# --shape: under the sung melody, a mark under each note as high as the note is above the
# melody's lowest, a level per scale step; the levels a character has, low to high. A row of
# them is added for every that many steps the session's notes span. The slabs' middle six
# are Unicode 13 (U+1FB76 on), which not every terminal draws.
SHAPES = dict(none="", slabs="▁🭻🭺🭹🭸🭷🭶▔", braille="⣀⠤⠒⠉")

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


def notes(config):
    """The MIDI notes a melody is drawn from, low to high. Sessions before 2026-11-13 had
    no `octaves`, and were one."""
    pc, octaves, register = parse_key(config["key"]), config.get("octaves", 1), config.get("register", "middle")
    target = REGISTERS[register] - 6 * octaves
    tonic = target + (pc - target + 6) % 12 - 6
    steps = sorted({SEMITONES[d] for d in config["degrees"] if d != "8"})
    place = lambda low: [low + 12 * o + s for o in range(octaves) for s in steps] + [low + 12 * octaves] * ("8" in config["degrees"])   # noqa: E731
    if register != "middle":
        while max(place(tonic)) > CEILING:
            tonic -= 12
        while min(place(tonic)) < FLOOR:
            tonic += 12
        return place(tonic)
    placed = [place(low) for low in (tonic, tonic - 12, tonic + 12, tonic - 24, tonic + 24)]
    # the fewest notes no singer has a sample near, the nearest to the centre first
    return min(placed, key=lambda among: sum(not near(config, m) for m in among))


def near(config, midi):
    """The singers with a sample of the note's syllable near enough to pitch to it."""
    return [s for s in SINGERS if shift(s, SYLLABLE[label(config, midi)], midi) <= MAX_SHIFT]


def able(config, midi):
    """The singers who can sing the note as themselves: it is within what they recorded and
    sing well (voice.SINGS), and a sample of its syllable is near. Since 2026-11-14; before, near was enough,
    and a note up to six semitones past a singer's range was still sung."""
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


def span(config):
    return f"{config['octaves']} octave{'s' * (config['octaves'] > 1)}"


def recipe(config, brief=False):
    """The exercise as words: the list (`brief`: by its scale's name), then the rest. Sessions before
    2026-11-08 had `step`, the share of moves to a neighbour, the rest uniform
    with repeats; the first (2026-11-03) drew every move uniformly."""
    if "spread" in config:
        moves = f"spread {config['spread']:g}"
    else:
        moves = "any move" if config["step"] is None else f"step {config['step']:g}"
    return ((short if brief else " ".join)(config["degrees"]),
            ", ".join([*([config["register"]] if config.get("register", "middle") != "middle" else []),
                       *([span(config)] if config.get("octaves", 1) > 1 else []), f"{config['length']} notes", moves, f"heard {config['hearings']}x"]))


def exercise(config, brief=False):
    """What the session drilled, after the mode name in the stats."""
    return recipe(config, brief)


def settings(config):
    """The session's settings for its box, as (name, value) rows; the register with the
    session's lowest and highest note."""
    among = notes(config)
    pitch = lambda m: f"{NOTE_NAMES[m % 12]}{m // 12 - 1}"      # noqa: E731
    moves = (("spread", f"{config['spread']:g}") if "spread" in config else
             ("step", "any move" if config["step"] is None else f"{config['step']:g}"))
    return [("key", key_text(config)), ("degrees", " ".join(config["degrees"])),
            ("octaves", f"{config.get('octaves', 1)}"), ("register", f"{config.get('register', 'middle')} ({pitch(among[0])} to {pitch(among[-1])})"),
            ("length", f"{config['length']} notes"), moves, ("hearings", f"{config['hearings']}"),
            ("bpm", f"{config['bpm']:g}"), ("singer", config.get("singer", "jennifer"))]


class Builder:
    def __init__(self, config, bank):
        self.config = config
        self.bank = bank
        self.beat = 60.0 / config["bpm"]
        self.pc = parse_key(config["key"])
        self.low = config.get("register", "middle") == "low"
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
        can sing is spoken instead, a degree a beat. Returns next_t."""
        who = singers(self.config, midis)
        if who is None:
            for m in midis:
                self.score.clips.append(Clip(t, f"spoken/{label(self.config, m)}"))
                t += self.beat
            return t
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
        t = self.clicks(t, ANSWER_CLICK_BEATS)
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

    def phrase_beats(self, notes):
        hearings = self.config["hearings"]
        return hearings * notes + (hearings - 1) * CLICK_BEATS + ANSWER_CLICK_BEATS + notes + REST_BEATS


def next_note(rng, config, among, last):
    """Any other note, weighted spread ** (positions away - 1)."""
    i = among.index(last)
    others = [(m, abs(j - i)) for j, m in enumerate(among) if j != i]
    return rng.choices([m for m, _ in others], [config["spread"] ** (away - 1) for _, away in others])[0]


def draw(rng, config, count):
    """`count` melodies for the config as MIDI notes, never the same one twice in a row."""
    out, previous, among = [], None, notes(config)
    while len(out) < count:
        melody = [rng.choice(among)]
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
    if not all(able(config, m) for m in among):
        b.spoken.ensure({d: SPOKEN[d] for d in {label(config, m) for m in among}})
    return b


def configure(a, last_config, rng):
    """A session config from the parsed flags, or a SystemExit saying why not."""
    pool = key_pool(a.key_pool)
    degrees, length, spread, hearings, bpm = parse_degrees(a.degrees, DEGREES), a.length, a.spread, a.hearings, a.bpm
    if len(degrees) < 2:
        raise SystemExit("a melody needs at least two degrees to move between")
    if a.octaves not in OCTAVES:
        raise SystemExit(f"--octaves is {', '.join(map(str, OCTAVES[:-1]))} or {OCTAVES[-1]}")
    if length < 1:
        raise SystemExit("--length must be at least 1")
    if hearings < 1:
        raise SystemExit("--hearings must be at least 1")
    if not 0 <= spread <= 1:
        raise SystemExit("--spread is 0 (steps only) to 1 (any other degree, equally)")
    if a.minutes <= 0:
        raise SystemExit("--minutes must be positive")
    if a.register not in REGISTERS:
        raise SystemExit(f"--register is {', '.join(REGISTERS)}")
    if a.shape not in SHAPES:
        raise SystemExit(f"--shape is {', '.join(SHAPES)}")
    config = dict(minutes=a.minutes, key=draw_key(pool, rng, last_config), key_pool=pool, bpm=bpm, degrees=list(degrees), octaves=a.octaves,
                  length=length, spread=spread, hearings=hearings, singer=a.singer, shape=a.shape, register=a.register, keys=length)
    if a.singer not in SINGERS:
        raise SystemExit(f"singer {a.singer!r}: choose from {', '.join(SINGERS)}")
    return config


def hint(config, width):
    """The keys and the flats' syllables."""
    flats = ", ".join(f"{d} {SYLLABLE[d]}" for d in config["degrees"] if d.startswith("b"))
    return (f"keys 1-9 or {HOME_ROW}uy (8 is 1, 9 is 2); flat: shifted, {FLAT_ROW}Y (> is b3)"
            + (f"\nflats sung: {flats}" if flats else ""))


def step(config, midi):
    """The note's height in scale steps, spelt from its degree (b3 is on the third's line)."""
    return spell(NOTE_NAMES[parse_key(config["key"])], label(config, midi), midi)[0]


@functools.lru_cache
def reach(key, degrees, octaves, register):
    """How many scale steps the session's notes span, both ends counted."""
    config = dict(key=key, degrees=degrees, octaves=octaves, register=register)
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
    rows = -(-reach(config["key"], tuple(config["degrees"]), config.get("octaves", 1), config.get("register", "middle")) // len(levels))
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
    count = max(1, int((limit - t) // (b.phrase_beats(config["length"]) * b.beat)))
    items = []
    for idx, midis in enumerate(draw(rng, config, count)):
        window_end, nxt = b.phrase(t, midis)
        degrees = [label(config, m) for m in midis]
        items.append(dict(idx=idx, truth=" ".join(degrees), ask_s=t, window_end_s=window_end,
                          meta=dict(degrees=degrees, midis=midis, answer="sung" if singers(config, midis) else "spoken")))
        t = nxt
    b.score.seconds = t + OUTRO_SECONDS
    return b.score, items, keymap()

