"""How the last exercise played is going: a histogram of right% over the
questions answered so far in the order they were asked (one bar per question
up to as many bars as fit, BARS at most, then that many equal groups), and, for
a mode whose answers are single labels (LABELS), the confusion matrix and each
label's recall and precision as a pair of bars, with the circle of fifths in
the width left over. A terminal with the height gets the matrix's cells two
lines tall. Minutes practised are the journal's.
"""

import json
import math
import random
import re
import shutil
import sys

from .modes import MODES
from .modes.degrees import degrees_of, parse_degrees

BARS = 60             # most bars, where the terminal is wide enough; past that many questions, that many groups
BAR = 2               # columns wide
RAMP = " ▁▂▃▄▅▆▇█"    # a cell filled by eighths from the bottom: the top of a bar lands within an eighth of a row
ROWS = 20             # rows of the histogram, 100% / ROWS each; labelled every 10%
SHORT = 44            # a terminal with fewer lines than this gets half the rows, so a report fits
PAD = 2               # columns between a box's edge and its contents
NONE = "∅"            # the confusion matrix's column for questions with no answer
RECENT = 500          # the confusion matrix covers this many of the latest questions: how the misses go now
CELL = 4              # a confusion cell is this many braille characters wide, its dots scattered
BIG = 2               # and this many lines tall where the terminal has the height (64 dots), one line where not (32)
BRIGHT = " " + "".join(chr(0xE000 + i) for i in range(1, 9))   # RAMP's blocks under private codes: drawn at full strength, not dimmed
LOW = 9               # fewest lines inside the boxes under the histogram: a few labels still get bars and a circle with room
PAIR = 3              # columns between one label's pair of recall and precision bars and the next
FIFTHS = ("C", "G", "D", "A", "E", "B", "F#", "Db", "Ab", "Eb", "Bb", "F")       # the circle, clockwise from the top
MINORS = ("a", "e", "b", "f#", "c#", "g#", "eb", "bb", "f", "c", "g", "d")       # each one's relative minor, spelt by its key signature
INNER = (0.5, 0.5)    # the minors' ring, as a share of the majors' width and height
DOT = {(0, 0): 0x01, (0, 1): 0x02, (0, 2): 0x04, (0, 3): 0x40,     # (column, row from the top) -> braille bit
       (1, 0): 0x08, (1, 1): 0x10, (1, 2): 0x20, (1, 3): 0x80}


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


def exercise(mode, cfg, brief=False):
    """What is being drilled: the mode and what its module says (the degree
    list, the level; for melody the list, then the rest of the recipe after a
    dot). A mode this version no longer has falls back to its level. `brief`
    names a list by its scale (`minor 8`), for a title; rows are grouped by the full one."""
    m = MODES.get(mode)
    parts = m.exercise(cfg, brief) if m else ([str(cfg["level"])] if cfg.get("level") is not None else [])
    return " · ".join([" ".join([mode, *parts[:1]]), *parts[1:]])


def table(headers, rows, dividers=(0,)):
    """Columns two spaces apart, a rule under the header, and a vertical line after each
    column in `dividers` (default: after the row labels)."""
    rows = [[str(c) for c in r] for r in rows]
    widths = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h) for i, h in enumerate(headers)]
    gap = lambda i, mid: (" " + mid + " ") if i in dividers else "  "
    fmt = lambda cells, mid="│": "".join(c.ljust(w) + (gap(i, mid) if i < len(widths) - 1 else "")
                                       for i, (c, w) in enumerate(zip(cells, widths)))
    return "\n".join([fmt(headers), fmt(["─" * w for w in widths], "┼").replace(" ", "─"), *[fmt(r) for r in rows]])


