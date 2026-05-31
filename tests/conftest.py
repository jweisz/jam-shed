"""
Test configuration for jam-shed.
"""

import pytest
from mock_midi import MockMIDIEngine

from jam_shed.agents.bassist import VirtualBassist
from jam_shed.agents.drummer import VirtualDrummer
from jam_shed.core.brain import RhythmicBrain
from jam_shed.core.session import JamSession


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment."""
    # Future: Mock MIDI devices, audio, etc.
    pass


@pytest.fixture
def mock_midi():
    """Provide a mock MIDI engine for testing."""
    engine = MockMIDIEngine()
    engine.open_input("Mock Input")
    engine.open_output("Mock Output")
    yield engine
    engine.reset()


@pytest.fixture
def mock_midi_brain(mock_midi):
    """Provide a brain with mock MIDI."""
    return RhythmicBrain()


@pytest.fixture
def mock_midi_session(mock_midi, mock_midi_brain):
    """
    Provide a session with drummer and bassist using mock MIDI.

    This fixture is useful for integration tests that verify
    agent interactions without requiring real MIDI hardware.
    """
    agents = [
        VirtualDrummer("Drummer", mock_midi, mock_midi_brain, channel=9),
        VirtualBassist("Bass", mock_midi, mock_midi_brain, channel=3),
    ]
    session = JamSession(agents=agents, brain=mock_midi_brain)
    yield session, mock_midi, mock_midi_brain
    mock_midi.reset()
