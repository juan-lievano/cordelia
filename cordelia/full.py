"""The whole record on one screen (`cordelia stats --full`): every drill in one
table, then what holds across them. For the single degrees (the degrees and
focus drills pooled): each degree and what it is mistaken for, the pairs mixed
up most, and right% by how long the answer took, by key, by register, by the
leap from the note before, by hour. Then the melodies note by note, every run of
three notes inside them as a dot (times heard against right%), the chord
qualities, and records.

A box is (title, body, note). They are packed into as few rows as the
terminal's width allows, every row stretched to the widest and every box in a
row to the tallest, so the edges line up.
"""

import re
import shutil
import statistics
import sys
import textwrap
from collections import Counter, defaultdict
from datetime import date, datetime

from .modes import DRILLS
from .stats import BAR, FIFTHS, PAD, RAMP, confusion_matrix, load, tally

TOP = 8               # rows of a ranking
RECENT = 100          # questions in a drill's "last" column
MIN_BAR = 30          # questions a column of a chart needs
MIN_ROW = 15          # questions a row of a table needs
JOURNAL_WEEKS = 12    # weeks of the practice wall here; `cordelia journal` shows as many as fit
DRILL_ROWS = 9        # drills listed by name; the rest are one row
SINGLE = ("degrees", "focus")     # the modes that ask one degree a question
ENHARMONIC = {"C#": "Db", "G#": "Ab", "D#": "Eb", "A#": "Bb", "Gb": "F#"}     # a session's key -> its name on the circle
LEAPS = ((0, 0, "the same note"), (1, 2, "a step, 1 – 2"), (3, 5, "3 – 5"), (6, 11, "6 – 11"), (12, 12, "an octave"), (13, 99, "more"))


# ------------------------------------------------------------------ drawing

def columns():
    """The terminal's width; 120 when piped."""
    return shutil.get_terminal_size((120, 40)).columns


def soft(text):
    """The bars in the terminal's dim colour, plain when piped."""
    return re.sub("[▁-▐]+", lambda m: f"\x1b[2m{m[0]}\x1b[22m", text) if sys.stdout.isatty() else text


def table(cols, rows):
    """Plain columns: `cols` is (header, align, format) per column; None cells print as '·'."""
    def cell(v, fmt):
        return "·" if v is None else format(v, fmt) if fmt else str(v)
    text = [[cell(v, c[2]) for v, c in zip(r, cols)] for r in rows]
    widths = [max(len(c[0]), *(len(t[i]) for t in text)) if text else len(c[0]) for i, c in enumerate(cols)]
    def line(cells):
        return "  ".join(f"{s:{c[1]}{w}}" for s, c, w in zip(cells, cols, widths)).rstrip()
    return "\n".join([line([c[0] for c in cols]), *(line(t) for t in text)])


