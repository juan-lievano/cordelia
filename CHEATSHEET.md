# cordelia
Repo `~/Documents/Developing/cordelia`, data in `data/`. (last; x) = last session's, x at first.

|                | Command                                | Does                                            |
|----------------|----------------------------------------|-------------------------------------------------|
| **Degrees**    | `cordelia degrees`                     | last session's settings, key drawn from the list |
|                | `cordelia degrees 1 2 5 6`             | any list = an exercise                          |
|                | `major` `minor` `all`                  | 1-7 / 1 2 b3 4 5 b6 b7 / the twelve             |
|                | `--minutes 5`                          | length (last; 4)                                |
|                | `--key D Eb E F F#`                    | keys to draw from, not the last (last; all)     |
|                | `--bpm 40`                             | tempo (last; 50)                                |
|                | `--voice Samantha`                     | any `say -v ?` voice (last; system)             |
|                | `--answer sung`                        | syllable sung on the note; `spoken` (last; spoken) |
|                | &nbsp;solfege | 1 do · 2 re · 3 mi · 4 fa · 5 so · 6 la · 7 ti |
|                | &nbsp;flats | b2 ga · b3 nu · b5 jur · b6 ki · b7 pe         |
|                | &nbsp;keys | `1`-`9` or `h , . n e i l u y`; 8 = 1, 9 = 2    |
|                | &nbsp;flat | twice (`33`) or shifted (`>`) = b3; `333` = 3   |
|                | &nbsp;counts | the last key before the voice                   |
|   | ────────────────────────────────────── | ─────────────────────────────────────────────── |
| **Focus**      | `cordelia focus`                       | last focus session's settings, `--run` too      |
|                | `cordelia focus minor`                 | each degree ∝ its miss rate (missed+1)/(asked+2) over its own last 40, each round; 4% at least |
|                | &nbsp;&nbsp;`--on b3 4`                | half evenly on these, half on all; `--on` = auto again |
|                | &nbsp;&nbsp;`--run 21 --minutes 3`     | 7 rounds, one box redrawn; `--run 0` one session |
|                | &nbsp;&nbsp;degrees flags              | `--bpm` `--key` `--answer` … kept apart from degrees' |
|                | &nbsp;&nbsp;`--by thompson`            | ∝ chance it's the weakest, Betas from the last 80 q (last; recall) |
|                | &nbsp;miss rate | (missed+1)/(asked+2)                            |
|                | &nbsp;stats | a drill of its own: `focus minor`; `--mode focus` |
|                | &nbsp;auto reads | the list's q, degrees and focus alike           |
|   | ────────────────────────────────────── | ─────────────────────────────────────────────── |
| **Melody**     | `cordelia melody`                      | last session's settings, key drawn from the list |
|                | `cordelia melody 1 2 b3 4 5`           | degrees allowed (`8`, shorthands too)           |
|                | &nbsp;&nbsp;`--length 3`               | notes (last; 4)                                 |
|                | &nbsp;&nbsp;`--spread 0.5`             | 0 steps only, 1 anywhere (last; 0.2)            |
|                | &nbsp;&nbsp;`--hearings 2`             | plays before the answer (last; 3)               |
|                | &nbsp;&nbsp;`--bpm 60`                 | tempo (last; 55)                                |
|                | &nbsp;&nbsp;`--minutes 5`              | length (last; 5)                                |
|                | &nbsp;&nbsp;`--key G`                  | keys to draw from, not the last (last; all)     |
|                | &nbsp;&nbsp;`--singer chengu`          | or `jennifer` (last; jennifer)                  |
|                | &nbsp;exercise | list + length + spread + hearings               |
|                | &nbsp;keys | `1`-`9` or `h , . n e i l u y`; 8 = 1, 9 = 2    |
|                | &nbsp;flat | shifted: `H < > N E I L Y` (`>` = b3)           |
|                | &nbsp;counts | what stands when the singing starts             |
|                | &nbsp;past the last note / backspace | starts over / clears                            |
|   | ────────────────────────────────────── | ─────────────────────────────────────────────── |
| **Chords**     | `cordelia chords`                      | last session's settings                         |
|                | `cordelia chords 1`                    | maj min sus4 aug 5                              |
|                | `cordelia chords 2`                    | dom7 maj7 min7 dim7 m7b5                        |
|                | `cordelia chords 3`                    | all ten, root an octave down                    |
|                | `cordelia chords 4-6`                  | same sets, arpeggio after the answer            |
|                | &nbsp;&nbsp;`--minutes 5`              | length (last; 4)                                |
|                | &nbsp;&nbsp;`--bpm 40`                 | tempo (last; 50)                                |
|                | &nbsp;&nbsp;`--voice Samantha`         | any `say -v ?` voice (last; system)             |
|                | &nbsp;tension, most to least | dim7, dom7, m7b5, maj7, min7                    |
|                | `M` maj · 1 3 5                        | `d` dom7 · 1 3 5 b7                             |
|                | `m` min · 1 b3 5                       | `j` maj7 · 1 3 5 7                              |
|                | `s` sus4 · 1 4 5                       | `n` min7 · 1 b3 5 b7                            |
|                | `a` aug · 1 3 #5                       | `o` dim7 · 1 b3 b5 bb7                          |
|                | `5` 5 · 1 5                            | `h` m7b5 · 1 b3 b5 b7                           |
|   | ────────────────────────────────────── | ─────────────────────────────────────────────── |
| **Any drill**  | `--run 20`                             | rounds of `--minutes` for ~20 min, one box redrawn |
|                | `--tag headphones`                     | sticky tag; `none` clears                       |
|                | `--seed 7`                             | same questions again                            |
|                | `--keep-wav`                           | keep the audio in `data/sessions/`              |
|                | `--midi t.mid`                         | also write MIDI                                 |
|                | `--ambient`                            | just play, nothing recorded                     |
|                | `caffeinate -i cordelia …`             | long `--ambient`: outlast idle sleep            |
|                | `Esc`                                  | stop; everything before is kept                 |
|                | `Ctrl-C`                               | same, and ends a `;` chain or loop              |
|   | ────────────────────────────────────── | ─────────────────────────────────────────────── |
| **Review**     | `cordelia review`                      | listen to b3 4 b7; new key, nothing kept        |
|                | &nbsp;&nbsp;`review b3 4`              | those degrees instead                           |
|                | &nbsp;&nbsp;`--minutes 2`              | each part after the scales (default 1)          |
|                | &nbsp;&nbsp;`--bpm 50` `--key G A`     | tempo (60); keys drawn from (all 12)            |
|                | &nbsp;parts                            | cadence · scale · held · tonic · pairs · one way · free · singles |
|                | &nbsp;groups                           | played, named, played again; `--repeat 2` times           |
|                | &nbsp;cadence                          | i iv V i, then i VI VII i (major: I IV V I)     |
|                | &nbsp;screen                           | the notes on a staff as they sound (tall terminal) |
|   | ────────────────────────────────────── | ─────────────────────────────────────────────── |
| **Afterwards** | `cordelia stats`                       | last exercise: right% bars, trend, confusions   |
|                | &nbsp;trend | pp per hour practised                           |
|                | &nbsp;&nbsp;`--mode chords`            | last session of that mode (or `focus`)          |
|                | &nbsp;&nbsp;`--degrees minor`          | degrees sessions with exactly that list         |
|                | &nbsp;&nbsp;`--key G`                  | only that key                                   |
|                | &nbsp;&nbsp;`--tag x`                  | only that tag                                   |
|                | &nbsp;confusions | rows asked, latest 500 q; degrees and chords    |
|                | `cordelia history`                     | settings played, sessions + minutes each, newest first |
|                | &nbsp;&nbsp;`history melody`           | that drill (`degrees` `focus` `melody` `chords`) |
|                | `cordelia journal`                     | a cell a day, a dot per 2 min practised         |
|                | `cordelia rescore`                     | rebuild answers from the key presses            |
|                | `cordelia tags`                        | sticky tags                                     |
|                | `cordelia data`                        | data directory; `CORDELIA_DATA_DIR=…` overrides |
|   | ────────────────────────────────────── | ─────────────────────────────────────────────── |
| **Data**       | `sessions`                             | session: mode (`focus` for focus), config, tags, outcome |
|                | `items`                                | question: label, onset, window end, meta        |
|                | `keystrokes`                           | key press: ms since playback start, key         |
|                | `answers`                              | derived: answer, correct, latency               |
|                | `sqlite3 $(cordelia data)/cordelia.db` | open the database                               |
