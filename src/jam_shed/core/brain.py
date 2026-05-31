"""
Rhythmic learning brain for jam-shed.

The RhythmicBrain analyzes incoming MIDI hits to:
- Track tempo (BPM) adaptively or use fixed BPM
- Calculate musical complexity and intensity
- Learn and store groove patterns and fills
- Provide timing callbacks for synchronized playback
"""

import re
import time
from collections import deque
from typing import Any, Callable, Dict, List, Optional, Tuple

from jam_shed.core.constants import (
    DEFAULT_BPM,
    MAX_BPM,
    MIN_BPM,
    TICKS_PER_BEAT,
    BPMMode,
    RecordingMode,
)


class RhythmicBrain:
    """
    Rhythmic learning engine that tracks tempo, complexity, and musical patterns.

    The brain processes MIDI hits to learn grooves and fills, calculate BPM,
    and provide synchronized timing callbacks for AI agents.
    """

    def __init__(self, beats_per_bar: int = 4, history_size: int = 20):
        """
        Initialize the rhythmic brain.

        Args:
            beats_per_bar: Number of beats per bar (typically 4)
            history_size: Number of hits/intervals to keep in history
        """
        self.beats_per_bar = beats_per_bar
        self.hit_history: deque = deque(maxlen=history_size)  # (timestamp, note, velocity)
        self.interval_history: deque = deque(maxlen=history_size)
        self.bpm: float = DEFAULT_BPM
        self.last_hit_time: float = 0
        self.complexity: float = 0.0  # 0 to 1
        self.intensity: float = 0.0  # 0 to 127
        self.beat_accumulator: float = 0.0
        self.on_beat_callback: Optional[Callable] = None
        self.on_tick_callback: Optional[Callable[[int], None]] = None  # Callback for sub-beats
        self.current_tick: int = 0  # 0 to 47
        self.last_sub_beat: int = -1
        self.is_listening: bool = False

        # Wall-clock timing anchor (set at first musical hit)
        self._beat_zero_time: float = 0.0  # time.time() of beat 0
        self._beats_fired: int = 0  # how many beat callbacks fired so far

        # Timing data collection
        self.human_timings: List[float] = []

        # Pattern Learning (16th note resolution)
        # Each pattern is a dict: { tick_idx (0-47): [(note, velocity), ...] }
        self.groove_pattern: Dict[int, List[Tuple[int, int]]] = {}
        self.fill_pattern: Dict[int, List[Tuple[int, int]]] = {}

        # Buffer for scrolling history visualizer
        self.buffered_scrolling_hits: List[int] = []
        self.current_recording: str = RecordingMode.GROOVE.value
        self.is_jamming: bool = False
        self.current_bar: int = 0

        # Shared Activity History (8 bars at 48-tick resolution)
        # Each bar is 48 ticks. 8 bars = 384 ticks.
        # { agent_name: [ticks_0_to_383] where each tick is a list of (note, velocity) }
        self.agent_history: Dict[str, List[List[Tuple[int, int]]]] = {}
        self.history_length_bars = 8
        self.total_history_ticks = self.history_length_bars * self.beats_per_bar * TICKS_PER_BEAT

        # Tempo Control
        self.bpm_mode: str = BPMMode.FIXED.value

        # Scrolling Visual History (16th note resolution)
        # deque of strings representing what happened at each step
        self.rolling_visual_history: deque = deque(maxlen=64)
        self.last_step_idx: int = -1  # Track 16th note steps (0-15 for 4/4)

    def capture_scrolling_hit(self, note: int):
        """Captures a hit specifically for the linear scrolling visualizer."""
        self.buffered_scrolling_hits.append(note)

    def _get_drum_symbol(self, notes: List[int]) -> Optional[str]:
        """Map drum MIDI notes to symbols according to user request."""
        # Priorities: Crashes > Ride > Snare > HH > Toms > Kick
        has_cr1 = 49 in notes
        has_cr2 = 57 in notes
        if has_cr1 and has_cr2:
            return "X "
        if has_cr1:
            return "C "
        if has_cr2:
            return "c "

        if 51 in notes:
            return "R "
        if 38 in notes or 40 in notes:
            return "SN"
        if 42 in notes or 44 in notes or 46 in notes:
            return "HH"
        if 48 in notes:
            return "T1"
        if 45 in notes:
            return "T2"
        if 41 in notes:
            return "T3"
        if 36 in notes:
            return "K "

        return None

    def advance_scrolling_history(
        self, bar_beat: int, sub_beat: int, hits: Optional[List[Tuple[int, int]]] = None, is_melodic: bool = False
    ):
        """Advances history. If hits is None, uses self.buffered_scrolling_hits then clears it."""
        step_idx = sub_beat // 3
        current_global_step = (bar_beat * 4) + step_idx

        # Hits to use for this update
        active_notes = []
        if hits:
            active_notes = [h[0] for h in hits]
        elif self.buffered_scrolling_hits:
            active_notes = list(self.buffered_scrolling_hits)

        # If we haven't moved to a new step, we might want to UPDATE the current step's symbol
        if current_global_step == self.last_step_idx:
            if active_notes and self.rolling_visual_history:
                # Update existing symbol if it was just a dot
                if self.rolling_visual_history[0] == ". ":
                    if not is_melodic:
                        ds = self._get_drum_symbol(active_notes)
                        if ds:
                            self.rolling_visual_history[0] = ds
                            if not hits:
                                self.buffered_scrolling_hits.clear()
                    else:
                        from jam_shed.core.theory import MusicTheory

                        self.rolling_visual_history[0] = MusicTheory.get_note_name(active_notes[0]).ljust(2)
                        if not hits:
                            self.buffered_scrolling_hits.clear()
            return

        self.last_step_idx = current_global_step

        # 1. Determine the symbol for this step
        symbol = ". "
        if active_notes:
            if not is_melodic:
                ds = self._get_drum_symbol(active_notes)
                if ds:
                    symbol = ds
            else:
                from jam_shed.core.theory import MusicTheory

                symbol = MusicTheory.get_note_name(active_notes[0]).ljust(2)

            # Clear buffer if we consumed it
            if not hits:
                self.buffered_scrolling_hits.clear()

        # 2. Check for measure boundary
        if bar_beat == 0 and step_idx == 0:
            self.rolling_visual_history.appendleft("| ")

        # 3. Add the step to the left
        self.rolling_visual_history.appendleft(symbol)

    def get_scrolling_visual(self) -> str:
        """Returns the scrolling history as a single-line string with a fixed 'now' marker."""
        from jam_shed.tui.visual import render_scrolling_visual

        return render_scrolling_visual(self.rolling_visual_history)

    def start_listening(self) -> None:
        """Start listening mode to record human playing."""
        self.is_listening = True
        self.human_timings.clear()

    def stop_listening(self) -> None:
        """Stop listening mode."""
        self.is_listening = False

    def notify_hit(self, beat: int, sub_beat: int, note: int, velocity: int) -> None:
        """
        Record a hit during listening mode.

        Args:
            beat: Current beat in the bar
            sub_beat: Sub-beat tick (0-11)
            note: MIDI note number
            velocity: Note velocity (0-127)
        """
        if self.is_listening:
            self.human_timings.append(time.time())
            self.record_to_grid(beat, sub_beat, note, velocity)

    def process_hit(self, note: int, velocity: int) -> None:
        """
        Process an incoming MIDI hit.

        Updates intensity, calculates intervals, and updates BPM if in adaptive mode.

        Args:
            note: MIDI note number
            velocity: Note velocity (0-127)
        """
        current_time = time.time()
        self.intensity = velocity

        if self.last_hit_time > 0:
            interval = current_time - self.last_hit_time
            self.interval_history.append(interval)

            if self.bpm_mode == BPMMode.ADAPTIVE.value:
                self._update_bpm()

            self._update_complexity()

        self.hit_history.append((current_time, note, velocity))
        self.last_hit_time = current_time

    def set_bpm(self, bpm: float) -> None:
        """
        Set the BPM and seed interval history.

        Args:
            bpm: Beats per minute (40-300)
        """
        old_bpm = self.bpm
        self.bpm = max(MIN_BPM, min(MAX_BPM, bpm))
        # Seed history to match new BPM
        if self.bpm > 0:
            interval = 60.0 / self.bpm
            self.interval_history.clear()
            for _ in range(4):
                self.interval_history.append(interval)

        # Re-anchor wall clock if currently jamming so we don't get
        # a burst of catch-up beats from the changed beat_duration.
        if self.is_jamming and self._beat_zero_time > 0 and old_bpm != self.bpm:
            self._beat_zero_time = time.time()
            self._beats_fired = 0
            self.beat_accumulator = 0.0

    def calculate_bpm(self) -> float:
        """
        Calculate BPM from recorded timings.

        Returns:
            Calculated BPM, or current BPM if insufficient data
        """
        if len(self.human_timings) < 4:
            return self.bpm

        intervals = []
        for i in range(1, len(self.human_timings)):
            intervals.append(self.human_timings[i] - self.human_timings[i - 1])

        if intervals:
            avg_interval = sum(intervals) / len(intervals)
            if avg_interval > 0:
                return 60.0 / avg_interval

        return self.bpm

    def reset_beat_clock(self) -> None:
        """
        Anchor the beat clock to the current wall-clock instant.

        Call this synchronously at the moment the first musical hit is detected.
        Beat 0 is assumed to have fired at this instant (caller fires it directly);
        subsequent beats are scheduled by update_time() relative to this timestamp.
        """
        self._beat_zero_time = time.time()
        self._beats_fired = 1  # beat 0 fires synchronously from the caller
        self.beat_accumulator = 0.0
        self.last_sub_beat = -1
        self.is_jamming = True

    def update_time(self, delta: float) -> None:
        """
        Update internal time and fire callbacks.

        Should be called regularly (e.g., every frame) with time delta.
        When jamming, uses wall-clock anchoring (not accumulated deltas) so
        beat intervals are accurate regardless of poll-loop jitter.

        Args:
            delta: Time elapsed since last call (seconds) [kept for API compat]
        """
        if self.bpm <= 0:
            return

        beat_duration = 60.0 / self.bpm

        if not self.is_jamming:
            # Keep accumulator bounded while waiting for first hit
            self.beat_accumulator += delta
            if self.beat_accumulator >= beat_duration:
                self.beat_accumulator %= beat_duration
            return

        # Safety guard: _beat_zero_time must be set before we use it
        if self._beat_zero_time <= 0:
            self.is_jamming = False
            return

        # Wall-clock-anchored timing: compute position relative to _beat_zero_time.
        # This eliminates drift from floating-point delta accumulation and makes
        # every beat accurate to time.time() resolution (~microseconds).
        elapsed = time.time() - self._beat_zero_time
        total_beats = int(elapsed / beat_duration)

        # Fire any beats we haven't fired yet (normally 0 or 1 per call)
        while self._beats_fired <= total_beats:
            self._beats_fired += 1
            if self.on_beat_callback:
                self.on_beat_callback()

        # Keep beat_accumulator updated (used by sub-beat position reads elsewhere)
        self.beat_accumulator = elapsed % beat_duration

        # Handle Sub-Beat Tick (12 steps per beat)
        current_sub = int((self.beat_accumulator / beat_duration) * TICKS_PER_BEAT)
        current_sub = max(0, min(TICKS_PER_BEAT - 1, current_sub))

        if current_sub != self.last_sub_beat:
            self.last_sub_beat = current_sub
            if self.on_tick_callback:
                self.on_tick_callback(current_sub)

    def _update_bpm(self) -> None:
        """Update BPM estimate based on interval history (adaptive mode)."""
        if len(self.interval_history) < 4:
            return

        # Simple BPM estimation based on average intervals
        avg_interval = sum(self.interval_history) / len(self.interval_history)
        if avg_interval > 0:
            estimated_bpm = 60.0 / avg_interval
            # Basic smoothing/clamping
            if MIN_BPM <= estimated_bpm <= MAX_BPM:
                self.bpm = (self.bpm * 0.8) + (estimated_bpm * 0.2)

    def _update_complexity(self) -> None:
        """Calculate complexity metric based on timing variance."""
        if len(self.interval_history) < 5:
            return
        avg = sum(self.interval_history) / len(self.interval_history)
        variance = sum((x - avg) ** 2 for x in self.interval_history) / len(self.interval_history)
        self.complexity = min(1.0, variance * 10)

    def record_to_grid(self, bar_beat: int, sub_beat: int, note: int, velocity: int) -> None:
        """Deprecated: Use record_to_grid_absolute."""
        tick = (bar_beat * TICKS_PER_BEAT) + sub_beat
        self.record_to_grid_absolute(tick, note, velocity)

    def record_to_grid_absolute(self, tick_idx: int, note: int, velocity: int) -> None:
        """Records a hit to a specific tick index (0-191 for 4 bars)."""
        target = self.groove_pattern if self.current_recording == RecordingMode.GROOVE.value else self.fill_pattern
        if tick_idx not in target:
            target[tick_idx] = []
        target[tick_idx].append((note, velocity))

        # Buffer for visualizer
        self.buffered_scrolling_hits.append(note)

    def log_agent_activity(self, agent_name: str, bar_beat: int, sub_beat: int, note: int, velocity: int):
        """Logs what an agent played into the shared history (max 8 bars)."""
        if agent_name not in self.agent_history:
            self.agent_history[agent_name] = [[] for _ in range(self.total_history_ticks)]

        # Calculate absolute tick index in the rolling 8-bar window
        total_ticks_per_bar = self.beats_per_bar * TICKS_PER_BEAT
        abs_tick = (
            self.current_bar * total_ticks_per_bar + bar_beat * TICKS_PER_BEAT + sub_beat
        ) % self.total_history_ticks

        self.agent_history[agent_name][abs_tick].append((note, velocity))

    def notify_bar_elapsed(self):
        """Notify brain that a bar has passed. Increments counter and clears upcoming history."""
        self.current_bar += 1
        # Clear the next bar in history to make room for new notes
        self.clear_agent_history_bar(self.current_bar)

    def clear_agent_history_bar(self, bar_idx: int):
        """Clears a specific bar in the rolling history."""
        total_ticks_per_bar = self.beats_per_bar * TICKS_PER_BEAT
        # Index in the 8-bar rolling history
        start_tick = (bar_idx * total_ticks_per_bar) % self.total_history_ticks
        for t in range(start_tick, start_tick + total_ticks_per_bar):
            idx = t % self.total_history_ticks
            for agent in self.agent_history:
                self.agent_history[agent][idx] = []

    def update_time_signature(self, beats_per_bar: int):
        """Updates the time signature and resizes history buffers."""
        if beats_per_bar == self.beats_per_bar:
            return

        self.beats_per_bar = beats_per_bar
        self.total_history_ticks = self.history_length_bars * self.beats_per_bar * TICKS_PER_BEAT

        # Reset agent history as the indexing has changed
        self.agent_history = {}
        self.current_bar = 0

    def get_beats_per_bar(self) -> int:
        return self.beats_per_bar

    def get_pattern_data(self, pattern_name: str = "groove") -> Dict[int, List[Tuple[int, int]]]:
        """
        Get pattern data.

        Args:
            pattern_name: "groove" or "fill"

        Returns:
            Pattern dictionary mapping tick index to list of (note, velocity) tuples
        """
        return self.groove_pattern if pattern_name == "groove" else self.fill_pattern

    def clear_pattern(self, pattern_name: str = "groove") -> None:
        """
        Clear a pattern.

        Args:
            pattern_name: "groove" or "fill"
        """
        if pattern_name == "groove":
            self.groove_pattern = {}
        else:
            self.fill_pattern = {}

    def reset_history(self) -> None:
        """Clears all history buffers and patterns for a fresh session."""
        self.hit_history.clear()
        self.interval_history.clear()
        self.groove_pattern.clear()
        self.fill_pattern.clear()
        self.human_timings.clear()
        self.buffered_scrolling_hits.clear()
        if hasattr(self, "rolling_visual_history"):
            self.rolling_visual_history.clear()
        self.beat_accumulator = 0.0
        self._beat_zero_time = 0.0
        self._beats_fired = 0
        self.is_jamming = False

    def get_groove_visual_rich(self, current_bar_beat: int, current_sub_beat: int) -> str:
        """Returns a multi-line 4-bar Textual-markup visualization of the current pattern."""
        target = self.groove_pattern if self.current_recording == RecordingMode.GROOVE.value else self.fill_pattern
        num_bars = 4
        beats_per_bar = self.beats_per_bar
        subdivision = 4  # Steps per beat (16th notes)
        step_size = 3  # ticks per step

        # Calculate active step in the 4-bar phrase
        current_bar_in_phrase = getattr(self, "current_bar_in_phrase", 0)
        global_active_idx = (
            (current_bar_in_phrase * beats_per_bar * subdivision)
            + (current_bar_beat * subdivision)
            + (current_sub_beat // step_size)
        )

        # 4 rows: Cymbals, Toms/HH, Snare, Kick
        rows = [[] for _ in range(4)]
        labels = ["[dim]CYM[/]", "[dim]TOM[/]", "[dim]SNR[/]", "[dim]KIK[/]"]

        for bar in range(num_bars):
            bar_cols = [[] for _ in range(4)]
            for b in range(beats_per_bar):
                for s in range(subdivision):
                    tick_idx = (bar * beats_per_bar * TICKS_PER_BEAT) + (b * TICKS_PER_BEAT) + (s * step_size)
                    hits = []
                    # Check the window for this step
                    for t in range(tick_idx, tick_idx + step_size):
                        if t in target:
                            hits.extend(target[t])

                    notes = [h[0] for h in hits]
                    has_kick = 36 in notes
                    has_snare = any(n in [38, 40] for n in notes)
                    has_tom = any(n in [41, 45, 47, 48, 50] for n in notes)
                    has_hh = any(n in [42, 44, 46] for n in notes)
                    has_crash = any(n in [49, 57] for n in notes)
                    has_ride = 51 in notes

                    syms = ["·", "·", "·", "·"]
                    if has_crash:
                        syms[0] = "C"
                    elif has_ride:
                        syms[0] = "R"
                    if has_tom:
                        syms[1] = "T"
                    elif has_hh:
                        syms[1] = "H"
                    if has_snare:
                        syms[2] = "S"
                    if has_kick:
                        syms[3] = "K"

                    is_active = (bar * beats_per_bar * subdivision) + (b * subdivision) + s == global_active_idx
                    for i in range(4):
                        char = syms[i]
                        style = "reverse green" if is_active else ("bold yellow" if char != "·" else "wide dim")
                        bar_cols[i].append(f"[{style}]{char}[/]")

            for i in range(4):
                rows[i].append(f"| {' '.join(bar_cols[i])}")

        lines = []
        for i in range(4):
            bar_content = " ".join(rows[i]) + " |"
            lines.append(f"{labels[i]} {bar_content}")

        return "\n".join(lines)

    def get_grid_visual(self) -> str:
        """Get plain text visualization without markup."""
        raw = self.get_groove_visual_rich(0, 0)
        return re.sub(r"\[.*?\]", "", raw)

    def get_current_state(self) -> Dict[str, Any]:
        """
        Get current brain state for agents to use.

        Returns:
            Dictionary with complexity, intensity, and density metrics
        """
        return {
            "complexity": self.complexity,
            "intensity": max(60, self.intensity),
            "density": min(1.0, len(self.groove_pattern) / 48.0),
        }

    def get_agent_energy(self) -> float:
        """Returns a 0-127 energy value based on recent agent note activity.

        Scans the last beat's worth of ticks in agent_history and returns the
        average velocity across all agents, or 0 if no recent activity exists.
        This is used by the Jam mode energy visualizer so that AI-driven notes
        register as energy even when the human is not playing.
        """
        recent_velocities: list = []
        total_ticks_per_bar = self.beats_per_bar * TICKS_PER_BEAT
        current_abs = (self.current_bar * total_ticks_per_bar) % self.total_history_ticks
        # Scan the last full beat (TICKS_PER_BEAT ticks) in the ring buffer
        for offset in range(TICKS_PER_BEAT):
            tick = (current_abs - 1 - offset) % self.total_history_ticks
            for history in self.agent_history.values():
                for _note, velocity in history[tick]:
                    recent_velocities.append(velocity)
        if not recent_velocities:
            return 0.0
        return sum(recent_velocities) / len(recent_velocities)

    def get_state(self) -> Dict[str, Any]:
        """
        Get full state including visualization (for UI).

        Returns:
            Dictionary with BPM, intensity, complexity, pattern info, and visualization
        """
        return {
            "bpm": round(self.bpm, 1),
            "intensity": round(self.intensity, 1),
            "complexity": round(self.complexity, 1),
            "rhythm_pattern": self.current_recording.upper(),
            "visual": self.get_grid_visual(),
            "current_tick": self.current_tick,
        }
