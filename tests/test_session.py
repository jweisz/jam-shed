"""
Tests for jam_shed.session module.
"""
import pytest
from jam_shed.core.session import JamSession
from jam_shed.agents import AgentMode, PlayingStyle
from jam_shed.agents.bassist import VirtualBassist
from jam_shed.midi.engine import MIDIEngine
from jam_shed.core.brain import RhythmicBrain


@pytest.fixture
def session_with_agents():
    """Create a session with test agents."""
    midi = MIDIEngine()
    brain = RhythmicBrain(beats_per_bar=4)

    agents = [
        VirtualBassist("Bass", midi, brain, channel=1, style=PlayingStyle.ROCK),
        VirtualBassist("Guitar", midi, brain, channel=2, style=PlayingStyle.JAZZ),
    ]

    session = JamSession(agents=agents)
    return session


def test_session_initialization():
    """Test session initializes correctly."""
    session = JamSession()
    assert session.agents == []
    assert session.is_trading is False
    assert session.current_soloist == "Human"


def test_session_with_agents(session_with_agents):
    """Test session with agents."""
    assert len(session_with_agents.agents) == 2


def test_start_trading(session_with_agents):
    """Test starting trading mode."""
    session_with_agents.start_trading(bars=4)
    assert session_with_agents.is_trading is True
    assert session_with_agents.bars_per_solo == 4


def test_stop_trading(session_with_agents):
    """Test stopping trading mode."""
    session_with_agents.start_trading(bars=4)
    session_with_agents.stop_trading()
    assert session_with_agents.is_trading is False


def test_update_theory(session_with_agents):
    """Test updating musical theory context."""
    session_with_agents.update_theory("D", "Minor", "12-Bar Blues")
    assert session_with_agents.key_root == "D"
    assert session_with_agents.scale_name == "Minor"
    assert session_with_agents.progression_name == "12-Bar Blues"
    assert len(session_with_agents.chord_sequence) == 12


def test_notify_beat_elapsed():
    """Test beat notification."""
    session = JamSession()
    session.start_first_hit()

    initial_beats = session.beats_elapsed
    session.notify_beat_elapsed()

    assert session.beats_elapsed == initial_beats + 1


def test_agent_modes_update_on_solo(session_with_agents):
    """Test that agent modes update when soloist changes."""
    session_with_agents.current_soloist = "Bass"
    session_with_agents._update_agent_modes()

    bass_agent = session_with_agents.agents[0]
    guitar_agent = session_with_agents.agents[1]

    assert bass_agent.mode == AgentMode.SOLO
    assert guitar_agent.mode == AgentMode.ACCOMPANY


def test_get_status():
    """Test status dictionary."""
    session = JamSession()
    status = session.get_status()

    assert "is_trading" in status
    assert "current_soloist" in status
    assert "bars_elapsed" in status
    assert "phase" in status
    assert status["is_waiting"] is True


# ============================================================
# Shed Mode 12-Bar Cycle Tests
# ============================================================


@pytest.fixture
def shed_session():
    """Create a session configured for Shed Mode with a drum partner.

    After this fixture returns, the session has completed the lead-in
    and is at bars_elapsed=1 (first bar of the cycle has been counted).
    The phase is "GROOVE: Human (AI Listening)" and the current_soloist
    is "Human".
    """
    midi = MIDIEngine()
    brain = RhythmicBrain(beats_per_bar=4)

    from jam_shed.agents.drummer import DrumShedAgent
    drum_partner = DrumShedAgent("Drum Partner", midi, brain, channel=9)

    session = JamSession(agents=[drum_partner])
    session.start_trading(bars=4)
    # Simulate the first hit to exit waiting state
    session.start_first_hit()
    # Simulate lead-in: 4 beats fills the bar, then the 5th beat
    # triggers `beats_elapsed > beats_per_bar`, ending lead-in.
    # The transition immediately fires notify_bar_elapsed() for bar 1.
    for _ in range(5):
        session.notify_beat_elapsed()

    assert session.is_leadin is False, "Lead-in should be complete"
    assert session.bars_elapsed == 1, f"Expected bars_elapsed=1, got {session.bars_elapsed}"
    return session


def _advance_bars(session, n_bars):
    """Helper: advance the session by n full bars (4 beats each)."""
    for _ in range(n_bars):
        for _ in range(4):  # 4 beats per bar
            session.notify_beat_elapsed()


def test_shed_cycle_length():
    """Test that the Shed Mode cycle is 12 bars."""
    session = JamSession()
    session.start_trading(bars=4)
    assert session.bars_per_cycle == 12


