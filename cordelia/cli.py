"""cordelia: ear training that writes down every answer. The drills are `degrees`, `melody` and `chords`. See README.md."""

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import textwrap

from . import review, scorer, stats, store
from .collector import collect
from .modes import MODES, chords, degrees, melody
from .synth import render
from .voice import SINGERS


def main(argv=None):
    p = argparse.ArgumentParser(prog="cordelia", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("degrees", help="scale degrees over a drone, the answer spoken after each")
    d.add_argument("degrees", nargs="*", metavar="DEGREE",
                   help=f"the degrees to ask, from {' '.join(degrees.SEMITONES)}; "
                        + ", ".join(f"{w} = {' '.join(l)}" for w, l in degrees.SHORTHANDS.items())
                        + " (default: the last degrees session's list)")
    d.add_argument("--minutes", type=float, default=degrees.DEFAULTS["minutes"])
    d.add_argument("--key", help="tonic: C D E F G A B with # or b (default: random, not the last session's)")
    d.add_argument("--bpm", type=float, default=degrees.DEFAULTS["bpm"])
    d.add_argument("--voice", default=degrees.DEFAULTS["voice"], help="a `say -v ?` voice; default = system voice")
    session_flags(d)

    m = sub.add_parser("melody", help="short melodies over a drone, sung back after each")
    m.add_argument("level", type=int, nargs="?",
                   help="; ".join(f"{n}: {spec['about']}" for n, spec in melody.LEVELS.items())
                   + " (default: the last melody session's level)")
    m.add_argument("--minutes", type=float, default=melody.DEFAULTS["minutes"])
    m.add_argument("--key", help="tonic: C D E F G A B with # or b (default: random, not the last session's)")
    m.add_argument("--scale", default=melody.DEFAULTS["scale"], help=" | ".join(melody.CADENCE))
    m.add_argument("--bpm", type=float, default=melody.DEFAULTS["bpm"])
    m.add_argument("--singer", default=melody.DEFAULTS["singer"], help=" | ".join(SINGERS))
    session_flags(m)

    c = sub.add_parser("chords", help="chord qualities, the answer spoken then arpeggiated after each")
    c.add_argument("level", type=int, nargs="?",
                   help="; ".join(f"{n}: {spec['about']}" for n, spec in chords.LEVELS.items())
                   + " (default: the last chords session's level)")
    c.add_argument("--minutes", type=float, default=chords.DEFAULTS["minutes"])
    c.add_argument("--bpm", type=float, default=chords.DEFAULTS["bpm"])
    c.add_argument("--voice", default=chords.DEFAULTS["voice"], help="a `say -v ?` voice; default = system voice")
    session_flags(c)

    r = sub.add_parser("review", help="replay what a session missed, each with its answer")
    r.add_argument("session", nargs="?", type=int, help="session id (default: the last one)")
    r.add_argument("--midi", metavar="FILE")
    r.add_argument("--render", metavar="FILE", help="write the review WAV to FILE instead of playing it")

    s = sub.add_parser("stats", help="minutes by week, a right%% histogram per exercise, degree and chord confusions")
    s.add_argument("--mode", default="all", help=" | ".join(MODES) + " | all (default: every mode in turn)")
    s.add_argument("--degrees", nargs="*", metavar="DEGREE", help="degrees sessions that asked exactly this list")
    s.add_argument("--key")
    s.add_argument("--tag")
    s.add_argument("--full", action="store_true", help="minutes by week and every exercise, not just the last one played")

    sub.add_parser("rescore", help="rebuild every session's answers from its key presses")
    sub.add_parser("tags", help="show the sticky tags")
    sub.add_parser("data", help="where the database lives")

    if not (sys.argv[1:] if argv is None else argv):
        return p.print_help()
    a = p.parse_args(argv)
    if a.cmd in MODES:
        return cmd_session(MODES[a.cmd], a)
    if a.cmd == "review":
        return review.run(a.session, a.render, a.midi)
    if a.cmd == "stats":
        return stats.report(store.connect(), a.mode, a.degrees, a.key, a.tag, a.full)
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
    p.add_argument("--tag", help="tag this and every later session (sticky); 'none' clears")
    p.add_argument("--keep-wav", action="store_true", help="keep the session's WAV in data/sessions/")
    p.add_argument("--midi", metavar="FILE", help="also write the score as a MIDI file")
    p.add_argument("--seed", type=int, help="draw the same questions again")


def tags(con, flag=None):
    if flag is not None:
        store.set_setting(con, "tags", json.dumps([] if flag == "none" else [t.strip() for t in flag.split(",")]))
    return json.loads(store.setting(con, "tags", "[]"))


def cmd_session(mode, a):
    con = store.connect()
    last = store.session(con, store.last_session_id(con, mode.NAME) or 0)
    if not degrees.MIN_BPM <= a.bpm <= degrees.MAX_BPM:
        raise SystemExit(f"--bpm must be between {degrees.MIN_BPM} and {degrees.MAX_BPM}")
    config = mode.configure(a, last and last["config"], random.Random(a.seed))
    bank = mode.bank(config, store.data_dir())
    score, items, keymap = mode.build_session(config, bank, random.Random(a.seed))
    config["keymap"] = keymap
    config["seed"] = a.seed
    config["commit"] = commit()

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
        title = (f"session {sid} · {mode.describe(config)} · {len(items)} questions, "
                 f"{score.seconds / 60:.0f} min" + (f" · tags: {', '.join(tg)}" if tg else ""))
        width = shutil.get_terminal_size().columns - 2 - 2 * stats.PAD
        body = "\n".join(textwrap.fill(l, width) for l in mode.hint(config, width).split("\n"))
        warning = stats.box("UNCOMMITTED CHANGES", "this session is recorded with commit: null, "
                            "nothing says what code produced it") + "\n" if config["commit"] is None else ""
        print("\r\x1b[K\n" + warning + stats.box(title, body) + "\n")
        ask_ms = [round(it["ask_s"] * 1000) for it in items]
        keystrokes, outcome, stopped_at = collect(
            wav, ask_ms, status=lambda cur, n, keys: mode.status(cur, n, scorer.typed(keys, keymap), config))
        store.add_keystrokes(con, sid, keystrokes)
        store.replace_answers(con, sid, scorer.score(store.items(con, sid), keystrokes, keymap, config["keys"]))
        store.finish_session(con, sid, outcome, stopped_at)
        print(f"saved session {sid} ({outcome}, {stopped_at / 60000:.0f} min).  "
              f"cordelia review {sid} · cordelia stats")
    except BaseException:
        store.finish_session(con, sid, "aborted", None)
        raise
    finally:
        if tmpdir:
            if os.path.exists(wav):
                os.remove(wav)
            os.rmdir(tmpdir)


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
