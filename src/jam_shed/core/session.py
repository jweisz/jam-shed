import threading
import time
from typing import List, Dict, Optional
from jam_shed.agents.base import VirtualInstrumentalist, AgentMode
from jam_shed.utils.debug import debug_log

class JamSession:
    def __init__(self, agents: Optional[List[VirtualInstrumentalist]] = None, brain=None):
        self._lock = threading.Lock()
        self.agents = agents if agents is not None else []
        self.brain = brain
        self.bars_per_solo = 4
        self.beats_per_bar = 4
        self.current_soloist: Optional[str] = "Human" # "Human" or Agent Name
        self.bars_elapsed = 0
        self.beats_elapsed = 0 # 0-indexed count within bar
        self.is_trading = False
        self.is_groove = False
        self.waiting_for_first_hit = True
        self.is_leadin = False
        self.bars_per_cycle = 12
        self.current_phase = "Waiting for First Hit..."
        self.on_bar_elapsed: Optional[callable] = None

        # Musical Context
        self.key_root = "C"
        self.scale_name = "Pentatonic Minor"
        self.progression_name = "12-Bar Blues"
        self.chord_sequence = []
        self.current_chord = ("C", "Minor") # (Root, Type)
        self.chord_index = 0

    def start_first_hit(self):
        """First hit detected: Enter 1-bar lead-in countdown."""
        # Set lead-in flag FIRST to prevent race condition with clock thread
        self.is_leadin = True
        self._leadin_ending = False
        self.waiting_for_first_hit = False
        self.bars_elapsed = -1  # notify_bar_elapsed will increment to 0
        self.beats_elapsed = 0
        self.current_soloist = "READYING..."
        self.current_phase = "COUNT-IN"
        debug_log("SESSION: First Hit Started -> Lead-in Mode")

    def update_theory(self, key: str, scale: str, progression: str = "12-Bar Blues"):
        from jam_shed.core.theory import MusicTheory
        self.key_root = key
        self.scale_name = scale
        self.progression_name = progression
        self.chord_sequence = MusicTheory.get_progression_chords(key, scale, progression)
        self.chord_index = 0
        if self.chord_sequence:
            self.current_chord = self.chord_sequence[0]

    def notify_beat_elapsed(self):
        """Called by the brain's beat callback."""
        with self._lock:
            self._notify_beat_elapsed_unlocked()

    def _notify_beat_elapsed_unlocked(self):
        if self.waiting_for_first_hit:
            return

        # Complete deferred lead-in transition (set on the previous beat)
        if getattr(self, '_leadin_ending', False):
            self._leadin_ending = False
            self.is_leadin = False
            self.beats_elapsed = -1  # will be incremented to 0 below
            if self.is_groove:
                self.current_soloist = "Human"
                self.current_phase = "YOUR GROOVE (AI Listening)"
            elif self.is_trading:
                self.current_soloist = "Human"
                self.current_phase = "GROOVE: Human (AI Listening)"
            else:
                self.current_soloist = "Human"
                self.current_phase = "JAMMING"
            debug_log(f"SESSION: Lead-in Complete. Mode: {'Groove' if self.is_groove else ('Shed' if self.is_trading else 'Jam')}")
            if hasattr(self, "_update_agent_modes"):
                self._update_agent_modes()
            self.notify_bar_elapsed()

        self.beats_elapsed += 1

        # Lead-in handling: mark for deferred transition on the NEXT beat
        # so this beat's UI still sees is_leadin=True (display stays blank).
        if self.is_leadin:
            if self.beats_elapsed >= self.beats_per_bar:
                debug_log("SESSION: Lead-in final beat. Transition deferred to next beat.")
                self._leadin_ending = True
            return

        debug_log(f'SESSION: Beat {self.beats_elapsed}/{self.beats_per_bar}')

        if self.beats_elapsed >= self.beats_per_bar:
            self.beats_elapsed = 0
            debug_log(f"SESSION: Bar Elapsed ({self.bars_elapsed + 1})")
            self.notify_bar_elapsed()

    def start_groove(self):
        """Start Groove mode: 8-bar call-and-response."""
        self.is_groove = True
        self.is_trading = False
        self.bars_per_cycle = 8
        self.bars_elapsed = 0
        self.current_soloist = "Human"
        self.current_phase = "Waiting for Start..."
        self._update_agent_modes()

    def stop_groove(self):
        self.is_groove = False
        self.current_soloist = "Human"
        self.current_phase = "JAMMING"
        self._update_agent_modes()

    def start_trading(self, bars: int = 4):
        self.is_trading = True
        self.bars_per_solo = bars
        self.bars_elapsed = 0
        self.current_soloist = "Human"
        self.current_phase = "Waiting for Start..."
        self._update_agent_modes()

    def stop_trading(self):
        self.is_trading = False
        self.current_soloist = "Human" # Default back to human
        self.current_phase = "JAMMING"
        self._update_agent_modes()

    def notify_bar_elapsed(self):
        if self.waiting_for_first_hit:
            return

        self.bars_elapsed += 1

        # LOG: Detailed transition
        debug_log(f"SESSION: Bar {self.bars_elapsed} (Trading: {self.is_trading})")

        if self.on_bar_elapsed:
            self.on_bar_elapsed()

        # Advance Chord Progression (Should happen in Jam mode too)
        if self.chord_sequence:
             self.chord_index = (self.chord_index + 1) % len(self.chord_sequence)
             self.current_chord = self.chord_sequence[self.chord_index]

        if not self.is_trading and not self.is_groove:
            self.current_phase = "JAMMING"
            self.current_soloist = "Human"
            self._update_agent_modes()
            return

        # Groove Mode: 8-bar cycle (4 bars human, 4 bars AI)
        if self.is_groove:
            if self.bars_elapsed >= self.bars_per_cycle:
                self.bars_elapsed = 0
                if self.brain:
                    self.brain.clear_pattern("groove")
                    self.brain.clear_pattern("fill")
                if hasattr(self, "on_cycle_reset") and self.on_cycle_reset:
                    self.on_cycle_reset()

            old_phase = self.current_phase
            from jam_shed.core.constants import RecordingMode

            if 0 <= self.bars_elapsed <= 3:
                self.current_soloist = "Human"
                self.current_phase = "YOUR GROOVE (AI Listening)"
                if self.brain:
                    self.brain.current_recording = RecordingMode.GROOVE.value
                self.bars_left_in_turn = 4 - self.bars_elapsed
            elif 4 <= self.bars_elapsed <= 7:
                self.current_soloist = "DRUMMER"
                self.current_phase = "AI GROOVE (Copying You)"
                if self.brain:
                    self.brain.current_recording = RecordingMode.GROOVE.value
                self.bars_left_in_turn = 8 - self.bars_elapsed

            if self.current_phase != old_phase:
                debug_log(f"SESSION: Phase changed to {self.current_phase}")
                if hasattr(self, "on_turn_change") and self.on_turn_change:
                    self.on_turn_change(self.current_phase)

            self._update_agent_modes()
            return

        # 12-bar Interactive Cycle: 3 turns of 4 bars each (Shed Mode)
        if self.bars_elapsed >= self.bars_per_cycle:
            debug_log("SESSION: Trading Cycle Reset")
            self.bars_elapsed = 0
            if self.brain:
                self.brain.clear_pattern("groove")
                self.brain.clear_pattern("fill")
            if hasattr(self, "on_cycle_reset") and self.on_cycle_reset:
                self.on_cycle_reset()

        # Phase logic based on current bars_elapsed
        old_phase = self.current_phase

        # Determine the recording mode needed
        from jam_shed.core.constants import RecordingMode

        if 0 <= self.bars_elapsed <= 3:
            # Turn 1: Human lays down groove, AI is SILENT
            self.current_soloist = "Human"
            self.current_phase = "GROOVE: Human (AI Listening)"
            if self.brain:
                self.brain.current_recording = RecordingMode.GROOVE.value
            self.bars_left_in_turn = 4 - self.bars_elapsed
        elif 4 <= self.bars_elapsed <= 7:
            # Turn 2: Human plays fill, AI plays back learned groove
            self.current_soloist = "DRUMMER"
            self.current_phase = "HUMAN FILL (AI Groove)"
            if self.brain:
                self.brain.current_recording = RecordingMode.FILL.value
            self.bars_left_in_turn = 8 - self.bars_elapsed
        elif 8 <= self.bars_elapsed <= 11:
            # Turn 3: Human plays groove, AI plays response fill
            self.current_soloist = "DRUMMER"
            self.current_phase = "AI FILL (Human Groove)"
            self.bars_left_in_turn = 12 - self.bars_elapsed

        if self.current_phase != old_phase:
            debug_log(f"SESSION: Phase changed to {self.current_phase}")
            if hasattr(self, "on_turn_change") and self.on_turn_change:
                self.on_turn_change(self.current_phase)

        self._update_agent_modes()



    def _update_agent_modes(self):
        for agent in self.agents:
            # Match by name or class if name varies
            is_soloist = (agent.name == self.current_soloist) or \
                         (self.current_soloist == "DRUMMER" and "Drum" in agent.name) or \
                         (self.current_soloist == "Virtual Drummer" and "Drum" in agent.name)

            if is_soloist:
                agent.mode = AgentMode.SOLO
            else:
                # In Trading/Shed/Groove mode, others should be silent
                if self.is_trading or self.is_groove:
                    agent.mode = AgentMode.SILENT
                else:
                    agent.mode = AgentMode.ACCOMPANY

    def get_status(self) -> Dict:
        with self._lock:
            return {
                "is_trading": self.is_trading,
                "is_leadin": self.is_leadin,
                "current_soloist": self.current_soloist,
                "bars_elapsed": self.bars_elapsed,
                "bars_remaining": (self.bars_per_cycle - self.bars_elapsed) if self.is_trading else 0,
                "bars_left_in_turn": getattr(self, "bars_left_in_turn", 0),
                "beats_elapsed": self.beats_elapsed,
                "beats_per_bar": self.beats_per_bar,
                "phase": self.current_phase,
                "current_chord": f"{self.current_chord[0]} {self.current_chord[1]}", # e.g. "C Major"
                "is_waiting": self.waiting_for_first_hit
        }
