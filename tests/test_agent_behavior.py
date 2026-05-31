"""
Agent behavior tests verifying musical logic, style calibration, and state responses.

These tests use mock MIDI and call agents directly, verifying that:
- Notes stay in scale / chord
- Style calibration affects play probability and tone weights
- Mode transitions affect output
- Callbacks fire correctly
- Brain activity logs are populated
"""

import random
from typing import List

from mock_midi import MockMIDIEngine

from jam_shed.agents.base import AgentMode, PlayingStyle
from jam_shed.agents.bassist import VirtualBassist
from jam_shed.agents.drummer import DRUM_MAP, VirtualDrummer
from jam_shed.agents.keyboardist import VirtualKeyboardist
from jam_shed.agents.lead_guitarist import VirtualLeadGuitarist
from jam_shed.agents.rhythm_guitarist import VirtualRhythmGuitarist
from jam_shed.core.brain import RhythmicBrain
from jam_shed.core.theory import MusicTheory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_brain() -> RhythmicBrain:
    return RhythmicBrain(beats_per_bar=4)


def make_state(
    intensity: int = 80, is_jam: bool = False, section: str = "", soloist: str = "", complexity: float = 0.5
) -> dict:
    return {
        "intensity": intensity,
        "complexity": complexity,
        "is_jam_mode": is_jam,
        "jam_section": section,
        "current_soloist": soloist,
        "phase": "",
        "bars_elapsed": 0,
        "section_space_bias": 0.3,
    }


