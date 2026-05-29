import random
import threading
from enum import Enum
from typing import Optional, List, Dict, Any
from jam_shed.midi.engine import MIDIEngine
from jam_shed.core.brain import RhythmicBrain
from jam_shed.core.theory import MusicTheory


class PlayingStyle(Enum):
    """Musical styles that influence agent playing behavior."""
    ROCK = "rock"
    JAZZ = "jazz"
    HIP_HOP = "hip_hop"
    BLUES = "blues"
    FUNK = "funk"
    LATIN = "latin"


class AgentMode(Enum):
    """Agent playing modes."""
    SOLO = "solo"
    ACCOMPANY = "accompany"
    SILENT = "silent"


class VirtualInstrumentalist:
    """Base class for all virtual instrument players (AI musicians)."""

    def __init__(
        self,
        name: str,
        midi_engine: MIDIEngine,
        brain: RhythmicBrain,
        channel: int = 0,
        style: PlayingStyle = PlayingStyle.ROCK,
        **kwargs
    ):
        self.name = name
        self.midi = midi_engine
        self.brain = brain
        self.channel = channel
        self.style = style
        self.octave_range = [3, 4]
        self.is_running = True

        # Musical state
        self.root_note = "C"
        self.scale_name = "Pentatonic Minor"

        # Jam state
        self.mode = AgentMode.ACCOMPANY
        self.bar_count = 0
        self.beats_per_bar = 4
        self.subdivision = 2  # 8th notes by default (2 hits per beat)

        # Personality - influenced by style
        self.reactivity = 0.8
        self.complexity_bias = 0.5
        self.on_play_callback: Optional[callable] = None

        # Jam personality/endurance model
        self.endurance = 1.0
        self.personality_aggression = 0.5
        self.personality_restraint = 0.5
        self.endurance_drain_rate = 0.06
        self.endurance_recovery_rate = 0.10
        self._rest_ticks_remaining = 0

        # Linear Scrolling Visualization
        from collections import deque
        self.rolling_visual_history: deque = deque(maxlen=64)
        self.last_step_idx: int = -1
        self.buffered_scrolling_hits: List[int] = []

        # Chord Context (shared across melodic agents)
        self.current_chord_root = "C"
        self.current_chord_type = "Major"

        # Tracking active notes to prevent stuck notes
        self._playing_notes: set = set()

        # Rhythmic Motif (Boolean pattern for 8 bars)
        self.history_length_bars = 8
        self.motif: List[bool] = []
        self.generate_motif()

        # Grid Pattern (like brain's groove_pattern)
        self.pattern: Dict[int, List[tuple]] = {}  # {tick_idx: [(note, velocity), ...]}

        # Timer cleanup
        self._active_timers: List[threading.Timer] = []

    def generate_motif(self) -> None:
        """Generates a rhythmic pattern based on subdivision and style (8 bars long)."""
        steps_per_bar = self.beats_per_bar * self.subdivision
        total_steps = steps_per_bar * self.history_length_bars

        # Style-Specific Rhythmic Anchors (Indices within a single bar)
        # These beats will have much higher probability of being 'True'
        anchors = []
        if self.style == PlayingStyle.ROCK:
            # Quarter note downbeats
            anchors = [i * self.subdivision for i in range(self.beats_per_bar)]
        elif self.style == PlayingStyle.LATIN:
            # Simplified Clave pattern (3-2)
            # Bar 1: 0, 1.5, 3 | Bar 2: 1, 2
            # For 8th note subdivision (sub=2): 0, 3, 6 (Bar 1) | 2, 4 (Bar 2)
            anchors = [0, 3, 6, 10, 12] # Rough mapping
        elif self.style == PlayingStyle.FUNK:
            # "The One" is everything. Plus 16th note syncopations
            anchors = [0, 7, 11] if self.subdivision == 4 else [0, 3]
        elif self.style in [PlayingStyle.JAZZ, PlayingStyle.BLUES]:
            # Shuffle feel (emphasis on beats 1 and 3, and the 'and')
            anchors = [0, 2, 4, 6] if self.subdivision == 2 else [0, 3, 6, 9]

        style_density_mod = {
            PlayingStyle.ROCK: 0.0,
            PlayingStyle.JAZZ: 0.2,
            PlayingStyle.HIP_HOP: -0.1,
            PlayingStyle.BLUES: -0.05,
            PlayingStyle.FUNK: 0.15,
            PlayingStyle.LATIN: 0.1,
        }

        density = 0.3 + (self.complexity_bias * 0.4) + style_density_mod.get(self.style, 0.0)
        density = max(0.1, min(0.9, density))

        self.motif = [random.random() < density for _ in range(total_steps)]

        # Apply Anchors Across All 8 Bars
        for b in range(self.history_length_bars):
            for a in anchors:
                if a < steps_per_bar:
                    self.motif[b * steps_per_bar + a] = True

            # Additional emphasis on the very first beat of the 8-bar phrase
            if b == 0:
                self.motif[0] = True


    def update_theory(self, root: str, scale: str) -> None:
        """Update root note and scale, optionally regenerating motif."""
        self.root_note = root
        self.scale_name = scale
        if random.random() > 0.5:
            self.generate_motif()

    def update_chord_context(self, root: str, chord_type: str) -> None:
        """Update the current chord being played."""
        self.current_chord_root = root
        self.current_chord_type = chord_type

    def setup_grid(self, beats_per_bar: int, subdivision: int) -> None:
        """Setup grid parameters."""
        self.beats_per_bar = beats_per_bar
        self.subdivision = subdivision
        self.generate_motif()

    def stop(self) -> None:
        """Stop the agent and clean up active timers."""
        self.is_running = False

        # Kill all currently playing notes
        playing = list(self._playing_notes)
        for note in playing:
            self.midi.send_message([0x80 | self.channel, note, 0])
        self._playing_notes.clear()

        # Cancel all pending note-off timers
        for timer in self._active_timers:
            timer.cancel()
        self._active_timers.clear()

    def tick(self, state: Dict[str, Any], beat: int, sub_beat: int) -> None:
        """Called 12 times per beat. 0<=sub_beat<12."""
        if not self.is_running or self.mode == AgentMode.SILENT:
            return

        # Update endurance once per beat.
        if sub_beat == 0:
            self.update_endurance_from_state(state)
            if state.get("is_jam_mode"):
                space = max(0.0, min(1.0, state.get("section_space_bias", 0.3)))
                # Lower endurance and higher space bias encourage intentional rests.
                rest_prob = max(0.0, min(0.75, space * (1.15 - self.endurance)))
                if random.random() < rest_prob:
                    self._rest_ticks_remaining = 12

        if self._rest_ticks_remaining > 0:
            self._rest_ticks_remaining -= 1
            return

        step_size = 12 // self.subdivision
        if sub_beat % step_size == 0:
            step_in_beat = sub_beat // step_size
            # Calculate motif index across 8 bars
            steps_per_bar = self.beats_per_bar * self.subdivision
            bar_idx = self.brain.current_bar % self.history_length_bars
            motif_idx = (bar_idx * steps_per_bar) + (beat * self.subdivision) + step_in_beat

            if not self.motif:
                self.generate_motif()

            should_play = self.motif[motif_idx % len(self.motif)]
            play_prob = self.calculate_play_probability(state)

            if should_play and random.random() < (play_prob + 0.2):
                self.play_note(state, beat, sub_beat)
            elif not should_play and random.random() < 0.05:
                # 5% chance of a "ghost" note even if motif says no
                self.play_note(state, beat, sub_beat, ghost=True)

    def calculate_play_probability(self, state: Dict[str, Any]) -> float:
        """Calculate probability of playing based on mode and state."""
        base = 0.5 if self.mode == AgentMode.SOLO else 0.3
        reactivity = state["complexity"] * self.reactivity
        prob = base + reactivity

        # Listening for gaps (Dialogic Playing)
        # If no one has played in the last 8 ticks (roughly a half beat), increase prob
        # If many people have played, decrease prob to avoid clutter
        recent_agents = self.get_recent_activity(self.brain.last_sub_beat, 0, window_ticks=12)

        if not recent_agents:
            prob += 0.2  # Step into the gap
        elif len(recent_agents) >= 2:
            prob -= 0.15 # Back off, room is crowded

        # In Jam mode, endurance and personality influence pacing.
        if state.get("is_jam_mode"):
            section_density = max(0.0, min(1.0, state.get("section_density_target", 0.5)))
            section_space = max(0.0, min(1.0, state.get("section_space_bias", 0.3)))

            # Density target scales overall activity by section.
            prob *= (0.5 + (0.9 * section_density))

            if self.endurance < 0.25:
                prob *= 0.45 + (0.2 * self.personality_aggression)
            elif self.endurance < 0.5:
                prob *= 0.75 + (0.2 * self.personality_aggression)

            # Restraint encourages leaving space at higher energies.
            energy = max(0.0, min(1.0, state.get("energy_norm", 0.5)))
            prob -= self.personality_restraint * energy * 0.18
            prob -= section_space * 0.12

        return max(0.1, min(0.95, prob))

    def update_endurance_from_state(self, state: Dict[str, Any]) -> None:
        """Update endurance using tempo/energy/complexity pressure and recovery."""
        bpm = max(40.0, float(state.get("bpm", 120.0)))
        tempo_norm = max(0.0, min(1.0, (bpm - 40.0) / 200.0))
        energy = max(0.0, min(1.0, state.get("energy_norm", 0.5)))
        complexity = max(0.0, min(1.0, state.get("complexity", 0.3)))

        # Role pressure: soloists deplete faster than accompanists.
        role_pressure = 1.2 if self.mode == AgentMode.SOLO else 0.9

        cost = self.endurance_drain_rate * role_pressure * (
            0.45 * energy +
            0.35 * tempo_norm +
            0.20 * complexity
        )
        recovery = self.endurance_recovery_rate * (1.0 - energy) * (0.7 + (0.3 * self.personality_restraint))

        self.endurance = max(0.0, min(1.0, self.endurance - cost + recovery))


    def get_recent_activity(self, beat: int, sub_beat: int, window_ticks: int = 12) -> List[str]:
        """Returns list of other agent names who played in the recent history window."""
        active_agents = []
        total_ticks_per_bar = self.beats_per_bar * 12
        current_abs = (self.brain.current_bar * total_ticks_per_bar + beat * 12 + sub_beat)

        for t in range(current_abs - window_ticks, current_abs):
            if t < 0: continue
            hist_idx = t % self.brain.total_history_ticks
            for agent_name, history in self.brain.agent_history.items():
                if agent_name == self.name: continue
                if history[hist_idx]:
                    if agent_name not in active_agents:
                        active_agents.append(agent_name)
        return active_agents

    def play_note(self, state: Dict[str, Any], beat: int, sub_beat: int, ghost: bool = False) -> None:
        """Play a note from the current scale."""
        if not self.midi.is_out_open():
            return

        notes = MusicTheory.get_notes_in_key(self.root_note, self.scale_name, octaves=self.octave_range)
        if not notes:
            return

        note = random.choice(notes)
        velocity = int(state["intensity"] * self.reactivity)
        if ghost:
            velocity = int(velocity * 0.5)

        velocity = max(40, min(100, velocity))

        # Send Note On
        self.midi.send_message([0x90 | self.channel, note, velocity])
        self._playing_notes.add(note)

        # Schedule Note Off with cleanup
        duration = 0.1
        timer = threading.Timer(
            duration,
            lambda: self._note_off_with_cleanup(note, timer)
        )
        self._active_timers.append(timer)
        timer.start()

        # Record to pattern grid
        grid_idx = (beat * 12) + sub_beat
        if grid_idx not in self.pattern:
            self.pattern[grid_idx] = []
        self.pattern[grid_idx].append((note, velocity))

        # Buffer for scrolling visual
        self.buffered_scrolling_hits.append(note)

        # Log to shared history in brain for inter-agent "listening"
        self.brain.log_agent_activity(self.name, beat, sub_beat, note, velocity)

        if self.on_play_callback:
            self.on_play_callback(self.name, note)

    def advance_scrolling_history(self, bar_beat: int, sub_beat: int, hits: list = None) -> None:
        """Advance the melodic scrolling visual history by one 16th note step."""
        step_idx = sub_beat // 3
        current_global_step = (bar_beat * 4) + step_idx

        if current_global_step == self.last_step_idx:
            # Update existing dot if a note fired mid-step
            if self.buffered_scrolling_hits and self.rolling_visual_history:
                if self.rolling_visual_history[0] == ". ":
                    self.rolling_visual_history[0] = "N "
                    self.buffered_scrolling_hits.clear()
            return

        self.last_step_idx = current_global_step

        symbol = ". "
        if self.buffered_scrolling_hits:
            symbol = "N "
            self.buffered_scrolling_hits.clear()

        if bar_beat == 0 and step_idx == 0:
            self.rolling_visual_history.appendleft("| ")

        self.rolling_visual_history.appendleft(symbol)

    def get_scrolling_visual(self) -> str:
        """Returns the scrolling history as a single-line string with a fixed 'now' marker."""
        from jam_shed.tui.visual import render_scrolling_visual
        return render_scrolling_visual(self.rolling_visual_history)

    def _note_off_with_cleanup(self, note: int, timer: threading.Timer) -> None:
        """Send note off and remove timer from active list."""
        if self.is_running:
            self.midi.send_message([0x80 | self.channel, note, 0])
            if note in self._playing_notes:
                self._playing_notes.remove(note)
        try:
            self._active_timers.remove(timer)
        except ValueError:
            pass  # Timer already removed

    def get_groove_visual_rich(self, current_bar_beat: int, current_sub_beat: int, beats_per_bar: Optional[int] = None) -> str:
        """Returns Textual-markup visualization matching the human groove format."""
        b_per_bar = beats_per_bar if beats_per_bar is not None else self.beats_per_bar

        parts = []
        subdivision = 4  # Show as 16th notes
        step_size = 3    # 12 ticks / 4 steps = 3 ticks per 16th

        step_idx = current_sub_beat // step_size
        global_active_idx = (current_bar_beat * subdivision) + step_idx

        for b in range(b_per_bar):
            beat_parts = []
            for s in range(subdivision):
                start_tick = (b * 12) + (s * step_size)

                # Aggregate hits in this step
                hits = []
                for t in range(start_tick, start_tick + step_size):
                    if t in self.pattern:
                        hits.extend(self.pattern[t])

                if hits:
                    val = "N"  # Generic note indicator for melodic instruments
                else:
                    val = "."

                val_str = val.ljust(2) + " " # Standardized 3-char width

                current_idx = (b * subdivision) + s
                if current_idx == global_active_idx:
                    beat_parts.append(f"[reverse green]{val_str}[/]")
                else:
                    if val == ".":
                        beat_parts.append(f"[dim]{val_str}[/]")
                    else:
                        beat_parts.append(f"[bold white]{val_str}[/]")

            parts.append(f"| {''.join(beat_parts)} |")

        return " ".join(parts)
