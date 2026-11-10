# cordelia — ear-training drills that write down every answer

A mode asks, you answer, and everything is recorded. A mode writes a *score*
(what sounds when) and a *key* (what was asked, when, and the right answer),
the renderer turns the score into one WAV, the collector plays it and logs
every key you press with its time, the scorer matches presses to questions
afterwards, and `stats` reads the record. Nothing reacts while the audio
plays, and nothing on screen says whether you were right. Standard library
only; the spoken answers come from macOS `say`.

`CHEATSHEET.md` lists every command, flag and key in a line each, and is the
page to keep current: a change to a command updates it in the same commit.
That matters more than keeping this README current; the README explains how
things work and can lag, the cheat sheet is what gets read before typing.

```sh
cordelia degrees                                   # every setting the last degrees session's (at first: 4 min, 50 BPM, major), random key
cordelia degrees minor --minutes 5
python3 -m cordelia degrees                        # the same, from the repo
python3 -m cordelia degrees 1 2 b3 4 5 b6 b7 --key A   # any list of degrees is an exercise; minor = this list, all = the twelve
python3 -m cordelia degrees 1 2 5 6                # a list never typed before is a new exercise from this session on
python3 -m cordelia degrees --voice Samantha       # any `say -v ?` voice
python3 -m cordelia degrees --tag headphones       # sticky, like teepee; --tag none clears
python3 -m cordelia degrees --midi t.mid           # also write the score as MIDI
python3 -m cordelia chords --ambient --minutes 60   # any mode: the same audio, no keys read, nothing recorded
python3 -m cordelia melody                         # the last melody session's settings (at first: 5 min, four notes on 1 to 5, mostly stepwise, 55 BPM), sung back
python3 -m cordelia melody 1 2 b3 4 5 --length 3 --spread 0.5 --key G --singer chengu
python3 -m cordelia chords                         # the last chords session's settings (at first: 4 min, 50 BPM, level 1)
python3 -m cordelia chords 2                       # the sevenths; 3: all ten, open voicing; 4-6: the same without the arpeggio first
python3 -m cordelia stats                          # the last exercise played: histogram, trend, confusions
python3 -m cordelia stats --degrees minor --tag headphones
python3 -m cordelia stats --mode melody            # the last melody session's recipe
python3 -m cordelia journal                        # minutes practised, a cell per day, a column per week
python3 -m cordelia rescore                        # rebuild answers from the raw presses
python3 -m cordelia tags | data
```

Every drill setting left off the command line is the last session's of that
drill (`cli.remember`), the mode's default before there is one; the key is the
exception, drawn at random and never the last one.

`~/.local/bin/cordelia` is a two-line wrapper that runs `python3 -m cordelia`
from this checkout; `pip install -e .` does the same.

### The `degrees` mode

Over a breathing drone, rooted two
octaves under the middle-register tonic (C2 for C), its core steady and its
fifths and shimmer above swelling in and out over several seconds, with
the note timbre of the additive tone (four damped harmonics, softer as it rises). The drone fades in for a beat, then tonic, fifth and tonic an
octave up (a beat each) set the key, and after two beats of rest the
questions start, each at 50 BPM (1.2 s a beat; `--bpm` changes it):

```
beats 1-2   the note           — press 1-7 (8 is 1), or h , . n e i l (u is 1); the same key twice, or shifted, for the flat (33 or > = ♭3), a third time for the natural again
beats 3-4   silence            — the answer window; the last key pressed in it counts
beat  5     the voice says it  — "four", "flat seven"
beats 6-7   the note again
beat  8     rest
```

Without `--key`, every session draws a random key, never the one the last
session was in. The session asks the degrees listed on the command line,
any of `1 b2 2 b3 3 4 b5 5 b6 6 b7 7` (`major`, `minor` and `all` expand
to lists while typing; only the list is stored). The list is the exercise:
there is no level table, `cordelia degrees 1 2 5 6` is a new exercise the
first time it is typed, and the stats keep each list apart. Without a list
the last degrees session's is asked again. Every degree is typeable
whatever the list, so a ♭3 answered in a major session is recorded as ♭3.
Registers are those of the original drill: the low octave asks the upper
half of the scale, the high octave the lower half. Every question is equally
likely except degree 1, asked half as often; nothing is avoided but the exact
same question twice in a row. Esc stops;
everything before it is kept.

