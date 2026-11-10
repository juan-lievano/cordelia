# cordelia
Repo `~/Documents/Developing/cordelia`, data in `data/`. (last; x) = last session's, x at first.

|                | Command                                | Does                                            |
|----------------|----------------------------------------|-------------------------------------------------|
| **Degrees**    | `cordelia degrees`                     | last list, random key                           |
|                | `cordelia degrees 1 2 5 6`             | any list = an exercise                          |
|                | `major` `minor` `all`                  | 1-7 / 1 2 b3 4 5 b6 b7 / the twelve             |
|                | `--minutes 5`                          | length (2)                                      |
|                | `--key A`                              | tonic (random, not the last)                    |
|                | `--bpm 40`                             | tempo (50)                                      |
|                | `--voice Samantha`                     | any `say -v ?` voice                            |
|                | &nbsp;keys | `1`-`7` or `h , . n e i l`; `8` / `u` = 1       |
|                | &nbsp;flat | twice (`33`) or shifted (`>`) = b3              |
|                | &nbsp;counts | the last key before the voice                   |
|   | ────────────────────────────────────── | ─────────────────────────────────────────────── |
| **Melody**     | `cordelia melody`                      | last recipe                                     |
|                | `cordelia melody 1 2 b3 4 5`           | degrees allowed (`8`, shorthands too)           |
|                | &nbsp;&nbsp;`--length 3`               | notes (last; 4)                                 |
|                | &nbsp;&nbsp;`--spread 0.5`             | 0 steps only, 1 anywhere (last; 0.2)            |
|                | &nbsp;&nbsp;`--hearings 2`             | plays before the answer (last; 3)               |
|                | &nbsp;&nbsp;`--bpm 60`                 | tempo (last; 55)                                |
|                | &nbsp;&nbsp;`--minutes 5`              | length (5)                                      |
|                | &nbsp;&nbsp;`--key G`                  | tonic (random, not the last)                    |
|                | &nbsp;&nbsp;`--singer chengu`          | or `jennifer` (default)                         |
|                | &nbsp;exercise | list + length + spread + hearings               |
|                | &nbsp;keys | `1`-`7` or `h , . n e i l`; `8` / `u` = 1       |
|                | &nbsp;flat | shifted: `H < > N E I L` (`>` = b3)             |
|                | &nbsp;counts | what stands when the singing starts             |
|                | &nbsp;past the last note / backspace | starts over / clears                            |
|   | ────────────────────────────────────── | ─────────────────────────────────────────────── |
| **Chords**     | `cordelia chords`                      | last level                                      |
|                | `cordelia chords 1`                    | maj min sus4 aug 5                              |
|                | `cordelia chords 2`                    | dom7 maj7 min7 dim7 m7b5                        |
|                | `cordelia chords 3`                    | all ten, root an octave down                    |
|                | `cordelia chords 4-6`                  | same sets, arpeggio after the answer            |
|                | &nbsp;&nbsp;`--minutes 5`              | length (4)                                      |
|                | &nbsp;&nbsp;`--bpm 40`                 | tempo (50)                                      |
|                | &nbsp;&nbsp;`--voice Samantha`         | any `say -v ?` voice                            |
|                | &nbsp;tension, most to least | dim7, dom7, m7b5, maj7, min7                    |
|                | `M` maj · 1 3 5                        | `d` dom7 · 1 3 5 b7                             |
|                | `m` min · 1 b3 5                       | `j` maj7 · 1 3 5 7                              |
|                | `s` sus4 · 1 4 5                       | `n` min7 · 1 b3 5 b7                            |
|                | `a` aug · 1 3 #5                       | `o` dim7 · 1 b3 b5 bb7                          |
|                | `5` 5 · 1 5                            | `h` m7b5 · 1 b3 b5 b7                           |
|   | ────────────────────────────────────── | ─────────────────────────────────────────────── |
| **Any drill**  | `--tag headphones`                     | sticky tag; `none` clears                       |
|                | `--seed 7`                             | same questions again                            |
|                | `--keep-wav`                           | keep the audio in `data/sessions/`              |
|                | `--midi t.mid`                         | also write MIDI                                 |
|                | `--ambient`                            | just play, nothing recorded                     |
|                | `caffeinate -i cordelia …`             | long `--ambient`: outlast idle sleep            |
|                | `Esc`                                  | stop; everything before is kept                 |
|   | ────────────────────────────────────── | ─────────────────────────────────────────────── |
| **Afterwards** | `cordelia stats`                       | last exercise: right% bars, trend, confusions   |
|                | &nbsp;&nbsp;`--mode chords`            | last session of that mode                       |
|                | &nbsp;&nbsp;`--degrees minor`          | degrees sessions with exactly that list         |
|                | &nbsp;&nbsp;`--key G`                  | only that key                                   |
|                | &nbsp;&nbsp;`--tag x`                  | only that tag                                   |
|                | &nbsp;confusions | rows asked, latest 500 q; degrees and chords    |
|                | `cordelia journal`                     | a cell a day, a dot per 2 min practised         |
|                | `cordelia rescore`                     | rebuild answers from the key presses            |
|                | `cordelia tags`                        | sticky tags                                     |
|                | `cordelia data`                        | data directory; `CORDELIA_DATA_DIR=…` overrides |
|   | ────────────────────────────────────── | ─────────────────────────────────────────────── |
| **Data**       | `sessions`                             | session: mode, config, tags, outcome            |
|                | `items`                                | question: label, onset, window end, meta        |
|                | `keystrokes`                           | key press: ms since playback start, key         |
|                | `answers`                              | derived: answer, correct, latency               |
|                | `sqlite3 $(cordelia data)/cordelia.db` | open the database                               |