def test_shed_turn1_human_groove_ai_silent(shed_session):
    """Turn 1 (bars 1-4): Human plays groove, AI is SILENT."""
    session = shed_session
    drum_partner = session.agents[0]

    # After lead-in, bars_elapsed=1, phase is Turn 1
    assert session.current_soloist == "Human"
    assert "AI Listening" in session.current_phase
    assert drum_partner.mode == AgentMode.SILENT

    # Advance through remaining bars of Turn 1 (bars 2-4)
    for bar in range(3):
        _advance_bars(session, 1)
        assert session.current_soloist == "Human", f"Soloist wrong at bar {session.bars_elapsed}"
        assert drum_partner.mode == AgentMode.SILENT, f"AI not silent at bar {session.bars_elapsed}"

    # At this point bars_elapsed should be 4 (last bar of Turn 1)
    assert session.bars_elapsed == 4


def test_shed_turn2_human_fill_ai_groove(shed_session):
    """Turn 2 (bars 5-8): Human fills, AI plays back learned groove."""
    session = shed_session
    drum_partner = session.agents[0]

    # Advance from bar 1 into Turn 2 (bar 5 is the first bar of Turn 2)
    _advance_bars(session, 4)
    assert session.bars_elapsed == 5

    assert session.current_soloist == "Drum Partner"
    assert "HUMAN FILL" in session.current_phase
    assert drum_partner.mode == AgentMode.SOLO

    # Verify Turn 2 persists for remaining 3 bars (bars 6, 7, 8)
    for i in range(3):
        _advance_bars(session, 1)
        assert "HUMAN FILL" in session.current_phase, f"Phase wrong at bar {session.bars_elapsed}"
        assert drum_partner.mode == AgentMode.SOLO, f"AI not SOLO at bar {session.bars_elapsed}"

    assert session.bars_elapsed == 8


def test_shed_turn3_ai_fill_human_groove(shed_session):
    """Turn 3 (bars 9-12): AI plays response fill, human grooves."""
    session = shed_session
    drum_partner = session.agents[0]

    # Advance from bar 1 into Turn 3 (bar 9 is the first bar of Turn 3)
    _advance_bars(session, 8)
    assert session.bars_elapsed == 9

    assert session.current_soloist == "Drum Partner"
    assert "AI FILL" in session.current_phase
    assert drum_partner.mode == AgentMode.SOLO

    # Verify Turn 3 persists for remaining 3 bars (bars 10, 11, 12)
    for i in range(3):
        _advance_bars(session, 1)
        assert "AI FILL" in session.current_phase, f"Phase wrong at bar {session.bars_elapsed}"
        assert drum_partner.mode == AgentMode.SOLO, f"AI not SOLO at bar {session.bars_elapsed}"

    assert session.bars_elapsed == 12


def test_shed_cycle_resets_after_12_bars(shed_session):
    """After 12 bars, the cycle resets back to Turn 1."""
    session = shed_session
    drum_partner = session.agents[0]

    # Advance through full 12-bar cycle and one boundary beat into next cycle.
    _advance_bars(session, 12)

    # Cycle should have reset; bars_elapsed is now back in Turn 1 range
    assert "AI Listening" in session.current_phase
    assert session.current_soloist == "Human"
    assert drum_partner.mode == AgentMode.SILENT


def test_shed_bars_left_in_turn(shed_session):
    """Test that bars_left_in_turn counts down correctly within each turn."""
    session = shed_session

    # After fixture, bars_elapsed=1, bars_left_in_turn should be 4
    # Turn 1: bars_left counts down 4, 3, 2, 1
    assert session.bars_left_in_turn == 4
    _advance_bars(session, 1)
    assert session.bars_left_in_turn == 3
    _advance_bars(session, 1)
    assert session.bars_left_in_turn == 2
    _advance_bars(session, 1)
    assert session.bars_left_in_turn == 1

    # Advance into Turn 2
    _advance_bars(session, 1)
    assert session.bars_left_in_turn == 4
    _advance_bars(session, 1)
    assert session.bars_left_in_turn == 3
    _advance_bars(session, 1)
    assert session.bars_left_in_turn == 2
    _advance_bars(session, 1)
    assert session.bars_left_in_turn == 1

    # Advance into Turn 3
    _advance_bars(session, 1)
    assert session.bars_left_in_turn == 4
    _advance_bars(session, 1)
    assert session.bars_left_in_turn == 3
    _advance_bars(session, 1)
    assert session.bars_left_in_turn == 2
    _advance_bars(session, 1)
    assert session.bars_left_in_turn == 1


