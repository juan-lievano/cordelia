"""cordelia: ear training that writes down every answer. The drills are `degrees`, `melody` and `chords`. See README.md."""

import argparse
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time

from . import journal, scorer, stats, store
from .collector import collect
from .modes import MODES, chords, degrees, melody
from .synth import render
from .voice import SINGERS


KEY_HELP = ("the keys a session's tonic is drawn from, not the last session's when there is another: "
            "C D E F G A B with # or b, or all")


def main(argv=None):
    p = argparse.ArgumentParser(prog="cordelia", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("degrees", help="scale degrees over a drone, the answer spoken after each")
    degree_flags(d)
    session_flags(d)

    f = sub.add_parser("focus", help="degrees with half the questions on the ones giving trouble; its own settings")
    degree_flags(f)
    f.add_argument("--on", nargs="*", metavar="DEGREE",
                   help="half the questions on these degrees of the list, split evenly; nothing after it: "
                        f"auto, half on the {degrees.TOP} with the most trouble in the latest {degrees.WINDOW} "
                        "questions of the list, worked out afresh each round (default: the last focus session's way)")
    session_flags(f)
    f.epilog = ("Every setting left out is the last focus session's (before the first, the last degrees "
                "session's), --run too; the sessions are degrees sessions, and stats keep them with their list.")

    m = sub.add_parser("melody", help="short melodies over a drone, sung back after each")
    m.add_argument("degrees", nargs="*", metavar="DEGREE",
                   help=f"the degrees a melody may use, from {' '.join(melody.DEGREES)}; "
                        + ", ".join(f"{w} = {' '.join(l)}" for w, l in degrees.SHORTHANDS.items()))
    m.add_argument("--length", type=int, help="notes in a melody")
    m.add_argument("--spread", type=float,
                   help="how far a move tends to go: a move of d positions along the list weighs spread^(d-1), "
                        "so 0 is steps only, 1 any other degree equally, 0.2 mostly steps with the odd third")
    m.add_argument("--hearings", type=int, help="times a melody is played before the answer")
    m.add_argument("--minutes", type=float)
    m.add_argument("--key", dest="key_pool", nargs="+", metavar="KEY", help=KEY_HELP)
    m.add_argument("--bpm", type=float)
    m.add_argument("--singer", help=" | ".join(SINGERS))
    session_flags(m)

    c = sub.add_parser("chords", help="chord qualities, the answer spoken then arpeggiated after each")
    c.add_argument("level", type=int, nargs="?",
                   help="; ".join(f"{n}: {spec['about']}" for n, spec in chords.LEVELS.items())
                  )
    c.add_argument("--minutes", type=float)
    c.add_argument("--bpm", type=float)
    c.add_argument("--voice", help="a `say -v ?` voice; 'default' = system voice")
    session_flags(c)

    s = sub.add_parser("stats", help="the last exercise played: a right%% histogram, degree and chord confusions")
    s.add_argument("--mode", default="all", help=" | ".join(MODES) + " | all (default: every mode in turn)")
    s.add_argument("--degrees", nargs="*", metavar="DEGREE", help="degrees sessions that asked exactly this list")
    s.add_argument("--key")
    s.add_argument("--tag")

    sub.add_parser("journal", help="the practice wall: a column per week, a cell per day shaded by minutes")
    sub.add_parser("rescore", help="rebuild every session's answers from its key presses")
    sub.add_parser("tags", help="show the sticky tags")
    sub.add_parser("data", help="where the database lives")

    if not (sys.argv[1:] if argv is None else argv):
        return p.print_help()
    a, extra = p.parse_known_args(argv)
    a.argv = list(sys.argv[1:] if argv is None else argv)
    if extra:       # argparse would blame the top-level usage; the subcommand's is the useful one
        sub.choices[a.cmd].error(f"unrecognized arguments: {' '.join(extra)}  (--help lists the flags)")
    if a.cmd in MODES:
        return cmd_session(MODES[a.cmd], a)
    if a.cmd == "focus":
        return cmd_session(degrees, a, focused=True)
    if a.cmd == "stats":
        return stats.report(store.connect(), a.mode, a.degrees, a.key, a.tag)
    if a.cmd == "journal":
        return journal.show(store.connect())
    if a.cmd == "rescore":
        return cmd_rescore()
    if a.cmd == "tags":
        print(", ".join(tags(store.connect())) or "no tags")
    if a.cmd == "data":
        print(store.data_dir())


def commit():
    """The checkout's commit, or None when the tree has uncommitted changes (or git is
    missing). The code at that commit is what every rule the config leaves implicit meant;
    with edits on top of it, the record can't say what ran."""
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        if subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=here, capture_output=True, text=True, check=True).stdout:
            return None
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=here, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def degree_flags(p):
    p.add_argument("degrees", nargs="*", metavar="DEGREE",
                   help=f"the degrees to ask, from {' '.join(degrees.SEMITONES)}; "
                        + ", ".join(f"{w} = {' '.join(l)}" for w, l in degrees.SHORTHANDS.items()))
    p.add_argument("--minutes", type=float)
    p.add_argument("--key", dest="key_pool", nargs="+", metavar="KEY", help=KEY_HELP)
    p.add_argument("--bpm", type=float)
    p.add_argument("--voice", help="a `say -v ?` voice; 'default' = system voice")
    p.add_argument("--answer", help="spoken: the degree said, then the note again; sung: its syllable sung on the note")


