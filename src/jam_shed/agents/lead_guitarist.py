import random
from typing import Dict, Any
from jam_shed.agents.base import VirtualInstrumentalist, PlayingStyle
from jam_shed.agents.style_calibration import get_lead_section_multiplier
from jam_shed.core.theory import MusicTheory


class VirtualLeadGuitarist(VirtualInstrumentalist):
    """
    Virtual lead guitarist.

    Plays melodic lead lines with 16th note subdivision for faster playing.
    Higher complexity bias and reactivity for expressive solos.
    """

    def __init__(self, name, midi_engine, brain, channel=1, style=PlayingStyle.ROCK, **kwargs):
        """Initialize lead guitarist with lead-appropriate settings."""
        super().__init__(name, midi_engine, brain, channel=channel, style=style, **kwargs)
        self.subdivision = 4  # 16th notes for faster playing
        self.complexity_bias = 0.6  # More complex, expressive lines
        self.reactivity = 0.9  # Very responsive to musical context

    def calculate_play_probability(self, state: Dict[str, Any]) -> float:
        """Section-aware lead behavior for Jam mode role shaping."""
        prob = super().calculate_play_probability(state)
        if not state.get("is_jam_mode"):
            return prob

        section = state.get("jam_section", "")
        current_soloist = state.get("current_soloist", "")

        if section in ["INTRO", "GROOVE_ESTABLISH", "OUTRO"]:
            prob *= 0.72
        elif section == "CONVERSATION":
            prob *= 0.92
        elif section == "SPOTLIGHT":
            if current_soloist == self.name:
                prob = min(0.98, prob + 0.18)
            else:
                prob *= 0.62

        prob *= get_lead_section_multiplier(self.style, section)

        return max(0.1, min(0.98, prob))

    def play_note(self, state: Dict[str, Any], beat: int, sub_beat: int, ghost: bool = False) -> None:
        """Play a melodic solo note, prioritizing chord tones (Chord-Tone Soloing)."""
        if not self.midi.is_out_open():
            return

        # Get scale notes
        scale_notes = MusicTheory.get_notes_in_key(self.root_note, self.scale_name, octaves=self.octave_range)
        # Get chord notes
        chord_notes = MusicTheory.get_chord_notes(self.current_chord_root, self.current_chord_type, octaves=self.octave_range)

        if not scale_notes:
            return

        # Chord-Tone Soloing: Favor chord tones (70% probability)
        if chord_notes and random.random() < 0.7:
            note = random.choice(chord_notes)
        else:
            note = random.choice(scale_notes)

        velocity = int(state.get("intensity", 80) * self.reactivity)
        if ghost:
            velocity = int(velocity * 0.5)

        velocity = max(40, min(110, velocity))

        # Send Note On
        self.midi.send_message([0x90 | self.channel, note, velocity])
        self._playing_notes.add(note)

        # Schedule Note Off (shorter for leads)
        import threading
        duration = 0.15
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
        self.buffered_scrolling_hits.append(note)
        self.brain.log_agent_activity(self.name, beat, sub_beat, note, velocity)

        if self.on_play_callback:
            self.on_play_callback(self.name, note)
