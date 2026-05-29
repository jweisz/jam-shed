"""
Jam Room - AI Jam Session Application

A virtual band where you can jam with AI musicians
that learn and respond to your playing in real-time.
"""
from jam_shed.agents import (
    VirtualInstrumentalist,
    PlayingStyle,
    AgentMode,
    VirtualBassist,
    VirtualDrummer,
    VirtualKeyboardist,
    VirtualLeadGuitarist,
    VirtualRhythmGuitarist,
    AgentFactory,
)
from jam_shed.midi import MIDIEngine, MIDIMessage
from jam_shed.core import (
    RhythmicBrain,
    JamSession,
    MusicTheory,
    DEFAULT_BPM,
)
from jam_shed.tui import JamShedApp

__version__ = "0.1.0"

__all__ = [
    # Agents
    "VirtualInstrumentalist",
    "PlayingStyle",
    "AgentMode",
    "VirtualBassist",
    "VirtualDrummer",
    "VirtualKeyboardist",
    "VirtualLeadGuitarist",
    "VirtualRhythmGuitarist",
    "AgentFactory",
    # MIDI
    "MIDIEngine",
    "MIDIMessage",
    # Core
    "RhythmicBrain",
    "JamSession",
    "MusicTheory",
    "DEFAULT_BPM",
    # TUI
    "JamShedApp",
]
