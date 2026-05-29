"""
Agent factory for creating virtual instrumentalists with consistent configuration.
"""
from typing import Dict, Type
from jam_shed.agents.base import VirtualInstrumentalist, PlayingStyle
from jam_shed.agents.bassist import VirtualBassist
from jam_shed.agents.lead_guitarist import VirtualLeadGuitarist
from jam_shed.agents.rhythm_guitarist import VirtualRhythmGuitarist
from jam_shed.agents.drummer import VirtualDrummer
from jam_shed.agents.keyboardist import VirtualKeyboardist
from jam_shed.midi.engine import MIDIEngine
from jam_shed.core.brain import RhythmicBrain


# Agent Registry: maps agent type to (Class, default_channel, display_name)
AGENT_REGISTRY: Dict[str, tuple[Type[VirtualInstrumentalist], int, str]] = {
    "drummer": (VirtualDrummer, 9, "Drummer"),  # Channel 10 (MIDI drums)
    "keyboardist": (VirtualKeyboardist, 4, "Keyboardist"),
    "lead_guitar": (VirtualLeadGuitarist, 1, "Lead Guitar"),
    "rhythm_guitar": (VirtualRhythmGuitarist, 2, "Rhythm Guitar"),
    "bassist": (VirtualBassist, 3, "Bass"),
}


class AgentFactory:
    """Factory for creating virtual instrumentalist agents."""

    @staticmethod
    def create_agent(
        agent_type: str,
        midi_engine: MIDIEngine,
        brain: RhythmicBrain,
        style: PlayingStyle = PlayingStyle.ROCK,
        name: str = None,
        channel: int = None
    ) -> VirtualInstrumentalist:
        """
        Create a virtual instrumentalist agent.

        Args:
            agent_type: Type of agent ("drummer", "keyboardist", "lead_guitar", etc.)
            midi_engine: MIDI engine instance
            brain: Rhythmic brain instance
            style: Musical style for the agent
            name: Optional custom name (uses default if None)
            channel: Optional custom MIDI channel (uses default if None)

        Returns:
            Configured VirtualInstrumentalist instance

        Raises:
            ValueError: If agent_type is not registered
        """
        if agent_type not in AGENT_REGISTRY:
            raise ValueError(f"Unknown agent type: {agent_type}. Available: {list(AGENT_REGISTRY.keys())}")

        agent_class, default_channel, default_name = AGENT_REGISTRY[agent_type]

        final_name = name if name is not None else default_name
        final_channel = channel if channel is not None else default_channel

        return agent_class(
            name=final_name,
            midi_engine=midi_engine,
            brain=brain,
            channel=final_channel,
            style=style
        )

    @staticmethod
    def get_available_agents() -> Dict[str, str]:
        """
        Get map of available agent types to their display names.

        Returns:
            Dictionary mapping agent_type to display_name
        """
        return {agent_type: info[2] for agent_type, info in AGENT_REGISTRY.items()}

    @staticmethod
    def create_band(
        midi_engine: MIDIEngine,
        brain: RhythmicBrain,
        style: PlayingStyle = PlayingStyle.ROCK,
        include: list = None
    ) -> list[VirtualInstrumentalist]:
        """
        Create a full band of agents.

        Args:
            midi_engine: MIDI engine instance
            brain: Rhythmic brain instance
            style: Musical style for all agents
            include: Optional list of agent types to include (default: all)

        Returns:
            List of configured VirtualInstrumentalist instances
        """
        agent_types = include if include is not None else list(AGENT_REGISTRY.keys())

        band = []
        for agent_type in agent_types:
            if agent_type in AGENT_REGISTRY:
                agent = AgentFactory.create_agent(agent_type, midi_engine, brain, style)
                band.append(agent)

        return band