def last_config(con, mode, focused):
    """The settings a session starts from: the last session's of the drill; for degrees the
    last one without a focus, and for `focus` the last one with (before the first, degrees')."""
    sid = None
    if mode is degrees:
        sid = store.last_session_id(con, mode.NAME, focused) or (focused and store.last_session_id(con, mode.NAME, False))
    else:
        sid = store.last_session_id(con, mode.NAME)
    s = store.session(con, sid or 0)
    return s and s["config"]


def session_flags(p):
    p.epilog = "Every setting left out is the last session's of this drill, the --key list too."
    p.add_argument("--tag", help="tag this and every later session (sticky); 'none' clears")
    p.add_argument("--keep-wav", action="store_true", help="keep the session's WAV in data/sessions/")
    p.add_argument("--midi", metavar="FILE", help="also write the score as a MIDI file")
    p.add_argument("--seed", type=int, help="draw the same questions again")
    p.add_argument("--run", type=float, metavar="MINUTES",
                   help="rounds of --minutes each, back to back, until about this long; "
                        "between rounds the mix-ups so far (and with --focus auto a new focus)")
    p.add_argument("--ambient", action="store_true",
                   help="just play: the same audio, no keys read, nothing recorded (Esc stops)")


def tags(con, flag=None):
    if flag is not None:
        store.set_setting(con, "tags", json.dumps([] if flag == "none" else [t.strip() for t in flag.split(",")]))
    return json.loads(store.setting(con, "tags", "[]"))


def remember(a, defaults, last_config):
    """Every setting left off the command line is the last session's of the mode (the mode's
    default before there is one). The key is drawn from the remembered `--key` list."""
    for name, default in defaults.items():
        if getattr(a, name) in (None, []):
            setattr(a, name, (last_config or {}).get(name, default))


def cmd_session(mode, a, focused=False):
    """One session, or with --run rounds of them, each ordinary and recorded on its own, the
    settings worked out afresh before each (a new key, with an auto focus a new focus).
    A focus session remembers its --run too; `--run 0` is one session."""
    a.focused = focused
    con = store.connect()
    last = last_config(con, mode, focused)
    if focused and a.run is None:
        a.run = ((last or {}).get("focus") and (last.get("run") or {}).get("minutes"))
    if not a.run or a.ambient:
        return play(mode, a)
    remember(a, mode.DEFAULTS, last)          # --minutes, so the rounds can be counted
    run = dict(id=round(time.time() * 1000), minutes=a.run, round=0, rounds=max(1, round(a.run / a.minutes)))
    seed, played = a.seed, []
    while True:
        run["round"] += 1
        a.seed = None if seed is None else seed + run["round"] - 1
        sid, outcome = play(mode, a, run)
        played.append(sid)
        last = run["round"] >= run["rounds"] or outcome != "completed"
        print(stats.centred(stats.box("this run" if last else f"round {run['round']} / {run['rounds']} done",
                                      round_summary(store.connect(), played))) + "\n")
        if last:
            return


def round_summary(con, sids):
    """Right of asked in the last round and in the run so far, and the run's mix-ups, most first."""
    marks = ",".join("?" * len(sids))
    rows = con.execute(f"""SELECT i.session_id, i.truth, a.answer, a.correct FROM items i LEFT JOIN answers a
                           ON a.session_id = i.session_id AND a.idx = i.idx WHERE i.session_id IN ({marks})""", sids).fetchall()

    def right(rs):
        n = sum(1 for r in rs if r[3] == 1)
        return f"{n} / {len(rs)} right" + (f" ({100 * n / len(rs):.0f}%)" if rs else "")
    mixups = {}
    for _, truth, answer, correct in rows:
        if correct != 1:
            k = f"{truth} → {answer or stats.NONE}"
            mixups[k] = mixups.get(k, 0) + 1
    worst = sorted(mixups.items(), key=lambda kv: -kv[1])[:8]
    lines = [f"round  {right([r for r in rows if r[0] == sids[-1]])}"] if len(sids) > 1 else []
    lines += [f"run    {right(rows)}"]
    return "\n".join(lines + (["", "mix-ups this run, asked → answered"] + [f"{k}  ×{n}" for k, n in worst] if worst else []))