### The `melody` mode

The same drone, with 1, the asked degrees and 8 played up the octave over
the tonic and fifth to set the key (a beat a step, the last held; no third,
so the list alone says what the key is). Then each question is one melody
of quarter notes, drawn at random within the recipe; with the default
three hearings:

```
beats 1-4     the melody
beats 5-6     a click a beat
beats 7-10    the melody again
beats 11-12   clicks
beats 13-16   the melody once more
beats 17-20   clicks, to think
beats 21-24   the answer, sung a note a beat   — "do re mi do", on the melody's own pitches
beats 25-26   rest
```

Sessions before 2026-11-08 had four clicks between hearings; the commit
stored with each session tells which.

At 55 BPM, the first session's tempo, a beat is 1.09 s (`--bpm` changes it; later sessions keep the last one's).

Type the degrees as you make them out, one key per note (1-7, or
h , . n e i l; shifted for the flat, since a key twice is a repeated note
here). A degree is the same key in any octave: 1 answers an 8 (and the 8 key, or u, is another 1), and the
scorer folds the two before comparing (since 2026-11-08; before, 8 and u
were the tonic above). A note past the last starts the answer over,
backspace clears it, and what stands when the singing starts is the
answer, stored as `1 2 b3 1`, so a note can be right on its own in the
stats. The singing comes from the
solfege samples in `solfege_samples/` (fixed-do, one syllable per
semitone): each note is the singer's nearest sample of that syllable,
pitched to the note by TD-PSOLA (`cordelia/psola.py`), which moves the
pitch and leaves the singer's speed and vowel alone, so any key sounds
like her. The shift is the key's distance from C, six semitones at most,
and the melody sits in the octave nearest middle C whatever the key.
`--singer`
picks `jennifer` (default) or `chengu`; the sung clips are made once per
note under `data/voices/sung-<singer>/`.

The recipe is given on the command line, as in the degrees mode: the
degrees a melody may use (any of the twelve, `8` for the tonic above, and
the same shorthands), `--length` for how many notes, `--spread` for how far
a move tends to go (to any other degree in the list, one d positions away
weighing spread^(d-1): 0 is steps only, 1 any other degree equally; the
first note is uniform), and `--hearings` for
how many times a melody is played before the answer. The four together are the exercise the stats group
by, so `cordelia melody 1 2 b3 4 5` is a new exercise the first time it is
typed, and so is `--length 5` or `--hearings 2` on a list already played. The two numbered
levels of 2026-11-03 to 11-05 were rewritten into recipes (level 2 is the
default above; level 1 was three degrees with every move equally likely,
shown as "any move").

### The `chords` mode

No drone: a chord is asked for its quality relative to its own root, and a
key under it would be something else to hear it against. The root changes
every question, F3 to E4, and is always the lowest note, so the bass gives
the root and the quality is all that is asked. Levels 1-3:

```
beats 1-2   the chord
beats 3-4   the chord again a note at a time from the root up, half a beat
            apart, each held (three beats for a four-note chord)
beats 5-6   a click a beat          — the answer window runs from the first
                                      chord to the voice, so a key pressed
                                      before or during the arpeggio counts
beat  7     the voice names it      — "minor seven", "half diminished"
beats 8-9   the chord
beat  10    rest
```

Levels 4-6 are the same chords without the arpeggio before the answer: the
chord, two clicks, the voice, then the arpeggio. The ten qualities and the
three sets are Joe Luegers' "The 10 Best Chords" (Epic Ear Training): levels
1 and 4 are major, minor, sus4, augmented and the bare fifth in close voicing
(`M m s a 5`); 2 and 5 the dominant, major, minor, diminished and
half-diminished sevenths (`d j n o h`); 3 and 6 all ten with the root an
octave under the rest. No diminished triad: the diminished seventh stands in
for it. Levels are rows of `LEVELS` in `cordelia/modes/chords.py`; the answer
is stored as the quality label (`maj`, `m7b5`, ...) whatever the level, so
the confusion matrix reads across them, and the keymap is stored with each
session, so the keys can change without touching the record.

