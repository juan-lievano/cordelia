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
cordelia                                           # the drill played last, at its settings
cordelia degrees                                   # every setting the last degrees session's (at first: 4 min, 50 BPM, major, any key)
cordelia degrees minor --minutes 5
python3 -m cordelia degrees                        # the same, from the repo
python3 -m cordelia degrees 1 2 b3 4 5 b6 b7 --key D Eb E   # a key drawn from these each session (all = the twelve); any list of degrees is an exercise; minor = this list, all = the twelve
python3 -m cordelia degrees 1 2 5 6                # a list never typed before is a new exercise from this session on
python3 -m cordelia degrees minor --range 0 12     # semitones under and over the tonic: here the tonic up to its octave (at first 5 17, as it always was)
python3 -m cordelia degrees --voice Samantha       # any `say -v ?` voice
python3 -m cordelia focus minor --minutes 3 --run 21   # 7 rounds of 3 min, each focused on the latest trouble
python3 -m cordelia focus minor --on b3 4          # half the questions on b3 and 4, the other half the usual mix
python3 -m cordelia focus                          # the last focus session's settings, its --run too
python3 -m cordelia degrees --tag headphones       # sticky, like teepee; --tag none clears
python3 -m cordelia degrees --midi t.mid           # also write the score as MIDI
python3 -m cordelia chords --ambient --minutes 60   # any mode: the same audio, no keys read, nothing recorded
python3 -m cordelia melody                         # the last melody session's settings (at first: 5 min, four notes on 1 to 5, mostly stepwise, 55 BPM), sung back
python3 -m cordelia melody 1 2 b3 4 5 --length 3 --spread 0.5 --key G --singer chengu
python3 -m cordelia melody minor --range low       # = E1 0 12, a bass line: the tonic (E1 to Eb2) up to its octave (high = G4 0 12)
python3 -m cordelia melody minor --range E1 0 19   # the same, up to the fifth over the octave
python3 -m cordelia chords                         # the last chords session's settings (at first: 4 min, 50 BPM, level 1)
python3 -m cordelia chords 2                       # the sevenths; 3: all ten, open voicing; 4-6: the same without the arpeggio first
python3 -m cordelia review                         # listen to b3 4 b7 in a fresh key: cadence, scales, the tonic, pairs, triples, named, on a staff as it plays; nothing recorded
python3 -m cordelia review b3 4 --minutes 2 --bpm 50
python3 -m cordelia stats                          # the last exercise played: histogram, trend, confusions
python3 -m cordelia stats --degrees minor --tag headphones
python3 -m cordelia stats --mode melody            # the last melody session's recipe
python3 -m cordelia stats --full                   # the whole record: every drill in one table, the degrees by mix-up,
                                                   # speed, key, register, the note before and hour, melodies (note by note, the pairs of notes missed most, and every
                                                   # run of two and of three notes as a dot: times heard against right%), chords, records
python3 -m cordelia history degrees                # every combination of settings played, its sessions, minutes, right%, last played
python3 -m cordelia journal                        # minutes practised, a cell per day, a column per week
python3 -m cordelia rescore                        # rebuild answers from the raw presses
python3 -m cordelia tags | data
```

Every drill setting left off the command line is the last session's of that
drill (`cli.remember`), the mode's default before there is one. That includes
the `--key` list: each session draws its key from it, never the last session's
when the list has another.

`~/.local/bin/cordelia` is a two-line wrapper that runs `python3 -m cordelia`
from this checkout; `pip install -e .` does the same.

### The `degrees` mode

Over a breathing drone, rooted two
octaves under the middle-register tonic (C2 for C), its core steady and its
fifths and shimmer above swelling in and out over several seconds, with
the note timbre of the additive tone (four damped harmonics, softer as it rises). The drone fades in for a beat, then tonic, fifth and tonic an
octave up (a beat each) set the key (when the list is `major` or `minor`, the whole scale
instead, up to the tonic on top, over the tonic and fifth an octave down, as a melody
session opens), and after two beats of rest the
questions start, each at 50 BPM (1.2 s a beat; `--bpm` changes it):

```
beats 1-2   the note           — press 1-7 (8 is 1), or h , . n e i l (u is 1); the same key twice, or shifted, for the flat (33 or > = ♭3), a third time for the natural again
            — a degree the list asks only flat, or only natural, is that whatever the key (minor: 3, 33 and > are all ♭3; major: all 3), since 2026-11-16