def hbar(frac, width=10):
    """A bar `frac` of `width` columns long, to the eighth of a column."""
    n = round(max(0.0, min(1.0, frac)) * width * 8)
    return ("█" * (n // 8) + (" ▏▎▍▌▋▊▉"[n % 8] if n % 8 else "")).ljust(width)


def sided(v, most, half=5):
    """A bar left of the axis for a negative v, right for a positive one, to half a column; `most` fills a side."""
    n = round(min(1.0, abs(v) / most) * half * 2) if most else 0
    full, odd = "█" * (n // 2), n % 2
    left = (("▐" if odd else "") + full).rjust(half) if v < 0 else " " * half
    right = (full + ("▌" if odd else "")).ljust(half) if v > 0 else " " * half
    return left + "│" + right


def chart(labels, vals, rows=8, bar=BAR):
    """A column per label, in the order given, on an axis from 10 under the lowest value (rounded to 10s) to the highest."""
    lo = max(0, int((min(vals) - 10) // 10 * 10))
    hi = max(int(-(-max(vals) // 10) * 10), lo + 10)
    step = (hi - lo) / rows
    lines = []
    for i in range(rows):
        y = hi - i * step
        lines.append((f"{hi:>3.0f}" if i == 0 else "   ") + " │ " + " ".join(RAMP[round(8 * min(1, max(0, (v - y) / step + 1)))] * bar for v in vals))
    lines.append(f"{lo:>3.0f} └─" + "─" * ((bar + 1) * len(vals) - 1))
    lines.append("      " + " ".join(f"{l:<{bar}}" for l in labels))
    return "\n".join(lines)


def beside(blocks, gap="    "):
    """Several multi-line strings side by side, each padded to its own width."""
    split = [b.split("\n") for b in blocks]
    widths = [max(len(l) for l in s) for s in split]
    return "\n".join(gap.join((s[i] if i < len(s) else "").ljust(w) for s, w in zip(split, widths)).rstrip()
                     for i in range(max(len(s) for s in split)))


def box_lines(title, body, note=None, width=None, height=None):
    """The body in a rounded box, the title in its top edge, the note word-wrapped under the body to the
    body's width. `width` and `height` (outer) pad it out to sit in a grid."""
    lines = body.split("\n")
    inner = max(len(title) + 2, *(len(l) for l in lines))
    if note:
        inner = min(max(inner, 36), max(inner, columns() - 2 - 2 * PAD))
        lines += ["", *textwrap.wrap(note, inner)]
    inner = max(inner, (width or 0) - 2 - 2 * PAD)
    lines += [""] * ((height or 0) - 4 - len(lines))
    width = inner + 2 * PAD
    top = "╭─ " + title + " " + "─" * (width - len(title) - 3) + "╮"
    mid = ["│" + " " * PAD + l.ljust(width - 2 * PAD) + " " * PAD + "│" for l in ["", *lines, ""]]
    return [top, *mid, "╰" + "─" * width + "╯"]


def grid(parts, gap=1):
    """The boxes as one block. Widest first, each into the first row with room, gives the number of rows;
    of every way to fill that many or one more, the one with the fewest rows under two thirds full, then the fewest lines (tall boxes share a row), then the fullest emptiest row. A row keeps the order the
    boxes were given in, and the rows the order of their first boxes."""
    firsts_ = [box_lines(*p) for p in parts]
    natural = [len(b[0]) for b in firsts_]
    room = columns()
    def used(r):
        return sum(natural[k] for k in r) + gap * (len(r) - 1)
    packed = []
    for i in sorted(range(len(parts)), key=lambda i: -natural[i]):
        for r in packed:
            if used(r) + gap + natural[i] <= room:
                r.append(i); break
        else:
            packed.append([i])
    tall = [len(b) for b in firsts_]
    def cost(rows):          # rows left under two thirds full, then the lines the block takes, then how empty its emptiest row is
        return (sum(3 * used(r) < 2 * room for r in rows), sum(max(tall[k] for k in r) for r in rows), -min(map(used, rows), default=0))
    best = (cost(packed), [list(r) for r in packed])
    budget = 200_000          # placements tried; the search keeps the best it has seen when this runs out
    def place(i, rows):
        nonlocal best, budget
        budget -= 1
        if budget < 0 or (0, sum(max(tall[k] for k in r) for r in rows)) > best[0][:2]:    # rows only grow taller
            return
        if i == len(parts):
            if cost(rows) < best[0]:
                best = (cost(rows), [list(r) for r in rows])
            return
        for r in rows:
            if used(r) + gap + natural[i] <= room:
                r.append(i); place(i + 1, rows); r.pop()
        if len(rows) <= len(packed):
            rows.append([i]); place(i + 1, rows); rows.pop()
    if len(parts) <= 16:
        place(0, [])
    spec = [[parts[i] for i in sorted(r)] for r in sorted(best[1], key=min)]
    total = max(used(r) for r in best[1])
    out = []
    for ps in spec:
        firsts = [box_lines(*p) for p in ps]
        spare = total - sum(len(b[0]) for b in firsts) - gap * (len(ps) - 1)
        widths = [len(b[0]) + spare // len(ps) + (k < spare % len(ps)) for k, b in enumerate(firsts)]
        boxes = [box_lines(*p, width=w) for p, w in zip(ps, widths)]
        height = max(len(b) for b in boxes)
        boxes = [b[:-1] + ["│" + " " * (len(b[0]) - 2) + "│"] * (height - len(b)) + b[-1:] for b in boxes]
        out += [(" " * gap).join(line) for line in zip(*boxes)]
    width = max(len(l) for l in out)
    margin = " " * max(0, (shutil.get_terminal_size().columns - width) // 2) if sys.stdout.isatty() else ""
    return "\n".join(margin + l for l in out)


# ------------------------------------------------------------------ counting

def right(rows):
    """% of the questions answered right; no answer is not right."""
    return 100 * sum(r["correct"] == 1 for r in rows) / len(rows)


def groups(rows, key):
    out = defaultdict(list)
    for r in rows:
        k = key(r)
        if k is not None:
            out[k].append(r)
    return out


def seconds(rows):
    """Median seconds from the question to the answer, of the questions answered."""
    took = [r["latency"] / 1000 for r in rows if r["latency"] is not None]
    return statistics.median(took) if took else None


def minutes(rows):
    """Minutes of the sessions these questions came from: how far each one's audio got."""
    return sum({r["sid"]: (r["stopped"] or 0) for r in rows}.values()) / 6e4


def day(r):
    return datetime.fromtimestamp(r["started"] / 1000).date()


def order(mode):
    labels = list(DRILLS[mode].LABELS)
    return lambda l: (labels.index(l) if l in labels else len(labels), l)


# ------------------------------------------------------------------ the boxes

def drills_box(rows, title):
    """A row per drill (a mode on a list; a melody's recipe and a range are pooled into it), most practised first."""
    by = groups(rows, lambda r: r["exercise"].split(" · ")[0])
    ranked = sorted(by.items(), key=lambda kv: -minutes(kv[1]))
    def line(name, rs, one=True):
        return (name, len(rs), minutes(rs), right(rs), right(rs[-RECENT:]) if one and len(rs) > RECENT else None,
                100 * sum(r["answer"] is None for r in rs) / len(rs), seconds(rs))
    body = [line(n, rs) for n, rs in ranked[:DRILL_ROWS]]
    rest = [r for _, rs in ranked[DRILL_ROWS:] for r in rs]
    if rest:
        body.append(line(f"{len(ranked) - DRILL_ROWS} more", rest, one=False))
    cols = [("drill", "<", ""), ("questions", ">", "d"), ("min", ">", ".0f"), ("right %", ">", ".0f"), (f"last {RECENT}", ">", ".0f"),
            ("no answer %", ">", ".0f"), ("s", ">", ".1f")]
    return (title, table(cols, body), f"a melody is right only whole · last {RECENT} = right % of the latest {RECENT} questions · "
            "s = the median seconds from the question to the answer")


def confusions(rows, mode, what):
    """Each label asked: how often, how often right, how fast, and what it was taken for most when missed."""
    by = groups(rows, lambda r: r["truth"])
    body = []
    for label in sorted(by, key=order(mode)):
        rs = by[label]
        wrong = Counter(r["answer"] for r in rs if r["correct"] == 0)
        took, n = wrong.most_common(1)[0] if wrong else (None, 0)
        misses = sum(r["correct"] != 1 for r in rs)
        body.append((label, len(rs), hbar(right(rs) / 100), right(rs), seconds([r for r in rs if r["correct"] == 1]),
                     took, 100 * n / misses if misses else None))
    cols = [(what, "<", ""), ("asked", ">", "d"), ("", "<", ""), ("right %", ">", ".0f"), ("s", ">", ".1f"),
            ("taken for", "<", ""), ("% of misses", ">", ".0f")]
    return table(cols, body)


def mixups(rows, mode):
    """The pairs of labels taken for each other most, both ways counted together."""
    pairs = Counter((r["truth"], r["answer"]) for r in rows if r["correct"] == 0 and r["answer"] is not None)
    both = Counter()
    for (t, a), n in pairs.items():
        both[tuple(sorted((t, a), key=order(mode)))] += n
    if not both:
        return None
    misses = sum(both.values())
    top = both.most_common(TOP)
    body = [(f"{a} ↔ {b}", hbar(n / top[0][1], 8), n, 100 * n / misses, f"{a} as {b}: {pairs[(a, b)]}", f"{b} as {a}: {pairs[(b, a)]}")
            for (a, b), n in top]
    return ("degrees · the mix-ups", table([("pair", "<", ""), ("", "<", ""), ("times", ">", "d"), ("% of misses", ">", ".0f"),
                                             ("", "<", ""), ("", "<", "")], body),
            "a wrong answer counts for its pair, whichever of the two was asked")


def matrix_box(rows, title):
    """Every question of these rows in one confusion matrix: a row per label asked, its answers as cells of dots."""
    if len(rows) < MIN_ROW:
        return None
    labels, counts = tally(rows)
    return (title, confusion_matrix(labels, counts, big=True),
            "rows asked, columns answered · a cell full of dots = every answer of that row · ∅ = no answer, or a key off the list")


def speed_box(rows):
    """Right % by how long the answer took, in half seconds."""
    by = groups(rows, lambda r: None if r["latency"] is None else min(max(r["latency"] // 500, 2), 9))
    slots = [k for k in sorted(by) if len(by[k]) >= MIN_BAR]
    if len(slots) < 2:
        return None
    labels = [f"{k / 2:.1f}" for k in slots]
    labels[-1] += "+" if slots[-1] == 9 else ""
    return ("degrees · right % by seconds to answer", chart(labels, [right(by[k]) for k in slots], bar=4),
            f"each column a half second, from the question's onset to the key · {MIN_BAR}+ answers a column")


def keys_box(rows):
    """Right % in each key, around the circle of fifths from C."""
    by = groups(rows, lambda r: ENHARMONIC.get(r["config"].get("key"), r["config"].get("key")))
    keys = [k for k in FIFTHS if len(by.get(k, ())) >= MIN_BAR]
    if len(keys) < 2:
        return None
    return ("degrees · right % by key", chart(keys, [right(by[k]) for k in keys]),
            f"clockwise round the circle of fifths · {MIN_BAR}+ questions a key")


def register_box(rows):
    """Right % by the octave the note sounded in, low to high."""
    by = groups(rows, lambda r: r["meta"].get("midi") and r["meta"]["midi"] // 12 - 1)
    octaves = [o for o in sorted(by) if len(by[o]) >= MIN_BAR]
    if len(octaves) < 2:
        return None
    body = table([("octave", "<", ""), ("asked", ">", "d"), ("", "<", ""), ("right %", ">", ".0f")],
                 [(f"C{o} – B{o}", len(by[o]), hbar(right(by[o]) / 100), right(by[o])) for o in octaves])
    return ("degrees · by register", body, "the octave the asked note sounded in")


def leaps_box(rows):
    """Right % by how far the note was from the one asked before it, and after a hit or a miss."""
    by, after = defaultdict(list), defaultdict(list)
    last = None
    for r in rows:
        if last is not None and last["sid"] == r["sid"] and "midi" in r["meta"] and "midi" in last["meta"]:
            leap = abs(r["meta"]["midi"] - last["meta"]["midi"])
            by[next(name for lo, hi, name in LEAPS if lo <= leap <= hi)].append(r)
            after["the same degree again" if last["truth"] == r["truth"] else "another degree"].append(r)
            after["after a right answer" if last["correct"] == 1 else "after a miss"].append(r)
        last = r
    names = [n for _, _, n in LEAPS if len(by[n]) >= MIN_BAR]
    if len(names) < 2:
        return None
    body = [(n, len(by[n]), hbar(right(by[n]) / 100), right(by[n])) for n in names]
    body += [("", None, "", None)] + [(n, len(after[n]), hbar(right(after[n]) / 100), right(after[n]))
                                       for n in ("the same degree again", "another degree", "after a right answer", "after a miss") if after[n]]
    text = table([("semitones from the note before", "<", ""), ("asked", ">", "d"), ("", "<", ""), ("right %", ">", ".0f")], body)
    return ("degrees · after the note before", text.replace("  ·  ", "     ").replace("   ·", "    "), None)


def hours_box(rows):
    """Each question against the right % of its drill that day, by three hours of the clock."""
    usual = {k: right(v) for k, v in groups(rows, lambda r: (r["exercise"], day(r))).items() if len(v) >= 20}
    by = defaultdict(list)
    for r in rows:
        if (r["exercise"], day(r)) in usual:
            hour = datetime.fromtimestamp((r["started"] + r["ask"]) / 1000).hour // 3 * 3
            by[hour].append(100 * (r["correct"] == 1) - usual[(r["exercise"], day(r))])
    hours = [h for h in sorted(by) if len(by[h]) >= 2 * MIN_BAR]
    if len(hours) < 2:
        return None
    means = {h: sum(by[h]) / len(by[h]) for h in hours}
    most = max(abs(v) for v in means.values())
    body = table([("hour", "<", ""), ("asked", ">", "d"), ("", "<", ""), ("pp", ">", "+.1f")],
                 [(f"{h:02d} – {h + 3:02d}", len(by[h]), sided(means[h], most), means[h]) for h in hours])
    return ("degrees · by hour", body, "a question against the right % of its drill that day (20+ questions), in points")


def melody_box(rows):
    """Melodies note by note: whole, per position, and the ways of being nearly right."""
    rows = [r for r in rows if r["answer"] is not None and len(r["answer"].split()) == len(r["truth"].split())]
    if len(rows) < MIN_ROW:
        return None
    length = Counter(len(r["truth"].split()) for r in rows).most_common(1)[0][0]
    rows = [r for r in rows if len(r["truth"].split()) == length]
    pairs = [(r["truth"].split(), r["answer"].split()) for r in rows]
    n = len(pairs)
    at = [100 * sum(t[i] == a[i] for t, a in pairs) / n for i in range(length)]
    off = Counter(sum(x != y for x, y in zip(t, a)) for t, a in pairs)
    def steps(seq):          # the moves between notes, by degree number: a melody moved up or down whole keeps them
        nums = [int(re.sub(r"\D", "", d)) for d in seq]
        return [q - p for p, q in zip(nums, nums[1:])]
    moved = sum(t != a and steps(t) == steps(a) for t, a in pairs)
    def turns(seq):
        return [(s > 0) - (s < 0) for s in steps(seq)]
    contour = sum(turns(t) == turns(a) for t, a in pairs)
    left = table([("note", "<", ""), ("", "<", ""), ("right %", ">", ".0f")],
                 [(f"{i + 1}{('st', 'nd', 'rd')[i] if i < 3 else 'th'}", hbar(p / 100), p) for i, p in enumerate(at)])
    facts = [("every note right", 100 * off[0] / n), ("one note off", 100 * off[1] / n), ("two or more off", 100 * sum(v for k, v in off.items() if k >= 2) / n),
             ("ups and downs right", 100 * contour / n), ("right shape, wrong place", 100 * moved / n)]
    rightside = table([("of the melodies", "<", ""), ("", "<", ""), ("%", ">", ".0f")], [(f, hbar(p / 100), p) for f, p in facts])
    return (f"melodies · {n} of them, {length} notes each", beside([left, rightside]),
            "ups and downs right = every move in the right direction · right shape, wrong place = the same moves, started on another degree")


CLOUD = 4             # the fragment cloud: lines between two labels of its scale (0, 25 ... 100 %); it is as wide as the terminal
RUN = 3               # notes in a fragment
DOTS = (0x01, 0x02, 0x04, 0x40, 0x08, 0x10, 0x20, 0x80)     # a braille character's dots, left column then right, top down


def count_ticks(at, most, across):
    """The line of labels under a doubling scale: 1, 2, 4, 8 ..."""
    line = [" "] * (across + 4)
    n = 1
    while n <= most:
        line[int(at(n) * across): int(at(n) * across) + len(str(n))] = str(n)
        n *= 2
    return "".join(line).rstrip()


def fragments_box(rows):
    """Every run of three notes inside a melody as a dot: across, how many times it has been heard (each doubling
    the same step); up, how often all three were answered right. A run is its degrees and the leaps between them,
    in semitones, whatever the key and the octave: 5 up a fourth to 1 and 5 down a fifth to 1 are two runs.
    A run heard n times is set at random between n and n + 1, so the ones heard once or twice fill a band
    rather than stack in a line."""
    import math
    import random
    heard, right_ = Counter(), Counter()
    for r in rows:
        if r["answer"] is None:
            continue
        truth, answer = r["truth"].split(), r["answer"].split()
        ok = [i < len(answer) and answer[i] == t for i, t in enumerate(truth)]     # note for note; a note not given is wrong
        midis = r["meta"]["midis"]
        for i in range(len(truth) - RUN + 1):
            run = " ".join(truth[i:i + RUN]) + " " + " ".join(f"{q - p:+d}" for p, q in zip(midis[i:], midis[i + 1:i + RUN]))
            heard[run] += 1
            right_[run] += all(ok[i:i + RUN])
    if len(heard) < 50:
        return None
    across, apart = columns() - 12, CLOUD            # the box fills the terminal: its edges, its padding and the scale take 12
    down = 4 * apart + 1                             # a line for 100 %, then `apart` lines to each label below it
    span = math.log2(max(heard.values()) + 1)
    at = lambda n: math.log2(n) / span                # where a count sits, 0 at the left edge to 1
    lit = set()
    for run, n in heard.items():
        x = int(at(n + random.Random(run).random()) * across * 2)
        lit.add((min(x, across * 2 - 1), round((1 - right_[run] / n) * 4 * apart * 4 + 1.5)))      # a labelled share is the middle of its line
    labels = {k * apart: 100 - 25 * k for k in range(5)}
    lines = []
    for r in range(down):
        cells = (sum(DOTS[dx * 4 + dy] for dx in (0, 1) for dy in range(4) if (2 * c + dx, 4 * r + dy) in lit) for c in range(across))
        lines.append((f"{labels[r]:>4} │" if r in labels else "     │") + "".join(chr(0x2800 + b) if b else " " for b in cells))
    lines += ["     └" + "─" * across, "      " + count_ticks(at, max(heard.values()), across)]
    return (f"melodies · {len(heard)} runs of {RUN} notes · times heard against % right", "\n".join(lines))


def chords_box(rows):
    if len(rows) < MIN_ROW:
        return None
    return ("chords", confusions(rows, "chords", "quality"), "s = the median seconds to a right answer · taken for = the wrong answer given most")


def streaks(days):
    """(longest run of consecutive days, the run ending on the last day)."""
    best = run = 1
    for p, q in zip(days, days[1:]):
        run = run + 1 if (q - p).days == 1 else 1
        best = max(best, run)
    return best, run


def records(con, rows, single):
    """One line per fact about the record as a whole."""
    days = sorted({day(r) for r in rows})
    out = [("first session", str(days[0]), f"last {days[-1]}")]
    best, now = streaks(days)
    out.append(("days in a row", str(best), "and counting" if now == best and (date.today() - days[-1]).days <= 1 else f"{now} at the end"))
    by_day = groups(rows, day)
    d = max(by_day, key=lambda d: minutes(by_day[d]))
    out.append(("longest day", f"{minutes(by_day[d]):.0f} min", f"{len(by_day[d])} questions · {d}"))
    if single:
        run = best_run = 0
        for r in single:
            run = run + 1 if r["correct"] == 1 else 0
            best_run = max(best_run, run)
        out.append(("right in a row", str(best_run), "degrees, across sessions"))
        sessions = [rs for rs in groups(single, lambda r: r["sid"]).values() if len(rs) >= 20]
        if sessions:
            s = max(sessions, key=right)
            out.append(("best session", f"{right(s):.0f}%", f"{s[0]['exercise'].split(' · ')[0]} · {len(s)} questions · {day(s[0])}"))
        quick = min((r for r in single if r["correct"] == 1 and r["latency"]), key=lambda r: r["latency"], default=None)
        if quick:
            out.append(("fastest right answer", f"{quick['latency'] / 1000:.2f} s", f"{quick['truth']} in {quick['config'].get('key')} · {day(quick)}"))
        asked = Counter(r["truth"] for r in single).most_common(1)[0]
        out.append(("most asked degree", asked[0], f"{asked[1]} times"))
    silent = sum(r["answer"] is None for r in rows)
    out.append(("questions left unanswered", str(silent), f"one in {len(rows) / silent:.0f}" if silent else ""))
    presses = con.execute("SELECT count(*) FROM keystrokes").fetchone()[0]
    out.append(("keys pressed", f"{presses:,}".replace(",", " "), ""))
    return ("records", table([("", "<", ""), ("", ">", ""), ("", "<", "")], out).split("\n", 1)[1], None)


def journal_box(con):
    """The practice wall of `cordelia journal`, its latest weeks: every session, whatever the filters."""
    from datetime import timedelta
    from . import journal            # journal imports stats, as this does
    by_day = journal.minutes_by_day(con)
    if not by_day:
        return None
    first = min(by_day) - timedelta(days=min(by_day).weekday())
    last = date.today() - timedelta(days=date.today().weekday())
    weeks = [first + timedelta(weeks=i) for i in range((last - first).days // 7 + 1)][-JOURNAL_WEEKS:]
    body, note = journal.wall(by_day, weeks).rsplit("\n\n", 1)
    return (f"journal · {sum(by_day.values()):.0f} min", body, note)


def report(con, key=None, tag=None):
    rows = load(con, None, None, key, tag)
    if not rows:
        print("no sessions recorded yet" + (" with those filters" if (key or tag) else ""))
        return
    single = [r for r in rows if r["mode"] in SINGLE]
    days = len({day(r) for r in rows})
    title = (f"cordelia · {days} day{'s' if days != 1 else ''} · {minutes(rows) / 60:.1f} h listening · "
             f"{len({r['sid'] for r in rows})} sessions · {len(rows)} questions")
    parts = [drills_box(rows, title), records(con, rows, single), journal_box(con)]
    if len(single) >= MIN_ROW:
        parts += [("degrees · every list", confusions(single, "degrees", "degree"),
                   "the degrees and focus drills together · s = the median seconds to a right answer · taken for = the wrong answer given most"),
                  matrix_box(single, f"degrees · every question, {len(single)}"), mixups(single, "degrees"), speed_box(single), keys_box(single), register_box(single), leaps_box(single), hours_box(single)]
    chords = [r for r in rows if r["mode"] == "chords"]
    melodies = [r for r in rows if r["mode"] == "melody"]
    parts += [melody_box(melodies), chords_box(chords), matrix_box(chords, f"chords · every question, {len(chords)}"), fragments_box(melodies)]
    print("\n" + soft(grid([p for p in parts if p])) + "\n")
