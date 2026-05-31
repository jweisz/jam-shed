from jam_shed.agents.base import PlayingStyle
from jam_shed.agents.bassist import VirtualBassist
from jam_shed.agents.drummer import VirtualDrummer
from jam_shed.agents.lead_guitarist import VirtualLeadGuitarist
from jam_shed.agents.rhythm_guitarist import VirtualRhythmGuitarist
from jam_shed.core.brain import RhythmicBrain


class FakeMIDI:
    def is_out_open(self):
        return False

    def send_message(self, _msg):
        pass


def test_lead_spotlight_probability_above_intro():
    lead = VirtualLeadGuitarist("Lead Guitar", FakeMIDI(), RhythmicBrain())

    base_state = {
        "complexity": 0.4,
        "energy_norm": 0.55,
        "is_jam_mode": True,
        "current_soloist": "Lead Guitar",
    }

    intro_state = dict(base_state)
    intro_state["jam_section"] = "INTRO"

    spotlight_state = dict(base_state)
    spotlight_state["jam_section"] = "SPOTLIGHT"

    intro_prob = lead.calculate_play_probability(intro_state)
    spotlight_prob = lead.calculate_play_probability(spotlight_state)

    assert spotlight_prob > intro_prob


def test_drum_phrase_fill_window_true_at_8_bar_boundary():
    drummer = VirtualDrummer("Drummer", FakeMIDI(), RhythmicBrain())
    state = {
        "is_jam_mode": True,
        "jam_section_bars": 7,
    }

    assert drummer._is_phrase_fill_window(state, beat=3, sub_beat=6) is True


def test_drum_phrase_fill_window_false_off_boundary():
    drummer = VirtualDrummer("Drummer", FakeMIDI(), RhythmicBrain())
    state = {
        "is_jam_mode": True,
        "jam_section_bars": 6,
    }

    assert drummer._is_phrase_fill_window(state, beat=3, sub_beat=6) is False


def test_drum_jam_mode_keeps_steady_anchor_hits():
    from unittest.mock import MagicMock, patch

    midi = MagicMock()
    midi.is_out_open.return_value = True
    drummer = VirtualDrummer("Drummer", midi, RhythmicBrain())
    state = {
        "intensity": 90,
        "is_jam_mode": True,
        "jam_section": "GROOVE_ESTABLISH",
        "jam_section_bars": 0,
        "section_density_target": 0.45,
        "section_space_bias": 0.35,
    }

    with patch("jam_shed.agents.drummer.random.random", return_value=1.0):
        drummer.play_note(state, beat=1, sub_beat=0)

    midi.send_message.assert_any_call([0x99, 42, 90])


def test_bass_tone_weights_shift_by_section():
    bassist = VirtualBassist("Bass", FakeMIDI(), RhythmicBrain())

    convo = bassist._get_tone_weights(
        {
            "is_jam_mode": True,
            "jam_section": "CONVERSATION",
            "current_soloist": "Human",
        }
    )
    ret = bassist._get_tone_weights(
        {
            "is_jam_mode": True,
            "jam_section": "RETURN_GROOVE",
            "current_soloist": "Human",
        }
    )

    # RETURN_GROOVE should favor root stronger than CONVERSATION.
    assert ret[0] > convo[0]
    # CONVERSATION should allow more color tones.
    assert convo[2] > ret[2]


def test_lead_style_curve_changes_conversation_probability():
    rock_lead = VirtualLeadGuitarist("Lead Guitar", FakeMIDI(), RhythmicBrain(), style=PlayingStyle.ROCK)
    jazz_lead = VirtualLeadGuitarist("Lead Guitar", FakeMIDI(), RhythmicBrain(), style=PlayingStyle.JAZZ)

    state = {
        "complexity": 0.45,
        "energy_norm": 0.5,
        "is_jam_mode": True,
        "current_soloist": "Human",
        "jam_section": "CONVERSATION",
    }

    rock_prob = rock_lead.calculate_play_probability(state)
    jazz_prob = jazz_lead.calculate_play_probability(state)

    assert jazz_prob > rock_prob


def test_bass_style_curve_changes_return_groove_root_weight():
    jazz_bass = VirtualBassist("Bass", FakeMIDI(), RhythmicBrain(), style=PlayingStyle.JAZZ)
    hiphop_bass = VirtualBassist("Bass", FakeMIDI(), RhythmicBrain(), style=PlayingStyle.HIP_HOP)

    state = {
        "is_jam_mode": True,
        "jam_section": "RETURN_GROOVE",
        "current_soloist": "Human",
    }

    jazz_weights = jazz_bass._get_tone_weights(state)
    hiphop_weights = hiphop_bass._get_tone_weights(state)

    assert hiphop_weights[0] > jazz_weights[0]


def test_bass_jam_mode_keeps_kick_following_anchor():
    from unittest.mock import MagicMock, patch

    midi = MagicMock()
    midi.is_out_open.return_value = True
    brain = RhythmicBrain()
    brain.current_bar = 0
    brain.agent_history = {"Drummer": [[(36, 100)]] + [[] for _ in range(brain.total_history_ticks - 1)]}
    bassist = VirtualBassist("Bass", midi, brain)
    state = {
        "intensity": 85,
        "complexity": 0.35,
        "energy_norm": 0.5,
        "is_jam_mode": True,
        "jam_section": "GROOVE_ESTABLISH",
        "section_density_target": 0.45,
        "section_space_bias": 0.35,
    }

    with patch("jam_shed.agents.bassist.random.random", return_value=0.0):
        bassist.tick(state, beat=0, sub_beat=0)

    assert midi.send_message.called
    assert midi.send_message.call_args_list[0][0][0][0] == 0x93


def test_rhythm_guitar_jam_mode_keeps_steady_pattern_hits():
    from unittest.mock import MagicMock, patch

    midi = MagicMock()
    midi.is_out_open.return_value = True
    guitarist = VirtualRhythmGuitarist("Rhythm Guitar", midi, RhythmicBrain())
    guitarist.current_pattern_name = "steady_8th"
    state = {
        "intensity": 80,
        "complexity": 0.4,
        "energy_norm": 0.5,
        "is_jam_mode": True,
        "jam_section": "GROOVE_ESTABLISH",
        "section_density_target": 0.45,
        "section_space_bias": 0.35,
    }

    with patch("jam_shed.agents.rhythm_guitarist.random.random", return_value=0.99):
        guitarist.tick(state, beat=0, sub_beat=0)

    assert midi.send_message.call_count > 0
