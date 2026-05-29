"""
Virtual agents package - AI musicians with style-based playing.
"""
from jam_shed.agents.base import (
    VirtualInstrumentalist,
    PlayingStyle,
    AgentMode,
)
from jam_shed.agents.bassist import VirtualBassist
from jam_shed.agents.drummer import VirtualDrummer
from jam_shed.agents.keyboardist import VirtualKeyboardist
from jam_shed.agents.lead_guitarist import VirtualLeadGuitarist
from jam_shed.agents.rhythm_guitarist import VirtualRhythmGuitarist
from jam_shed.agents.factory import AgentFactory, AGENT_REGISTRY

__all__ = [
    # Base classes and enums
    "VirtualInstrumentalist",
    "PlayingStyle",
    "AgentMode",
    # Agent classes
    "VirtualBassist",
    "VirtualDrummer",
    "VirtualKeyboardist",
    "VirtualLeadGuitarist",
    "VirtualRhythmGuitarist",
    # Factory
    "AgentFactory",
    "AGENT_REGISTRY",
]
