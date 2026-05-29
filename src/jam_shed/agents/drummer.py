"""
VirtualDrummer - AI drummer that plays learned groove patterns.
"""
import random
import threading
from typing import Dict, Any, Optional, List, Tuple
from jam_shed.agents.base import VirtualInstrumentalist, PlayingStyle, AgentMode
from jam_shed.agents.style_calibration import get_drum_phrase_fill_multiplier
from jam_shed.midi.engine import MIDIEngine
from jam_shed.core.brain import RhythmicBrain


# GM Drum Map (General MIDI Standard on Channel 10)
DRUM_MAP = {
    "kick": 36,
    "snare": 38,
    "closed_hihat": 42,
    "open_hihat": 46,
    "low_tom": 45,
    "mid_tom": 47,
    "high_tom": 50,
    "crash": 49,
    "ride": 51,
}


class VirtualDrummer(VirtualInstrumentalist):
    """AI drummer that plays with structured grooves, ostinatos, and fills."""

    def __init__(
        self,
        name: str,
        midi_engine: MIDIEngine,
        brain: RhythmicBrain,
        channel: int = 9, # Drummers always use MIDI channel 10 (index 9)
        style: PlayingStyle = PlayingStyle.ROCK,
        **kwargs
    ):
        super().__init__(name, midi_engine, brain, channel=channel, style=style, **kwargs)

        # Drummer settings
        self.subdivision = 4  # 16th resolution
        self.complexity_bias = 0.5
        self.current_groove_mode = "GROOVE" # GROOVE or FILL

        # Ostinato patterns (set of ticks (0-47))
        self.kick_ostinato = set()
        self.last_ostinato_bar = -1

        # Style-specific kit emphasis
        self.kit_config = self._configure_kit_for_style(style)
        self.generate_motif()

    def _generate_kick_ostinato(self):
        """Generates a steady 1-bar kick pattern to be used as an ostinato."""
        self.kick_ostinato = {0} # Always on 1

        # Add a few more hits based on style
        if self.style == PlayingStyle.ROCK or self.style == PlayingStyle.BLUES:
            # Simple 1 and 3 feel or steady 8ths
            if random.random() < 0.7: self.kick_ostinato.add(24) # Beat 3
            if random.random() < 0.3: self.kick_ostinato.add(18) # Beat 2&
        elif self.style == PlayingStyle.FUNK or self.style == PlayingStyle.HIP_HOP:
            # More syncopated
            candidates = [6, 12, 18, 30, 36, 42]
            for c in random.sample(candidates, 2):
                self.kick_ostinato.add(c)
        elif self.style == PlayingStyle.JAZZ:
            # Feathering the kick (all beats usually, but very light - we'll just do 1 and 3)
            self.kick_ostinato.add(24)

    def _configure_kit_for_style(self, style: PlayingStyle) -> Dict[str, float]:
        """Configure drum kit emphasis based on style."""
        configs = {
            PlayingStyle.ROCK: {"kick": 1.0, "snare": 1.0, "closed_hihat": 0.9, "open_hihat": 0.3, "crash": 0.2},
            PlayingStyle.JAZZ: {"kick": 0.4, "snare": 0.6, "closed_hihat": 0.4, "ride": 1.0, "open_hihat": 0.5},
            PlayingStyle.HIP_HOP: {"kick": 1.0, "snare": 0.9, "closed_hihat": 1.0, "open_hihat": 0.1},
            PlayingStyle.FUNK: {"kick": 1.0, "snare": 0.8, "closed_hihat": 1.0, "open_hihat": 0.4},
            PlayingStyle.LATIN: {"kick": 0.6, "snare": 0.7, "closed_hihat": 0.5, "ride": 0.8, "high_tom": 0.6},
            PlayingStyle.BLUES: {"kick": 0.8, "snare": 0.7, "closed_hihat": 0.6, "ride": 0.5, "open_hihat": 0.4},
        }
        return configs.get(style, configs[PlayingStyle.ROCK])

    def tick(self, state: Dict[str, Any], beat: int, sub_beat: int) -> None:
        """Called 12 times per beat. Overrides base to use structured logic."""
        if not self.is_running or self.mode == AgentMode.SILENT:
            return

        if sub_beat == 0:
            self.update_endurance_from_state(state)

        # In this overhaul, we don't use the motif/pattern logic of the base class
        # We use the structured logic in play_note (dispatched to groove/fill)
        self.play_note(state, beat, sub_beat)

    def play_note(self, state: Dict[str, Any], beat: int, sub_beat: int, ghost: bool = False) -> None:
        """Play drum hits based on structured groove/fill logic."""
        if not self.midi.is_out_open():
            return

        intensity = state.get("intensity", 80)
        current_bar = self.brain.current_bar
        phase = state.get("phase", "")
        grid_idx = (beat * 12) + sub_beat
        total_bar_beat = (beat * 12) + sub_beat

        # 1. Update Mode & Ostinato on Bar Start
        if beat == 0 and sub_beat == 0:
            # Change kick ostinato every 4 bars for variety
            if current_bar % 4 == 0:
                self._generate_kick_ostinato()

            # Determine Mode (Groove vs Fill)
            # 12-bar Cycle: Match phase names from session.py
            # Groove Mode: "AI GROOVE (Copying You)"
            # Shed Mode: "HUMAN FILL (AI Groove)", "AI FILL (Human Groove)"
            if "AI GROOVE" in phase or "AI Groove" in phase:
                self.current_groove_mode = "LEARNED_GROOVE"
            elif "AI FILL" in phase:
                self.current_groove_mode = "RESPONSE_FILL"
                # Prepare fill skeleton at the start of the turn (or every 4 bars)
                if current_bar % 4 == 0 or not hasattr(self, '_fill_skeleton'):
                    self._prepare_response_fill()
            else:
                self.current_groove_mode = "GROOVE"

        # 2. Logic Dispatch
        if self.current_groove_mode == "RESPONSE_FILL":
            self._generate_response_fill(beat, sub_beat, state, intensity)
        elif self.current_groove_mode == "LEARNED_GROOVE":
            self._generate_learned_groove(beat, sub_beat, state, intensity)
        elif self.current_groove_mode == "FILL":
            self._generate_fill_hit(beat, sub_beat, state, intensity)
        else:
            self._generate_groove_hit(beat, sub_beat, state, intensity, ghost)

    def _prepare_response_fill(self):
        """Phase 1: Pre-generate a 4-bar fill skeleton from the human's fill."""
        fill_pattern = self.brain.get_pattern_data("fill")
        ticks_per_bar = 48  # 4 beats * 12 sub-beats
        total_ticks = ticks_per_bar * 4  # 4 bars

        # Extract human's rhythmic density per bar
        human_hits_per_bar = [0] * 4
        for tick in fill_pattern:
            bar = tick // ticks_per_bar
            if bar < 4:
                human_hits_per_bar[bar] += len(fill_pattern[tick])

        avg_density = max(sum(human_hits_per_bar) / 4, 2)  # At least 2 hits/bar

        # Generate skeleton: place hits on 16th-note boundaries (every 3 ticks)
        skeleton = {}  # tick -> voice_hint ("accent" or "ghost")
        for bar in range(4):
            # Slight build over 4 bars, capped at a tasteful maximum
            bar_density = min(avg_density * (1 + bar * 0.15), 10)
            for step in range(16):  # 16th notes per bar
                tick = (bar * ticks_per_bar) + (step * 3)
                # Always accent downbeats with moderate probability
                if step % 4 == 0:
                    if random.random() < 0.55:
                        skeleton[tick] = "accent"
                # Fill in between steps based on density
                elif random.random() < (bar_density / 32):
                    skeleton[tick] = "ghost" if step % 2 == 1 else "accent"

        self._fill_skeleton = skeleton

    def _generate_response_fill(self, beat: int, sub: int, state: Dict[str, Any], intensity: int):
        """Phase 2: Play pre-generated fill skeleton with orchestrated voices."""
        if not hasattr(self, '_fill_skeleton') or not self._fill_skeleton:
            return

        bar_in_phrase = self.brain.current_bar % 4
        ticks_per_bar = 48
        abs_tick = (bar_in_phrase * ticks_per_bar) + (beat * 12) + sub

        if abs_tick not in self._fill_skeleton:
            return

        hint = self._fill_skeleton[abs_tick]

        # Orchestrate based on position in the 4-bar fill
        if hint == "accent":
            # Tom cascade: high → mid → low → floor over bars
            tom_sequence = [50, 47, 45, 41]  # High Tom, Mid Tom, Low Tom, Floor Tom
            note = tom_sequence[min(bar_in_phrase, 3)]
            vel = int(intensity * 1.05)
        else:  # "ghost"
            note = 38  # Snare ghost note
            vel = int(intensity * 0.55)

        self._play_drum_hit(note, vel, beat, sub)

    def _generate_learned_groove(self, beat: int, sub: int, state: Dict[str, Any], intensity: int):
        """AI Groove Phase: Reproduce the human's groove from earlier.

        Plays back the exact 4-bar recording bar-by-bar, using bars_elapsed
        from the session to look up the correct absolute tick index.
        """
        groove_pattern = self.brain.get_pattern_data("groove")
        ticks_per_bar = 48  # 4 beats * 12 sub-beats

        # Use bars_elapsed % 4 to match the recording's bar index
        bars_elapsed = state.get("bars_elapsed", 0)
        bar_in_phrase = bars_elapsed % 4
        abs_tick = (bar_in_phrase * ticks_per_bar) + (beat * 12) + sub

        if abs_tick in groove_pattern:
            for note, vel in groove_pattern[abs_tick]:
                self._play_drum_hit(note, vel, beat, sub)

    def _generate_groove_hit(self, beat: int, sub_beat: int, state: Dict[str, Any], intensity: int, ghost: bool):
        """Steady timekeeping and ostinato-based groove."""
        grid_idx = (beat * 12) + sub_beat

        # --- CRASH: Only on the release (Bar 0, Beat 0) ---
        if beat == 0 and sub_beat == 0 and self.brain.current_bar % 4 == 0:
            self._play_drum_hit(DRUM_MAP["crash"], int(intensity * 1.2), beat, sub_beat)

        # --- KICK: Ostinato ---
        if grid_idx in self.kick_ostinato:
            self._play_drum_hit(DRUM_MAP["kick"], int(intensity * 1.1), beat, sub_beat)

        # --- SNARE: Backbeats (2 and 4) ---
        if sub_beat == 0 and beat in [1, 3]:
            if random.random() < 0.95:
                self._play_drum_hit(DRUM_MAP["snare"], intensity, beat, sub_beat)
        elif sub_beat == 6 and random.random() < 0.1: # Light ghost snares
             self._play_drum_hit(DRUM_MAP["snare"], intensity // 3, beat, sub_beat)

        # Phrase transition fills near 8-bar boundaries in Jam mode.
        if self._is_phrase_fill_window(state, beat, sub_beat):
            self._play_phrase_transition_fill(state, beat, sub_beat, intensity)

        # --- TIMEKEEPING: HH / Ride (Steady 8ths or 16ths) ---
        recent_human_activity = self.brain.get_pattern_data("groove")
        human_ride = any(51 in [h[0] for h in hits] for hits in recent_human_activity.values())
        use_ride = (intensity > 105 or human_ride or self.style == PlayingStyle.JAZZ)
        timekeeper = DRUM_MAP["ride"] if use_ride else DRUM_MAP["closed_hihat"]

        # Steady 8th notes (always play)
        if sub_beat == 0 or sub_beat == 6:
            vel = intensity if sub_beat == 0 else int(intensity * 0.7) # Accent on the beat
            self._play_drum_hit(timekeeper, vel, beat, sub_beat)

        # Optional 16th fillers (syncopated/tight feel)
        elif sub_beat in [3, 9] and (self.style in [PlayingStyle.FUNK, PlayingStyle.HIP_HOP] or intensity > 90):
            if random.random() < 0.6:
                self._play_drum_hit(timekeeper, int(intensity * 0.5), beat, sub_beat)

    def _is_phrase_fill_window(self, state: Dict[str, Any], beat: int, sub_beat: int) -> bool:
        """Return True in the final beat of each 8-bar phrase during Jam mode."""
        if not state.get("is_jam_mode"):
            return False
        if beat != 3 or sub_beat not in [0, 3, 6, 9]:
            return False

        bars_in_section = int(state.get("jam_section_bars", 0))
        # Trigger on bars 8, 16, 24, ... of a section.
        return (bars_in_section + 1) % 8 == 0

    def _play_phrase_transition_fill(self, state: Dict[str, Any], beat: int, sub_beat: int, intensity: int) -> None:
        """Play tasteful fills when approaching phrase boundaries."""
        section = state.get("jam_section", "")
        fill_probs = {
            "INTRO": 0.20,
            "GROOVE_ESTABLISH": 0.45,
            "CONVERSATION": 0.65,
            "SPOTLIGHT": 0.70,
            "RETURN_GROOVE": 0.50,
            "OUTRO": 0.25,
        }

        final_fill_prob = fill_probs.get(section, 0.45) * get_drum_phrase_fill_multiplier(self.style)

        if random.random() > final_fill_prob:
            return

        # Simple descending tom cadence through the last beat.
        note_by_sub = {
            0: DRUM_MAP["snare"],
            3: DRUM_MAP["high_tom"],
            6: DRUM_MAP["mid_tom"],
            9: DRUM_MAP["low_tom"],
        }
        note = note_by_sub.get(sub_beat, DRUM_MAP["snare"])
        vel = int(intensity * (0.85 if sub_beat == 0 else 1.0))
        self._play_drum_hit(note, vel, beat, sub_beat)

    def _generate_fill_hit(self, beat: int, sub_beat: int, state: Dict[str, Any], intensity: int):
        """Snare and Tom based builds/fills."""
        # Fills get busier as they approach the end of the bar
        fill_density = (beat + 1) / 4.0 # 0.25 to 1.0

        # Higher probability of playing on 8th or 16th boundaries
        is_sub_boundary = (sub_beat % 3 == 0)

        if is_sub_boundary and random.random() < fill_density:
            # Choose voice: Snare or Toms
            r = random.random()
            if r < 0.4:
                note = DRUM_MAP["snare"]
            elif r < 0.6:
                note = DRUM_MAP["high_tom"]
            elif r < 0.8:
                note = DRUM_MAP["mid_tom"]
            else:
                note = DRUM_MAP["low_tom"]

            vel = int(intensity * (0.8 + 0.4 * random.random()))
            self._play_drum_hit(note, vel, beat, sub_beat)

        # Keep the kick on 1 and 3 during fills for stability
        if sub_beat == 0 and beat in [0, 2]:
            self._play_drum_hit(DRUM_MAP["kick"], intensity, beat, sub_beat)

    def _play_drum_hit(self, note: int, velocity: int, beat: int, sub: int) -> None:
        """Helper to send drum hit and log to brain."""
        self.midi.send_message([0x90 | self.channel, note, velocity])
        self.brain.log_agent_activity(self.name, beat, sub, note, velocity)
        if self.on_play_callback:
            self.on_play_callback(self.name, note)

        # Quick note off (tracked for cleanup)
        timer = threading.Timer(0.05, lambda: self.midi.send_message([0x80 | self.channel, note, 0]))
        self._active_timers.append(timer)
        timer.start()

        # Record and Log
        self.buffered_scrolling_hits.append(note)
        grid_idx = (beat * 12) + sub
        if grid_idx not in self.pattern: self.pattern[grid_idx] = []
        self.pattern[grid_idx].append((note, velocity))

    def advance_scrolling_history(self, bar_beat: int, sub_beat: int, hits: List[Tuple[int, int]]):
        """Advances the scrolling visual history by one 16th note step."""
        step_idx = sub_beat // 3
        current_global_step = (bar_beat * 4) + step_idx

        if not hasattr(self, "rolling_visual_history"):
            from collections import deque
            self.rolling_visual_history = deque(maxlen=64)
            self.last_step_idx = -1

        if current_global_step == self.last_step_idx:
            # Update current step if it was empty but we have hits now
            if hits and self.rolling_visual_history and self.rolling_visual_history[0] == ". ":
                notes = [h[0] for h in hits]
                ds = self._get_drum_symbol(notes)
                if ds: self.rolling_visual_history[0] = ds
            return

        self.last_step_idx = current_global_step

        symbol = ". "
        if not hits and self.buffered_scrolling_hits:
             hits = list(self.buffered_scrolling_hits)
             self.buffered_scrolling_hits.clear()

        # Update symbol based on hits (either passed or buffered)
        if hits:
            # Tuples (note, vel) -> just notes
            notes = [h[0] if isinstance(h, tuple) else h for h in hits]
            ds = self._get_drum_symbol(notes)
            if ds: symbol = ds

        if bar_beat == 0 and step_idx == 0:
            self.rolling_visual_history.appendleft("| ")

        self.rolling_visual_history.appendleft(symbol)

    def _get_drum_symbol(self, notes: List[int]) -> str:
        """Shared symbol mapper for drum agents."""
        has_cr1 = 49 in notes
        has_cr2 = 57 in notes
        if has_cr1 and has_cr2: return "X "
        if has_cr1: return "C "
        if has_cr2: return "c "
        if 51 in notes: return "R "
        if 38 in notes or 40 in notes: return "SN"
        if 42 in notes or 44 in notes or 46 in notes: return "HH"
        if 48 in notes: return "T1"
        if 45 in notes: return "T2"
        if 41 in notes: return "T3"
        if 36 in notes: return "K "
        return None

    def get_scrolling_visual(self) -> str:
        from jam_shed.tui.visual import render_scrolling_visual
        if not hasattr(self, "rolling_visual_history"):
            return "[bold green]▶[/]"
        return render_scrolling_visual(self.rolling_visual_history)

class DrumShedAgent(VirtualDrummer):
    """Specialized Drummer for Shed Mode (TradingSolos)."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Shed mode agents can have different personality if needed
        self.reactivity = 0.95
        self.complexity_bias = 0.7