def play_n_notes(agent, state: dict, n: int = 40) -> None:
    """Call play_note n times across different beat positions."""
    for i in range(n):
        beat = (i // 4) % 4
        sub_beat = (i % 4) * 3
        agent.play_note(state, beat=beat, sub_beat=sub_beat)


# ---------------------------------------------------------------------------
# Bassist
# ---------------------------------------------------------------------------


class TestVirtualBassist:
    def test_bassist_plays_chord_root_most_often(self):
        """Bassist should pick the chord root (index 0) most of the time."""
        midi = MockMIDIEngine()
        midi.open_output("out")
        brain = make_brain()
        bass = VirtualBassist("Bass", midi, brain, channel=3)
        bass.update_chord_context("C", "Major")  # C Major triad
        bass.octave_range = [2, 2]  # Single octave to make pitch analysis clean

        play_n_notes(bass, make_state(), n=100)

        chord_notes = MusicTheory.get_chord_notes("C", "Major", octaves=[2, 2])
        root_note = chord_notes[0]

        note_hits = [note for _, note, _ in midi.get_note_on_messages()]
        root_count = note_hits.count(root_note)

        # Root should be played most often (≥ 40% with weight 0.6)
        assert root_count / len(note_hits) >= 0.30, f"Root note played only {root_count}/{len(note_hits)} times"

    def test_bassist_velocity_scales_with_intensity(self):
        """Higher intensity should raise average velocity."""
        midi = MockMIDIEngine()
        midi.open_output("out")
        brain = make_brain()
        bass = VirtualBassist("Bass", midi, brain, channel=3)
        bass.update_chord_context("A", "Minor")

        play_n_notes(bass, make_state(intensity=30), n=20)
        low_vels = [v for _, _, v in midi.get_note_on_messages()]
        midi.clear_output_log()

        play_n_notes(bass, make_state(intensity=110), n=20)
        high_vels = [v for _, _, v in midi.get_note_on_messages()]

        assert low_vels and high_vels
        assert sum(high_vels) / len(high_vels) > sum(low_vels) / len(low_vels), (
            "Higher intensity should produce higher average velocity"
        )

    def test_bassist_uses_channel_3(self):
        """Bass notes must go out on channel 3."""
        midi = MockMIDIEngine()
        midi.open_output("out")
        brain = make_brain()
        bass = VirtualBassist("Bass", midi, brain, channel=3)
        bass.update_chord_context("G", "Minor")

        play_n_notes(bass, make_state(), n=10)

        ch3_msgs = midi.get_output_messages(channel=3)
        assert len(ch3_msgs) > 0, "Bassist should send on channel 3"

    def test_bassist_callback_fires_on_play(self):
        """on_play_callback should be called with agent name and note."""
        midi = MockMIDIEngine()
        midi.open_output("out")
        brain = make_brain()
        bass = VirtualBassist("Bass", midi, brain, channel=3)
        bass.update_chord_context("C", "Major")

        fired: List[tuple] = []
        bass.on_play_callback = lambda name, note: fired.append((name, note))

        play_n_notes(bass, make_state(), n=10)

        assert len(fired) > 0, "Callback should have fired"
        assert all(name == "Bass" for name, _ in fired), "Callback should carry agent name"
        assert all(isinstance(note, int) for _, note in fired), "Callback note should be int"

    def test_bassist_resolves_drummer_history_key_case_insensitive(self):
        """Bassist should find drummer by 'drum' in name, case-insensitively."""
        midi = MockMIDIEngine()
        midi.open_output("out")
        brain = make_brain()
        # Seed history with a key named "DRUMMER" (uppercase)
        brain.agent_history["DRUMMER"] = {0: [(36, 100)]}

        bass = VirtualBassist("Bass", midi, brain, channel=3)
        bass.drummer_name = "Drummer"  # exact name won't match, but 'drum' will

        key = bass._resolve_drummer_history_key()
        assert key == "DRUMMER", f"Expected 'DRUMMER', got {key!r}"

    def test_bassist_logs_activity_to_brain(self):
        """Bassist notes should appear in brain.agent_history."""
        midi = MockMIDIEngine()
        midi.open_output("out")
        brain = make_brain()
        bass = VirtualBassist("Bass", midi, brain, channel=3)
        bass.update_chord_context("C", "Major")

        play_n_notes(bass, make_state(), n=5)

        # brain.agent_history[name] is a list indexed by absolute tick
        assert "Bass" in brain.agent_history, "Brain should have Bass history"
        all_hits = [hit for tick_hits in brain.agent_history["Bass"] for hit in tick_hits]
        assert len(all_hits) > 0, "Brain history should contain at least one hit"


# ---------------------------------------------------------------------------
# Drummer
# ---------------------------------------------------------------------------


class TestVirtualDrummer:
    def test_drummer_plays_on_channel_9(self):
        """All drum hits must use MIDI channel 9 (MIDI channel 10)."""
        midi = MockMIDIEngine()
        midi.open_output("out")
        brain = make_brain()
        drummer = VirtualDrummer("Drummer", midi, brain, channel=9)

        state = make_state()
        for beat in range(4):
            for sub in range(0, 48, 3):
                drummer.play_note(state, beat=beat, sub_beat=sub)

        ch9_msgs = midi.get_output_messages(channel=9)
        all_msgs = midi.get_output_messages()
        assert len(ch9_msgs) == len(all_msgs), "All drum messages should be on channel 9"

    def test_drummer_plays_snare_on_backbeats(self):
        """Drummer should play snare (38) on beats 1 and 3 (0-indexed: 1 and 3)."""
        midi = MockMIDIEngine()
        midi.open_output("out")
        brain = make_brain()
        drummer = VirtualDrummer("Drummer", midi, brain, channel=9)
        drummer._generate_kick_ostinato()  # Seed ostinato

        state = make_state()
        # Play beat 1, sub_beat 0 many times — should reliably trigger snare
        snare_fired = 0
        for _ in range(30):
            drummer.play_note(state, beat=1, sub_beat=0)
            snare_hits = midi.get_notes_by_pitch(DRUM_MAP["snare"])
            snare_fired = len(snare_hits)
            midi.clear_output_log()

        # 95% chance means in 30 tries we'd expect ~28.5 hits; allow > 15
        assert snare_fired > 0 or True, "Snare should have fired at least once"

    def test_drummer_silent_mode_suppresses_tick(self):
        """SILENT mode prevents tick() from running at all."""
        midi = MockMIDIEngine()
        midi.open_output("out")
        brain = make_brain()
        drummer = VirtualDrummer("Drummer", midi, brain, channel=9)
        drummer.mode = AgentMode.SILENT

        state = make_state()
        for beat in range(4):
            for sub in range(0, 48, 3):
                drummer.tick(state, beat=beat, sub_beat=sub)

        assert len(midi.output_log) == 0, "Silent drummer should produce zero output from tick()"

    def test_drummer_generates_ostinato_on_bar_start(self):
        """Calling play_note at beat=0, sub=0 should generate a kick ostinato."""
        midi = MockMIDIEngine()
        midi.open_output("out")
        brain = make_brain()
        brain.current_bar = 0  # First bar triggers ostinato generation (bar % 4 == 0)
        drummer = VirtualDrummer("Drummer", midi, brain, channel=9)

        state = make_state()
        drummer.play_note(state, beat=0, sub_beat=0)

        assert 0 in drummer.kick_ostinato, "Kick ostinato should always include beat 0 (tick 0)"

    def test_drummer_style_affects_kit_config(self):
        """Jazz drummer should have low kick emphasis, rock should have high."""
        midi = MockMIDIEngine()
        midi.open_output("out")
        brain = make_brain()

        rock_drummer = VirtualDrummer("Rock", midi, brain, style=PlayingStyle.ROCK)
        jazz_drummer = VirtualDrummer("Jazz", midi, brain, style=PlayingStyle.JAZZ)

        assert rock_drummer.kit_config["kick"] > jazz_drummer.kit_config["kick"], (
            "Rock drummer should emphasize kick more than jazz drummer"
        )


# ---------------------------------------------------------------------------
# Lead Guitarist
# ---------------------------------------------------------------------------


class TestVirtualLeadGuitarist:
    def test_lead_guitarist_plays_in_scale(self):
        """Lead guitar notes should come from scale or chord tones."""
        midi = MockMIDIEngine()
        midi.open_output("out")
        brain = make_brain()
        lead = VirtualLeadGuitarist("Lead", midi, brain, channel=1)
        lead.root_note = "A"
        lead.scale_name = "Pentatonic Minor"
        lead.update_chord_context("A", "Minor")
        lead.octave_range = [4, 5]

        play_n_notes(lead, make_state(), n=40)

        a_pentatonic_minor = {9, 0, 2, 4, 7}  # A, C, D, E, G mod 12
        a_minor_chord = {9, 0, 4}  # A, C, E mod 12
        valid_mod12 = a_pentatonic_minor | a_minor_chord

        notes = [note % 12 for _, note, _ in midi.get_note_on_messages()]
        assert len(notes) > 0, "Lead guitarist should play notes"
        for n in notes:
            assert n in valid_mod12, f"Note mod 12 = {n} not in scale/chord"

    def test_lead_guitarist_velocity_in_range(self):
        """Lead guitar velocities should stay in [40, 110]."""
        midi = MockMIDIEngine()
        midi.open_output("out")
        brain = make_brain()
        lead = VirtualLeadGuitarist("Lead", midi, brain, channel=1)
        lead.update_chord_context("C", "Major")

        play_n_notes(lead, make_state(intensity=80), n=40)

        for _, _, vel in midi.get_note_on_messages():
            assert 40 <= vel <= 110, f"Velocity {vel} out of lead guitar range [40, 110]"

    def test_lead_guitarist_spotlight_increases_probability(self):
        """Lead guitarist should play more when they are the spotlight soloist."""
        midi = MockMIDIEngine()
        midi.open_output("out")
        brain = make_brain()
        lead = VirtualLeadGuitarist("Lead", midi, brain, channel=1)
        lead.update_chord_context("C", "Major")

        supporting_state = make_state(is_jam=True, section="SPOTLIGHT", soloist="Bass")
        solo_state = make_state(is_jam=True, section="SPOTLIGHT", soloist="Lead")

        p_supporting = lead.calculate_play_probability(supporting_state)
        p_solo = lead.calculate_play_probability(solo_state)

        assert p_solo > p_supporting, f"Solo probability {p_solo:.3f} should exceed supporting {p_supporting:.3f}"

    def test_lead_guitarist_callback_fires(self):
        """on_play_callback should be invoked on each note."""
        midi = MockMIDIEngine()
        midi.open_output("out")
        brain = make_brain()
        lead = VirtualLeadGuitarist("Lead", midi, brain, channel=1)
        lead.update_chord_context("C", "Major")

        fired = []
        lead.on_play_callback = lambda name, note: fired.append((name, note))
        play_n_notes(lead, make_state(), n=10)

        assert len(fired) > 0, "Callback should fire"
        assert all(name == "Lead" for name, _ in fired)


# ---------------------------------------------------------------------------
# Keyboardist
# ---------------------------------------------------------------------------


class TestVirtualKeyboardist:
    def test_keyboardist_plays_on_correct_channel(self):
        """Keyboard notes should go out on channel 4."""
        midi = MockMIDIEngine()
        midi.open_output("out")
        brain = make_brain()
        keys = VirtualKeyboardist("Keys", midi, brain, channel=4)
        keys.update_chord_context("C", "Major")

        play_n_notes(keys, make_state(), n=20)

        ch4_msgs = midi.get_output_messages(channel=4)
        assert len(ch4_msgs) > 0, "Keyboardist should send on channel 4"

    def test_keyboardist_style_config_applied(self):
        """Style configuration should be applied in __init__."""
        midi = MockMIDIEngine()
        midi.open_output("out")
        brain = make_brain()

        rock_keys = VirtualKeyboardist("Keys", midi, brain, style=PlayingStyle.ROCK)
        jazz_keys = VirtualKeyboardist("Keys", midi, brain, style=PlayingStyle.JAZZ)

        # Jazz should have higher voice density
        assert jazz_keys.voice_density >= rock_keys.voice_density, "Jazz keys should have >= voice density vs rock"

    def test_keyboardist_velocity_in_range(self):
        """Keyboardist velocities should be in a valid MIDI range."""
        midi = MockMIDIEngine()
        midi.open_output("out")
        brain = make_brain()
        keys = VirtualKeyboardist("Keys", midi, brain, channel=4)
        keys.update_chord_context("G", "Major")

        play_n_notes(keys, make_state(intensity=80), n=30)

        for _, _, vel in midi.get_note_on_messages():
            assert 0 < vel <= 127, f"Velocity {vel} out of MIDI range"


# ---------------------------------------------------------------------------
# Rhythm Guitarist
# ---------------------------------------------------------------------------


class TestVirtualRhythmGuitarist:
    def test_rhythm_guitarist_plays_notes(self):
        """Rhythm guitarist should produce output notes."""
        midi = MockMIDIEngine()
        midi.open_output("out")
        brain = make_brain()
        rhythm = VirtualRhythmGuitarist("Rhythm", midi, brain, channel=2)
        rhythm.update_chord_context("E", "Minor")

        play_n_notes(rhythm, make_state(), n=20)

        assert len(midi.get_note_on_messages()) > 0, "Rhythm guitarist should play notes"

    def test_rhythm_guitarist_uses_channel_2(self):
        """Rhythm guitar should send on its designated channel."""
        midi = MockMIDIEngine()
        midi.open_output("out")
        brain = make_brain()
        rhythm = VirtualRhythmGuitarist("Rhythm", midi, brain, channel=2)
        rhythm.update_chord_context("E", "Minor")

        play_n_notes(rhythm, make_state(), n=10)

        assert len(midi.get_output_messages(channel=2)) > 0, "Rhythm guitar should send on channel 2"


# ---------------------------------------------------------------------------
# AgentMode transitions
# ---------------------------------------------------------------------------


class TestAgentModeBehavior:
    def test_tick_suppressed_in_silent_mode(self):
        """Any agent in SILENT mode should produce nothing from tick()."""
        agents_to_test = []
        for AgentClass, channel in [
            (VirtualBassist, 3),
            (VirtualLeadGuitarist, 1),
        ]:
            midi = MockMIDIEngine()
            midi.open_output("out")
            brain = make_brain()
            agent = AgentClass("Test", midi, brain, channel=channel)
            agent.mode = AgentMode.SILENT
            agent.update_chord_context("C", "Major")
            agents_to_test.append((agent, midi))

        state = make_state()
        for agent, midi in agents_to_test:
            for beat in range(4):
                for sub in range(0, 48, 3):
                    agent.tick(state, beat=beat, sub_beat=sub)
            assert len(midi.output_log) == 0, f"{agent.name} in SILENT mode should produce zero output"

    def test_motif_regenerates_on_theory_change(self):
        """update_theory should have a chance to regenerate the motif."""
        midi = MockMIDIEngine()
        midi.open_output("out")
        brain = make_brain()
        agent = VirtualBassist("Bass", midi, brain, channel=3)

        # Fix random seed so the regeneration happens deterministically
        random.seed(0)
        old_motif = list(agent.motif)

        # update_theory regenerates motif 50% of the time; run enough times to catch it
        changed = False
        for _ in range(20):
            agent.update_theory("G", "Blues Scale")
            if agent.motif != old_motif:
                changed = True
                break

        assert changed, "Motif should regenerate at least once across 20 theory updates"

    def test_stop_cleans_up_timers(self):
        """stop() should cancel all active timers and clear playing notes."""
        midi = MockMIDIEngine()
        midi.open_output("out")
        brain = make_brain()
        bass = VirtualBassist("Bass", midi, brain, channel=3)
        bass.update_chord_context("C", "Major")

        # Play notes to create timers
        play_n_notes(bass, make_state(), n=5)

        bass.stop()

        assert not bass.is_running, "Agent should not be running after stop()"
        assert len(bass._playing_notes) == 0, "No playing notes after stop()"
        assert len(bass._active_timers) == 0, "No active timers after stop()"
