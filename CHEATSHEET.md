# cordelia

Repo `~/Documents/Developing/cordelia`, data in `data/` there. Runs from the checkout.

## Degrees

| Command                         | Does                                  |
|---------------------------------|---------------------------------------|
| `cordelia degrees`              | last list, 2 min, 50 BPM, random key  |
| `cordelia degrees 1 2 5 6`      | any list = an exercise                |
| `major` `minor` `all`           | 1-7 / 1 2 b3 4 5 b6 b7 / the twelve   |
| `--minutes 5`                   | length (2)                            |
| `--key A`                       | tonic (random, not the last)          |
| `--bpm 40`                      | tempo (50)                            |
| `--voice Samantha`              | any `say -v ?` voice                  |

- Keys `1`-`7` or `h , . n e i l`; twice for the flat (`33` = b3).
- Last key before the voice counts.

## Melody

| Command                         | Does                                  |
|---------------------------------|---------------------------------------|
| `cordelia melody`               | last recipe, 5 min                    |
| `cordelia melody 1 2 b3 4 5`    | degrees allowed (`8`, shorthands too) |
| `--length 3`                    | notes (last; 4)                       |
| `--spread 0.5`                  | 0 steps only, 1 anywhere (last; 0.2)  |
| `--hearings 2`                  | plays before the answer (last; 3)     |
| `--bpm 60`                      | tempo (last; 55)                      |
| `--minutes 5`                   | length (5)                            |
| `--key G`                       | tonic (random, not the last)          |
| `--singer chengu`               | `jennifer` (default) or `chengu`      |

- Exercise = list + length + spread + hearings.
- Keys `1`-`7` or `h , . n e i l`; shifted `H < > N E I L` for the flat (`>` = b3); `1` answers 8.
- A note past the last restarts; backspace clears; what stands at the singing counts.

## Chords

| Command                 | Does                                   |
|-------------------------|----------------------------------------|
| `cordelia chords`       | last level, 4 min, 50 BPM              |
| `cordelia chords 1`     | maj min sus4 aug 5                     |
| `cordelia chords 2`     | dom7 maj7 min7 dim7 m7b5               |
| `cordelia chords 3`     | all ten, root an octave down           |
| `cordelia chords 4-6`   | same sets, arpeggio after the answer   |
| `--minutes 5`           | length (4)                             |
| `--bpm 40`              | tempo (50)                             |
| `--voice Samantha`      | any `say -v ?` voice                   |

| Key | Chord | Spelling | Key | Chord | Spelling    |
|-----|-------|----------|-----|-------|-------------|
| `M` | maj   | 1 3 5    | `d` | dom7  | 1 3 5 b7    |
| `m` | min   | 1 b3 5   | `j` | maj7  | 1 3 5 7     |
| `s` | sus4  | 1 4 5    | `n` | min7  | 1 b3 5 b7   |
| `a` | aug   | 1 3 #5   | `o` | dim7  | 1 b3 b5 bb7 |
| `5` | 5     | 1 5      | `h` | m7b5  | 1 b3 b5 b7  |

- Tension, most to least: dim7, dom7, m7b5, maj7, min7.
- No drone; the root is the lowest note.

## Any drill

| Flag               | Does                                    |
|--------------------|-----------------------------------------|
| `--tag headphones` | sticky tag; `none` clears               |
| `--seed 7`         | same questions again                    |
| `--keep-wav`       | keep the audio in `data/sessions/`      |
| `--midi t.mid`     | also write MIDI                         |
| `--ambient`        | just play, nothing recorded             |
| `Esc`              | stop; everything before is kept         |

- Long ambient: `caffeinate -i cordelia chords --ambient --minutes 60`.

## Afterwards

| Command                 | Does                                        |
|-------------------------|---------------------------------------------|
| `cordelia stats`        | last exercise: right% bars, trend, confusions, recall / precision |
| `--mode chords`         | last session of that mode                   |
| `--degrees minor`       | degrees sessions with exactly that list     |
| `--key G`               | only that key                               |
| `--tag x`               | only that tag                               |
| `cordelia journal`      | minutes practised per day, a cell a day     |
| `cordelia rescore`      | rebuild answers from the key presses        |
| `cordelia tags`         | sticky tags                                 |
| `cordelia data`         | data directory                              |
| `CORDELIA_DATA_DIR=…`   | another data directory                      |

- Confusions: rows asked, latest 500 questions, degrees and chords only.

## Data

| Table        | Row per                                              |
|--------------|------------------------------------------------------|
| `sessions`   | session: mode, config, tags, outcome                 |
| `items`      | question: right label, onset, window end, meta       |
| `keystrokes` | key press: ms since playback start, key              |
| `answers`    | question: answer, correct, latency (derived)         |

- `sqlite3 "$(cordelia data)/cordelia.db"`
