"""The long view over the record: minutes practised by week, then for each
exercise a histogram of right% over the questions answered so far in the
order they were asked (one bar per question up to BARS questions, then BARS
equal groups), and, for a mode whose answers are single labels (LABELS), the confusion matrix.
"""

import json
import math
import shutil
import sys
from datetime import datetime, timedelta

from .modes import MODES
from .modes.degrees import degrees_of, parse_degrees

BARS = 40             # most bars; past that many questions, that many groups
BAR = 2               # columns wide
FILL = "▓"            # dark shade: a full block is too bright in a light font
ROWS = 20             # rows of the histogram, 100% / ROWS each; labelled every 10%
SHORT = 44            # a terminal with fewer lines than this gets half the rows, so a report fits
PAD = 2               # columns between a box's edge and its contents
NONE = "∅"            # the confusion matrix's column for questions with no answer
RECENT = 200          # the confusion matrix covers this many of the latest questions: how the misses go now
FIFTHS = ("C", "G", "D", "A", "E", "B", "F#", "Db", "Ab", "Eb", "Bb", "F")       # the circle, clockwise from the top
MINORS = ("a", "e", "b", "f#", "c#", "g#", "eb", "bb", "f", "c", "g", "d")       # each one's relative minor, spelt by its key signature
INNER = (0.5, 0.5)    # the minors' ring, as a share of the majors' width and height


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
    """What is being drilled: the mode, then what its module says (the degree
    list, the level). A mode this version no longer has falls back to its level."""
    m = MODES.get(mode)
    parts = m.exercise(cfg) if m else ([str(cfg["level"])] if cfg.get("level") is not None else [])
    return " ".join([mode, *parts])


def natural(name):
    """Sort key so that 'chords 2' comes before 'chords 10'."""
    return [(0, int(p)) if p.isdigit() else (1, p) for p in name.split()]


def table(headers, rows, dividers=(0,)):
    """Columns two spaces apart, a rule under the header, and a vertical line after each
    column in `dividers` (default: after the row labels)."""
    rows = [[str(c) for c in r] for r in rows]
    widths = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h) for i, h in enumerate(headers)]
    gap = lambda i, mid: (" " + mid + " ") if i in dividers else "  "
    fmt = lambda cells, mid="│": "".join(c.ljust(w) + (gap(i, mid) if i < len(widths) - 1 else "")
                                       for i, (c, w) in enumerate(zip(cells, widths)))
    return "\n".join([fmt(headers), fmt(["─" * w for w in widths], "┼").replace(" ", "─"), *[fmt(r) for r in rows]])


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
    exercises = sorted({r["exercise"] for r in rows}, key=natural) if full else [rows[-1]["exercise"]]
    blocks = [box("minutes, by week", practice(rows, exercises))] if full else []
    for ex in exercises:
        ex_rows = [r for r in rows if r["exercise"] == ex]
        n = len(ex_rows)
        per_bar = "a bar per question" if n <= BARS else f"each bar the mean of ~{n / BARS:.0f}"
        right = 100 * sum(1 for r in ex_rows if r["correct"] == 1) / n
        title = f"{ex} · {n} questions · {right:.0f}% right · {per_bar}"
        trend = slope(range(n), [100 * (r["correct"] == 1) for r in ex_rows])
        if trend is not None:
            title += f" · trend {100 * trend:+.2f} pp / 100 questions"
        hist = box(title, histogram(ex_rows))
        blocks.append(hist)
        if hasattr(MODES.get(ex_rows[0]["mode"]), "LABELS"):     # one label an answer: a matrix makes sense
            recent = ex_rows[-RECENT:]
            span = f"q: {n - len(recent) + 1}-{n}"
            boxes = [box(f"confusion, {span}, rows asked, %", confusion_matrix(recent)),
                     box(f"{span}, %", recall_precision(recent))]
            room = len(hist.split("\n")[0]) - sum(len(b.split("\n")[0]) + 1 for b in boxes) - 2 - 2 * PAD
            if room >= 24:       # the width left beside the two boxes, under the histogram: the circle of fifths
                boxes.append(box("", circle(room, len(boxes[0].split("\n")) - 4)))
            blocks.append(beside(boxes))
    print("\n" + "\n\n".join(centred(b) for b in blocks) + "\n")


def box(title, body):
    """The body in a rounded box with the title, if any, set into its top edge."""
    lines = body.split("\n")
    width = max(max(len(l) for l in lines) + 2 * PAD, len(title) + 5 if title else 0)   # "╭─ title ──╮", unpadded
    top = ("╭─ " + title + " " + "─" * (width - len(title) - 3) if title else "╭" + "─" * width) + "╮"
    mid = ["│" + " " * PAD + l.ljust(width - 2 * PAD) + " " * PAD + "│" for l in ["", *lines, ""]]
    bottom = "╰" + "─" * width + "╯"
    return "\n".join([top, *mid, bottom])


