"""
Virtual agents package - AI musicians with style-based playing.
"""

from jam_shed.agents.base import (
    AgentMode,
    PlayingStyle,
    VirtualInstrumentalist,
)
from jam_shed.agents.bassist import VirtualBassist
from jam_shed.agents.drummer import VirtualDrummer
from jam_shed.agents.factory import AGENT_REGISTRY, AgentFactory
from jam_shed.agents.keyboardist import VirtualKeyboardist
from jam_shed.agents.lead_guitarist import VirtualLeadGuitarist
from jam_shed.agents.rhythm_guitarist import VirtualRhythmGuitarist

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
