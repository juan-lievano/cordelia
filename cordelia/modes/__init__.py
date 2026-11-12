from . import chords, degrees, melody

MODES = {degrees.NAME: degrees, melody.NAME: melody, chords.NAME: chords}
# A session's mode -> the module that knows its questions: `focus` sessions are degrees
# sessions with a focus in their config (`cordelia focus`), stored under a name of their own.
DRILLS = {**MODES, "focus": degrees}
