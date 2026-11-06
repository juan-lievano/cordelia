"""The long view over the record: minutes practised by week, then for each
exercise a histogram of right% over the questions answered so far in the
order they were asked (one bar per question up to BARS questions, then BARS
equal groups), and for degrees and chords the confusion matrix.
"""

import json
import shutil
import sys
from datetime import datetime, timedelta

from .modes import MODES
from .modes.degrees import degrees_of, parse_degrees

BARS = 40             # most bars; past that many questions, that many groups
BAR = 2               # columns wide
FILL = "▓"            # dark shade: a full block is too bright in a light font
ROWS = 20             # rows of the histogram, 100% / ROWS each; labelled every 10%
PAD = 2               # columns between a box's edge and its contents


def load(con, mode=None, degrees=None, key=None, tag=None):
    """One row per question asked in a finished session; mode None is every mode."""
    sql = """SELECT s.id, s.started_at_ms, s.mode, s.config, s.tags, s.stopped_at_ms,
                    i.truth, i.meta, a.answer, a.correct, a.latency_ms
             FROM items i JOIN sessions s ON s.id = i.session_id
             LEFT JOIN answers a ON a.session_id = i.session_id AND a.idx = i.idx
             WHERE (? IS NULL OR s.mode = ?) AND s.outcome IN ('completed', 'stopped')
             ORDER BY s.started_at_ms, i.idx"""
    rows = []
    for sid, started, smode, config, tags, stopped, truth, meta, answer, correct, latency in con.execute(sql, (mode, mode)):
        cfg, tg = json.loads(config), json.loads(tags)
        if degrees and (smode != "degrees" or degrees_of(cfg) != degrees):
            continue
        if key and cfg.get("key", "").lower() != key.lower():
            continue
        if tag and tag not in tg:
            continue
        rows.append(dict(sid=sid, started=started, mode=smode, config=cfg, truth=truth, meta=json.loads(meta),
                         answer=answer, correct=correct, latency=latency, stopped=stopped,
                         exercise=exercise(smode, cfg)))
    return rows


def exercise(mode, cfg):
    """What is being drilled: the mode, plus the list of degrees it asked (degrees)
    or the level (melody, chords)."""
    parts = [mode]
    if mode == "degrees":
        parts += degrees_of(cfg)
    elif cfg.get("level") is not None:
        parts.append(str(cfg["level"]))
    return " ".join(parts)


def table(headers, rows):
    rows = [[str(c) for c in r] for r in rows]
    widths = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h) for i, h in enumerate(headers)]
    line = "  ".join(h.ljust(w) for h, w in zip(headers, widths))
    out = [line, "  ".join("-" * w for w in widths)]
    out += ["  ".join(c.ljust(w) for c, w in zip(r, widths)) for r in rows]
    return "\n".join(out)


def monday(ms):
    d = datetime.fromtimestamp(ms / 1000).date()
    return d - timedelta(days=d.weekday())


def report(con, mode="all", degrees=None, key=None, tag=None, full=False):
    """The exercise of the last session played; with full, the practice table and every exercise."""
    degrees = parse_degrees(degrees) if degrees else None
    rows = load(con, None if mode == "all" else mode, degrees, key, tag)
    if not rows:
        print("no sessions recorded yet" + (" with those filters" if (degrees or key or tag) else ""))
        return
    exercises = sorted({r["exercise"] for r in rows}) if full else [rows[-1]["exercise"]]
    blocks = [("minutes, by week", practice(rows, exercises))] if full else []
    for ex in exercises:
        ex_rows = [r for r in rows if r["exercise"] == ex]
        n = len(ex_rows)
        per_bar = "a bar per question" if n <= BARS else f"each bar the mean of ~{n / BARS:.0f}"
        right = 100 * sum(1 for r in ex_rows if r["correct"] == 1) / n
        blocks.append((f"{ex} · {n} questions · {right:.0f}% right · {per_bar}", histogram(ex_rows)))
        if ex_rows[0]["mode"] in ("degrees", "chords"):
            blocks.append((f"confusion, {n} questions · rows asked, % of each", confusion_matrix(ex_rows)))
    print("\n" + "\n\n".join(box(t, b) for t, b in blocks) + "\n")


