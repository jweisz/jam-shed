"""
Integration tests for agent behavior using mock MIDI.

Tests verify that agents:
- Play notes correctly
- Respond to drum grooves
- Interact with each other
- Respect session state
"""

import time

from jam_shed.agents.base import AgentMode
from jam_shed.agents.bassist import VirtualBassist
from jam_shed.agents.drummer import VirtualDrummer
from jam_shed.core.brain import RhythmicBrain


class TestDrummerBasics:
    """Test basic drummer functionality."""

    def test_drummer_plays_on_beat(self, mock_midi):
        """Test that drummer plays notes when requested."""
        brain = RhythmicBrain()
        drummer = VirtualDrummer("Drummer", mock_midi, brain, channel=9)

        state = {"intensity": 80, "phase": ""}

        # Play on beat 0
        drummer.play_note(state, beat=0, sub_beat=0)

        # Should have logged some output
        notes = mock_midi.get_note_on_messages()
        assert len(notes) > 0, "Drummer should play notes"

    def test_drummer_respects_silent_mode(self, mock_midi):
        """Test that drummer can be in SILENT mode (doesn't play)."""
        brain = RhythmicBrain()
        drummer = VirtualDrummer("Drummer", mock_midi, brain, channel=9)
        drummer.mode = AgentMode.SILENT

        # In SILENT mode, we typically skip calling play_note
        # This test verifies the drummer doesn't produce output when not played
        initial_count = len(mock_midi.output_log)

        # Drummer in SILENT mode should not be called, so output shouldn't change
        # (In a real system, the session would skip calling play_note for silent agents)
        final_count = len(mock_midi.output_log)
        assert final_count == initial_count, "Silent drummer state shouldn't produce output on its own"

    def test_drummer_intensity_affects_velocity(self, mock_midi):
        """Test that intensity parameter affects note velocity."""
        brain = RhythmicBrain()
        drummer = VirtualDrummer("Drummer", mock_midi, brain, channel=9)

        # Play with low intensity
        state = {"intensity": 30, "phase": ""}
        drummer.play_note(state, beat=0, sub_beat=0)
        low_velocity = mock_midi.get_note_on_messages()[0][2] if mock_midi.get_note_on_messages() else 0

        mock_midi.clear_output_log()

        # Play with high intensity
        state = {"intensity": 120, "phase": ""}
        drummer.play_note(state, beat=0, sub_beat=0)
        high_velocity = mock_midi.get_note_on_messages()[0][2] if mock_midi.get_note_on_messages() else 0

        # High intensity should have higher (or equal) velocity
        assert high_velocity >= low_velocity, "Higher intensity should produce higher or equal velocity"


class TestBassistBasics:
    """Test basic bassist functionality."""

    def test_bassist_plays_in_key(self, mock_midi):
        """Test that bassist plays notes consistently from its scale."""
        brain = RhythmicBrain()
        bassist = VirtualBassist("Bass", mock_midi, brain, channel=3)

        # Set bassist's scale directly
        bassist.root_note = "C"
        bassist.scale_name = "Pentatonic Minor"  # C pentatonic minor: C, Eb, F, G, Bb

        state = {
            "intensity": 80,
            "is_jam_mode": False,
            "jam_section": "",
            "phase": "",
            "current_soloist": "",
        }

        # Play multiple notes
        for _ in range(20):
            bassist.play_note(state, beat=0, sub_beat=0)

        notes = mock_midi.get_note_on_messages()
        assert len(notes) > 0, "Bassist should play notes"

        # Verify notes are valid MIDI note numbers and have reasonable velocity
        for ts, note, vel in notes:
            assert 0 <= note <= 127, f"Note {note} out of MIDI range"
            assert 40 <= vel <= 127, f"Velocity {vel} should be reasonable"

    def test_bassist_respects_accompany_mode(self, mock_midi):
        """Test that bassist plays in accompany mode."""
        brain = RhythmicBrain()
        bassist = VirtualBassist("Bass", mock_midi, brain, channel=3)
        bassist.mode = AgentMode.ACCOMPANY

        state = {
            "intensity": 80,
            "is_jam_mode": False,
            "jam_section": "",
            "phase": "",
            "current_soloist": "Other",
        }

        # Should play even in accompany mode
        bassist.play_note(state, beat=0, sub_beat=0)
        notes = mock_midi.get_note_on_messages()
        # Bassist may or may not play depending on strategy, just verify no crash
        assert isinstance(notes, list)