def report(con, mode="all", degrees=None, key=None, tag=None):
    """The exercise of the last session played, within the filters."""
    degrees = parse_degrees(degrees) if degrees else None
    rows = load(con, None if mode == "all" else mode, degrees, key, tag)
    if not rows:
        print("no sessions recorded yet" + (" with those filters" if (degrees or key or tag) else ""))
        return
    ex = rows[-1]["exercise"]
    ex_rows = [r for r in rows if r["exercise"] == ex]
    n = len(ex_rows)
    bars = bar_count(n)
    per_bar = "a bar per q" if n <= bars else f"each bar the mean of ~{n / bars:.0f}"
    right = 100 * sum(1 for r in ex_rows if r["correct"] == 1) / n
    title = f"{exercise(ex_rows[-1]['mode'], ex_rows[-1]['config'], brief=True)} · {n} q · {right:.0f}% right · {per_bar}"
    trend = slope(range(n), [100 * (r["correct"] == 1) for r in ex_rows])
    if trend is not None:
        b, se = trend
        title += f" · trend {sig2(100 * b, '+')} ± {sig2(100 * se)} pp / 100 q"
    hist = box(title, histogram(ex_rows, bars))
    blocks = [hist]
    if hasattr(MODES.get(ex_rows[0]["mode"]), "LABELS"):     # one label an answer: a matrix makes sense
        recent = ex_rows[-RECENT:]
        span = f"q: {n - len(recent) + 1}-{n}"
        labels, counts = tally(recent)
        big = lines() >= len(hist.split("\n")) + max(BIG * len(labels) + 2, LOW) + 4 + 4     # both boxes, the blank lines, the prompt
        body = confusion_matrix(labels, counts, big)
        height = max(body.count("\n") + 1, LOW)                     # the three boxes are as tall as the matrix, LOW at least
        matrix = box(f"confusion, {span}, rows asked", body + "\n" * (height - body.count("\n") - 1))
        boxes = [matrix, box(f"recall, then precision, % · {span}", pairs(labels, counts, height))]
        room = len(hist.split("\n")[0]) - sum(len(b.split("\n")[0]) + 1 for b in boxes) - 2 - 2 * PAD
        if room >= 24:       # the width left beside the two boxes, under the histogram: the circle of fifths
            boxes.append(box("", circle(room, height)))
        fits = sum(len(b.split("\n")[0]) + 1 for b in boxes) - 1 <= columns()
        blocks += [beside(boxes)] if fits else boxes       # a narrow terminal: one under the other
    print("\n" + soft("\n\n".join(centred(b) for b in blocks)) + "\n")


def columns():
    """The terminal's width; no limit when piped."""
    return shutil.get_terminal_size().columns if sys.stdout.isatty() else 10 ** 6


def lines():
    """The terminal's height; no limit when piped."""
    return shutil.get_terminal_size().lines if sys.stdout.isatty() else 10 ** 6


def sig2(x, sign=""):
    """x to two significant figures, written out: -104.5 is -100, 0.4321 is 0.43."""
    if not x:
        return "0"
    places = 1 - math.floor(math.log10(abs(x)))
    return f"{round(x, places):{sign}.{max(places, 0)}f}"


def box(title, body):
    """The body in a rounded box with the title, if any, set into its top edge. A title may
    widen the box as far as the terminal; the parts (split at " · ") that still do not fit
    go on lines of their own inside, above the body."""
    lines = body.split("\n")
    room = max(max(len(l) for l in lines) + 2 * PAD, columns() - 2)     # widest the inside may get
    parts, rest = title.split(" · "), []
    while len(parts) > 1 and len(" · ".join(parts)) + 5 > room:
        rest.insert(0, parts.pop())
    title = " · ".join(parts)[:room - 5]
    if rest:
        wrapped = [rest.pop(0)]
        for part in rest:
            if len(wrapped[-1]) + 3 + len(part) <= room - 2 * PAD:
                wrapped[-1] += " · " + part
            else:
                wrapped.append(part)
        lines = [*wrapped, "", *lines]
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


def slope(xs, ys):
    """Least-squares slope of ys over xs and its standard error, fitted to every point
    (not the bars); None when the fit is undefined. The error takes the points as
    independent, which they are not quite (a bad day is a run of them), so it is a floor."""
    xs, ys = list(xs), list(ys)
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if not sxx:
        return None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    rss = sum((y - my - b * (x - mx)) ** 2 for x, y in zip(xs, ys))
    return b, math.sqrt(rss / (n - 2) / sxx)


def bar_count(n):
    """A bar per question up to BARS, fewer where the terminal is too narrow for that many."""
    fit = (columns() - 2 - 2 * PAD - 7) // (BAR + 1)      # the box's edges and padding, "100 │ " and a column of slack
    return max(1, min(n, BARS, fit))


