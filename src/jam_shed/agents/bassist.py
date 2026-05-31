"""
VirtualBassist - AI bass player with style-based playing and kick-following.
"""

import random
from typing import Any, Dict

from jam_shed.agents.base import AgentMode, PlayingStyle, VirtualInstrumentalist
from jam_shed.agents.style_calibration import get_bass_tone_weights


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

    def _resolve_drummer_history_key(self) -> str | None:
        """Find the drummer key in shared history, tolerant of naming variants."""
        if self.drummer_name in self.brain.agent_history:
            return self.drummer_name
        for name in self.brain.agent_history:
            if "drum" in name.lower():
                return name
        return None

    def _get_tone_weights(self, state: Dict[str, Any]) -> tuple[float, float, float]:
        """Return (root, fifth, other) note-choice weights by Jam section role."""
        if not state.get("is_jam_mode"):
            return (0.6, 0.3, 0.1)

        section = state.get("jam_section", "")
        current_soloist = state.get("current_soloist", "")
        return get_bass_tone_weights(
            self.style,
            section,
            is_supporting_spotlight=(section == "SPOTLIGHT" and current_soloist != self.name),
        )

    def tick(self, state: Dict[str, Any], beat: int, sub_beat: int) -> None:
        """Called 12 times per beat. Overrides base to include kick-following logic."""
        if not self.is_running or self.mode == AgentMode.SILENT:
            return

        if sub_beat == 0:
            self.update_endurance_from_state(state)

        # Check if we should play based on motif
        step_size = 12 // self.subdivision
        is_motif_step = sub_beat % step_size == 0

        # Listening: Did the drummer just play a kick?
        kick_detect = False
        drummer_key = self._resolve_drummer_history_key()
        if self.follow_drummer and drummer_key:
            total_ticks_per_bar = self.beats_per_bar * 12
            abs_tick = (
                self.brain.current_bar * total_ticks_per_bar + beat * 12 + sub_beat
            ) % self.brain.total_history_ticks

            # Check current tick for kick (36)
            hits = self.brain.agent_history[drummer_key][abs_tick]
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
            self.current_chord_root, self.current_chord_type, octaves=self.octave_range
        )

        if not chord_notes:
            # Fallback to scale notes
            notes = MusicTheory.get_notes_in_key(self.root_note, self.scale_name, octaves=self.octave_range)
            if not notes:
                return
            note = random.choice(notes)
        else:
            # Bass Logic varies by section (Conversation vs Return Groove etc).
            root_w, fifth_w, _other_w = self._get_tone_weights(state)
            r = random.random()
            if r < root_w:
                note = chord_notes[0]  # Root
            elif r < (root_w + fifth_w) and len(chord_notes) > 2:
                note = chord_notes[2]  # Fifth (typically index 2 in simple triads/7ths)
            else:
                note = random.choice(chord_notes)

        velocity = int(state.get("intensity", 80) * self.reactivity)
        if ghost:
            velocity = int(velocity * 0.5)

        # In RETURN_GROOVE, emphasize pocket on downbeats.
        if state.get("is_jam_mode") and state.get("jam_section") == "RETURN_GROOVE":
            if sub_beat == 0 and beat in [0, 2]:
                velocity = int(velocity * 1.1)

        velocity = max(40, min(100, velocity))

        # Send Note On
        self.midi.send_message([0x90 | self.channel, note, velocity])
        self._playing_notes.add(note)

        # Schedule Note Off (longer for bass)
        import threading

        duration = 0.25
        if state.get("is_jam_mode"):
            if state.get("jam_section") == "CONVERSATION":
                duration = 0.20
            elif state.get("jam_section") == "RETURN_GROOVE":
                duration = 0.30
        timer = threading.Timer(duration, lambda: self._note_off_with_cleanup(note, timer))
        self._active_timers.append(timer)
        timer.start()

        # Record and Log
        grid_idx = (beat * 12) + sub_beat
        if grid_idx not in self.pattern:
            self.pattern[grid_idx] = []
        self.pattern[grid_idx].append((note, velocity))
        self.buffered_scrolling_hits.append(note)
        self.brain.log_agent_activity(self.name, beat, sub_beat, note, velocity)

        if self.on_play_callback:
            self.on_play_callback(self.name, note)
