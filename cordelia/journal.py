"""The practice wall: a column per week, a row per weekday, each cell shaded
by the minutes practised that day in every mode together. Blank is a day off.
"""

import shutil
import sys
from datetime import date, datetime, timedelta

from .stats import PAD, box, centred

SHADES = ((60, "█"), (30, "▓"), (15, "▒"), (0, "░"))   # (at least this many minutes, the cell)
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
LABEL = 4             # the weekday column, "Mon "
CELL = 2              # a shade and a gap, so a cell is about square


def minutes_by_day(con):
    """Date -> minutes of finished sessions started that day."""
    out = {}
    sql = "SELECT started_at_ms, stopped_at_ms FROM sessions WHERE outcome IN ('completed', 'stopped')"
    for started, stopped in con.execute(sql):
        d = datetime.fromtimestamp(started / 1000).date()
        out[d] = out.get(d, 0) + (stopped or 0) / 6e4
    return out


def cell(minutes):
    if minutes < 1:
        return " " * CELL
    return next(shade for floor, shade in SHADES if minutes >= floor) + " " * (CELL - 1)


def wall(by_day, weeks):
    """Month names over the weeks they start in (a name is three characters over
    two-character weeks, so a first month with one week showing goes unnamed
    rather than run into the next), then a line per weekday."""
    months = [" "] * (CELL * len(weeks) + 3)
    starts = [i for i, w in enumerate(weeks) if i == 0 or w.month != weeks[i - 1].month] + [len(weeks)]
    end = 0
    for i, j in zip(starts, starts[1:]):
        if CELL * i >= end and (i or j - i >= 2):
            months[CELL * i:CELL * i + 3] = weeks[i].strftime("%b")
            end = CELL * i + 3
    lines = [" " * LABEL + "".join(months).rstrip()]
    for d, name in enumerate(DAYS):
        lines.append(name.ljust(LABEL) + "".join(cell(by_day.get(w + timedelta(d), 0)) for w in weeks).rstrip())
    legend = "   ".join(f"{shade} {floor}+" if floor else f"{shade} <{SHADES[-2][0]}" for floor, shade in reversed(SHADES))
    return "\n".join([*lines, "", " " * LABEL + legend + " min"])


def show(con):
    by_day = minutes_by_day(con)
    if not by_day:
        print("no sessions recorded yet")
        return
    first = min(by_day) - timedelta(days=min(by_day).weekday())
    last = date.today() - timedelta(days=date.today().weekday())
    weeks = [first + timedelta(weeks=i) for i in range((last - first).days // 7 + 1)]
    room = (shutil.get_terminal_size().columns - 2 - 2 * PAD - LABEL) // CELL if sys.stdout.isatty() else len(weeks)
    weeks = weeks[-max(1, room):]                        # the oldest weeks scroll off the left
    title = f"journal · {sum(by_day.values()):.0f} min since {min(by_day)}"
    print("\n" + centred(box(title, wall(by_day, weeks))) + "\n")