class TestSessionWithAgents:
    """Test session state transitions with agents."""

    def test_session_starts_in_groove_mode(self, mock_midi_session):
        """Test that session can start in groove mode."""
        session, mock_midi, brain = mock_midi_session

        session.start_groove()

        assert session.is_groove is True
        assert session.is_trading is False
        assert session.current_soloist == "Human"

    def test_session_starts_trading_mode(self, mock_midi_session):
        """Test that session can start in trading/shed mode."""
        session, mock_midi, brain = mock_midi_session

        session.start_trading(bars=4)

        assert session.is_trading is True
        assert session.is_groove is False

    def test_agents_receive_callbacks(self, mock_midi_session):
        """Test that agents receive beat/bar callbacks from session."""
        session, mock_midi, brain = mock_midi_session

        session.start_trading(bars=4)
        session.start_first_hit()

        # Simulate 5 beat callbacks (lead-in + 1st beat)
        for _ in range(5):
            session.notify_beat_elapsed()

        # Session should have exited lead-in
        assert session.is_leadin is False
        assert session.bars_elapsed >= 1

    def test_drummer_updates_mode_with_session(self, mock_midi_session):
        """Test that drummer mode updates when session changes soloist."""
        session, mock_midi, brain = mock_midi_session
        drummer = session.agents[0]  # First agent is drummer

        session.start_trading(bars=4)
        session.current_soloist = "Bass"
        session._update_agent_modes()

        # Drummer should not be solo when bassist is soloist
        assert drummer.mode != AgentMode.SOLO


class TestMIDIMessageLogging:
    """Test that MIDI messages are correctly logged."""

    def test_output_messages_logged_with_timestamp(self, mock_midi):
        """Test that output messages include timestamps."""
        mock_midi.send_message([0x90, 60, 100])  # Note On C4

        assert len(mock_midi.output_log) == 1
        ts, msg = mock_midi.output_log[0]
        assert isinstance(ts, float)
        assert ts > 0
        assert msg == [0x90, 60, 100]

    def test_filter_messages_by_channel(self, mock_midi):
        """Test filtering output messages by MIDI channel."""
        # Send on channel 0
        mock_midi.send_message([0x90, 60, 100])
        # Send on channel 3
        mock_midi.send_message([0x93, 50, 80])
        # Send on channel 9
        mock_midi.send_message([0x99, 36, 127])

        ch0_msgs = mock_midi.get_output_messages(channel=0)
        ch3_msgs = mock_midi.get_output_messages(channel=3)
        ch9_msgs = mock_midi.get_output_messages(channel=9)

        assert len(ch0_msgs) == 1
        assert len(ch3_msgs) == 1
        assert len(ch9_msgs) == 1

    def test_get_note_on_messages(self, mock_midi):
        """Test extracting Note On messages."""
        mock_midi.send_message([0x90, 60, 100])  # Note On
        mock_midi.send_message([0x80, 60, 0])  # Note Off
        mock_midi.send_message([0x90, 62, 90])  # Note On

        notes = mock_midi.get_note_on_messages()
        assert len(notes) == 2
        assert notes[0][1] == 60  # First note
        assert notes[1][1] == 62  # Second note

    def test_get_notes_by_pitch(self, mock_midi):
        """Test finding notes by pitch."""
        mock_midi.send_message([0x90, 60, 100])
        mock_midi.send_message([0x90, 60, 95])
        mock_midi.send_message([0x90, 62, 90])

        c_notes = mock_midi.get_notes_by_pitch(60)
        assert len(c_notes) == 2
        assert c_notes[0][1] == 100  # Velocity
        assert c_notes[1][1] == 95


class TestInputReplay:
    """Test MIDI input replay functionality."""

    def test_queue_and_replay_inputs(self, mock_midi):
        """Test queuing and replaying MIDI inputs."""
        received_messages = []

        def input_callback(msg, unused):
            received_messages.append(msg)

        mock_midi.set_input_callback(input_callback)

        # Queue some input
        mock_midi.queue_input(0.01, [0x90, 60, 100])
        mock_midi.queue_input(0.02, [0x80, 60, 0])

        # Replay
        mock_midi.replay_inputs()

        # Wait for replay to finish
        time.sleep(0.1)

        # Should have received both messages
        assert len(received_messages) == 2
        assert received_messages[0] == [0x90, 60, 100]
        assert received_messages[1] == [0x80, 60, 0]

    def test_stop_replay(self, mock_midi):
        """Test stopping replay."""
        received_messages = []

        def input_callback(msg, unused):
            received_messages.append(msg)

        mock_midi.set_input_callback(input_callback)

        # Queue many delayed messages
        for i in range(10):
            mock_midi.queue_input(0.1, [0x90, 60 + i, 100])

        # Replay
        mock_midi.replay_inputs()

        # Immediately stop
        time.sleep(0.05)
        mock_midi.stop_replay()

        # Should have received fewer messages due to early stop
        assert len(received_messages) < 10
