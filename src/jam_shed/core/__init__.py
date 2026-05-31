"""
Core package - Core music theory, brain, and session logic.
"""

from typing import TYPE_CHECKING

# Import only constants to avoid circular dependencies
# Other imports should be done explicitly by users
from jam_shed.core.constants import (
    CLOSED_HIHAT,
    CRASH,
    DEFAULT_BEATS_PER_BAR,
    DEFAULT_BPM,
    KICK,
    OPEN_HIHAT,
    RIDE,
    SNARE,
    DrumNote,
    MIDICommand,
)

if TYPE_CHECKING:
    from jam_shed.core.brain import RhythmicBrain
    from jam_shed.core.session import JamSession
    from jam_shed.core.theory import MusicTheory


# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name == "RhythmicBrain":
        from jam_shed.core.brain import RhythmicBrain

        return RhythmicBrain
    elif name == "JamSession":
        from jam_shed.core.session import JamSession

        return JamSession
    elif name == "MusicTheory":
        from jam_shed.core.theory import MusicTheory

        return MusicTheory
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    # Core classes (lazy-loaded)
    "RhythmicBrain",
    "JamSession",
    "MusicTheory",
    # Constants
    "MIDICommand",
    "DrumNote",
    "KICK",
    "SNARE",
    "CLOSED_HIHAT",
    "OPEN_HIHAT",
    "RIDE",
    "CRASH",
    "DEFAULT_BPM",
    "DEFAULT_BEATS_PER_BAR",
]