beats 3-4   silence            — the answer window; the last key pressed in it counts
beat  5     the voice says it  — "four", "flat seven"
beats 6-7   the note again
beat  8     rest
```

The word is as long at any tempo: it gets the beats it lasts, less 0.3 s that its end may
run under the note again (since 2026-11-16), so it is one beat up to 110 BPM and 100 BPM
asks twice what 50 does; faster, a "flat" word takes two.

Each session draws its key from the `--key` list (all twelve until one is
given), never the one the last session was in. The session asks the degrees listed on the command line,
any of `1 b2 2 b3 3 4 b5 5 b6 6 b7 7` (`major`, `minor` and `all` expand
to lists while typing; only the list is stored). The list is the exercise:
there is no level table, `cordelia degrees 1 2 5 6` is a new exercise the
first time it is typed, and the stats keep each list apart. Without a list
the last degrees session's is asked again. Every degree is typeable
whatever the list, so a ♭3 answered in a major session is recorded as ♭3.
`--range` says how many semitones under and over the tonic the notes go (`--range 5 17`:
from the fifth under it to the fourth over its octave), and every note in between that is a
degree of the list is asked, so the range moves with the key. A note before the two numbers
is the lowest the tonic may be (`--range E1 0 12`: the tonic, E1 to Eb2, up to its octave);
without one the tonic is the middle-register one, G3 to F#4. Five words stand for a range while typing, as `minor` does for a list, and only the note
and the numbers are stored: `narrow` (G3 0 11) is the list once, the tonic up to the seventh;
`middle` (G3 5 17) the fifth under the tonic to the fourth over its octave; `wide` (G3 12 24)
three octaves, the one under the tonic and the two over it; `low` (E1 0 12) and `high`
(G4 0 12) the tonic to its octave, in the bass and an octave over the middle. A range other than G3 5 17 is an exercise of its own in the
stats. One that sits under C3 is played in the bass voice, the drone an octave up; a sung
answer needs a range the singer has (C3 to B5). Since 2026-11-14: before, every session was
`middle`, which is still where a session with no range since starts. Every degree is equally
likely except degree 1, asked half as often, whichever of its notes in the range (before 2026-11-15 ♭5, with one note in the middle range, came half as often too); nothing is avoided but the exact
same question twice in a row. Esc stops;
everything before it is kept.

`cordelia focus` asks degrees questions with the mix shifted toward what goes
wrong, and is a drill of its own: its sessions are never pooled with `degrees` ones in an analysis. By default (auto) it looks at each degree's own latest 40 questions on
the same list, so a degree that has come up rarely rests on as much evidence
as one that comes up often, and asks each in proportion to its miss rate,
(missed + 1) / (asked + 2): the mean of a Beta(right + 1, missed + 1) belief
about its recall, which more answers make surer but never more extreme
(`--by f1`, 1 − F1, was tried and dropped on 2026-11-12). `--by thompson`
asks each degree as often as the chance that it is the weakest (Thompson
sampling, computed once a round from 20,000 seeded draws): Betas from the
list's latest 80 questions, so a degree with few answers among them stays
uncertain and gets explored; it leans much harder and moves more from round
to round. Equal skill on every degree is an even mix under both, 1
included; no degree gets under 4%. The questions are the list's in plain degrees and focus sessions alike. `--on b3 4` instead asks half the
questions evenly over the list and half evenly over degrees of your choosing
(they must be in the list); `--on` with nothing after it goes back to auto. Its
sessions are stored under mode `focus`. Focus keeps its own settings: everything left off is the last focus session's
(before the first, the last degrees session's), `--run` included, and plain
`cordelia degrees` remembers only its own sessions. The config stores how the focus was
chosen, the part of the questions each degree got and, for auto, the counts
behind it.

`--run 20` (any drill) plays rounds of `--minutes` back to back until about
that long; `--run 0` is one session. Each round is an ordinary session, set
up afresh (a new key; with an auto focus, a new focus from the answers so
far, this round's included). Each round's session box is written over the
last one in place (cursor moves, like the question panel), the round in its
title; the next round renders on the line under it, and after the last one
line gives the run's right count. Esc ends the run after its round.

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
beat  25      rest (two beats until 2026-11-14)
```

Sessions before 2026-11-08 had four clicks between hearings; the commit
stored with each session tells which.

At 55 BPM, the first session's tempo, a beat is 1.09 s (`--bpm` changes it; later sessions keep the last one's).

