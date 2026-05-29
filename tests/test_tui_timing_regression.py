import asyncio

from jam_shed.tui.app import JamShedApp


def test_bar_display_index_is_zero_based_for_active_cycle():
    # First active bar should light first dot.
    assert JamShedApp._bar_display_index(1, 4) == 0
    # Fourth active bar should light last dot.
    assert JamShedApp._bar_display_index(4, 4) == 3
    # Wrap to beginning on next cycle.
    assert JamShedApp._bar_display_index(5, 4) == 0


def test_countin_click_includes_transition_beat():
    # During lead-in, count-in click should emit.
    assert JamShedApp._should_emit_countin_click(True, False) is True


def test_countin_click_not_emitted_when_inactive_and_click_off():
    assert JamShedApp._should_emit_countin_click(False, False) is False


def test_countin_click_emitted_when_click_track_active():
    assert JamShedApp._should_emit_countin_click(False, True) is True


def test_jam_sidebar_lists_bassist_checkbox():
    async def run_check():
        app = JamShedApp()
        async with app.run_test() as pilot:
            del pilot
            labels = [str(box.label) for box in app.query("#jam_controls Checkbox")]
            assert labels == [
                "Drummer",
                "Keyboardist",
                "Lead Guitar",
                "Rhythm Guitar",
                "Bassist",
            ]

    asyncio.run(run_check())
