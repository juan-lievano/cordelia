"""The settings a drill has been played with: one row for each combination, how many
sessions and minutes it got, how right, and when it was last played, newest first. What
is drawn afresh each session (the key, the seed) and what the code fills in (the
keymap, the commit) are left out, and a setting that never changed goes in the title
(unless none ever has).
"""

import json
from datetime import datetime

from .modes import DRILLS
from .modes.degrees import degrees_of, short
from .stats import box, centred, table

ROWS = 25             # the most recent combinations shown

# The settings shown, per drill, in this order: (name, function of the config -> text).
LIST = ("degrees", lambda c: short(degrees_of(c)))
KEYS = ("keys", lambda c: "all" if len(c.get("key_pool") or []) == 12 else " ".join(c["key_pool"]) if c.get("key_pool") else "")
BPM = ("bpm", lambda c: f"{c['bpm']:g}")
MINUTES = ("minutes", lambda c: f"{c['minutes']:g}")
SETTINGS = {
    "degrees": [LIST, BPM, MINUTES, ("answer", lambda c: c.get("answer", "spoken")), ("voice", lambda c: c.get("voice", "")), KEYS],
    "focus": [LIST, ("focus", lambda c: f"on {' '.join(c['focus']['degrees'])}" if c["focus"]["how"] == "manual"
                     else f"auto by {c['focus'].get('by', 'recall')}"),
              BPM, MINUTES, ("run", lambda c: f"{c['run']['minutes']:g}" if c.get("run") else ""),
              ("answer", lambda c: c.get("answer", "spoken")), ("voice", lambda c: c.get("voice", "")), KEYS],
    "melody": [("degrees", lambda c: short(c["degrees"]) if c.get("degrees") else ""),
               ("octaves", lambda c: str(c.get("octaves", 1))),
               ("length", lambda c: str(c.get("length", ""))), ("spread", lambda c: f"{c['spread']:g}" if "spread" in c else ""),
               ("hearings", lambda c: str(c.get("hearings", ""))), BPM, MINUTES, ("singer", lambda c: c.get("singer", "")), KEYS],
    "chords": [("level", lambda c: str(c.get("level", ""))), BPM, MINUTES, ("voice", lambda c: c.get("voice", ""))],
}


def show(con, mode=None):
    """The combinations `mode` (default: the drill played last) has been played with."""
    if mode is None:
        row = con.execute("SELECT mode FROM sessions WHERE outcome IN ('completed','stopped') ORDER BY id DESC LIMIT 1").fetchone()
        if not row:
            return print("no sessions recorded yet")
        mode = row[0]
    if mode not in SETTINGS:
        raise SystemExit(f"no such drill: {mode}. Use {' | '.join(DRILLS)}.")
    sql = """SELECT s.config, s.started_at_ms, s.stopped_at_ms,
                    (SELECT count(*) FROM answers a WHERE a.session_id = s.id),
                    (SELECT count(*) FROM answers a WHERE a.session_id = s.id AND a.correct = 1)
             FROM sessions s WHERE s.mode = ? AND s.outcome IN ('completed', 'stopped') ORDER BY s.id"""
    groups = {}
    for config, started, stopped, asked, right in con.execute(sql, (mode,)):
        cfg = json.loads(config)
        combo = tuple(f(cfg) for _, f in SETTINGS[mode])
        g = groups.setdefault(combo, dict(sessions=0, ms=0, asked=0, right=0))
        g["sessions"] += 1
        g["ms"] += stopped or 0
        g["asked"] += asked
        g["right"] += right
        g["last"] = started
    if not groups:
        return print(f"no {mode} sessions recorded yet")
    names = [n for n, _ in SETTINGS[mode]]
    varied = [i for i in range(len(names)) if len({c[i] for c in groups}) > 1]
    if not varied:          # one way of playing it so far: every setting a column
        varied = [i for i in range(len(names)) if next(iter(groups))[i]]
    fixed = [f"{names[i]} {next(iter(groups))[i]}" for i in range(len(names)) if i not in varied and next(iter(groups))[i]]
    recent = sorted(groups.items(), key=lambda kv: -kv[1]["last"])
    rows = [[combo[i] for i in varied]
            + [g["sessions"], f"{g['ms'] / 6e4:.0f}", f"{100 * g['right'] / g['asked']:.0f}%" if g["asked"] else "",
               datetime.fromtimestamp(g["last"] / 1000).strftime("%b %d %H:%M")]
            for combo, g in recent[:ROWS]]
    body = table([names[i] for i in varied] + ["sessions", "played", "right", "last"], rows, dividers=(len(varied) - 1,))
    more = len(recent) - ROWS
    title = " · ".join([f"{mode} history", *fixed, f"{len(recent)} settings"] + ([f"the latest {ROWS} shown"] if more > 0 else []))
    print("\n" + centred(box(title, body)) + "\n")
