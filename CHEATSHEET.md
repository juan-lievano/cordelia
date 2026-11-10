# cordelia

Ear training in the terminal. Every key press is written down; nothing on
screen says whether you were right, the voice just gives the answer.
Repo: ~/Documents/Developing/cordelia (`cordelia` is a wrapper that runs it, no
reinstall after edits). Data: `data/` inside it (gitignored).

## Degrees (a note over a drone, name its scale degree)

| Command                                   | Does                                                       |
|-------------------------------------------|------------------------------------------------------------|
| `cordelia`                                | the list of commands                                       |
| `cordelia degrees`                        | 2 min, 50 BPM, the degrees you asked last time, random key |
| `cordelia degrees major`                  | 1 2 3 4 5 6 7                                              |
| `cordelia degrees minor`                  | 1 2 b3 4 5 b6 b7                                           |
| `cordelia degrees all`                    | the twelve: 1 b2 2 b3 3 4 b5 5 b6 6 b7 7                   |
| `cordelia degrees 1 2 5 6`                | any list of degrees; a new list is a new exercise          |
| `cordelia degrees minor --minutes 5 --key A` | longer, in a chosen key                                 |
| `cordelia degrees --bpm 40 --voice Samantha` | slower; any `say -v ?` voice                            |

Keys: `1`-`7`, or `h , . n e i l` under the fingers. The same key twice is
the flat: `33` = b3, `..` = b3, `77` = b7. The last key before the voice
counts. Esc stops, everything before it is kept.

Each question: note (2 beats), silence (2 beats, answer here), the voice
says it, the note again, a beat of rest. The session opens with tonic,
fifth, tonic an octave up.

## Melody (a short melody over a drone, type it back)

| Command                                   | Does                                                       |
|-------------------------------------------|------------------------------------------------------------|
| `cordelia melody`                         | 5 min, the recipe and BPM you played last (at first: four notes on 1 to 5, mostly stepwise, 55 BPM) |
| `cordelia melody 1 2 b3 4 5`              | the degrees a melody may use (`8`, `major`, `minor`, `all` too) |
| `... --length 3`                          | notes in a melody                                          |
| `... --spread 0.5`                        | how far a move goes: 0 steps only, 1 anywhere, 0.2 mostly steps |
| `... --hearings 2`                        | times it is played before the answer (3 at first)          |
| `... --key G --singer chengu`             | singer `jennifer` (default) or `chengu`                    |

The list, length, spread and hearings together are the exercise: change one
and the stats start a new one. Each defaults to the last melody session's.

Keys: `1`-`7`, or `h , . n e i l`; shifted (`H < > N E I L`) for the flat,
`>` = b3. A degree is the same key in any octave: `1` answers an 8. Type the
notes as you hear them; a note past the last starts the answer over,
backspace clears it, and what stands when the singing starts counts.
The melody is played with clicks between hearings, then the answer is sung.

## Chords (a chord on a random root, name its quality)

| Command                                   | Does                                                       |
|-------------------------------------------|------------------------------------------------------------|
| `cordelia chords`                         | 4 min, 50 BPM, the level you played last (1 at first)      |
| `cordelia chords 1`                       | maj min sus4 aug 5, arpeggiated before you answer          |
| `cordelia chords 2`                       | dom7 maj7 min7 dim7 m7b5, arpeggiated before               |
| `cordelia chords 3`                       | all ten, root an octave down, arpeggiated before           |
| `cordelia chords 4` / `5` / `6`           | the same three sets, arpeggio only after the answer        |

The session opens with the cheat sheet for its level. Keys and spellings
(against the major scale):

| Key | Chord | Spelling      | Key | Chord | Spelling        |
|-----|-------|---------------|-----|-------|-----------------|
| `M` | maj   | 1 3 5         | `d` | dom7  | 1 3 5 b7        |
| `m` | min   | 1 b3 5        | `j` | maj7  | 1 3 5 7         |
| `s` | sus4  | 1 4 5         | `n` | min7  | 1 b3 5 b7       |
| `a` | aug   | 1 3 #5        | `o` | dim7  | 1 b3 b5 bb7     |
| `5` | 5     | 1 5           | `h` | m7b5  | 1 b3 b5 b7      |

Sevenths from most to least tense (Luegers): dim7, dom7, m7b5, maj7, min7.
min7 is a minor chord with a major triad on top; m7b5 is a minor 6 chord
with the bass moved; dim7 is stacked minor thirds with no root feeling.
No drone here: the root is always the lowest note.

## Flags for every drill

| Flag                  | Does                                                              |
|-----------------------|-------------------------------------------------------------------|
| `--minutes 5`         | length                                                            |
| `--bpm 40`            | slower beat (degrees 50, chords 50; melody keeps the last session's, 55 at first) |
| `--tag headphones`    | sticky: this and every later session; `--tag none` clears         |
| `--seed 7`            | the same questions again                                          |
| `--keep-wav`          | keep the session audio in `data/sessions/`                        |
| `--midi t.mid`        | also write the score as MIDI                                      |
| `--ambient`           | just play, no keys read, nothing recorded; `caffeinate -i cordelia chords --ambient --minutes 60` to outlast the idle-sleep timer |

## Afterwards

| Command                                   | Does                                                       |
|-------------------------------------------|------------------------------------------------------------|
| `cordelia stats`                          | the exercise you played last: right% histogram + trend, confusion matrix, recall and precision |
| `cordelia stats --mode chords`            | the last session of one mode; `--degrees minor`, `--key G`, `--tag x` filter |
| `cordelia journal`                        | the practice wall: a cell per day shaded by minutes, every mode together |
| `cordelia rescore`                        | rebuild every answer from the raw key presses              |
| `cordelia tags` / `cordelia data`         | the sticky tags; where the database lives                  |

An exercise in stats is `degrees <list>`, a melody recipe or `chords <level>`.
The trend is the slope of right% over the questions, with its standard error.
The confusion matrix is rows asked, a block of dots per cell that fills with
the share of that answer, over the latest 500 questions (degrees and chords).

## Data

| Table        | One row per                                                       |
|--------------|-------------------------------------------------------------------|
| `sessions`   | session: mode, config (key, degrees, melody recipe or level, bpm, keymap), tags, outcome |
| `items`      | question: the right label, onset ms, answer-window end, meta      |
| `keystrokes` | key press: ms since playback started, key name                    |
| `answers`    | question: answer, correct, latency (derived, `rescore` rebuilds)  |

Open it with `sqlite3 "$(cordelia data)/cordelia.db"`.