def beside(boxes):
    """Boxes of the same height side by side, a space apart."""
    return "\n".join(" ".join(r) for r in zip(*(b.split("\n") for b in boxes)))


def centred(text):
    """Every line shifted right so the widest sits in the middle of the terminal."""
    lines = text.split("\n")
    width = max(len(l) for l in lines)
    margin = " " * max(0, (shutil.get_terminal_size().columns - width) // 2) if sys.stdout.isatty() else ""
    return "\n".join(margin + l for l in lines)


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
    return table(["week of"] + exercises + ["all"], out, dividers=(0, len(exercises)))


def slope(xs, ys):
    """Least-squares slope of ys over xs, fitted to every point (not the bars); None when the fit is undefined."""
    xs, ys = list(xs), list(ys)
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else None


def histogram(rows):
    """right% per question, or per group once there are more than BARS, oldest left. A melody is right only whole."""
    n = len(rows)
    bars = min(n, BARS)
    bins = [[] for _ in range(bars)]
    for i, r in enumerate(rows):
        bins[i * bars // n].append(r)
    pcts = [100 * sum(1 for r in b if r["correct"] == 1) / len(b) if b else None for b in bins]
    lines = []
    rows_ = ROWS if shutil.get_terminal_size(fallback=(0, SHORT)).lines >= SHORT else ROWS // 2   # piped: tall
    for level in range(rows_, 0, -1):
        y = level * 100 / rows_
        cells = [FILL * BAR if p is not None and p >= y - 1e-9 else " " * BAR for p in pcts]
        lines.append(f"{y:>3.0f}" if y % 10 == 0 else "   ") 
        lines[-1] += " │ " + " ".join(cells)
    lines.append("    └─" + "─" * ((BAR + 1) * bars - 1) + " ")   # one column of slack keeps the edge off the bars
    return "\n".join(lines)


def confusion_matrix(rows):
    """Each row an asked label, the share of its answers (%) under each label,
    ∅ for no answer. Rows and columns in the mode's LABELS order."""
    labels = asked_labels(rows)
    given = {r["answer"] for r in rows} - set(labels) - {None, "pass"}    # answered though never asked
    answers = labels + sorted(given, key=lambda l: (l in MODES[rows[0]["mode"]].LABELS, l)) + [NONE]
    matrix = []
    for l in labels:
        asked = [r for r in rows if r["truth"] == l]
        counts = {a: 0 for a in answers}
        for r in asked:
            a = r["answer"] if r["answer"] not in (None, "pass") else NONE   # passes, before 2026-11-03
            counts[a] = counts.get(a, 0) + 1
        matrix.append([l] + [pct(counts[a], len(asked)) for a in answers])
    return table([""] + answers, matrix, dividers=(0, len(answers) - 1))     # labels | answers | ∅


def circle(width, height):
    """The circle of fifths, majors around the outside and their relative minors
    on a ring just inside, C at the top, drawn to fill width columns and height lines."""
    grid = [[" "] * width for _ in range(height)]
    cx, cy = (width - 1) / 2, (height - 1) / 2

    def put(label, rx, ry, k):
        a = math.radians(30 * k)
        x, y = round(cx + rx * math.sin(a) - (len(label) - 1) / 2), round(cy - ry * math.cos(a))
        grid[y][x:x + len(label)] = label

    for k, (major, minor) in enumerate(zip(FIFTHS, MINORS)):
        put(major, cx - 1, cy, k)
        put(minor, (cx - 1) * INNER[0], cy * INNER[1], k)
    return "\n".join("".join(r) for r in grid)


def asked_labels(rows):
    """The labels asked, in the mode's LABELS order."""
    order = list(MODES[rows[0]["mode"]].LABELS)
    return sorted({r["truth"] for r in rows}, key=lambda l: (order.index(l) if l in order else len(order), l))


def pct(part, whole):
    return f"{100 * part / whole:.0f}" if part else "."


def recall_precision(rows):
    """Each asked label's recall (answered so when asked, % of asked: the matrix's
    diagonal) and precision (asked when answered so, % of the answers)."""
    out = []
    for l in asked_labels(rows):
        right = sum(1 for r in rows if r["truth"] == l and r["answer"] == l)
        out.append([l, pct(right, sum(1 for r in rows if r["truth"] == l)),
                    pct(right, sum(1 for r in rows if r["answer"] == l))])
    return table(["", "recall", "precision"], out)
