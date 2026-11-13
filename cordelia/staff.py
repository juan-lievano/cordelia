"""A few bars of a grand staff drawn in characters: a row per line or space, notes as ● (○
when held), each note's own ♭ or ♯ beside it (no key signature), ledger lines as needed, the
clefs as the letter on their line (G on treble G, F on bass F). Under each column its name.

A note is spelt from its degree (the third of D is some F, whatever the flat), so the letters
follow the scale. Positions count diatonic steps: 7 * octave + letter, C4 = 28.
"""

LETTERS = "CDEFGAB"
NATURAL = (0, 2, 4, 5, 7, 9, 11)
TREBLE = (30, 32, 34, 36, 38)      # E4 G4 B4 D5 F5
BASS = (18, 20, 22, 24, 26)        # G2 B2 D3 F3 A3
MIDDLE_C = 28
CLEF = {32: "G", 24: "F"}
ACCIDENTAL = {-2: "𝄫", -1: "♭", 0: "", 1: "♯", 2: "𝄪"}
CELL = 4                           # columns per note: space, accidental, head, space
MARGIN = 3
HEAD, HELD = "●", "○"
LIT = {HEAD: "", HELD: ""}     # the sounding note, coloured once the box is drawn
COLOUR = "\x1b[1;33m"


def spell(key, label, midi):
    """(position, accidental) of degree `label` sounding as `midi` in `key` ('F#', 'Eb')."""
    letter = (LETTERS.index(key[0]) + int(label.lstrip("b#")) - 1) % 7
    acc = (midi - NATURAL[letter] + 6) % 12 - 6
    return 7 * ((midi - acc - NATURAL[letter]) // 12 - 1) + letter, acc


def rows(key, columns):
    """(top, bottom) positions covering both staves and every note in `columns`."""
    ps = [spell(key, l, m)[0] for notes, _, _ in columns for l, m in notes]
    return max([TREBLE[-1], *ps]), min([BASS[0], *ps])


def draw(key, columns, top, bottom, lit=None, named=True, cells=16):
    """The staff as lines. `columns`: [(notes [(label, midi)], held, name)], `lit` the index
    sounding now, `named` whether the names are shown yet (else ·). `cells` columns wide, always:
    a longer excerpt scrolls to keep `lit` in."""
    fit = cells
    start = 0 if len(columns) <= fit or lit is None else min(max(0, lit - fit // 2), len(columns) - fit)
    shown = columns[start:start + fit]
    spelt = [{p: a for p, a in (spell(key, l, m) for l, m in notes)} for notes, _, _ in shown]
    out = []
    for p in range(top, bottom - 1, -1):
        line = p in TREBLE or p in BASS
        fill = "─" if line else " "
        row = CLEF.get(p, " ") + fill * (MARGIN - 1)
        for i, (heads, (_, held, _)) in enumerate(zip(spelt, shown)):
            cell = [fill] * CELL
            if p % 2 == 0 and not line and (p > TREBLE[-1] and max(heads) >= p or p < BASS[0] and min(heads) <= p
                                            or p == MIDDLE_C and p in heads):
                cell[1:] = "───"
            if p in heads:
                head = HELD if held else HEAD
                cell[2] = LIT[head] if start + i == lit else head
                if heads[p]:
                    cell[1] = ACCIDENTAL[heads[p]]
            row += "".join(cell)
        out.append(row + fill * (CELL * (cells - len(shown)) + 1))
    names = " " * MARGIN + "".join((name if named else "·").center(CELL) for _, _, name in shown)
    width = MARGIN + cells * CELL + 1
    return out + ["", names.ljust(width)]


def colour(text):
    """The lit note in colour: after the box is drawn, since the box counts characters."""
    for plain, lit in LIT.items():
        text = text.replace(lit, COLOUR + plain + "\x1b[0m")
    return text
