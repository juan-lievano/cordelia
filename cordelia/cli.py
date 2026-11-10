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
    d.add_argument("degrees", nargs="*", metavar="DEGREE",
                   help=f"the degrees to ask, from {' '.join(degrees.SEMITONES)}; "
                        + ", ".join(f"{w} = {' '.join(l)}" for w, l in degrees.SHORTHANDS.items()))
    d.add_argument("--minutes", type=float)
    d.add_argument("--key", dest="key_pool", nargs="+", metavar="KEY", help=KEY_HELP)
    d.add_argument("--bpm", type=float)
    d.add_argument("--voice", help="a `say -v ?` voice; 'default' = system voice")
    session_flags(d)

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
    if extra:       # argparse would blame the top-level usage; the subcommand's is the useful one
        sub.choices[a.cmd].error(f"unrecognized arguments: {' '.join(extra)}  (--help lists the flags)")
    if a.cmd in MODES:
        return cmd_session(MODES[a.cmd], a)
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


def session_flags(p):
    p.epilog = "Every setting left out is the last session's of this drill, the --key list too."
    p.add_argument("--tag", help="tag this and every later session (sticky); 'none' clears")
    p.add_argument("--keep-wav", action="store_true", help="keep the session's WAV in data/sessions/")
    p.add_argument("--midi", metavar="FILE", help="also write the score as a MIDI file")
    p.add_argument("--seed", type=int, help="draw the same questions again")
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


def cmd_session(mode, a):
    con = store.connect()
    last = store.session(con, store.last_session_id(con, mode.NAME) or 0)
    remember(a, mode.DEFAULTS, last and last["config"])
    config = mode.configure(a, last and last["config"], random.Random(a.seed))
    if not degrees.MIN_BPM <= config["bpm"] <= degrees.MAX_BPM:
        raise SystemExit(f"--bpm must be between {degrees.MIN_BPM} and {degrees.MAX_BPM}")
    bank = mode.bank(config, store.data_dir())
    score, items, keymap = mode.build_session(config, bank, random.Random(a.seed))
    config["keymap"] = keymap
    config["seed"] = a.seed
    config["commit"] = commit()
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
        title = (f"session {sid} · {mode.describe(config)} · {len(items)} q, "
                 f"{score.seconds / 60:.0f} min · " + (f"tags: {', '.join(tg)}" if tg else "no tags"))
        width = shutil.get_terminal_size().columns - 2 - 2 * stats.PAD
        body = "\n".join(textwrap.fill(l, width) for l in mode.hint(config, width).split("\n"))
        warning = stats.box("UNCOMMITTED CHANGES", "this session is recorded with `commit: null`, "
                            "nothing says what code produced it") + "\n" if config["commit"] is None else ""
        print("\r\x1b[K\n" + warning + stats.box(title, body) + "\n")
        ask_ms = [round(it["ask_s"] * 1000) for it in items]
        keystrokes, outcome, stopped_at = collect(
            wav, ask_ms, status=lambda cur, n, keys: mode.status(cur, n, scorer.typed(keys, keymap, config["keys"]), config))
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
        title = f"ambient · {mode.describe(config)} · {len(items)} q, {score.seconds / 60:.0f} min · not recorded"
        print("\r\x1b[K\n" + stats.box(title, "Esc stops.") + "\n")
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
