"""Play a WAV and write down every key pressed, with its time.

The collector knows nothing about modes or right answers. It gets the
question onsets only so it can show which question is sounding, and it
hands the status line the keys pressed since it began, so you can see they
registered. It never judges.
"""

import select
import subprocess
import sys
import termios
import time
import tty

ESC = "\x1b"


def collect(wav_path, ask_ms, status=None, show=None, reveal_ms=None):
    """Returns (keystrokes, outcome, stopped_at_ms).

    `status(current, n, typed, revealed)` is the text for the question on now and the keys typed
    for it, `revealed` once its `reveal_ms` moment has passed (the answer has been said),
    `show(text)` puts it on the screen (default: a line of its own, after "question ").
    keystrokes: [(t_ms, key)] with t_ms counted from the moment playback was
    started. outcome is 'completed' when the audio ran to its end, 'stopped'
    on Esc, 'interrupted' on Ctrl+C (the caller saves it as stopped, then
    dies of the interrupt so the shell ends a `;` chain or loop).
    """
    if not sys.stdin.isatty():
        raise SystemExit("the collector needs a terminal to read keys from")
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    keystrokes = []
    outcome = "completed"
    try:
        player = subprocess.Popen(["afplay", wav_path])
    except FileNotFoundError:
        raise SystemExit("afplay not found: playback needs macOS")
    t0 = time.monotonic_ns()

    def now_ms():
        return (time.monotonic_ns() - t0) // 1_000_000

    shown, shown_revealed = -1, False
    typed = []
    dirty = True
    try:
        tty.setcbreak(fd)
        sys.stdout.write("\x1b[?25l")   # hide the cursor
        while True:
            if player.poll() is not None:
                break
            t = now_ms()
            current = sum(1 for a in ask_ms if a <= t)
            revealed = bool(reveal_ms) and current > 0 and t >= reveal_ms[current - 1]
            if current != shown:
                typed, dirty = [], True             # a new question: the echoed keys reset
            if revealed != shown_revealed:
                dirty = True
            if dirty:
                shown, shown_revealed, dirty = current, revealed, False
                line = status(current, len(ask_ms), typed, revealed) if status else f"{current} / {len(ask_ms)}"
                if show:
                    show(line)
                else:
                    sys.stdout.write("\r\x1b[Kquestion " + "   ".join(l for l in line.split("\n") if l))
                sys.stdout.flush()
            ready, _, _ = select.select([sys.stdin], [], [], 0.05)
            if not ready:
                continue
            t = now_ms()
            key = _read_key(fd)
            if key == "esc":
                outcome = "stopped"
                break
            keystrokes.append((t, key))
            typed.append(key)
            dirty = True
    except KeyboardInterrupt:
        outcome = "interrupted"
    finally:
        stopped_at = now_ms()
        if player.poll() is None:
            player.terminate()
            player.wait()
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write("\x1b[?25h\r\x1b[K")
        sys.stdout.flush()
    return keystrokes, outcome, stopped_at


def _read_key(fd):
    """One key as a name: '4', 'space', 'esc', 'ctrl+c', 'enter', 'other'."""
    b = sys.stdin.read(1)
    if b == ESC:
        # a lone Esc, or the start of an arrow-key sequence?
        ready, _, _ = select.select([sys.stdin], [], [], 0.03)
        if not ready:
            return "esc"
        while ready:
            sys.stdin.read(1)
            ready, _, _ = select.select([sys.stdin], [], [], 0.01)
        return "other"
    if b == " ":
        return "space"
    if b in ("\r", "\n"):
        return "enter"
    if b == "\x7f":
        return "backspace"
    if ord(b) < 32:
        return f"ctrl+{chr(ord(b) + 96)}"
    return b
