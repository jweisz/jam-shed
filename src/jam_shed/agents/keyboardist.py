"""
VirtualKeyboardist - AI keyboard player that plays chords and melodies.
"""
import random
from typing import Dict, Any, List, Optional
from jam_shed.agents.base import VirtualInstrumentalist, PlayingStyle, AgentMode
from jam_shed.midi.engine import MIDIEngine
from jam_shed.core.brain import RhythmicBrain
from jam_shed.core.theory import MusicTheory


class VirtualKeyboardist(VirtualInstrumentalist):
    """AI keyboardist that plays chords, comping, and melodies based on style."""

    def __init__(
        self,
        name: str,
        midi_engine: MIDIEngine,
        brain: RhythmicBrain,
        channel: int = 4, # Keyboards typically on channel 4
        style: PlayingStyle = PlayingStyle.ROCK,
        **kwargs
    ):
        super().__init__(name, midi_engine, brain, channel=channel, style=style, **kwargs)

        # Keyboardist-specific settings
        self.subdivision = 2  # 8th notes for comping
        self.complexity_bias = 0.6

        # Voicing preferences based on style
        self.voice_density = 0.7  # 0-1: single notes vs full chords
        self.chord_inversions = True

        # Style-specific behavior
        self._configure_for_style(style)

        self.generate_motif()

    def _configure_for_style(self, style: PlayingStyle) -> None:
        """Configure playing characteristics based on style."""
        style_configs = {
            PlayingStyle.ROCK: {
                "voice_density": 0.8,  # Full chords
                "subdivision": 2,  # 8th note comping
                "octave_range": [3, 4],
            },
            PlayingStyle.JAZZ: {
                "voice_density": 0.9,  # Complex voicings
                "subdivision": 4,  # 16th note runs
                "octave_range": [4, 5],
            },
            PlayingStyle.HIP_HOP: {
                "voice_density": 0.5,  # Sparse, single note hits
                "subdivision": 2,
                "octave_range": [4, 5],
            },
            PlayingStyle.FUNK: {
                "voice_density": 0.8,  # Staccato chords
                "subdivision": 4,  # 16th note rhythm
                "octave_range": [3, 4],
            },
            PlayingStyle.BLUES: {
                "voice_density": 0.7,  # Mix of chords and runs
                "subdivision": 3,  # Triplet feel (approximated)
                "octave_range": [3, 4],
            },
            PlayingStyle.LATIN: {
                "voice_density": 0.75,  # Montuno patterns
                "subdivision": 4,
                "octave_range": [4, 5],
            },
        }

        config = style_configs.get(style, style_configs[PlayingStyle.ROCK])
        self.voice_density = config["voice_density"]
        self.subdivision = config["subdivision"]
        self.octave_range = config["octave_range"]


    def play_note(self, state: Dict[str, Any], beat: int, sub_beat: int, ghost: bool = False) -> None:
        """Play keyboard voicings - chords or melody based on mode and style."""
        if not self.midi.is_out_open():
            return

        # Decide: chord or single note
        if self.mode == AgentMode.SOLO:
            #Solo mode: more single notes melody
            play_chord = random.random() < (self.voice_density * 0.3)
        else:
            # Accompany mode: more chords
            play_chord = random.random() < self.voice_density

        if play_chord:
            self._play_chord(state, beat, sub_beat, ghost)
        else:
            self._play_melody_note(state, beat, sub_beat, ghost)


    def _play_chord(self, state: Dict[str, Any], beat: int, sub_beat: int, ghost: bool = False) -> None:
        """Play a chord voicing."""
        # Determine chord type (use local variable to avoid mutating shared state)
        chord_type = self.current_chord_type

        # Apply style-specific voicing
        if self.style == PlayingStyle.JAZZ:
            if chord_type == "Major":
                chord_type = "Maj7"
            elif chord_type == "Minor":
                chord_type = "Min7"

        # Get chord notes
        chord_notes = MusicTheory.get_chord_notes(
            self.current_chord_root,
            chord_type,
            octaves=self.octave_range
        )

        if not chord_notes:
            return

        # Velocity based on intensity
        velocity = int(state.get("intensity", 70) * self.reactivity)
        if ghost:
            velocity = velocity // 2
        velocity = max(40, min(100, velocity))

        # Play the chord (all notes at once)
        import threading
        for note in chord_notes[:4]:  # Limit to 4 notes for cleaner voicing
            self.midi.send_message([0x90 | self.channel, note, velocity])
            self._playing_notes.add(note)

            # Schedule note off
            duration = 0.2 if self.style == PlayingStyle.FUNK else 0.3
            timer = threading.Timer(
                duration,
                lambda n=note, t_ref=[None]: self._note_off_with_cleanup(n, t_ref[0])
            )
            timer.args[0][-1] = timer  # Back-fill the reference
            self._active_timers.append(timer)
            timer.start()

            # Record to pattern
            grid_idx = (beat * 12) + sub_beat
            if grid_idx not in self.pattern:
                self.pattern[grid_idx] = []
            self.pattern[grid_idx].append((note, velocity))

            # Log to shared history in brain for inter-agent "listening"
            self.brain.log_agent_activity(self.name, beat, sub_beat, note, velocity)


    def _play_melody_note(self, state: Dict[str, Any], beat: int, sub_beat: int, ghost: bool = False) -> None:
        """Play a single melody note from the scale."""
        notes = MusicTheory.get_notes_in_key(
            self.root_note,
            self.scale_name,
            octaves=self.octave_range
        )

        if not notes:
            return

        # Choose note with slight preference for chord tones
        chord_notes = MusicTheory.get_chord_notes(
            self.current_chord_root,
            self.current_chord_type,
            octaves=self.octave_range
        )

        # 70% chance to play chord tone, 30% scale tone
        if random.random() < 0.7 and chord_notes:
            note = random.choice(chord_notes)
        else:
            note = random.choice(notes)

        velocity = int(state.get("intensity", 70) * self.reactivity)
        if ghost:
            velocity = velocity // 2
        velocity = max(40, min(100, velocity))

        # Send note
        self.midi.send_message([0x90 | self.channel, note, velocity])
        self._playing_notes.add(note)

        # Schedule note off
        import threading
        duration = 0.15
        timer = threading.Timer(
            duration,
            lambda: self._note_off_with_cleanup(note, timer)
        )
        self._active_timers.append(timer)
        timer.start()

        # Record to pattern
        grid_idx = (beat * 12) + sub_beat
        if grid_idx not in self.pattern:
            self.pattern[grid_idx] = []
        self.pattern[grid_idx].append((note, velocity))

        if self.on_play_callback:
            self.on_play_callback(self.name, note)

    def get_groove_visual_rich(self, current_bar_beat: int, current_sub_beat: int, beats_per_bar: Optional[int] = None) -> str:
        """Visual representation showing chord vs melody notes."""
        b_per_bar = beats_per_bar if beats_per_bar is not None else self.beats_per_bar

        parts = []
        subdivision = 4
        step_size = 3

        step_idx = current_sub_beat // step_size
        global_active_idx = (current_bar_beat * subdivision) + step_idx

        for b in range(b_per_bar):
            beat_parts = []
            for s in range(subdivision):
                start_tick = (b * 12) + (s * step_size)

                # Count hits
                hits = []
                for t in range(start_tick, start_tick + step_size):
                    if t in self.pattern:
                        hits.extend(self.pattern[t])

                # Display
                if len(hits) >= 3:
                    val = "CH"  # Chord
                elif len(hits) > 0:
                    val = "N "  # Note
                else:
                    val = ". "

                val_str = val.ljust(2) + " " # Standardized 3-char width

                current_idx = (b * subdivision) + s
                if current_idx == global_active_idx:
                    beat_parts.append(f"[reverse green]{val_str}[/]")
                else:
                    if val == ". ":
                        beat_parts.append(f"[dim]{val_str}[/]")
                    else:
                        beat_parts.append(f"[bold cyan]{val_str}[/]")  # Cyan for keys

            parts.append(f"| {''.join(beat_parts)} |")

        return " ".join(parts)