def box(title, body):
    """The body in a rounded box with the title set into its top edge, centred on the terminal."""
    lines = body.split("\n")
    width = max(len(title) + 4, *(len(l) for l in lines)) + 2 * PAD
    top = "╭─ " + title + " " + "─" * (width - len(title) - 3) + "╮"
    mid = ["│" + " " * PAD + l.ljust(width - 2 * PAD) + " " * PAD + "│" for l in ["", *lines, ""]]
    bottom = "╰" + "─" * width + "╯"
    margin = " " * max(0, (shutil.get_terminal_size().columns - width - 2) // 2) if sys.stdout.isatty() else ""
    return "\n".join(margin + l for l in [top, *mid, bottom])


def practice(rows, exercises):
    """Minutes by week and exercise, with a total row and column."""
    minutes = {}
    seen = set()
    for r in rows:
        if r["sid"] in seen:
            continue
        seen.add(r["sid"])
        minutes[(monday(r["started"]), r["exercise"])] = \
            minutes.get((monday(r["started"]), r["exercise"]), 0) + (r["stopped"] or 0) / 6e4
    weeks = sorted({w for w, _ in minutes})
    cell = lambda m: f"{m:.0f}" if m else "."
    out = [[str(w)] + [cell(minutes.get((w, ex), 0)) for ex in exercises]
           + [cell(sum(minutes.get((w, ex), 0) for ex in exercises))] for w in weeks]
    out.append(["total"] + [cell(sum(m for (_, e), m in minutes.items() if e == ex)) for ex in exercises]
               + [cell(sum(minutes.values()))])
    return table(["week of"] + exercises + ["all"], out)


def histogram(rows):
    """right% per question, or per group once there are more than BARS, oldest left. A melody is right only whole."""
    n = len(rows)
    bars = min(n, BARS)
    bins = [[] for _ in range(bars)]
    for i, r in enumerate(rows):
        bins[i * bars // n].append(r)
    pcts = [100 * sum(1 for r in b if r["correct"] == 1) / len(b) if b else None for b in bins]
    lines = []
    for level in range(ROWS, 0, -1):
        y = level * 100 / ROWS
        cells = [FILL * BAR if p is not None and p >= y - 1e-9 else " " * BAR for p in pcts]
        lines.append(f"{y:>3.0f}" if y % 10 == 0 else "   ") 
        lines[-1] += " │ " + " ".join(cells)
    lines.append("    └─" + "─" * ((BAR + 1) * bars - 1) + "  ")   # the slack keeps the right edge off the bars
    return "\n".join(lines)


def confusion_matrix(rows):
    """Each row an asked label, the share of its answers (%) under each label.
    Rows and columns in the mode's LABELS order."""
    order = list(MODES[rows[0]["mode"]].LABELS)
    rank = lambda l: (order.index(l) if l in order else len(order), l)
    labels = sorted({r["truth"] for r in rows}, key=rank)
    given = {r["answer"] for r in rows} - set(labels) - {None, "pass"}    # answered though never asked
    answers = labels + sorted(given, key=rank) + ["none"]
    matrix = []
    for l in labels:
        asked = [r for r in rows if r["truth"] == l]
        counts = {a: 0 for a in answers}
        for r in asked:
            a = r["answer"] if r["answer"] not in (None, "pass") else "none"   # passes, before 2026-11-03
            counts[a] = counts.get(a, 0) + 1
        matrix.append([l] + [f"{100 * counts[a] / len(asked):.0f}" if counts[a] else "." for a in answers])
    return table(["asked"] + answers, matrix)