def histogram(rows, bars):
    """right% per question, or per group once there are more questions than bars, oldest left. A melody is right only whole."""
    n = len(rows)
    bins = [[] for _ in range(bars)]
    for i, r in enumerate(rows):
        bins[i * bars // n].append(r)
    pcts = [100 * sum(1 for r in b if r["correct"] == 1) / len(b) if b else None for b in bins]
    out = []
    rows_ = ROWS if lines() >= SHORT else ROWS // 2
    for level in range(rows_, 0, -1):
        y = level * 100 / rows_
        cells = [RAMP[0 if p is None else round(8 * min(1, max(0, p * rows_ / 100 - level + 1)))] * BAR for p in pcts]
        out.append((f"{y:>3.0f}" if y % 10 == 0 else "   ") + " │ " + " ".join(cells))
    out.append("    └─" + "─" * ((BAR + 1) * bars - 1) + " ")   # one column of slack keeps the edge off the bars
    return "\n".join(out)


def soft(text):
    """The bars in the terminal's dim colour, plain when piped: a block at full strength is too
    bright in a light font. The BRIGHT ones become plain blocks here, after the dimming."""
    if sys.stdout.isatty():
        text = re.sub("[▁-█]+", lambda m: f"\x1b[2m{m[0]}\x1b[22m", text)
    return text.translate(str.maketrans(BRIGHT[1:], RAMP[1:]))


def tally(rows):
    """The labels asked, in the mode's LABELS order, and for each how often every one of them
    was the answer. An answer that is none of them (a slip of the hand; a pass, before
    2026-11-03) counts with no answer, under NONE."""
    order = list(MODES[rows[0]["mode"]].LABELS)
    labels = sorted({r["truth"] for r in rows}, key=lambda l: (order.index(l) if l in order else len(order), l))
    counts = {l: dict.fromkeys([*labels, NONE], 0) for l in labels}
    for r in rows:
        counts[r["truth"]][r["answer"] if r["answer"] in labels else NONE] += 1
    return labels, counts


def confusion_matrix(labels, counts, big):
    """Each row an asked label, the share of its answers under each label as a cell of dots
    (all lit = all of them; any at all lights one, so an empty cell is never), ∅ for no
    answer. A `big` cell is BIG lines tall, a small one a single line."""
    matrix = []
    for l in labels:
        asked = sum(counts[l].values())
        cells = [scatter(n, asked, BIG if big else 1, f"{l}/{a}") for a, n in counts[l].items()]
        matrix += [[l if i == 0 else ""] + [c[i] for c in cells] for i in range(len(cells[0]))]
    return table(["", *labels, NONE], matrix, dividers=(0, len(labels)))      # labels | answers | ∅


def scatter(part, whole, rows, seed):
    """A cell CELL characters by `rows` lines, part/whole of its dots lit: dealt out to its characters evenly, give or
    take one, then at random inside each, so the cell reads as one even density. `seed`
    fixes the draw: a cell looks the same every run and changes only with its share."""
    chars = CELL
    rng = random.Random(seed)
    lit = math.ceil(8 * chars * rows * part / whole) if part else 0
    order = list(range(chars * rows))
    rng.shuffle(order)
    cells = [0] * (chars * rows)
    for i, c in enumerate(order):
        for bit in rng.sample(sorted(DOT.values()), lit // len(cells) + (i < lit % len(cells))):
            cells[c] |= bit
    return ["".join(chr(0x2800 + b) for b in cells[r * chars:(r + 1) * chars]) for r in range(rows)]


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


def pairs(labels, counts, height):
    """Each asked label's recall (answered so when asked, % of asked: the matrix's diagonal)
    and precision (asked when answered so, % of the answers) as two upright bars, recall
    first and at full strength. `height` lines in all."""
    right = {l: counts[l][l] for l in labels}
    recall = {l: 100 * right[l] / sum(counts[l].values()) for l in labels}
    said = {l: sum(counts[t][l] for t in labels) for l in labels}
    precision = {l: 100 * right[l] / said[l] if said[l] else 0 for l in labels}
    bar, gap = BAR, " " * PAIR
    slot = 2 * bar + 1 + PAIR                                   # columns a label, its gap included
    rows = max(2, (height - 2) // 2 * 2)                        # under the bars: the axis, the labels; even, so 50 is a row's top

    def column(pct, level, ramp):
        return ramp[max(0, min(8, round(pct / 100 * rows * 8) - 8 * level))] * bar

    out = [""] * (height - 2 - rows)
    for level in range(rows - 1, -1, -1):
        tick = "100" if level == rows - 1 else " 50" if level == rows // 2 - 1 else "   "
        out.append(tick + " │ " + gap.join(column(recall[l], level, BRIGHT) + " " + column(precision[l], level, RAMP) for l in labels))
    out.append("    └─" + "─" * (slot * len(labels) - len(gap) + 1))
    out.append("      " + gap.join(l.center(2 * bar + 1) for l in labels))
    return "\n".join(out)
