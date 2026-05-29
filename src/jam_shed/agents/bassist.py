"""
VirtualBassist - AI bass player with style-based playing and kick-following.
"""
from typing import Dict, Any
import random
from jam_shed.agents.base import VirtualInstrumentalist, PlayingStyle


class VirtualBassist(VirtualInstrumentalist):
    """
    Virtual bass player.

    Plays foundational bass lines with 8th note subdivision.
    Lower complexity bias for solid, steady bass lines.
    """

    def __init__(self, name, midi_engine, brain, channel=3, style=PlayingStyle.ROCK, **kwargs):
        """Initialize bass player with bass-appropriate settings."""
        super().__init__(name, midi_engine, brain, channel=channel, style=style, **kwargs)
        self.subdivision = 2  # 8th notes
        self.complexity_bias = 0.3  # Steady, simple bass lines
        self.octave_range = [1, 2]  # Deeper range for bass

        # Bass-specific logic
        self.follow_drummer = True
        self.drummer_name = "Drummer"

    def tick(self, state: Dict[str, Any], beat: int, sub_beat: int) -> None:
        """Called 12 times per beat. Overrides base to include kick-following logic."""
        if not self.is_running:
            return

        # Check if we should play based on motif
        step_size = 12 // self.subdivision
        is_motif_step = (sub_beat % step_size == 0)

        # Listening: Did the drummer just play a kick?
        kick_detect = False
        if self.follow_drummer and self.drummer_name in self.brain.agent_history:
            total_ticks_per_bar = self.beats_per_bar * 12
            abs_tick = (self.brain.current_bar * total_ticks_per_bar + beat * 12 + sub_beat) % self.brain.total_history_ticks

            # Check current tick for kick (36)
            hits = self.brain.agent_history[self.drummer_name][abs_tick]
            if any(h[0] == 36 for h in hits):
                kick_detect = True

        # Decision logic:
        # 1. If it's a motif step, play with high probability
        # 2. If we detect a kick and it's NOT a motif step, play with moderate probability (syncopation)

        play_prob = self.calculate_play_probability(state)
        should_play = False

        if is_motif_step:
            steps_per_bar = self.beats_per_bar * self.subdivision
            bar_idx = self.brain.current_bar % self.history_length_bars
            motif_idx = (bar_idx * steps_per_bar) + (beat * self.subdivision) + (sub_beat // step_size)
            if self.motif[motif_idx] and random.random() < (play_prob + 0.3):
                should_play = True

        if not should_play and kick_detect and random.random() < 0.6:
            # Sync with drummer even if not in motif
            should_play = True

        if should_play:
            self.play_note(state, beat, sub_beat)
        elif not should_play and is_motif_step and random.random() < 0.05:
            self.play_note(state, beat, sub_beat, ghost=True)

    def play_note(self, state: Dict[str, Any], beat: int, sub_beat: int, ghost: bool = False) -> None:
        """Play a bass note, prioritizing Root and Fifth of the current chord."""
        if not self.midi.is_out_open():
            return

        from jam_shed.core.theory import MusicTheory

        # Get chord notes
        chord_notes = MusicTheory.get_chord_notes(
            self.current_chord_root,
            self.current_chord_type,
            octaves=self.octave_range
        )

        if not chord_notes:
            # Fallback to scale notes
            notes = MusicTheory.get_notes_in_key(self.root_note, self.scale_name, octaves=self.octave_range)
            if not notes: return
            note = random.choice(notes)
        else:
            # Bass Logic:
            # 60% Root, 30% Fifth, 10% Other Chord Tones
            r = random.random()
            if r < 0.6:
                note = chord_notes[0] # Root
            elif r < 0.9 and len(chord_notes) > 2:
                note = chord_notes[2] # Fifth (typically index 2 in simple triads/7ths)
            else:
                note = random.choice(chord_notes)

        velocity = int(state.get("intensity", 80) * self.reactivity)
        if ghost:
            velocity = int(velocity * 0.5)
        velocity = max(40, min(100, velocity))

        # Send Note On
        self.midi.send_message([0x90 | self.channel, note, velocity])
        self._playing_notes.add(note)

        # Schedule Note Off (longer for bass)
        import threading
        duration = 0.25
        timer = threading.Timer(
            duration,
            lambda: self._note_off_with_cleanup(note, timer)
        )
        self._active_timers.append(timer)
        timer.start()

        # Record and Log
        grid_idx = (beat * 12) + sub_beat
        if grid_idx not in self.pattern:
            self.pattern[grid_idx] = []
        self.pattern[grid_idx].append((note, velocity))
        self.brain.log_agent_activity(self.name, beat, sub_beat, note, velocity)

        if self.on_play_callback:
            self.on_play_callback(self.name, note)
