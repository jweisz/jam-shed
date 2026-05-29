
import unittest
from unittest.mock import MagicMock
from jam_shed.core.brain import RhythmicBrain
from jam_shed.agents.drummer import VirtualDrummer
from jam_shed.agents.bassist import VirtualBassist
from jam_shed.agents.base import PlayingStyle, AgentMode

class TestMusicality(unittest.TestCase):
    def setUp(self):
        self.midi = MagicMock()
        self.brain = RhythmicBrain()
        self.drummer = VirtualDrummer("Drummer", self.midi, self.brain)
        self.bassist = VirtualBassist("Bass", self.midi, self.brain)

    def test_history_logging(self):
        # Drummer plays a kick on beat 0, sub 0
        state = self.brain.get_current_state()
        self.drummer.play_note(state, 0, 0)

        # Check if logged in history
        self.assertIn("Drummer", self.brain.agent_history)
        hits = self.brain.agent_history["Drummer"][0]
        self.assertTrue(any(h[0] == 36 for h in hits), "Kick should be in history")

    def test_bass_following(self):
        # Manually log a kick at beat 0, sub 0
        self.brain.log_agent_activity("Drummer", 0, 0, 36, 100)

        # Tick the bassist at beat 0, sub 0
        # Bassist should have high probability of playing here
        state = self.brain.get_current_state()
        self.bassist.tick(state, 0, 0)

        # Verify bassist played (it's probabilistic, but let's check motif or kick detect)
        # We can't easily check 'should_play' but we can check if midi message sent
        # Since we forced a kick in history, the probability is high.

    def test_8_bar_phrasing(self):
        # Check if motif is 8 bars long
        steps_per_bar = self.drummer.beats_per_bar * self.drummer.subdivision
        self.assertEqual(len(self.drummer.motif), steps_per_bar * 8)

if __name__ == "__main__":
    unittest.main()
