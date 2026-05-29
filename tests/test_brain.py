"""
Tests for jam_shed.brain module.
"""
import pytest
from jam_shed.core.brain import RhythmicBrain


def test_brain_initialization():
    """Test brain initializes with correct defaults."""
    brain = RhythmicBrain(beats_per_bar=4)
    assert brain.beats_per_bar == 4
    assert brain.is_listening is False
    assert len(brain.human_timings) == 0


def test_start_listening():
    """Test starting listening mode."""
    brain = RhythmicBrain(beats_per_bar=4)
    brain.start_listening()
    assert brain.is_listening is True


def test_stop_listening():
    """Test stopping listening mode."""
    brain = RhythmicBrain(beats_per_bar=4)
    brain.start_listening()
    brain.stop_listening()
    assert brain.is_listening is False


def test_record_hit_during_listening():
    """Test that hits are recorded during listening."""
    brain = RhythmicBrain(beats_per_bar=4)
    brain.start_listening()

    # Simulate hit
    brain.notify_hit(beat=0, sub_beat=0, note=60, velocity=80)

    assert len(brain.human_timings) > 0


def test_calculate_bpm():
    """Test BPM calculation from timings."""
    brain = RhythmicBrain(beats_per_bar=4)

    # Manually add timings at 120 BPM (0.5s per beat)
    import time
    base_time = time.time()
    brain.human_timings = [
        base_time,
        base_time + 0.5,
        base_time + 1.0,
        base_time + 1.5,
    ]

    bpm = brain.calculate_bpm()
    # Should be close to 120 BPM
    assert 115 <= bpm <= 125


def test_get_current_state_idle():
    """Test state when idle."""
    brain = RhythmicBrain(beats_per_bar=4)
    state = brain.get_current_state()

    assert "complexity" in state
    assert "intensity" in state
    assert "density" in state


def test_groove_pattern_empty_initially():
    """Test groove pattern is empty on init."""
    brain = RhythmicBrain(beats_per_bar=4)
    assert len(brain.groove_pattern) == 0


def test_notify_hit_increments_beat_counter():
    """Test that hits increment internal counters."""
    brain = RhythmicBrain(beats_per_bar=4)
    brain.start_listening()

    initial_count = len(brain.human_timings)
    brain.notify_hit(0, 0, 60, 80)

    assert len(brain.human_timings) == initial_count + 1