def play(mode, a, run=None):
    """One session: set up, rendered, played, scored, saved. Returns (session id, outcome)."""
    con = store.connect()
    last = last_config(con, mode, a.focused)
    remember(a, mode.DEFAULTS, last)
    a.recent = lambda degs: stats.load(con, mode.NAME, degs)
    config = mode.configure(a, last, random.Random(a.seed))
    if run:
        config["run"] = dict(run)
    if not degrees.MIN_BPM <= config["bpm"] <= degrees.MAX_BPM:
        raise SystemExit(f"--bpm must be between {degrees.MIN_BPM} and {degrees.MAX_BPM}")
    bank = mode.bank(config, store.data_dir())
    score, items, keymap = mode.build_session(config, bank, random.Random(a.seed))
    config["keymap"] = keymap
    config["seed"] = a.seed
    config["commit"] = commit()
    config["argv"] = a.argv           # what was typed; the rest of the config is what it came to
    if a.ambient:
        return ambient(a, mode, config, score, items, bank)

    tg = tags(con, a.tag)
    sid = store.new_session(con, mode.NAME, config, tg)
    sdir = store.sessions_dir()
    score.to_json(sdir / f"{sid}.score.json")
    write_key(sdir / f"{sid}.key.jsonl", mode, config, items)
    if a.midi:
        score.to_midi(a.midi)
    tmpdir = None
    if a.keep_wav:
        wav = str(sdir / f"{sid}.wav")
    else:
        tmpdir = tempfile.mkdtemp(prefix="cordelia_")
        wav = os.path.join(tmpdir, "session.wav")
    try:
        render(score, wav, bank, progress)
        store.add_items(con, sid, items)
        title = f"session {sid} · {mode.NAME}"
        width = shutil.get_terminal_size().columns - 2 - 2 * stats.PAD
        rows = [*mode.settings(config), ("length", f"{score.seconds / 60:.0f} min, {len(items)} questions"),
                *([("round", f"{run['round']} / {run['rounds']}")] if run else []),
                ("tags", ", ".join(tg) or "none")]
        status = lambda cur, n, keys, revealed: mode.status(  # noqa: E731
            cur, n, scorer.typed(keys, keymap, config["keys"]), config, items[cur - 1]["truth"] if revealed else None)
        widest = [mode.status(len(items), len(items), [label] * config["keys"], config, answer).split("\n")
                  for label in set(keymap.values()) for answer in (None, label)]
        text_width = max(len(l) for text in widest for l in text)
        text_height = max(len(text) for text in widest)
        hint = [textwrap.fill(l, width) for l in mode.hint(config, width).split("\n")]
        hint_width = max(len(l) for h in hint for l in h.split("\n"))
        lines = with_panel(settings_table(rows, width).split("\n"), text_width, text_height, hint_width, width)
        body = "\n".join(lines + [""] + hint)
        session = stats.box(title, body)
        inner = len(session.split("\n")[0]) - 2 - 2 * stats.PAD      # the warning matches the session box's width
        warning = stats.box("UNCOMMITTED CHANGES", "\n".join(
            l.ljust(inner) for l in textwrap.wrap("this session is recorded with `commit: null`, "
                                                  "nothing says what code produced it", inner))) + "\n" if config["commit"] is None else ""
        screen = stats.centred(warning + session)
        show = panel_writer(screen, text_width)
        print("\r\x1b[K\n" + screen.replace(PANEL, " ") + "\n")
        ask_ms = [round(it["ask_s"] * 1000) for it in items]
        keystrokes, outcome, stopped_at = collect(wav, ask_ms, status=status, show=show,
                                                    reveal_ms=[round(it["window_end_s"] * 1000) for it in items])
        interrupted = outcome == "interrupted"
        outcome = "stopped" if interrupted else outcome
        store.add_keystrokes(con, sid, keystrokes)
        store.replace_answers(con, sid, scorer.score(store.items(con, sid), keystrokes, keymap, config["keys"]))
        store.finish_session(con, sid, outcome, stopped_at)
        print(f"saved session {sid} ({outcome}, {stopped_at / 60000:.0f} min)")
    except BaseException:
        store.finish_session(con, sid, "aborted", None)
        raise
    finally:
        if tmpdir:
            if os.path.exists(wav):
                os.remove(wav)
            os.rmdir(tmpdir)
    if interrupted:
        die_of_interrupt()
    return sid, outcome


