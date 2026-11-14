"""A few bars of a grand staff drawn in characters, half as tall as a row per line and space:
a row is a line (or a ledger line's place), and a note in a space is the lower half of one row
over the upper half of the next (▄ over ▀), so a head is exactly a space tall wherever it sits.
A head is two columns wide, three when held; in a chord a note a second or third above another
steps a column right, so the heads stay apart. The clefs are the letter on their line (G on
treble G, F on bass F). The key signature is not drawn: the caller names the key and mode, and
a note has a ♭ ♯ or ♮ beside it only where it leaves that key. Under each column its name.

A note is spelt from its degree (the third of D is some F, whatever the flat), so the letters
follow the scale. Positions count diatonic steps: 7 * octave + letter, C4 = 28. Lines are the
even positions, row p // 2; a note at p fills the half rows p and p - 1 (row r's upper half
is 2r, its lower 2r - 1).
"""

LETTERS = "CDEFGAB"
NATURAL = (0, 2, 4, 5, 7, 9, 11)
MINOR = (0, 2, 3, 5, 7, 8, 10)
TREBLE = (30, 32, 34, 36, 38)      # E4 G4 B4 D5 F5
BASS = (18, 20, 22, 24, 26)        # G2 B2 D3 F3 A3
MIDDLE_C = 28
CLEF = {32: "G", 24: "F"}
ACCIDENTAL = {-2: "𝄫", -1: "♭", 0: "♮", 1: "♯", 2: "𝄪"}
CELL = 5                           # columns per note: space, accidental, the head's two, one to step into
MARGIN = 3
BLOCK = {(True, True): "█", (True, False): "▀", (False, True): "▄"}     # (upper half, lower half)
LIT = {"█": "", "▀": "", "▄": ""}     # the sounding note, coloured once the box is drawn
COLOUR = "\x1b[1;33m"


def spell(key, label, midi):
    """(position, accidental) of degree `label` sounding as `midi` in `key` ('F#', 'Eb')."""
    letter = (LETTERS.index(key[0]) + int(label.lstrip("b#")) - 1) % 7
    acc = (midi - NATURAL[letter] + 6) % 12 - 6
    return 7 * ((midi - acc - NATURAL[letter]) // 12 - 1) + letter, acc


def signature(key, minor):
    """{letter: accidental} of the key's own scale."""
    first = LETTERS.index(key[0])
    tonic = NATURAL[first] + {"#": 1, "b": -1}.get(key[1:], 0)
    return {(first + i) % 7: (tonic + s - NATURAL[(first + i) % 7] + 6) % 12 - 6
            for i, s in enumerate(MINOR if minor else NATURAL)}


def rows(key, columns):
    """(top, bottom) rows covering both staves and every note in `columns`."""
    ps = [spell(key, l, m)[0] for notes, _, _ in columns for l, m in notes]
    return (max([TREBLE[-1], *ps]) + 1) // 2, min([BASS[0], *ps]) // 2


def draw(key, columns, top, bottom, lit=None, named=True, cells=16, minor=True):
    """The staff as lines. `columns`: [(notes [(label, midi)], held, name)], `lit` the index
    sounding now, `named` whether the names are shown yet (else ·). `cells` columns wide, always:
    a longer excerpt scrolls to keep `lit` in."""
    fit = cells
    start = 0 if len(columns) <= fit or lit is None else min(max(0, lit - fit // 2), len(columns) - fit)
    shown = columns[start:start + fit]
    own = signature(key, minor)
    width = MARGIN + cells * CELL + 1
    halves, marks, ledgers = {}, {}, set()          # (half row, x): lit; (row, x): accidental; (row, x)
    for i, (notes, held, _) in enumerate(shown):
        x, last = MARGIN + i * CELL, None           # last: the head below, if it kept its column
        heads = sorted(spell(key, l, m) for l, m in notes)
        for p, acc in heads:
            step = last is not None and p - last <= 2
            last = None if step else p
            for dx in range(2 + step, 4 + step + bool(held)):
                halves[p, x + dx] = halves[p - 1, x + dx] = start + i == lit
            if acc != own[p % 7]:
                marks[(p + 1) // 2, x + 1] = ACCIDENTAL[acc]
        for r in range(bottom, top + 1):
            p = 2 * r
            if p > TREBLE[-1] and heads[-1][0] >= p or p < BASS[0] and heads[0][0] <= p or p == MIDDLE_C and any(q == p for q, _ in heads):
                ledgers.update((r, x + dx) for dx in range(1, CELL))
    out = []
    for r in range(top, bottom - 1, -1):
        line = 2 * r in TREBLE or 2 * r in BASS
        row = [CLEF.get(2 * r, " ")] + ["─" if line or (r, x) in ledgers else " " for x in range(1, width)]
        for x in range(MARGIN, width):
            block = BLOCK.get(((2 * r, x) in halves, (2 * r - 1, x) in halves))
            if block:
                row[x] = LIT[block] if halves.get((2 * r, x)) or halves.get((2 * r - 1, x)) else block
            elif (r, x) in marks:
                row[x] = marks[r, x]
        out.append("".join(row))
    under = lambda n: (" " * (2 if len(n) <= 2 else 1) + n).ljust(CELL)    # beneath the head's two columns
    names = " " * MARGIN + "".join(under(name if named else "·") for _, _, name in shown)
    return out + ["", names.ljust(width)]


def colour(text):
    """The lit note in colour: after the box is drawn, since the box counts characters."""
    for plain, lit in LIT.items():
        text = text.replace(lit, COLOUR + plain + "\x1b[0m")
    return text
