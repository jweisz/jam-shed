import random
from typing import Dict, Any
from jam_shed.agents.base import VirtualInstrumentalist, PlayingStyle
from jam_shed.core.theory import MusicTheory


class VirtualRhythmGuitarist(VirtualInstrumentalist):
    """
    Virtual rhythm guitarist that plays with rhythmic variety and voicing changes.
    """

    def __init__(self, name, midi_engine, brain, channel=2, style=PlayingStyle.ROCK, **kwargs):
        """Initialize rhythm guitarist with a library of strumming patterns."""
        super().__init__(name, midi_engine, brain, channel=channel, style=style, **kwargs)
        self.subdivision = 4  # 16th resolution for rhythmic flexibility
        self.complexity_bias = 0.4

        # Rhythmic Patterns (Ticks 0-47)
        self.patterns = {
            "steady_8th": {0, 6, 12, 18, 24, 30, 36, 42},
            "syncopated_rock": {0, 9, 12, 21, 24, 33, 36, 45},
            "driving_rock": {0, 3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36, 39, 42, 45},
            "funk_shuffle": {0, 9, 12, 21, 24, 30, 33, 42, 45},
            "blues_shuffle": {0, 8, 12, 20, 24, 32, 36, 44}
        }
        self.current_pattern_name = "steady_8th"
        self.voicing_index = 0

    def tick(self, state: Dict[str, Any], beat: int, sub_beat: int) -> None:
        """Called 12 times per beat. Decides when to strum based on the pattern."""
        if not self.is_running: return

        current_bar = self.brain.current_bar
        grid_idx = (beat * 12) + sub_beat

        # Switch pattern and voicing every 4 bars
        if beat == 0 and sub_beat == 0 and current_bar % 4 == 0:
            style_patterns = ["steady_8th", "syncopated_rock"]
            if self.style == PlayingStyle.FUNK: style_patterns = ["funk_shuffle", "syncopated_rock"]
            elif self.style == PlayingStyle.BLUES: style_patterns = ["blues_shuffle", "steady_8th"]
            elif state.get("intensity", 80) > 100: style_patterns = ["driving_rock", "syncopated_rock"]

            self.current_pattern_name = random.choice(style_patterns)
            self.voicing_index = random.randint(0, 2) # Toggle inversions

        # Play if tick is in pattern
        pattern = self.patterns.get(self.current_pattern_name, self.patterns["steady_8th"])
        if grid_idx in pattern:
            # Rhythmic Accent: hit harder on 1 and 3
            is_accent = (beat in [0, 2] and sub_beat == 0)
            self.play_note(state, beat, sub_beat, ghost=not is_accent)

    def play_note(self, state: Dict[str, Any], beat: int, sub_beat: int, ghost: bool = False) -> None:
        """Play a full chord voicing (strumming) with variations."""
        if not self.midi.is_out_open(): return

        # Get chord notes
        chord_notes = MusicTheory.get_chord_notes(
            self.current_chord_root,
            self.current_chord_type,
            octaves=self.octave_range
        )

        if not chord_notes:
            notes = MusicTheory.get_notes_in_key(self.root_note, self.scale_name, octaves=self.octave_range)
            if not notes: return
            chord_notes = [random.choice(notes)]

        # Apply Voicing Variation (Inversions)
        if len(chord_notes) > 3:
            if self.voicing_index == 1: # First Inversion
                chord_notes = chord_notes[1:] + [chord_notes[0] + 12]
            elif self.voicing_index == 2: # Second Inversion
                chord_notes = chord_notes[2:] + [chord_notes[0] + 12, chord_notes[1] + 12]

        # Velocity and Accents
        intensity = state.get("intensity", 75)
        # Accents are handled by the 'ghost' flag from tick()
        velocity = int(intensity * self.reactivity)
        if ghost: velocity = int(velocity * 0.75)
        velocity = max(40, min(100, velocity))

        # Perform the "Strum"
        import threading
        for i, note in enumerate(chord_notes[:4]):
            strum_delay = i * 0.015 # 15ms feel
            def trigger(n=note, v=velocity):
                self.midi.send_message([0x90 | self.channel, n, v])
                self._playing_notes.add(n)
                timer = threading.Timer(0.2, lambda: self._note_off_with_cleanup(n, timer))
                timer.start()

            if strum_delay > 0:
                t = threading.Timer(strum_delay, trigger); t.start()
            else:
                trigger()

        # Log
        self.brain.log_agent_activity(self.name, beat, sub_beat, chord_notes[0], velocity)
        if self.on_play_callback: self.on_play_callback(self.name, chord_notes[0])