PANEL = "\ue000"   # marks where the question panel's text starts, until the screen is printed


def with_panel(rows, text_width, text_height, right, room):
    """The settings rows with a small box at the right of the first few, for the question
    and the keys typed (`text_height` lines of it), its right edge at `right` (or just past the
    rows) and not past `room`; the rows unchanged when there is no room for it beside them."""
    inner = text_width + 4
    panel = ["╭─ question " + "─" * (inner - 11) + "╮",
             *["│  " + PANEL + " " * (text_width - 1) + "  │"] * text_height, "╰" + "─" * inner + "╯"]
    if len(rows) < len(panel):
        return rows
    at = max(max(len(r) for r in rows[:len(panel)]) + 4, right - len(panel[0]))
    if at + len(panel[0]) > room:
        return rows
    return [r.ljust(at) + panel[i] if i < len(panel) else r for i, r in enumerate(rows)]


def panel_writer(screen, text_width):
    """A function that writes the question panel's text, a line of it on each of the panel's
    lines, into the printed screen (the cursor two lines under it), or None when the screen has
    no panel."""
    lines = screen.split("\n")
    at = [(len(lines) + 1 - j, line.find(PANEL)) for j, line in enumerate(lines) if PANEL in line]
    if not at:
        return None
    def show(text):
        for (up, col), line in zip(at, text.split("\n") + [""] * len(at)):
            sys.stdout.write(f"\x1b[{up}A\r" + (f"\x1b[{col}C" if col else "") + line[:text_width].ljust(text_width)
                             + f"\x1b[{up}B\r")
    return show


def settings_table(rows, width):
    """(name, value) rows as two columns, a long value wrapped under its own column."""
    pad = max(len(name) for name, _ in rows) + 3
    return "\n".join(textwrap.fill(value, width, initial_indent=name.ljust(pad), subsequent_indent=" " * pad)
                     for name, value in rows)


def die_of_interrupt():
    """Ctrl+C was caught to save the session; now end the way an uncaught one would, killed by
    SIGINT, so the shell stops a `a; b` chain or a loop instead of going on to the next command."""
    sys.stdout.flush()
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    os.kill(os.getpid(), signal.SIGINT)


def ambient(a, mode, config, score, items, bank):
    """The session's audio and nothing else: no session row, no keys, no answers."""
    if a.tag:
        print("--tag ignored: an ambient session is not recorded")
    if a.midi:
        score.to_midi(a.midi)
    tmpdir = None
    if a.keep_wav:
        wav = str(store.sessions_dir() / "ambient.wav")
    else:
        tmpdir = tempfile.mkdtemp(prefix="cordelia_")
        wav = os.path.join(tmpdir, "session.wav")
    try:
        render(score, wav, bank, progress)
        title = f"ambient · {mode.NAME} · not recorded"
        width = shutil.get_terminal_size().columns - 2 - 2 * stats.PAD
        rows = [*mode.settings(config), ("length", f"{score.seconds / 60:.0f} min, {len(items)} questions")]
        print("\r\x1b[K\n" + stats.centred(stats.box(title, settings_table(rows, width) + "\n\nEsc stops.")) + "\n")
        _, outcome, _ = collect(wav, [round(it["ask_s"] * 1000) for it in items])
    finally:
        if tmpdir:
            if os.path.exists(wav):
                os.remove(wav)
            os.rmdir(tmpdir)
    if outcome == "interrupted":
        die_of_interrupt()


def cmd_rescore():
    con = store.connect()
    n = 0
    for (sid,) in con.execute("SELECT id FROM sessions WHERE outcome IN ('completed','stopped')").fetchall():
        sess = store.session(con, sid)
        cfg = sess["config"]
        rows = scorer.score(store.items(con, sid), store.keystrokes(con, sid), cfg["keymap"], cfg.get("keys", 1))
        store.replace_answers(con, sid, rows)
        n += 1
    print(f"rescored {n} sessions")


def write_key(path, mode, config, items):
    with open(path, "w") as f:
        f.write(json.dumps(dict(mode=mode.NAME, config=config)) + "\n")
        for it in items:
            f.write(json.dumps(it) + "\n")


def progress(p):
    print(f"\rrendering {p:4.0%}", end="", flush=True)