def test_shed_leadin_is_4_beats():
    """Test that the lead-in countdown is exactly 4 beats, with
    BAR 1 starting on the beat after the 4th count-in tick."""
    session = JamSession()
    session.start_trading(bars=4)
    session.start_first_hit()

    assert session.is_leadin is True

    # Beats 1-3: still in lead-in
    for i in range(1, 4):
        session.notify_beat_elapsed()
        assert session.is_leadin is True, f"Lead-in ended too early at beat {i}"

    # Beat 4 is still count-in (transition is deferred to the next beat)
    session.notify_beat_elapsed()
    assert session.is_leadin is True

    # Next beat starts BAR 1 / BEAT 1
    session.notify_beat_elapsed()
    assert session.is_leadin is False
    assert session.bars_elapsed == 1  # First bar started


def test_shed_phase_transitions_emit_callbacks():
    """Test that phase transitions trigger the on_turn_change callback."""
    midi = MIDIEngine()
    brain = RhythmicBrain(beats_per_bar=4)
    from jam_shed.agents.drummer import DrumShedAgent
    drum_partner = DrumShedAgent("Drum Partner", midi, brain, channel=9)

    session = JamSession(agents=[drum_partner])
    session.start_trading(bars=4)
    session.start_first_hit()

    phases_seen = []
    session.on_turn_change = lambda phase: phases_seen.append(phase)

    # Complete lead-in (5 beats)
    for _ in range(5):
        session.notify_beat_elapsed()

    # Advance through full 12-bar cycle and into next cycle boundary.
    _advance_bars(session, 12)

    # Should see transitions: Turn 1 -> Turn 2, Turn 2 -> Turn 3, Turn 3 -> Turn 1
    assert any("HUMAN FILL" in p for p in phases_seen), f"Missing HUMAN FILL phase: {phases_seen}"
    assert any("AI FILL" in p for p in phases_seen), f"Missing AI FILL phase: {phases_seen}"
    assert any("AI Listening" in p for p in phases_seen), f"Missing cycle reset phase: {phases_seen}"


# ============================================================
# Groove Mode 8-Bar Cycle Tests
# ============================================================


@pytest.fixture
def groove_session():
    """Create a session configured for Groove Mode (8-bar call-and-response)."""
    midi = MIDIEngine()
    brain = RhythmicBrain(beats_per_bar=4)

    from jam_shed.agents.drummer import DrumShedAgent
    drum_partner = DrumShedAgent("Drum Partner", midi, brain, channel=9)

    session = JamSession(agents=[drum_partner])
    session.start_groove()
    session.start_first_hit()
    # Complete lead-in (5 beats)
    for _ in range(5):
        session.notify_beat_elapsed()

    assert session.is_leadin is False
    assert session.bars_elapsed == 1
    return session


def test_groove_cycle_length():
    """Test that Groove mode cycle is 8 bars."""
    session = JamSession()
    session.start_groove()
    assert session.bars_per_cycle == 8
    assert session.is_groove is True
    assert session.is_trading is False


def test_groove_human_turn_ai_silent(groove_session):
    """Turn 1 (bars 1-4): Human plays groove, AI is SILENT."""
    session = groove_session
    drum_partner = session.agents[0]

    assert session.current_soloist == "Human"
    assert "YOUR GROOVE" in session.current_phase
    assert drum_partner.mode == AgentMode.SILENT

    # Advance through remaining bars of human turn
    for _ in range(3):
        _advance_bars(session, 1)
        assert drum_partner.mode == AgentMode.SILENT

    assert session.bars_elapsed == 4


def test_groove_ai_turn_copies(groove_session):
    """Turn 2 (bars 5-8): AI copies the human's groove."""
    session = groove_session
    drum_partner = session.agents[0]

    # Advance into AI turn
    _advance_bars(session, 4)
    assert session.bars_elapsed == 5

    assert session.current_soloist == "Drum Partner"
    assert "AI GROOVE" in session.current_phase
    assert drum_partner.mode == AgentMode.SOLO

    # AI continues through remaining bars of turn
    for _ in range(3):
        _advance_bars(session, 1)
        assert "AI GROOVE" in session.current_phase
        assert drum_partner.mode == AgentMode.SOLO


def test_groove_cycle_resets_after_8_bars(groove_session):
    """After 8 bars, the cycle resets back to human turn."""
    session = groove_session
    drum_partner = session.agents[0]

    # Advance through full 8-bar cycle and into the next boundary.
    _advance_bars(session, 8)

    assert "YOUR GROOVE" in session.current_phase
    assert session.current_soloist == "Human"
    assert drum_partner.mode == AgentMode.SILENT
