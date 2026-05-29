import threading
import time
from typing import List, Dict, Optional
from jam_shed.agents.base import VirtualInstrumentalist, AgentMode
from jam_shed.utils.debug import debug_log

class JamSession:
    def __init__(self, agents: Optional[List[VirtualInstrumentalist]] = None, brain=None):
        self._lock = threading.Lock()
        self._deferred_events: List[tuple[str, Optional[str]]] = []
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
        self._leadin_complete_pending = False
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

        # Jam Mode Arranger State
        self.jam_sections = [
            "INTRO",
            "GROOVE_ESTABLISH",
            "CONVERSATION",
            "SPOTLIGHT",
            "RETURN_GROOVE",
            "OUTRO",
        ]
        self.jam_section_index = 0
        self.jam_section_started_at_bar = 0
        self.jam_section_min_bars = 16
        self.jam_section_checkpoints = [16, 24, 32]
        self.human_confidence = 0.5
        self.human_energy = 0.5
        self.human_complexity = 0.3
        self.last_transition_readiness = 0.0
        self.jam_section_profiles = {
            "INTRO": {
                "density_target": 0.30,
                "space_bias": 0.55,
                "solo_bias": 0.10,
            },
            "GROOVE_ESTABLISH": {
                "density_target": 0.45,
                "space_bias": 0.35,
                "solo_bias": 0.20,
            },
            "CONVERSATION": {
                "density_target": 0.55,
                "space_bias": 0.30,
                "solo_bias": 0.35,
            },
            "SPOTLIGHT": {
                "density_target": 0.62,
                "space_bias": 0.25,
                "solo_bias": 0.80,
            },
            "RETURN_GROOVE": {
                "density_target": 0.48,
                "space_bias": 0.33,
                "solo_bias": 0.20,
            },
            "OUTRO": {
                "density_target": 0.35,
                "space_bias": 0.60,
                "solo_bias": 0.05,
            },
        }

    def _get_drummer_name(self) -> str:
        """Return the configured drummer agent name, or a sensible fallback."""
        for agent in self.agents:
            if "Drum" in agent.name:
                return agent.name
        return "DRUMMER"

    def start_first_hit(self):
        """First hit detected: Enter 1-bar lead-in countdown."""
        # Set lead-in flag FIRST to prevent race condition with clock thread
        self.is_leadin = True
        self.waiting_for_first_hit = False
        self.bars_elapsed = 0
        self.beats_elapsed = 0
        self._leadin_complete_pending = False
        self.current_soloist = "READYING..."
        self.current_phase = "COUNT-IN"
        debug_log("SESSION: First Hit Started -> Lead-in Mode")

    def start_jam(self):
        """Start Jam mode arranger state."""
        self.is_trading = False
        self.is_groove = False
        self.bars_per_cycle = 0
        self.jam_section_index = 0
        self.jam_section_started_at_bar = 0
        self.last_transition_readiness = 0.0
        self.current_soloist = "Human"
        self.current_phase = f"JAM: {self.jam_sections[self.jam_section_index]}"
        self._update_agent_modes()

    def get_jam_section_profile(self) -> Dict[str, float]:
        section = self.jam_sections[self.jam_section_index]
        return self.jam_section_profiles.get(section, {
            "density_target": 0.5,
            "space_bias": 0.3,
            "solo_bias": 0.2,
        })

    def update_human_state(self, confidence: float, energy: float, complexity: float) -> None:
        """Update human performance signals used by the Jam arranger."""
        self.human_confidence = max(0.0, min(1.0, confidence))
        self.human_energy = max(0.0, min(1.0, energy))
        self.human_complexity = max(0.0, min(1.0, complexity))

    def _get_avg_agent_endurance(self) -> float:
        """Average endurance across active agents (defaults to full endurance)."""
        if not self.agents:
            return 1.0
        vals = [getattr(agent, "endurance", 1.0) for agent in self.agents]
        return sum(vals) / len(vals)

    def _get_jam_transition_readiness(self) -> float:
        """Compute readiness to transition sections at phrase boundaries."""
        avg_endurance = self._get_avg_agent_endurance()
        endurance_pressure = 1.0 - avg_endurance
        variation_need = max(0.0, min(1.0, (self.human_complexity * 0.7) + (endurance_pressure * 0.3)))
        readiness = (
            0.45 * self.human_confidence +
            0.35 * endurance_pressure +
            0.20 * variation_need
        )
        self.last_transition_readiness = max(0.0, min(1.0, readiness))
        return self.last_transition_readiness

    def _advance_jam_section(self):
        """Advance to next Jam section and refresh phase label."""
        if self.jam_section_index < len(self.jam_sections) - 1:
            self.jam_section_index += 1
        self.jam_section_started_at_bar = self.bars_elapsed
        section = self.jam_sections[self.jam_section_index]
        self.current_phase = f"JAM: {section}"
        debug_log(f"SESSION: Jam section advanced -> {section}")

    def _pick_spotlight_soloist(self) -> str:
        """Pick a spotlight soloist with light role preference and endurance awareness."""
        if not self.agents:
            return "Human"

        priorities = ["Lead Guitar", "Keyboardist", "Rhythm Guitar", "Bass", "Drum"]
        ranked = []
        for agent in self.agents:
            role_score = 0
            for idx, role in enumerate(priorities):
                if role in agent.name:
                    role_score = len(priorities) - idx
                    break
            endurance = getattr(agent, "endurance", 1.0)
            ranked.append((role_score, endurance, agent.name))

        ranked.sort(reverse=True)
        return ranked[0][2] if ranked else "Human"

    def _update_jam_arranger(self):
        """Update Jam mode section transitions using phrase-level checkpoints."""
        section = self.jam_sections[self.jam_section_index]
        bars_in_section = self.bars_elapsed - self.jam_section_started_at_bar

        if section == "SPOTLIGHT":
            self.current_soloist = self._pick_spotlight_soloist()
        else:
            self.current_soloist = "Human"
        self.current_phase = f"JAM: {section}"

        if bars_in_section < self.jam_section_min_bars:
            return

        if bars_in_section not in self.jam_section_checkpoints:
            return

        readiness = self._get_jam_transition_readiness()

        # Transition thresholds loosen as the section grows longer.
        thresholds = {16: 0.78, 24: 0.64, 32: 0.50}
        threshold = thresholds.get(bars_in_section, 0.60)

        # Always advance by 32 bars to avoid sections lingering indefinitely.
        if bars_in_section >= 32 or readiness >= threshold:
            self._advance_jam_section()

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
        deferred_events: List[tuple[str, Optional[str]]] = []
        with self._lock:
            self._notify_beat_elapsed_unlocked()
            deferred_events = list(self._deferred_events)
            self._deferred_events.clear()

        # Emit callbacks outside the session lock to avoid cross-thread deadlocks.
        for event_name, event_payload in deferred_events:
            if event_name == "bar_elapsed" and self.on_bar_elapsed:
                self.on_bar_elapsed()
            elif event_name == "cycle_reset" and hasattr(self, "on_cycle_reset") and self.on_cycle_reset:
                self.on_cycle_reset()
            elif event_name == "turn_change" and hasattr(self, "on_turn_change") and self.on_turn_change:
                self.on_turn_change(event_payload)

    def _notify_beat_elapsed_unlocked(self):
        if self.waiting_for_first_hit:
            return

        # Lead-in handling:
        # - Beat 1..4 are count-in ticks
        # - Transition to BAR 1 / BEAT 1 occurs on the NEXT beat after tick 4
        if self.is_leadin:
            if self._leadin_complete_pending:
                self._leadin_complete_pending = False
                self.is_leadin = False
                self.beats_elapsed = 0
                if self.is_groove:
                    self.current_soloist = "Human"
                    self.current_phase = "YOUR GROOVE (AI Listening)"
                elif self.is_trading:
                    self.current_soloist = "Human"
                    self.current_phase = "GROOVE: Human (AI Listening)"
                else:
                    self.current_soloist = "Human"
                    self.current_phase = f"JAM: {self.jam_sections[self.jam_section_index]}"
                debug_log(f"SESSION: Lead-in Complete. Mode: {'Groove' if self.is_groove else ('Shed' if self.is_trading else 'Jam')}")
                if hasattr(self, "_update_agent_modes"):
                    self._update_agent_modes()
                self.notify_bar_elapsed(defer_callbacks=True)
                return

            self.beats_elapsed += 1
            if self.beats_elapsed >= self.beats_per_bar:
                self._leadin_complete_pending = True
            return

        self.beats_elapsed += 1

        debug_log(f'SESSION: Beat {self.beats_elapsed}/{self.beats_per_bar}')

        if self.beats_elapsed >= self.beats_per_bar:
            self.beats_elapsed = 0
            debug_log(f"SESSION: Bar Elapsed ({self.bars_elapsed + 1})")
            self.notify_bar_elapsed(defer_callbacks=True)

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

    def notify_bar_elapsed(self, defer_callbacks: bool = False):
        if self.waiting_for_first_hit:
            return

        self.bars_elapsed += 1

        # LOG: Detailed transition
        debug_log(f"SESSION: Bar {self.bars_elapsed} (Trading: {self.is_trading})")

        if defer_callbacks:
            self._deferred_events.append(("bar_elapsed", None))
        elif self.on_bar_elapsed:
            self.on_bar_elapsed()

        # Advance Chord Progression (Should happen in Jam mode too)
        if self.chord_sequence:
             self.chord_index = (self.chord_index + 1) % len(self.chord_sequence)
             self.current_chord = self.chord_sequence[self.chord_index]

        if not self.is_trading and not self.is_groove:
            self._update_jam_arranger()
            self._update_agent_modes()
            return

        # Groove Mode: 8-bar cycle (4 bars human, 4 bars AI)
        if self.is_groove:
            if self.bars_elapsed > self.bars_per_cycle:
                self.bars_elapsed = 1
                if self.brain:
                    self.brain.clear_pattern("groove")
                    self.brain.clear_pattern("fill")
                if defer_callbacks:
                    self._deferred_events.append(("cycle_reset", None))
                elif hasattr(self, "on_cycle_reset") and self.on_cycle_reset:
                    self.on_cycle_reset()

            old_phase = self.current_phase
            from jam_shed.core.constants import RecordingMode

            if 1 <= self.bars_elapsed <= 4:
                self.current_soloist = "Human"
                self.current_phase = "YOUR GROOVE (AI Listening)"
                if self.brain:
                    self.brain.current_recording = RecordingMode.GROOVE.value
                self.bars_left_in_turn = 5 - self.bars_elapsed
            elif 5 <= self.bars_elapsed <= 8:
                self.current_soloist = self._get_drummer_name()
                self.current_phase = "AI GROOVE (Copying You)"
                if self.brain:
                    self.brain.current_recording = RecordingMode.GROOVE.value
                self.bars_left_in_turn = 9 - self.bars_elapsed

            if self.current_phase != old_phase:
                debug_log(f"SESSION: Phase changed to {self.current_phase}")
                if defer_callbacks:
                    self._deferred_events.append(("turn_change", self.current_phase))
                elif hasattr(self, "on_turn_change") and self.on_turn_change:
                    self.on_turn_change(self.current_phase)

            self._update_agent_modes()
            return

        # 12-bar Interactive Cycle: 3 turns of 4 bars each (Shed Mode)
        if self.bars_elapsed > self.bars_per_cycle:
            debug_log("SESSION: Trading Cycle Reset")
            self.bars_elapsed = 1
            if self.brain:
                self.brain.clear_pattern("groove")
                self.brain.clear_pattern("fill")
            if defer_callbacks:
                self._deferred_events.append(("cycle_reset", None))
            elif hasattr(self, "on_cycle_reset") and self.on_cycle_reset:
                self.on_cycle_reset()

        # Phase logic based on current bars_elapsed
        old_phase = self.current_phase

        # Determine the recording mode needed
        from jam_shed.core.constants import RecordingMode

        if 1 <= self.bars_elapsed <= 4:
            # Turn 1: Human lays down groove, AI is SILENT
            self.current_soloist = "Human"
            self.current_phase = "GROOVE: Human (AI Listening)"
            if self.brain:
                self.brain.current_recording = RecordingMode.GROOVE.value
            self.bars_left_in_turn = 5 - self.bars_elapsed
        elif 5 <= self.bars_elapsed <= 8:
            # Turn 2: Human plays fill, AI plays back learned groove
            self.current_soloist = self._get_drummer_name()
            self.current_phase = "HUMAN FILL (AI Groove)"
            if self.brain:
                self.brain.current_recording = RecordingMode.FILL.value
            self.bars_left_in_turn = 9 - self.bars_elapsed
        elif 9 <= self.bars_elapsed <= 12:
            # Turn 3: Human plays groove, AI plays response fill
            self.current_soloist = self._get_drummer_name()
            self.current_phase = "AI FILL (Human Groove)"
            self.bars_left_in_turn = 13 - self.bars_elapsed

        if self.current_phase != old_phase:
            debug_log(f"SESSION: Phase changed to {self.current_phase}")
            if defer_callbacks:
                self._deferred_events.append(("turn_change", self.current_phase))
            elif hasattr(self, "on_turn_change") and self.on_turn_change:
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
                "is_waiting": self.waiting_for_first_hit,
                "jam_section": self.jam_sections[self.jam_section_index],
                "jam_section_bars": max(0, self.bars_elapsed - self.jam_section_started_at_bar),
                "jam_transition_readiness": round(self.last_transition_readiness, 2),
                "jam_density_target": self.get_jam_section_profile().get("density_target", 0.5),
                "jam_space_bias": self.get_jam_section_profile().get("space_bias", 0.3),
                "jam_solo_bias": self.get_jam_section_profile().get("solo_bias", 0.2),
        }
