import pytest

from jam_shed.agents.base import AgentMode, VirtualInstrumentalist
from jam_shed.core.brain import RhythmicBrain
from jam_shed.core.session import JamSession


class FakeMIDI:
    def is_out_open(self):
        return False

    def send_message(self, _msg):
        pass


class FakeAgent:
    def __init__(self, name: str, endurance: float):
        self.name = name
        self.endurance = endurance
        self.mode = AgentMode.ACCOMPANY


@pytest.fixture
def base_agent():
    return VirtualInstrumentalist("Agent", FakeMIDI(), RhythmicBrain())


def test_endurance_drains_with_high_energy(base_agent):
    start = base_agent.endurance
    state = {
        "bpm": 220,
        "energy_norm": 1.0,
        "complexity": 0.9,
    }
    base_agent.mode = AgentMode.SOLO

    for _ in range(48):
        base_agent.update_endurance_from_state(state)

    assert base_agent.endurance < start


def test_endurance_recovers_with_low_energy(base_agent):
    base_agent.endurance = 0.2
    state = {
        "bpm": 75,
        "energy_norm": 0.15,
        "complexity": 0.1,
    }

    for _ in range(48):
        base_agent.update_endurance_from_state(state)

    assert base_agent.endurance > 0.2


def _make_jam_session(agents=None):
    session = JamSession(agents=agents or [], brain=RhythmicBrain())
    session.waiting_for_first_hit = False
    session.is_leadin = False
    session.start_jam()
    return session


def test_jam_no_transition_before_16_bars():
    session = _make_jam_session()
    session.update_human_state(confidence=0.95, energy=0.8, complexity=0.8)

    for _ in range(15):
        session.notify_bar_elapsed()

    assert session.jam_section_index == 0


def test_jam_can_transition_at_24_with_readiness():
    # Set endurance low enough to create some transition pressure but
    # not enough to cross the stricter 16-bar threshold.
    agents = [FakeAgent("Drummer", endurance=0.3)]
    session = _make_jam_session(agents=agents)
    session.update_human_state(confidence=0.65, energy=0.7, complexity=0.6)

    for _ in range(24):
        session.notify_bar_elapsed()

    assert session.jam_section_index == 1


def test_jam_forces_transition_at_32_bars():
    session = _make_jam_session()
    session.update_human_state(confidence=0.1, energy=0.2, complexity=0.1)

    for _ in range(32):
        session.notify_bar_elapsed()

    assert session.jam_section_index == 1


def test_jam_section_profile_defaults_present():
    session = _make_jam_session()
    profile = session.get_jam_section_profile()

    assert "density_target" in profile
    assert "space_bias" in profile
    assert "solo_bias" in profile

    status = session.get_status()
    assert "jam_density_target" in status
    assert "jam_space_bias" in status
    assert "jam_solo_bias" in status


def test_spotlight_prefers_agent_soloist():
    agents = [
        FakeAgent("Lead Guitar", endurance=0.8),
        FakeAgent("Bass", endurance=0.9),
    ]
    session = _make_jam_session(agents=agents)
    session.jam_section_index = session.jam_sections.index("SPOTLIGHT")
    session.jam_section_started_at_bar = 0

    # Trigger arranger update through bar progression.
    session.notify_bar_elapsed()

    assert session.current_soloist != "Human"
