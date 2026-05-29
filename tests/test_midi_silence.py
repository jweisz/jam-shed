
import unittest
from unittest.mock import MagicMock
from jam_shed.midi.engine import MIDIEngine
from jam_shed.agents.base import VirtualInstrumentalist, PlayingStyle
from jam_shed.core.brain import RhythmicBrain

class TestNoteSilence(unittest.TestCase):
    def setUp(self):
        self.midi = MagicMock()
        self.brain = MagicMock()
        self.agent = VirtualInstrumentalist("TestAgent", self.midi, self.brain, channel=1)

    def test_agent_stop_silences_notes(self):
        # Fake playing a note
        state = {"intensity": 100, "complexity": 0.5}
        self.agent.play_note(state, 0, 0)

        # Verify note is tracked
        self.assertIn(random_choice_placeholder_fix := list(self.agent._playing_notes)[0], self.agent._playing_notes)
        note = random_choice_placeholder_fix

        # Stop the agent
        self.agent.stop()

        # Verify Note Off was sent for that specific note
        # MIDI Note Off for Ch 2 (index 1) is 0x81
        self.midi.send_message.assert_any_call([0x81, note, 0])
        self.assertEqual(len(self.agent._playing_notes), 0, "Active notes should be cleared on stop")

if __name__ == "__main__":
    import random
    # Mocking MusicTheory since it's used in play_note
    from jam_shed.core.theory import MusicTheory
    MusicTheory.get_notes_in_key = MagicMock(return_value=[60, 62, 64])

    unittest.main()