Type the degrees as you make them out, one key per note (1-7, or
h , . n e i l; shifted for the flat, since a key twice is a repeated note
here; a degree the list asks only flat, as the 3 of minor, or only natural, is that by either key, 3 for b3, and the box says so: since 2026-11-16). A degree is the same key in any octave: 1 answers an 8 (and the 8 key, or u, is another 1), and the
scorer folds the two before comparing (since 2026-11-08; before, 8 and u
were the tonic above). A note past the last starts the answer over,
backspace clears it, and what stands when the singing starts is the
answer, stored as `1 2 b3 1`, so a note can be right on its own in the
stats. The singing comes from the
solfege samples in `solfege_samples/` (fixed-do, one syllable per
semitone): each note is the singer's nearest sample of that syllable,
pitched to the note by TD-PSOLA (`cordelia/psola.py`), which moves the
pitch and leaves the singer's speed and vowel alone, so any key sounds
like her, a sample pitched six semitones at most.
`--singer`
picks `jennifer` (default) or `chengu`, who sings every melody that stays within
the notes they recorded; one that does not is sung by the other, or note by note by
whoever recorded each (jennifer's samples are C3 to B5, chengu's C2 to B4, of which he is
given G2 up: lower they are not pleasant), and a melody
with a note under G2 or over B5, and every melody of a bass line (a range whose middle is under C3), is spoken instead, a degree a beat ("one, flat three"):
since 2026-11-14, before which a note up to six semitones past a singer's range was still
sung. `--answer spoken` has every melody spoken (since 2026-11-15; `sung` is the usual). A spoken answer is followed by the melody played once more, a note a beat (since 2026-11-16), so the degrees just said can be heard on their pitches. `--answer visual` (since 2026-11-20, in degrees too) has no voice: the answer is written on the screen while the melody, or the note, is played once more. The sung clips are made once per
note under `data/voices/sung-<singer>/`.

The recipe is given on the command line, as in the degrees mode: the
degrees a melody may use (any of the twelve, and the same shorthands),
`--range` for how far under and over the tonic, as in the degrees mode, `--length` for how
many notes, `--spread` for how far a move tends to go (to any other note,
one d positions away weighing spread^(d-1): 0 is steps only, 1 any other
note equally; the first note is uniform), and `--hearings` for
how many times a melody is played before the answer, and `--think` for the beats of clicks before the answer (4, the only choice until 2026-11-18; not part of the exercise the stats group by). A melody is drawn from every note of
the list within the range (at first `narrow`: the tonic, G3 to F#4, up to the seventh), its first note any degree equally. A
range that sits under C3 (`low`: the tonic, E1 to Eb2, up to its octave) is a bass line:
played with a fuller tone, the drone an octave up, and its answers spoken. Since 2026-11-14:
before, `--octaves` (1, 2 or 3) and `--register` (low, middle, high) put the list that many
times over up from a tonic, and `8` in the list put the tonic on top. An
answer is the degrees in any octave, and the melody is shown that way once
sung (`1 7 5 6 1 6`), with `--shape slabs` or `--shape braille` a mark under
each note as high as the note is above the melody's lowest (a level per scale step, 8 or 4 to
a row; `none` turns it off). The five together, the range only when it is not `narrow`, are the exercise the stats group
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
| `sessions`   | session     | mode, config as JSON (key, the degrees asked or the level, bpm, voice, focus, run and round, the keymap, seed, the commit the code was at, null if the tree was dirty), tags, outcome (`completed` / `stopped` / `aborted`), ms into the audio when it ended |
| `items`      | question    | truth as a keymap label, onset ms, window-end ms (when the answer starts sounding), meta JSON (degree label, MIDI note; before 2026-11-14 the octave and register too) |
| `keystrokes` | key press   | ms since playback was started, key name (`4`, `space`, `other`...) |
| `answers`    | question    | derived: answer, correct (NULL when nothing was pressed), latency from onset to the press that counted, presses in the window, late presses after it |

A session can be deprecated: `cordelia deprecate 18-128 --mode melody --because "..."`
writes the reason in `sessions.deprecated`, and `stats`, `stats --full` and the
focus drill's choice of degrees no longer read it (they all load through
`stats.load`); `journal` and `history` still do, the time was practised.
Nothing is deleted, `--undo` brings the sessions back, and `cordelia deprecate`
alone lists what is left out and why.

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
sits in whatever width is left. Focus sessions are stored under mode
`focus` (degrees questions, a focus in the config; sessions 240-244 were
moved there from `degrees` on 2026-11-12), and the stats keep them apart as a
drill of their own (`focus minor` beside `degrees minor`; `--mode focus`),
since a mix that chases what goes wrong reads differently; an auto focus
still reads the list's questions from both. The trend is in percentage points per hour
practised: the earlier sessions' minutes, then how far into its own session
the question came.
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
