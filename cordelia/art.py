"""A violin drawn in braille dots, slanted, for the top of a session. Built from curves in
body lengths (the tail at y=0, the neck joint at y=1), then turned and plotted at two by
four dots a character, which are about square in a terminal cell."""

import math

# half the body's width along its length: lower bout, the waist's C-bouts, upper bout
PROFILE = [(0.0, 0.0), (0.015, 0.12), (0.06, 0.22), (0.15, 0.28), (0.25, 0.29), (0.35, 0.265),
           (0.41, 0.215), (0.46, 0.165), (0.53, 0.155), (0.6, 0.17), (0.65, 0.205), (0.74, 0.235),
           (0.84, 0.225), (0.92, 0.18), (0.975, 0.1), (1.0, 0.0)]   # a 35.5 cm body: bouts 20.5, 11, 16.5 cm


def half_width(y):
    for (y0, w0), (y1, w1) in zip(PROFILE, PROFILE[1:]):
        if y0 <= y <= y1:
            t = (y - y0) / (y1 - y0)
            return w0 + (w1 - w0) * (3 * t * t - 2 * t * t * t)    # eased, so the outline has no kinks
    return 0.0


def strokes():
    """The violin as polylines of (x, y) points."""
    n = 400
    ys = [0.5 - 0.5 * math.cos(math.pi * i / n) for i in range(n + 1)]   # dense at the rounded ends
    yield [(half_width(y), y) for y in ys]
    yield [(-half_width(y), y) for y in ys]
    for side in (-1, 1):                                       # the f-holes: an S with a dot at each end
        f = [(side * (0.115 + 0.025 * math.sin(math.pi * (t - 0.5))), 0.33 + 0.2 * t) for t in [i / 40 for i in range(41)]]
        yield f
        for (cx, cy) in (f[0], f[-1]):
            yield [(cx + 0.012 * math.cos(a / 8 * math.tau), cy + 0.012 * math.sin(a / 8 * math.tau)) for a in range(9)]
    yield [(-0.1, 0.43), (0.1, 0.43)]                        # the bridge
    yield [(-0.05, 0.03), (-0.035, 0.2), (0.035, 0.2), (0.05, 0.03), (-0.05, 0.03)]   # the tailpiece
    yield [(-0.032, 0.62), (-0.025, 1.45), (0.025, 1.45), (0.032, 0.62), (-0.032, 0.62)]   # the fingerboard
    yield [(-0.025, 1.45), (-0.03, 1.6)]                       # the pegbox
    yield [(0.025, 1.45), (0.03, 1.6)]
    for side in (-1, 1):                                       # its pegs
        for y in (1.49, 1.555):
            yield [(side * 0.03, y), (side * 0.075, y + 0.01)]
    spiral = []                                                # the scroll
    for i in range(121):
        a = i / 120 * 2.5 * math.tau
        r = 0.055 * (1 - i / 150)
        spiral.append((r * math.sin(a), 1.655 - r * math.cos(a)))
    yield spiral


def braille(rows, angle_deg=-50):
    """The violin turned by `angle_deg` (from upright, clockwise), `rows` lines tall, as braille."""
    c, s = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    lines = [[(x * c - y * s, x * s + y * c) for x, y in line] for line in strokes()]
    pts = [p for l in lines for p in l]
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    scale = (rows * 4 - 1) / (y1 - y0)
    width = math.ceil(((x1 - x0) * scale + 1) / 2)
    dots = set()
    for line in lines:
        for (ax, ay), (bx, by) in zip(line, line[1:]):
            steps = max(1, int(math.hypot(bx - ax, by - ay) * scale * 2))
            for k in range(steps + 1):
                x, y = ax + (bx - ax) * k / steps, ay + (by - ay) * k / steps
                dots.add((round((x - x0) * scale), round((y1 - y) * scale)))
    bit = {(0, 0): 0, (0, 1): 1, (0, 2): 2, (1, 0): 3, (1, 1): 4, (1, 2): 5, (0, 3): 6, (1, 3): 7}
    grid = [[0] * width for _ in range(rows)]
    for px, py in dots:
        grid[py // 4][px // 2] |= 1 << bit[(px % 2, py % 4)]
    return "\n".join("".join(chr(0x2800 + b) for b in row).rstrip("⠀") for row in grid)