### What is recorded

`data/cordelia.db` in the checkout (gitignored; `CORDELIA_DATA_DIR`
overrides it), plus `data/sessions/<id>.score.json` and `<id>.key.jsonl`
per session; `--keep-wav` keeps the audio too.

| table        | one row per | notes |
|--------------|-------------|-------|
| `sessions`   | session     | mode, config as JSON (key, the degrees asked or the level, bpm, voice, the keymap, seed, the commit the code was at, null if the tree was dirty), tags, outcome (`completed` / `stopped` / `aborted`), ms into the audio when it ended |
| `items`      | question    | truth as a keymap label, onset ms, window-end ms (when the answer starts sounding), meta JSON (degree label, octave, register, MIDI note) |
| `keystrokes` | key press   | ms since playback was started, key name (`4`, `space`, `other`...) |
| `answers`    | question    | derived: answer, correct (NULL when nothing was pressed), latency from onset to the press that counted, presses in the window, late presses after it |

The scorer is a pure function of items and presses (`cordelia/scorer.py`),
and `rescore` reruns it over every session, so the rule can change later
without losing anything. Timing caveat: `afplay` starts some tens of ms
after it is spawned, so every latency carries the same small offset; fine
for comparing degrees, not for absolute numbers.

### Stats

`stats` reports the exercise of the last session played: a histogram of
right% over its questions in the order they were asked, the trend with its
standard error, and for degrees and chords the confusion matrix and the
recall and precision of each answer over the latest 500 questions. The
histogram has as many bars as the terminal is wide, 60 at most. The matrix
has a column for each label asked and one for no answer, where an answer
outside the labels asked (a slip of the hand) is counted too; each cell is
a block of braille dots scattered as densely as the share of that answer
(any answer at all lights a dot, so an empty cell means never), twice as
tall where the terminal has the height. Recall and precision are
a pair of upright bars for each label, recall first; the circle of fifths
sits in whatever width is left.
`--mode`, `--degrees`, `--key` and `--tag` pick a different last session,
so that harder settings don't read as regression. An exercise is its mode
and its content (the degree list, the melody recipe, the chords level), and
no table mixes two. `journal` is the practice wall: a column per week, a
cell per weekday, a dot in it for every 2 minutes practised that day across
every mode (full at 128).

### Adding a mode

`cordelia/modes/degrees.py` is the whole of the mode: how questions are
drawn, how one question is laid on the timeline (`Builder.phrase`), the
keymap (key name → label), `configure` (flags → config, with `keys`: how
many presses make an answer), `bank` (the voice it answers with), `hint`
and `status` (the two lines the terminal shows), `describe`, `exercise`
(what the stats group sessions by) and `LABELS` (the order of its confusion
matrix; leave it out for a mode without one); `cordelia/modes/melody.py`
is the second one, and `cordelia/modes/chords.py` the third, the first
without a drone. Everything else — rendering,
collecting, scoring, storage — is shared. The synth is a package with one
file per voice (`tone`, `chord`, `click`, `drone`) and the mixer in
`synth/mix.py`; a `Note` names its voice, and a new timbre is a new file
plus a line in `VOICES`. A score is instrument-agnostic: `--midi` writes it as a
Standard MIDI File (notes per instrument, the drone as one long note, the
spoken labels as lyric events) for any soundfont; a voice bank is just a
directory of `<label>.wav` under `data/voices/<name>/`, so a sung or
sampled voice can replace the spoken one.


### Samples, data, lineage

`solfege_samples/` (not in the repo) holds the note folders of
https://github.com/wcgbg/solfege-samples, `samples/*/notes*`, one sung
syllable per semitone, fixed-do. `data/` (not in the repo either) is the
record: whatever syncs the checkout syncs it.

Grew out of https://github.com/juan-lievano/ambient-ear-training, where
the passive drone, chord and blues scripts still live; moved out on
2026-11-03 because a drill that asks and records is not ambient.
