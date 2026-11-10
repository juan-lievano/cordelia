"""The practice wall: a column per week, a row per weekday, each cell a block
of dots, one for every MINUTES minutes practised that day in every mode
together. Blank is a day off.
"""

import shutil
import sys
from datetime import date, datetime, timedelta

from .stats import BIG, CELL, PAD, box, centred, scatter

MINUTES = 2           # a dot; a cell (the confusion matrix's big one) holds 64, so it is full at 128 minutes
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
LABEL = 5             # the weekday column, "Mon  "
GAP = 2               # columns between two weeks


def minutes_by_day(con):
    """Date -> minutes of finished sessions started that day."""
    out = {}
    sql = "SELECT started_at_ms, stopped_at_ms FROM sessions WHERE outcome IN ('completed', 'stopped')"
    for started, stopped in con.execute(sql):
        d = datetime.fromtimestamp(started / 1000).date()
        out[d] = out.get(d, 0) + (stopped or 0) / 6e4
    return out


def cell(minutes, day):
    """A day's lines: its dots scattered, the draw fixed by the date; any practice at all lights one."""
    full = 8 * CELL * BIG * MINUTES
    return scatter(min(minutes, full), full, BIG, str(day)) if minutes >= 1 else [" " * CELL] * BIG


def wall(by_day, weeks):
    """Month names over the weeks they start in, then BIG lines per weekday."""
    step = CELL + GAP
    months = [" "] * (step * len(weeks))
    for i, w in enumerate(weeks):
        if i == 0 or w.month != weeks[i - 1].month:
            months[step * i:step * i + 3] = w.strftime("%b")
    lines = [" " * LABEL + "".join(months).rstrip()]
    for d, name in enumerate(DAYS):
        cells = [cell(by_day.get(w + timedelta(d), 0), w + timedelta(d)) for w in weeks]
        lines += [((name if r == 0 else "").ljust(LABEL) + (" " * GAP).join(c[r] for c in cells)).rstrip() for r in range(BIG)]
    return "\n".join([*lines, "", f"a dot is {MINUTES} min, a full cell {8 * CELL * BIG * MINUTES} or more"])


def show(con):
    by_day = minutes_by_day(con)
    if not by_day:
        print("no sessions recorded yet")
        return
    first = min(by_day) - timedelta(days=min(by_day).weekday())
    last = date.today() - timedelta(days=date.today().weekday())
    weeks = [first + timedelta(weeks=i) for i in range((last - first).days // 7 + 1)]
    room = (shutil.get_terminal_size().columns - 2 - 2 * PAD - LABEL + GAP) // (CELL + GAP) if sys.stdout.isatty() else len(weeks)
    weeks = weeks[-max(1, room):]                        # the oldest weeks scroll off the left
    title = f"journal · {sum(by_day.values()):.0f} min since {min(by_day)}"
    print("\n" + centred(box(title, wall(by_day, weeks))) + "\n")
