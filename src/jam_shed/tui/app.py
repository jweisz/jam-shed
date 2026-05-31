import argparse
import random
import threading
import time
from typing import List, Optional

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, ItemGrid, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    RadioButton,
    RadioSet,
    RichLog,
    Select,
    Static,
)

from jam_shed.agents import PlayingStyle
from jam_shed.agents.base import VirtualInstrumentalist
from jam_shed.agents.bassist import VirtualBassist
from jam_shed.agents.drummer import VirtualDrummer
from jam_shed.agents.keyboardist import VirtualKeyboardist
from jam_shed.agents.lead_guitarist import VirtualLeadGuitarist
from jam_shed.agents.rhythm_guitarist import VirtualRhythmGuitarist
from jam_shed.core.brain import RhythmicBrain
from jam_shed.core.session import JamSession
from jam_shed.core.theory import MusicTheory
from jam_shed.midi.engine import MIDIEngine
from jam_shed.tui.visual import (
    render_beat_dots,
    render_gauge,
)
from jam_shed.utils.debug import debug_log


class ClockThread(threading.Thread):
    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        self._stop_event = threading.Event()

    def run(self):
        try:
            last_time = time.time()
            debug_log("CLOCK: Thread Started")
            while not self._stop_event.is_set():
                now = time.time()
                delta = now - last_time
                last_time = now

                # Always advance time to keep beat accumulator running for visuals
                try:
                    self.app.brain.update_time(delta)
                except Exception as e:
                    debug_log(f"CLOCK: Update Error: {e}")

                time.sleep(0.01)
        except Exception as e:
            debug_log(f"CLOCK: Thread Crash: {e}")

    def stop(self):
        self._stop_event.set()


class JamShedApp(App):
    # MIDI Drum Mapping
    DRUM_NAMES = {
        36: "KICK",
        38: "SNARE",
        40: "S-RIM",
        42: "HH-CL",
        44: "HH-PD",
        46: "HH-OP",
        41: "F-TOM",
        45: "M-TOM",
        48: "H-TOM",
        49: "CRASH1",
        57: "CRASH2",
        51: "RIDE",
    }
    DRUM_AGENT_NAMES = {"DRUMMER", "MANUAL", "ME", "CLICK", "SIGNAL"}

    CSS = """
    Screen {
        layout: horizontal;
    }
    Header {
        dock: top;
    }

    /* ── Left Sidebar ─────────────────────────────── */
    #sidebar {
        width: 35;
        height: 100%;
        background: $surface;
        border-right: solid $primary;
        padding: 1;
        layout: vertical;
    }
    #sidebar_inner {
        height: auto;
        padding-right: 1;
    }

    /* ── Center Stage ─────────────────────────────── */
    #center_stage {
        width: 1fr;
        height: 100%;
        layout: vertical;
    }

    /* ── Right Sidebar (Activity Log) ─────────────── */
    #log_sidebar {
        width: 28;
        height: 1fr;
        min-height: 100%;
        background: $surface;
        border-left: solid $primary;
        padding: 0;
        layout: vertical;
    }
    #log_sidebar_header {
        background: $surface;
        color: #FF8800;
        text-style: bold;
        padding: 0 1;
        height: 1;
        width: 100%;
    }
    #monitor_log {
        height: 1fr;
        padding: 0 1;
        background: $surface;
    }
    #monitor_log:focus {
        border: solid $accent;
    }

    /* ── Shared Utility Classes ────────────────────── */
    .hidden {
        display: none;
    }
    .status-active {
        color: $accent;
        text-style: bold;
        margin-top: 1;
    }
    .status-inactive {
        color: red;
    }
    .midi-led {
        color: white;
        background: $background;
        padding: 0 1;
    }
    .midi-connected {
        color: #00FF00 !important;
        text-style: bold;
    }
    .activity-led {
        color: grey;
    }
    .activity-active {
        color: #FFFF00 !important;
        text-style: bold;
    }
    .sidebar-row {
        height: 1;
        margin-top: 1;
        width: 100%;
        color: white;
    }
    .spacer {
        width: 1fr;
    }
    Select {
        margin-top: 0;
        margin-bottom: 0;
        height: 3;
        padding: 0;
    }
    Checkbox {
        padding: 0;
    }
    #midi_actions {
        height: 3;
        margin-top: 1;
        margin-bottom: 1;
    }
    #btn_session {
        width: 100%;
        margin-top: 1;
    }
    #tempo_controls {
        height: auto;
        margin-top: 1;
        align: left middle;
    }
    #tempo_controls RadioSet {
        width: 20;
    }
    #tempo_controls Input {
        width: 10;
        margin-left: 2;
    }

    /* ── Jam Settings Layout ──────────────────────── */
    .settings-row {
        height: auto;
        margin-top: 1;
        width: 100%;
    }
    .settings-col {
        width: 1fr;
        height: auto;
    }

    /* ── Stats Dashboard ──────────────────────────── */
    #stats_dashboard {
        background: $surface;
        padding: 0 1;
        height: auto;
        min-height: 2;
        width: 100%;
        border-bottom: solid $primary;
    }
    #stats_row_1 {
        height: 1;
    }
    #stats_row_2 {
        height: 1;
    }
    .stat-label {
        color: $text;
    }
    .stat-value {
        color: $accent;
        text-style: bold;
    }
    #label_bpm_big {
        color: #FFFFFF;
        text-style: bold;
        width: 10;
    }
    #label_gauge_int {
        width: 1fr;
    }
    #label_gauge_cpx {
        width: 1fr;
    }
    #label_bar_dots {
        width: auto;
    }
    #label_beat_dots {
        width: auto;
        margin-left: 2;
    }

    /* ── Session Banner ───────────────────────────── */
    #session_banner {
        height: 3;
        border: solid $primary;
        padding: 0 1;
        background: $surface;
    }
    #session_banner.banner-human {
        background: #003300;
        border: solid #00FF00;
    }
    #session_banner.banner-ai {
        background: #002233;
        border: solid #00AAFF;
    }
    #session_banner.banner-jam {
        background: #1a0033;
        border: solid #AA00FF;
    }
    #session_banner.banner-waiting {
        background: $surface;
        border: solid $primary;
    }
    #session_banner.banner-leadin {
        background: #332200;
        border: solid #FFAA00;
    }
    .stat-box {
        width: 1fr;
        height: 1;
        content-align: left middle;
    }
    .turn-human {
        color: #00FF00 !important;
        text-style: bold italic;
    }
    .monitor-stat {
        color: $accent;
        text-style: bold;
    }

    /* ── Instructions Panel ───────────────────────── */
    #instructions_panel {
        height: 3;
        padding: 0 1;
        content-align: center middle;
        background: $surface;
        border: solid $primary;
        margin-top: 1;
    }
    #label_instructions {
        text-style: bold;
        width: 100%;
        text-align: center;
    }
    #instructions_panel.instructions-human {
        background: #004400;
        border: solid #00FF00;
        color: white;
    }
    #instructions_panel.instructions-fill {
        background: #332200;
        border: solid #FFAA00;
        color: white;
    }
    #instructions_panel.instructions-ai {
        background: #002244;
        border: solid #00AAFF;
        color: white;
    }

    /* ── Jam Controls ─────────────────────────────── */
    #jam_controls {
        height: auto;
        padding: 0 1;
        margin-top: 1;
        background: $surface;
        border: solid #AA00FF;
    }
    #jam_controls .settings-row {
        margin-top: 0;
    }
    #jam_controls .settings-grid {
        height: auto;
        margin-top: 0;
        grid-size: 3;
        grid-gutter: 0 1;
        width: 100%;
        overflow: hidden;
    }
    #jam_controls .settings-col {
        width: 1fr;
        height: 5;
        min-width: 0;
        overflow: hidden;
        border: solid $accent;
        align: left middle;
    }
    #jam_controls .flow-grid {
        height: auto;
        margin-top: 0;
    }
    #jam_controls Select {
        width: 1fr;
        height: 3;
        min-width: 0;
        overflow: hidden;
        padding: 0;
        margin: 0;
    }
    #jam_controls Checkbox {
        width: auto;
        height: auto;
        margin-left: 0;
        margin-right: 1;
        margin-top: 0;
    }

    /* ── Groove / Bouncing Ball ────────────────────── */
    #groove_section {
        height: auto;
        padding: 0 1;
        margin-top: 1;
    }
    .monitor-header {
        color: #00AAFF;
        text-style: bold;
        width: 100%;
        padding: 0 1;
    }
    .groove-bar {
        color: white;
        width: 100%;
        height: 1;
        padding-left: 1;
        text-style: bold;
    }


    /* ── Drum Kit (Dual Layer) ─────────────────────── */
    #kit_section {
        height: auto;
        padding: 0 1;
        margin-top: 1;
    }
    .kit-label-row {
        height: 1;
        margin-bottom: 0;
    }
    .kit-label {
        width: 1fr;
        min-width: 5;
        text-align: center;
        color: $accent;
        text-style: bold;
    }
    .kit-row {
        height: 3;
        margin: 0;
    }
    .kit-pad {
        width: 1fr;
        min-width: 5;
        height: 3;
        border: solid $accent;
        color: white;
        padding: 0;
        content-align: center middle;
    }
    .kit-indicator {
        width: 1fr;
        min-width: 5;
        height: 3;
        border: solid #555555;
        color: #555555;
        padding: 0;
        content-align: center middle;
    }
    .kit-active {
        background: yellow;
        color: black;
        text-style: bold;
    }
    .kit-active-soft {
        background: #555555;
        color: white;
    }
    .kit-active-hard {
        background: #FF3333;
        color: white;
        text-style: bold;
    }
    .kit-row-label {
        width: 6;
        height: 3;
        content-align: center middle;
        color: $accent;
        text-style: bold;
    }
    .kit-row-label-dim {
        width: 6;
        height: 1;
    }

    /* ── Instrumentalists ─────────────────────────── */
    #center_content {
        height: 1fr;
        width: 100%;
        padding: 0 1;
    }
    .agent-row {
        margin-top: 1;
        height: auto;
    }
    .agent-visual {
        color: $secondary;
        text-style: bold;
        margin-bottom: 0;
        height: 1;
    }

    /* ── Countdown Flash ──────────────────────────── */
    .countdown-flash {
        background: #550000 !important;
    }

    /* ── Visual Click Flashes ─────────────────────── */
    .vclick-beat {
        background: #003344 !important;
        border: solid #00CCFF !important;
    }
    .vclick-turn {
        background: #332200 !important;
        border: solid #FF8800 !important;
    }

    /* ── Monitor Stats (legacy compat) ─────────────── */
    #monitor_stats Select {
        width: 20;
        height: 1;
        max-height: 1;
        padding: 0;
        margin: 0;
    }
    #monitor_stats Horizontal {
        height: 1;
        max-height: 1;
    }

    Button.kit-part {
        border: solid $secondary;
        height: 3;
        padding: 0;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("space", "toggle_session", "Start/Stop"),
        Binding("1", "mode_groove", "Groove", priority=True),
        Binding("2", "mode_shed", "Shed", priority=True),
        Binding("3", "mode_jam", "Jam", priority=True),
        Binding("9", "toggle_click", "Audible Click", priority=True),
        Binding("0", "toggle_visual_click", "Visual Click", priority=True),
        Binding("r", "midi_reset", "Reset"),
        Binding("p", "palette", "palette"),
    ]

    def __init__(self, soundfont_path: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.soundfont_path = soundfont_path
        try:
            self.midi = MIDIEngine(soundfont_path=self.soundfont_path)
        except Exception as e:
            debug_log(f"Warning: MIDI Initialization failed: {e}")
            # Create a bare MIDIEngine without soundfont as fallback
            self.midi = MIDIEngine()

        self.brain = RhythmicBrain()
        self.agents: List[VirtualInstrumentalist] = []
        self.session_active = False
        self.jam_session: Optional[JamSession] = None
        self.beats_per_bar = 4
        self._trading_enabled = False
        self._hit_buffer = []
        self._hit_timer = None
        self._log_messages = []
        self.midi.log_callback = self.update_log
        self.click_track_active = False  # Default to off
        self.visual_click_active = False
        self._session_mode = "groove"  # Track selected mode

    @staticmethod
    def _as_str(value: object) -> Optional[str]:
        """Return value as non-empty str when possible, else None."""
        return value if isinstance(value, str) and value else None

    def compose(self) -> ComposeResult:
        yield Header()

        # ── Left Sidebar ──────────────────────────────
        with VerticalScroll(id="sidebar"):
            with Vertical(id="sidebar_inner"):
                # Section 1: MIDI Settings
                yield Label("MIDI Configuration", classes="status-active")
                with Horizontal(classes="sidebar-row"):
                    yield Label("Input (Drums)")
                    yield Static("", classes="spacer")
                    yield Label("⚡", id="conn_in", classes="midi-led")
                    yield Label("●", id="led_in", classes="midi-led activity-led")

                in_ports = self.midi.get_input_ports()
                if in_ports:
                    yield Select([(p, p) for p in in_ports], id="input_select", prompt="Select Input...")
                else:
                    yield Static("No Inputs Found", classes="status-inactive", id="no_in_ports")

                with Horizontal(classes="sidebar-row"):
                    yield Label("Output (Synth)")
                    yield Static("", classes="spacer")
                    yield Label("⚡", id="conn_out", classes="midi-led")
                    yield Label("●", id="led_out", classes="midi-led activity-led")

                out_ports = self.midi.get_output_ports()
                if out_ports:
                    yield Select([(p, p) for p in out_ports], id="output_select", prompt="Select Output...")
                else:
                    yield Static("No Outputs Found", classes="status-inactive", id="no_out_ports")

                with Horizontal(id="midi_actions"):
                    yield Button("Rescan", id="btn_rescan", variant="primary")
                    yield Button("Reset", id="btn_reset", variant="error")

                # Section 2: Session Mode
                yield Label("Session Mode", classes="status-active")
                with RadioSet(id="mode_select"):
                    yield RadioButton("Groove", id="mode_groove", value=True)
                    yield RadioButton("Shed", id="mode_shed")
                    yield RadioButton("Jam", id="mode_jam")

                # Section 3: Tempo
                yield Label("Tempo", classes="status-active")
                with Horizontal(id="tempo_controls"):
                    with RadioSet(id="bpm_mode_select"):
                        yield RadioButton("Fixed", id="bpm_fixed", value=True)
                        yield RadioButton("Adaptive", id="bpm_adaptive")
                    yield Input("120", id="bpm_input", type="integer", placeholder="BPM")

                yield Checkbox("Audible Click", id="click_track", value=False)
                yield Checkbox("Visual Click", id="visual_click", value=False)

            # Pinned Button
            yield Button("Start Session", id="btn_session", variant="success")

        # ── Center Stage ──────────────────────────────
        with Vertical(id="center_stage"):
            # 1. Stats Dashboard
            with Vertical(id="stats_dashboard"):
                with Horizontal(id="stats_row_1"):
                    yield Label("♩ 120", id="label_bpm_big")
                    yield Label("", id="label_gauge_int")
                    yield Label("", id="label_gauge_cpx")
                    yield Label("", id="label_bar_dots")
                    yield Label("", id="label_beat_dots")

            # 2. Session Banner (TURN/PHASE — Groove & Shed only)
            with Horizontal(id="session_banner", classes="banner-waiting"):
                with Horizontal(classes="stat-box"):
                    yield Label("TURN: ", classes="monitor-stat")
                    yield Label("HUMAN", id="label_turn", classes="turn-human")
                with Horizontal(classes="stat-box"):
                    yield Label("PHASE: ", classes="monitor-stat")
                    yield Label("Waiting...", id="label_phase")

            # 2a. Instructions Panel (Only visible during active Groove/Shed sessions)
            with Horizontal(id="instructions_panel", classes="hidden"):
                yield Label("Start playing to begin the session.", id="label_instructions")

            # 2b. Jam Controls (shown only in Jam mode)
            with Vertical(id="jam_controls", classes="hidden"):
                yield Label("JAM CONTROL", classes="status-active")
                with Grid(classes="settings-grid"):
                    with Horizontal(classes="settings-col"):
                        yield Select(
                            [("4/4", "4/4"), ("3/4", "3/4"), ("6/8", "6/8"), ("7/8", "7/8"), ("5/4", "5/4")],
                            id="select_time_sig",
                            value="4/4",
                        )
                    with Horizontal(classes="settings-col"):
                        yield Select([(k, k) for k in MusicTheory.KEYS.keys()], id="select_key", value="C")
                    with Horizontal(classes="settings-col"):
                        yield Select(
                            [(s, s) for s in MusicTheory.SCALE_OPTIONS], id="select_scale", value="Major (Ionian)"
                        )

                with Vertical(classes="settings-row hidden"):
                    yield Label("Style")
                    yield Select(
                        [(style.value.replace("_", " ").title(), style.value) for style in PlayingStyle],
                        id="select_style",
                        value=PlayingStyle.ROCK.value,
                    )

                yield Label("Instrumentalists", classes="status-active")
                with ItemGrid(classes="flow-grid", min_column_width=20, stretch_height=False):
                    yield Checkbox("Drummer", id="agent_drummer", value=False)
                    yield Checkbox("Keyboardist", id="agent_keyboardist", value=False)
                    yield Checkbox("Lead Guitar", id="agent_lead_guitar", value=False)
                    yield Checkbox("Rhythm Guitar", id="agent_rhythm_guitar", value=False)
                    yield Checkbox("Bassist", id="agent_bass", value=False)

            # 3. YOUR GROOVE pattern
            with Vertical(id="groove_section", classes="agent-row"):
                yield Label("YOUR GROOVE", classes="status-active")
                yield Label("· · · · · · · · · · · · · · · ·", id="label_groove", classes="agent-visual")

            # 4. Drum Kit
            with Vertical(id="kit_section"):
                yield Label("DRUM KIT", classes="status-active")
                with Horizontal(classes="kit-row"):
                    yield Button("KICK", id="kit_human_36", classes="kit-pad")
                    yield Button("SNAR", id="kit_human_38", classes="kit-pad")
                    yield Button("HH", id="kit_human_42", classes="kit-pad")
                    yield Button("T1", id="kit_human_48", classes="kit-pad")
                    yield Button("T2", id="kit_human_45", classes="kit-pad")
                    yield Button("T3", id="kit_human_41", classes="kit-pad")
                    yield Button("CR1", id="kit_human_49", classes="kit-pad")
                    yield Button("CR2", id="kit_human_57", classes="kit-pad")
                    yield Button("RIDE", id="kit_human_51", classes="kit-pad")

            # 5. Instrumentalists (scrollable)
            with VerticalScroll(id="center_content"):
                yield Label("INSTRUMENTALISTS", classes="status-active")
                with Vertical(id="agent_visuals"):
                    pass  # Dynamic agent rows will be added here

        # ── Right Sidebar (Activity Log) ──────────────
        with Vertical(id="log_sidebar"):
            yield Label("ACTIVITY LOG", id="log_sidebar_header")
            yield RichLog(id="monitor_log", max_lines=1000, wrap=True)

        yield Footer()

    def on_mount(self):
        self._thread_id = threading.get_ident()
        # Enable focus for the activity log to allow text selection
        self.query_one("#monitor_log").can_focus = True

        # Update display every 100ms for metronome pulsing and stats
        self.set_interval(0.1, self.update_analysis_display)
        # Ensure default metronome is visible
        self.update_metronome_layout(4)
        # Show default mode's groove bars
        self._update_mode_visibility()

        # Setup Beat Callback
        self.brain.on_beat_callback = self.on_beat_detected
        self.brain.on_tick_callback = self.on_tick_detected

        # Start master clock
        self.clock_thread = ClockThread(self)
        self.clock_thread.start()

        # Initial stats
        self._update_stats_dashboard()
        self._update_mode_visibility()

    def safe_call(self, func, *args, **kwargs):
        """Safely calls a UI-related function regardless of which thread we are on."""
        if threading.get_ident() == self._thread_id:
            func(*args, **kwargs)
        else:
            self.call_from_thread(func, *args, **kwargs)

    # ── Keyboard Shortcut Actions ─────────────────────────────────────

    def action_toggle_session(self) -> None:
        """Start or stop the session via Space key."""
        if not self.session_active:
            self.start_session()
        else:
            self.stop_session()

    def _adjust_bpm(self, delta: int) -> None:
        """Nudge the fixed BPM by delta, clamping to valid range."""
        try:
            inp = self.query_one("#bpm_input", Input)
            current = int(inp.value or 120)
        except (ValueError, TypeError):
            current = 120
        new_bpm = max(40, min(300, current + delta))
        self.brain.set_bpm(float(new_bpm))
        try:
            self.query_one("#bpm_input", Input).value = str(new_bpm)
        except Exception:
            pass

    def action_bpm_up(self) -> None:
        """Increment BPM by 1 via '+' key."""
        self._adjust_bpm(1)

    def action_bpm_down(self) -> None:
        """Decrement BPM by 1 via '-' key."""
        self._adjust_bpm(-1)

    def action_toggle_click(self) -> None:
        """Toggle audible click track via '9' key."""
        try:
            cb = self.query_one("#click_track", Checkbox)
            cb.value = not cb.value
        except Exception:
            pass

    def action_toggle_visual_click(self) -> None:
        """Toggle visual click via '0' key."""
        try:
            cb = self.query_one("#visual_click", Checkbox)
            cb.value = not cb.value
        except Exception:
            pass

    def action_midi_reset(self) -> None:
        """MIDI panic via 'r' key."""
        self.midi_panic()

    def action_palette(self) -> None:
        """Open the command palette via 'p' key."""
        try:
            self.action_command_palette()
        except Exception:
            pass

    def _set_session_mode(self, mode: str) -> None:
        """Apply session mode and keep mode radio + panel visibility in sync."""
        mode_to_id = {
            "groove": "mode_groove",
            "shed": "mode_shed",
            "jam": "mode_jam",
        }
        if mode not in mode_to_id:
            return

        self._session_mode = mode
        try:
            self.query_one(f"#{mode_to_id[mode]}", RadioButton).value = True
        except Exception:
            pass

        try:
            controls = self.query_one("#jam_controls")
            if mode == "jam":
                controls.remove_class("hidden")
            else:
                controls.add_class("hidden")
        except Exception:
            pass

        self._update_mode_visibility()

    def _select_radio_mode(self, mode_id: str) -> None:
        """Programmatically select a session mode radio button."""
        mode = {
            "mode_groove": "groove",
            "mode_shed": "shed",
            "mode_jam": "jam",
        }.get(mode_id)
        if mode:
            self._set_session_mode(mode)

    def action_mode_groove(self) -> None:
        """Switch session mode to Groove via '1' key."""
        self._select_radio_mode("mode_groove")

    def action_mode_shed(self) -> None:
        """Switch session mode to Shed via '2' key."""
        self._select_radio_mode("mode_shed")

    def action_mode_jam(self) -> None:
        """Switch session mode to Jam via '3' key."""
        self._select_radio_mode("mode_jam")

    # ── Event Handlers ────────────────────────────────────────────────

    @on(Input.Changed)
    def on_bpm_change(self, event: Input.Changed) -> None:
        if event.input.id == "bpm_input":
            try:
                val = int(event.value)
                self.brain.set_bpm(float(val))
            except (ValueError, TypeError):
                pass

    @on(Checkbox.Changed, "#click_track")
    def on_click_track_changed(self, event: Checkbox.Changed):
        self.click_track_active = event.value

    @on(Checkbox.Changed, "#visual_click")
    def on_visual_click_changed(self, event: Checkbox.Changed):
        self.visual_click_active = event.value

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.pressed is None:
            return

        if event.radio_set.id == "bpm_mode_select":
            mode = "fixed" if event.pressed.id == "bpm_fixed" else "adaptive"
            self.brain.bpm_mode = mode
            try:
                inp = self.query_one("#bpm_input", Input)
                if mode == "adaptive":
                    inp.add_class("hidden")
                else:
                    inp.remove_class("hidden")
                    inp.value = str(int(self.brain.bpm))
            except Exception:
                pass

        elif event.radio_set.id == "mode_select":
            mode = (
                "jam" if event.pressed.id == "mode_jam" else ("groove" if event.pressed.id == "mode_groove" else "shed")
            )
            self._set_session_mode(mode)

    def _update_mode_visibility(self):
        """Show/hide TURN/PHASE based on selected mode."""
        try:
            banner = self.query_one("#session_banner")
            if self._session_mode == "jam":
                banner.add_class("hidden")
            else:
                banner.remove_class("hidden")
        except Exception:
            pass

        # Groove/Shed always have an AI drummer — show placeholder row immediately
        try:
            container = self.query_one("#agent_visuals", Vertical)
            if self._session_mode in ("groove", "shed"):
                try:
                    container.query_one("#agent_row_drummer", Vertical)
                except Exception:
                    new_row = Vertical(id="agent_row_drummer", classes="agent-row")
                    container.mount(new_row)
                    new_row.mount(Label("DRUMMER", classes="status-active"))
                    new_row.mount(Label("· · · · · · · · · · · · · · · ·", classes="agent-visual"))
            else:
                # In Jam mode, remove the auto-mounted drummer row (checkboxes control agents)
                try:
                    container.query_one("#agent_row_drummer", Vertical).remove()
                except Exception:
                    pass
        except Exception:
            pass

    @on(Select.Changed)
    def handle_selection(self, event: Select.Changed) -> None:
        selected = self._as_str(event.value)
        if selected is None:
            return

        if event.select.id == "input_select":
            self.update_log(f"Attempting to open Input: {selected}")
            if self.midi.open_input(selected, callback=self.midi_callback):
                self.update_log(f"SUCCESS: Listening on {selected}")
            else:
                self.update_log(f"FAILED: Could not open Input {selected}")

        elif event.select.id == "output_select":
            self.update_log(f"Attempting to open Output: {selected}")
            if self.midi.open_output(selected):
                self.update_log(f"SUCCESS: Sending to {selected}")
            else:
                self.update_log(f"FAILED: Could not open Output {selected}")

        elif event.select.id in ["select_key", "select_scale"]:
            key = self._as_str(self.query_one("#select_key", Select).value)
            scale = self._as_str(self.query_one("#select_scale", Select).value)
            if key is None or scale is None:
                return
            for agent in self.agents:
                agent.update_theory(key, scale)

        elif event.select.id == "select_time_sig":
            sig = selected
            try:
                beats = int(sig.split("/")[0])
                if self.jam_session:
                    self.jam_session.beats_per_bar = beats

                # Notify Brain
                self.brain.update_time_signature(beats)

                # Update Agents
                for agent in self.agents:
                    if hasattr(agent, "setup_grid"):
                        agent.setup_grid(beats, agent.subdivision)
                    else:
                        agent.beats_per_bar = beats

                self.update_metronome_layout(beats)
                self.update_log(f"Time Signature set to {sig}")
            except (ValueError, AttributeError):
                pass

        # Immediate UI refresh
        self.update_analysis_display()

    # ── MIDI Handling ─────────────────────────────────────────────────

    def midi_callback(self, message, time_stamp):
        msg, delta = message

        # Suppress noisy system messages (248=Clock, 254=Active Sensing)
        if len(msg) == 1 and msg[0] in [248, 254]:
            return

        debug_log(f"MIDI_EVENT: {msg}")

        # Log hardware hits to the UI log
        if len(msg) > 0:
            if not ((msg[0] & 0xF0) == 0x90):
                self.safe_call(self.update_log, f"RAW MIDI: {msg}")
        if len(msg) >= 3 and (msg[0] & 0xF0) == 0x90:
            note = msg[1]
            velocity = msg[2]

            if velocity > 0:
                # First hit detection
                if self.jam_session and self.jam_session.waiting_for_first_hit:
                    self.jam_session.start_first_hit()
                    self.brain.reset_beat_clock()  # anchors wall-clock; sets is_jamming=True
                    self.on_beat_detected()  # fire beat 0 synchronously
                    self.safe_call(self.update_log, "SIGNAL RECEIVED: 1-Bar Lead-in...")
                    self.safe_call(self.blink_led, "led_in")
                    return

                # Human input goes on channel 10 (0-indexed: 9)
                self._play_drum_hit([note], agent_name="ME", channel=9)

                # Process in brain
                self.brain.process_hit(note, velocity)
                self.brain.capture_scrolling_hit(note)

                # Capture to Grid (4-bar window)
                bar_in_phrase = 0
                bar_beat = 0

                if self.jam_session:
                    bar_in_phrase = self.jam_session.bars_elapsed % 4
                    if not self.jam_session.waiting_for_first_hit:
                        bar_beat = self.jam_session.beats_elapsed

                # Estimate sub-beat
                beat_duration = 60.0 / self.brain.bpm if self.brain.bpm > 0 else 0.5
                sub_beat = int((self.brain.beat_accumulator / beat_duration) * 12)
                sub_beat = max(0, min(11, sub_beat))

                # Absolute tick in 4-bar phrase
                tick_idx = (bar_in_phrase * 4 * 12) + (bar_beat * 12) + sub_beat
                self.brain.record_to_grid_absolute(tick_idx, note, velocity)

                self.safe_call(self.blink_led, "led_in")

                # Visual highlight for human kit
                pad_note = note
                if note == 40:
                    pad_note = 38
                if note in [44, 46]:
                    pad_note = 42
                if note == 43:
                    pad_note = 41

                if pad_note in self.DRUM_NAMES:
                    self.safe_call(self.blink_kit_part, pad_note, "kit_human")

    def _buffer_midi_hit(self, msg):
        self._hit_buffer.append(msg)
        if self._hit_timer:
            self._hit_timer.stop()
        self._hit_timer = self.set_timer(0.02, self._flush_hit_buffer)

    def _flush_hit_buffer(self):
        if not self._hit_buffer:
            return

        names = []
        raw_data = []
        for msg in self._hit_buffer:
            names.append(self.DRUM_NAMES.get(msg[1], "NOTE"))
            raw_data.append(str(msg))

        log_msg = f"DRUMMER: {' + '.join(raw_data)} ({' + '.join(names)})"
        self.update_log(log_msg)
        self._hit_buffer = []
        self._hit_timer = None

    # ── Visual Feedback ───────────────────────────────────────────────

    def flash_ui(self):
        """Briefly flashes the monitor background during countdowns."""
        try:
            monitor = self.query_one("#center_stage")
            monitor.add_class("countdown-flash")
            self.set_timer(0.1, lambda: monitor.remove_class("countdown-flash"))
        except Exception:
            pass

    def _flash_banner_vclick(self, flash_class: str):
        """Flash the session banner on a visual-click beat."""
        try:
            banner = self.query_one("#session_banner")
            banner.add_class(flash_class)
            self.set_timer(0.12, lambda: banner.remove_class(flash_class))
        except Exception:
            pass

    def blink_led(self, led_id: str):
        try:
            led = self.query_one(f"#{led_id}", Label)
            led.add_class("activity-active")
            self.set_timer(0.1, lambda: led.remove_class("activity-active"))
        except Exception:
            pass

    def blink_kit_part(self, note: int, prefix: str):
        try:
            part = self.query_one(f"#{prefix}_{note}")
            part.add_class("kit-active")
            self.set_timer(0.1, lambda: part.remove_class("kit-active"))
        except Exception:
            pass

    @staticmethod
    def _format_pitched_note_name(note: int) -> str:
        """Format a MIDI note number as a pitched note name with octave."""
        note_name = MusicTheory.get_note_name(note)
        octave = (note // 12) - 1
        return f"{note_name}{octave}"

    @classmethod
    def _note_label_for_log(cls, agent_name: str, note: int, channel: Optional[int] = None) -> str:
        """Return the proper note label for logs based on drum vs pitched context."""
        normalized_name = (agent_name or "").strip().upper()
        is_drum_event = channel == 9 or normalized_name in cls.DRUM_AGENT_NAMES
        if is_drum_event:
            return cls.DRUM_NAMES.get(note, f"{note}")
        return cls._format_pitched_note_name(note)

    @staticmethod
    def _bar_display_index(bars_elapsed: int, bars_per_cycle: int) -> int:
        """Convert bars_elapsed to zero-based index within the cycle.

        Args:
            bars_elapsed: 1-indexed bar count (starting from 1)
            bars_per_cycle: Length of the cycle (e.g., 4, 8, 12)

        Returns:
            Zero-based index within the cycle (0 to bars_per_cycle - 1)
        """
        return (bars_elapsed - 1) % bars_per_cycle

    @staticmethod
    def _should_emit_countin_click(is_leadin: bool, click_track_enabled: bool) -> bool:
        """Determine if count-in click should be emitted.

        Args:
            is_leadin: Whether session is in lead-in phase
            click_track_enabled: Whether click track is enabled by user

        Returns:
            True if click should be emitted, False otherwise
        """
        return is_leadin or click_track_enabled

    def log_agent_activity(self, agent_name: str, note: int, channel: Optional[int] = None):
        self.safe_call(self.blink_led, "led_out")
        name = self._note_label_for_log(agent_name, note, channel)
        self.safe_call(self.update_log, f"{agent_name.upper()}: {name}")

    # ── Display Updates ───────────────────────────────────────────────

    def _update_stats_dashboard(self):
        """Update the stats dashboard with gauges and dot indicators."""
        try:
            state = self.brain.get_state()
            bpm = state["bpm"]
            intensity = int(state["intensity"])
            complexity = state["complexity"]

            # BPM (large)
            self.query_one("#label_bpm_big", Label).update(f"♩ {bpm:.0f}")

            # Gauge bars
            self.query_one("#label_gauge_int", Label).update(
                render_gauge(intensity, width=15, max_value=127, color="yellow", label="INT")
            )
            self.query_one("#label_gauge_cpx", Label).update(
                render_gauge(complexity * 100, width=15, max_value=100, color="cyan", label="CPX")
            )

            # Beat dots
            if self.jam_session and self.session_active:
                status = self.jam_session.get_status()
                bars_elapsed = status.get("bars_elapsed", 0)
                beat_in_bar = status.get("beats_elapsed", 0)
                bars_per_cycle = getattr(self.jam_session, "bars_per_cycle", 8)
                is_groove = getattr(self.jam_session, "is_groove", False)
                is_leadin = status.get("is_leadin", False)
                is_waiting = status.get("is_waiting", False)

                # bars_elapsed is 1-indexed (incremented on each bar transition),
                # so subtract 1 to get a 0-indexed dot position.
                # During lead-in/waiting, show no dots lit (-1).
                if is_leadin or is_waiting:
                    bar_in_display = -1
                    bars_per_display = 4  # arbitrary, nothing will be lit
                elif is_groove:
                    bars_per_display = bars_per_cycle // 2  # 4 dots per turn
                    bar_in_display = bars_elapsed % bars_per_display
                else:
                    bars_per_display = bars_per_cycle
                    bar_in_display = bars_elapsed % bars_per_cycle

                self.query_one("#label_bar_dots", Label).update(
                    render_beat_dots(bar_in_display, min(bars_per_display, 12), label="BAR", active_color="yellow")
                )
                beat_display = -1 if (is_leadin or is_waiting) else beat_in_bar
                self.query_one("#label_beat_dots", Label).update(
                    render_beat_dots(beat_display, self.beats_per_bar, label="BEAT", active_color="green")
                )
            else:
                self.query_one("#label_bar_dots", Label).update(
                    render_beat_dots(-1, self.beats_per_bar, label="BAR", active_color="yellow")
                )
                self.query_one("#label_beat_dots", Label).update(
                    render_beat_dots(-1, self.beats_per_bar, label="BEAT", active_color="green")
                )
        except Exception:
            pass

    def _update_session_banner(self):
        """Update the session banner color and content based on state."""
        try:
            banner = self.query_one("#session_banner")
            # Remove all banner classes
            for cls in ["banner-human", "banner-ai", "banner-jam", "banner-waiting", "banner-leadin"]:
                banner.remove_class(cls)

            if not self.session_active or not self.jam_session:
                banner.add_class("banner-waiting")
                self.query_one("#label_turn", Label).update("HUMAN")
                self.query_one("#label_turn", Label).add_class("turn-human")
                self.query_one("#label_phase", Label).update("Waiting...")
                try:
                    self.query_one("#instructions_panel").add_class("hidden")
                except Exception:
                    pass
                return

            status = self.jam_session.get_status()

            if status.get("is_leadin"):
                banner.add_class("banner-leadin")
            elif status["current_soloist"].upper() == "HUMAN":
                banner.add_class("banner-human")
            else:
                banner.add_class("banner-ai")

            # Turn label
            turn_label = self.query_one("#label_turn", Label)
            soloist = status["current_soloist"].upper()
            bars_left = status.get("bars_left_in_turn", 0)
            turn_text = f"{soloist} (Bars Left: {bars_left})" if bars_left > 0 else soloist
            turn_label.update(turn_text)

            if soloist == "HUMAN":
                turn_label.add_class("turn-human")
            else:
                turn_label.remove_class("turn-human")

            # Phase label
            phase_text = status["phase"]
            self.query_one("#label_phase", Label).update(phase_text)

            # Instructions Update
            try:
                instructions_panel = self.query_one("#instructions_panel")
                instructions_label = self.query_one("#label_instructions", Label)

                if status.get("is_waiting"):
                    instructions_panel.remove_class("hidden")
                    instructions_label.update("Start playing to begin the session.")
                elif status.get("is_leadin"):
                    instructions_panel.remove_class("hidden")
                    instructions_label.update("Get ready... 1 bar count-in!")
                elif "YOUR GROOVE" in phase_text or "GROOVE: Human" in phase_text:
                    instructions_panel.remove_class("hidden")
                    instructions_panel.classes = "instructions-human"
                    instructions_label.update("YOUR TURN: Play a steady 4-bar groove!")
                elif "HUMAN FILL" in phase_text:
                    instructions_panel.remove_class("hidden")
                    instructions_panel.classes = "instructions-human instructions-fill"
                    instructions_label.update("YOUR TURN: Chop! / Play a fill over the AI's groove!")
                elif "AI GROOVE" in phase_text or "AI FILL" in phase_text:
                    instructions_panel.remove_class("hidden")
                    instructions_panel.classes = "instructions-ai"
                    instructions_label.update(
                        "AI'S TURN: Keep the groove steady."
                        if "AI FILL" in phase_text
                        else "AI'S TURN: Listening & responding..."
                    )
                else:
                    instructions_panel.add_class("hidden")
            except Exception:
                pass

        except Exception:
            pass

    def _update_scrolling_histories(self) -> None:
        """High-frequency update for the scrolling history. Called every tick (12x per beat)."""
        if not self.jam_session:
            return

        status = self.jam_session.get_status()
        if status.get("is_waiting"):
            return

        # Scrolling History Logic
        current_bar_beat = status["beats_elapsed"]
        beat_duration = 60.0 / self.brain.bpm if self.brain.bpm > 0 else 0.5
        current_sub_beat = int((self.brain.beat_accumulator / beat_duration) * 12)
        current_sub_beat = max(0, min(11, current_sub_beat))

        # 1. Update Human Scrolling History
        self.brain.advance_scrolling_history(current_bar_beat, current_sub_beat)
        self.query_one("#label_groove", Label).update(self.brain.get_scrolling_visual())

        # 2. Update bouncing ball → now integrated as ▶ in get_scrolling_visual()

        # 3. Update AI Scrolling History (delegated to agents' internal buffers)
        for agent in self.agents:
            if hasattr(agent, "advance_scrolling_history"):
                agent.advance_scrolling_history(current_bar_beat, current_sub_beat, [])

        # 4. Update agent groove bars in INSTRUMENTALISTS
        self._update_agent_visuals(current_bar_beat, current_sub_beat)

    def update_analysis_display(self) -> None:
        # Update connection status (sidebar only)
        try:
            conn_in = self.query_one("#conn_in", Label)
            if self.midi.is_in_open():
                conn_in.styles.color = "#00FF00"
                conn_in.styles.text_style = "bold"
            else:
                conn_in.styles.color = "white"
        except Exception:
            pass

        try:
            conn_out = self.query_one("#conn_out", Label)
            if self.midi.is_out_open():
                conn_out.styles.color = "#00FF00"
                conn_out.styles.text_style = "bold"
            else:
                conn_out.styles.color = "white"
        except Exception:
            pass

        # Stats dashboard
        self._update_stats_dashboard()

        # Session banner (Groove/Shed)
        self._update_session_banner()

    def _update_agent_visuals(self, current_beat=0, current_sub_beat=0):
        """Updates the melodic history visualizer for active agents."""
        if not self.agents:
            return

        try:
            container = self.query_one("#agent_visuals", Vertical)
            for agent in self.agents:
                try:
                    visual_text: str = ""
                    if hasattr(agent, "get_scrolling_visual"):
                        visual_text = str(agent.get_scrolling_visual())
                    else:
                        get_history_visual = getattr(agent, "get_history_visual", None)
                        if callable(get_history_visual):
                            visual_text = str(get_history_visual())

                    if not visual_text:
                        visual_text = "· · · · · · · · · · · · · · · ·"

                    agent_id = agent.name.lower().replace(" ", "_").replace("(", "").replace(")", "")

                    try:
                        row = container.query_one(f"#agent_row_{agent_id}", Vertical)
                        row.query_one(".agent-visual", Label).update(visual_text)
                    except Exception:
                        # Before creating a new one, aggressively attempt to remove any broken/stale placeholder
                        try:
                            stale = container.query_one(f"#agent_row_{agent_id}")
                            if stale:
                                stale.remove()
                        except Exception:
                            pass

                        new_row = Vertical(id=f"agent_row_{agent_id}", classes="agent-row")
                        container.mount(new_row)
                        new_row.mount(Label(agent.name.upper(), classes="status-active"))
                        new_row.mount(Label(visual_text, classes="agent-visual"))
                except Exception as e:
                    self.safe_call(self.update_log, f"Visual error {agent.name}: {str(e)[:50]}")
        except Exception as e:
            self.safe_call(self.update_log, f"Container error: {str(e)[:50]}")

    # ── Button & Key Handlers ─────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_session":
            if not self.session_active:
                self.start_session()
            else:
                self.stop_session()
        elif event.button.id == "btn_rescan":
            self.rescan_midi()
        elif event.button.id == "btn_reset":
            self.midi_panic()
        elif event.button.id and event.button.id.startswith("kit_human_"):
            # Trigger drum hit from clicking YOU pad
            note = int(event.button.id.split("_")[-1])
            self.flash_pad_visual(note)
            self._play_drum_hit([note], agent_name="MANUAL", channel=9)

    def on_key(self, event) -> None:
        """Handle keyboard input for drumming and BPM control."""
        char = event.character or ""

        # BPM nudge — handled here because symbol key names are unreliable in BINDINGS
        if char == "=":
            self.action_bpm_up()
            return
        if char == "-":
            self.action_bpm_down()
            return

        # Drum key map: z,x,c,v,b,n,m,,,. → Kick, Snare, HH, Toms, Crash 1, Crash 2, Ride
        key_map = {
            "z": 36,  # Kick
            "x": 38,  # Snare
            "c": 42,  # HH Closed
            "v": 48,  # High Tom (T1)
            "b": 45,  # Mid Tom (T2)
            "n": 41,  # Low Tom (T3)
            "m": 49,  # Crash 1
            ",": 57,  # Crash 2
            ".": 51,  # Ride
        }
        if char.lower() in key_map:
            note = key_map[char.lower()]
            self.flash_pad_visual(note)
            self._play_drum_hit([note], agent_name="MANUAL", channel=9)

    def flash_pad_visual(self, note: int):
        """Flash the YOU kit pad when a note is triggered manually."""
        try:
            pad = self.query_one(f"#kit_human_{note}")
            pad.add_class("kit-active")

            def clear(p=pad):
                try:
                    p.remove_class("kit-active")
                except Exception:
                    pass

            self.set_timer(0.1, clear)
        except Exception:
            pass

    @on(Checkbox.Changed)
    def handle_agent_toggle(self, event: Checkbox.Changed) -> None:
        """Handles adding/removing agents via checkboxes."""
        cid = event.checkbox.id
        if cid is None:
            return
        if event.value:
            self._add_fixed_agent(cid)
        else:
            self._remove_fixed_agent(cid)

    def _add_fixed_agent(self, checkbox_id: str):
        mapping = {
            "agent_drummer": (VirtualDrummer, 9, "Drummer"),
            "agent_keyboardist": (VirtualKeyboardist, 4, "Keyboardist"),
            "agent_lead_guitar": (VirtualLeadGuitarist, 1, "Lead Guitar"),
            "agent_rhythm_guitar": (VirtualRhythmGuitarist, 2, "Rhythm Guitar"),
            "agent_bass": (VirtualBassist, 3, "Bass"),
        }
        if checkbox_id not in mapping:
            return

        agent_cls, chan, name = mapping[checkbox_id]

        if any(agent.name == name for agent in self.agents):
            return

        try:
            style_select = self.query_one("#select_style", Select)
            style_value = self._as_str(style_select.value)
            style = PlayingStyle(style_value) if style_value is not None else PlayingStyle.ROCK
        except (Exception, ValueError):
            style = PlayingStyle.ROCK

        new_agent = agent_cls(name, self.midi, self.brain, channel=chan, style=style)
        new_agent.on_play_callback = self.log_agent_activity

        key = self._as_str(self.query_one("#select_key", Select).value)
        scale = self._as_str(self.query_one("#select_scale", Select).value)
        if key is not None and scale is not None:
            new_agent.update_theory(key, scale)
        sig = self._as_str(self.query_one("#select_time_sig", Select).value)
        if hasattr(new_agent, "beats_per_bar") and sig is not None:
            new_agent.beats_per_bar = int(sig.split("/")[0])

        self.agents.append(new_agent)

        # Immediately mount a groove bar row in INSTRUMENTALISTS
        agent_id = name.lower().replace(" ", "_").replace("(", "").replace(")", "")
        try:
            container = self.query_one("#agent_visuals", Vertical)
            try:
                container.query_one(f"#agent_row_{agent_id}", Vertical)
            except Exception:
                new_row = Vertical(id=f"agent_row_{agent_id}", classes="agent-row")
                container.mount(new_row)
                new_row.mount(Label(name.upper(), classes="status-active"))
                new_row.mount(Label("· · · · · · · · · · · · · · · ·", classes="agent-visual"))
        except Exception:
            pass

        if self.jam_session:
            self.jam_session.agents = self.agents

    def _remove_fixed_agent(self, checkbox_id: str):
        agent_to_name = {
            "agent_drummer": "Drummer",
            "agent_keyboardist": "Keyboardist",
            "agent_lead_guitar": "Lead Guitar",
            "agent_rhythm_guitar": "Rhythm Guitar",
            "agent_bass": "Bass",
        }
        name = agent_to_name.get(checkbox_id)
        if not name:
            return

        for i, agent in enumerate(self.agents):
            if agent.name == name:
                self.update_log(f"Removing Agent: {name}")
                agent.stop()

                agent_id = name.lower().replace(" ", "_").replace("(", "").replace(")", "")
                try:
                    self.query_one(f"#agent_row_{agent_id}", Vertical).remove()
                except Exception:
                    pass

                self.agents.pop(i)
                break

        if self.jam_session:
            self.jam_session.agents = self.agents

    def update_metronome_layout(self, beats: int):
        self.beats_per_bar = beats

    # ── Clock Callbacks ───────────────────────────────────────────────

    def on_beat_detected(self):
        """Called by Brain when a quarter-note beat occurs. Master Clock."""
        if not self.session_active or not self.jam_session:
            return

        # 1. Progress Session Logic
        try:
            self.jam_session.notify_beat_elapsed()
            debug_log(f"APP: Beat Processed | beats={self.jam_session.beats_elapsed}/{self.jam_session.beats_per_bar}")
        except Exception as e:
            debug_log(f"APP: Critical Session Error: {e}")

        # 2. Audible Click — sent directly to bypass safe_call latency
        #    With the deferred lead-in transition, is_leadin stays True through
        #    the 4th count-in beat, so post-transition state is correct here.
        try:
            status = self.jam_session.get_status()
            if not status.get("is_waiting"):
                is_leadin = status.get("is_leadin")
                if is_leadin or self.click_track_active:
                    if is_leadin:
                        note = 77  # High Wood Block — count-in accent
                    else:
                        bars_elapsed = status.get("bars_elapsed", 0)
                        bar_in_turn = bars_elapsed % self.jam_session.beats_per_bar
                        note = 75 if bar_in_turn == self.jam_session.beats_per_bar - 1 else 76
                    # Send directly — no safe_call overhead before the MIDI send
                    if self.midi.is_out_open():
                        self.midi.send_message([0x99, note, 100])  # Ch10 note-on
                        self.safe_call(
                            self.set_timer,
                            0.05,
                            lambda n=note: self.midi.send_message([0x89, n, 0]) if self.midi.is_out_open() else None,
                        )
                    self.safe_call(self.update_log, f"CLICK: {note}")
        except Exception as e:
            debug_log(f"APP_CLOCK: Click Error: {e}")

        # 3. Visual Click flash
        if self.visual_click_active:
            try:
                status = self.jam_session.get_status()
                if not status.get("is_waiting") and not status.get("is_leadin"):
                    bars_elapsed = status.get("bars_elapsed", 0)
                    beats_per_bar = self.jam_session.beats_per_bar
                    # Bar 4 of the current turn = last bar → amber; bars 1-3 → cyan
                    bar_in_turn = bars_elapsed % beats_per_bar
                    flash_class = "vclick-turn" if bar_in_turn == beats_per_bar - 1 else "vclick-beat"
                    self.safe_call(self._flash_banner_vclick, flash_class)
            except Exception:
                pass

        # 4. Update UI (DEFERRED to main thread)
        self.safe_call(self.update_analysis_display)

    def on_tick_detected(self, sub_beat):
        """Called by Brain 12 times per beat. Drives agent performance."""
        if not self.session_active or not self.jam_session:
            return

        # High-frequency visual refresh
        self.safe_call(self._update_scrolling_histories)

        status = self.jam_session.get_status()

        # Suppress Agents during Lead-in Count
        if status.get("is_leadin"):
            return

        state = self.brain.get_current_state()
        state["phase"] = status["phase"]
        state["bars_elapsed"] = status.get("bars_elapsed", 0)

        beat = status["beats_elapsed"]
        for agent in self.agents:
            agent.tick(state, beat, sub_beat)

    # ── Playback ──────────────────────────────────────────────────────

    def _play_drum_hit(self, note_list: List[int], agent_name: str, channel: int):
        if agent_name == "MANUAL":
            if self.jam_session and self.jam_session.waiting_for_first_hit:
                self.jam_session.start_first_hit()  # synchronous — must run before clock starts
                self.brain.reset_beat_clock()  # sets _beat_zero_time AND is_jamming=True
                self.on_beat_detected()  # fire beat 0 synchronously
                self.safe_call(self.update_log, "JAM STARTED: Manual hit!")
                self._play_drum_hit([76], agent_name="SIGNAL", channel=10)

            for note in note_list:
                self.brain.process_hit(note, 100)

                if self.jam_session and not self.jam_session.waiting_for_first_hit:
                    # Fix: Record into correct 4-bar phrase index (0-191 ticks)
                    bars_elapsed = self.jam_session.get_status().get("bars_elapsed", 0)
                    bar_in_phrase = bars_elapsed % 4
                    abs_tick = (bar_in_phrase * 48) + (self.jam_session.beats_elapsed * 12)

                    beat_duration = 60.0 / self.brain.bpm if self.brain.bpm > 0 else 0.5
                    sub_beat = int((self.brain.beat_accumulator / beat_duration) * 12)
                    sub_beat = max(0, min(11, sub_beat))

                    self.brain.record_to_grid_absolute(abs_tick + sub_beat, note, 100)

        status_byte = 0x90 | (channel & 0x0F)

        for note in note_list:
            msg_on = [status_byte, note, random.randint(80, 110)]

            self.log_agent_activity(agent_name, note, channel)

            if self.midi.is_out_open():
                self.midi.send_message(msg_on)

            off_byte = 0x80 | (channel & 0x0F)
            self.safe_call(self.set_timer, 0.1, lambda n=note, b=off_byte: self._send_note_off(n, b))

    def _send_note_off(self, note: int, status_byte: int):
        if self.midi.is_out_open():
            msg_off = [status_byte, note, 0]
            self.midi.send_message(msg_off)

    def midi_panic(self):
        """Sends All Notes Off on all 16 channels to reset the synth engine."""
        if self.midi.midi_out and self.midi.midi_out.is_port_open():
            for chan in range(16):
                self.midi.send_message([0xB0 | chan, 123, 0])
            self.notify("MIDI Reset Sent")

    # ── Session Lifecycle ─────────────────────────────────────────────

    def start_session(self):
        if not self.midi.is_out_open():
            ui_val = self._as_str(self.query_one("#output_select", Select).value)
            if ui_val is not None:
                if self.midi.open_output(ui_val):
                    self.notify(f"Reconnected MIDI: {ui_val}")
                else:
                    self.notify(f"Could not connect to: {ui_val}", severity="error")
                    return
            else:
                self.notify("Please select a MIDI Output first!", severity="error")
                return

        # Clear existing state
        self.brain.reset_history()
        self.agents = []

        # Reset groove meter visuals
        try:
            self.query_one("#label_groove", Label).update("[bold green]▶[/]")
            container = self.query_one("#agent_visuals", Vertical)
            for widget in container.query(".agent-visual"):
                if isinstance(widget, Label):
                    widget.update("[bold green]▶[/]")

            # Specifically clear the drummer placeholder visual if it exists
            try:
                drummer_visual = container.query_one("#agent_row_drummer .agent-visual", Label)
                drummer_visual.update("[bold green]▶[/]")
            except Exception:
                pass
        except Exception:
            pass

        self.session_active = True
        self.query_one("#btn_session", Button).label = "Stop Session"
        self.query_one("#btn_session", Button).variant = "error"
        self.query_one("#mode_select").disabled = True

        mode_radio = self.query_one("#mode_select", RadioSet).pressed_button
        mode_id = mode_radio.id if mode_radio is not None else "mode_groove"
        is_shed = mode_id == "mode_shed"
        is_groove = mode_id == "mode_groove"

        if is_shed or is_groove:
            mode_name = "Groove" if is_groove else "Drum Shed"
            self.update_log(f"INITIALIZING: {mode_name} Mode...")
            from jam_shed.agents.drummer import DrumShedAgent

            drum_partner: VirtualInstrumentalist = DrumShedAgent("DRUMMER", self.midi, self.brain, channel=9)
            drum_partner.on_play_callback = self.log_agent_activity
            self.agents = [drum_partner]
            self._virtual_active = True
        else:
            self.update_log("INITIALIZING: Jam Session Mode...")
            self._virtual_active = False
            for cid in ["agent_drummer", "agent_keyboardist", "agent_lead_guitar", "agent_rhythm_guitar", "agent_bass"]:
                try:
                    cb = self.query_one(f"#{cid}", Checkbox)
                    if cb.value:
                        self._add_fixed_agent(cid)
                except Exception:
                    pass

        # Initialize the session state manager with the brain
        self.jam_session = JamSession(self.agents, self.brain)
        self.jam_session.is_trading = is_shed
        self.update_log(f"SESSION READY: {len(self.agents)} Agent(s) Registered.")

        # Set time signature from UI
        sig = self._as_str(self.query_one("#select_time_sig", Select).value) or "4/4"
        self.jam_session.beats_per_bar = int(sig.split("/")[0])
        self.update_metronome_layout(self.jam_session.beats_per_bar)

        # Wire up the Master Clock Callbacks
        self.brain.on_beat_callback = self.on_beat_detected
        self.brain.on_tick_callback = self.on_tick_detected
        self.jam_session.on_bar_elapsed = self.brain.notify_bar_elapsed
        self.jam_session.on_cycle_reset = self._on_cycle_reset
        self.jam_session.on_turn_change = self._on_turn_change

        # Reset counters and patterns
        self.brain.current_bar = 0
        self.brain.clear_pattern("groove")
        self.brain.clear_pattern("fill")
        self.jam_session.bars_elapsed = 0

        # Initialize Session Theory
        key = self._as_str(self.query_one("#select_key", Select).value) or "C"
        scale = self._as_str(self.query_one("#select_scale", Select).value) or "Major (Ionian)"
        self.jam_session.update_theory(key, scale, "12-Bar Blues")

        if is_groove:
            self.update_log("Groove Mode: Starting 8-bar call-and-response.")
            self.brain.current_recording = "groove"
            self.jam_session.start_groove()
            try:
                self.query_one("#stat_chord").add_class("hidden")
            except Exception:
                pass
        elif is_shed:
            self.update_log("Shed Mode: Auto-Starting Trading Cycle.")
            self.brain.current_recording = "groove"
            self.jam_session.start_trading(bars=4)
            try:
                self.query_one("#stat_chord").add_class("hidden")
            except Exception:
                pass

    def _on_turn_change(self, phase_name):
        """Called by session when the phase/turn shifts."""
        self.safe_call(self.update_log, f"TURN CHANGE: {phase_name}")

        # Groove Mode: simple 2-turn cycle
        if "YOUR GROOVE" in phase_name:
            self.brain.clear_pattern("groove")
            self.brain.current_recording = "groove"
        elif "AI GROOVE" in phase_name:
            self.brain.current_recording = "groove"
        # Shed Mode: 3-turn cycle
        elif "AI Listening" in phase_name:
            self.brain.clear_pattern("groove")
            self.brain.clear_pattern("fill")
            self.brain.current_recording = "groove"
        elif "HUMAN FILL" in phase_name:
            self.brain.clear_pattern("fill")
            self.brain.current_recording = "fill"
        elif "AI FILL" in phase_name:
            self.brain.current_recording = "groove"

    def _on_cycle_reset(self):
        """Called when the 12-bar trading cycle resets to 0."""
        self.safe_call(self.update_log, "CYCLE RESET: Starting fresh cycle...")
        self.brain.clear_pattern("groove")
        self.brain.clear_pattern("fill")

    def stop_session(self):
        self.session_active = False
        self.midi.panic()
        self.jam_session = None
        self._virtual_active = False
        self.brain.is_jamming = False
        self.brain._beat_zero_time = 0.0
        self.brain._beats_fired = 0
        self.query_one("#btn_session", Button).label = "Start Session"
        self.query_one("#btn_session", Button).variant = "success"
        self.query_one("#mode_select").disabled = False

        for agent in self.agents:
            if hasattr(agent, "stop"):
                agent.stop()
        self.agents = []

    def rescan_midi(self):
        input_ports = self.midi.get_input_ports()
        output_ports = self.midi.get_output_ports()

        self.query_one("#input_select", Select).set_options([("Select Input...", "")] + [(p, p) for p in input_ports])
        self.query_one("#output_select", Select).set_options(
            [("Select Output...", "")] + [(p, p) for p in output_ports]
        )
        self.update_log("MIDI Ports Rescanned.")

    def update_log(self, message: str) -> None:
        try:
            log = self.query_one("#monitor_log", RichLog)
            log.write(message)
        except Exception:
            pass

    def on_unmount(self):
        if hasattr(self, "clock_thread"):
            self.clock_thread.stop()
        self.midi.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Jam Room TUI")
    parser.add_argument("--soundfont", type=str, help="Path to custom SoundFont (.sf2/.sf3)")
    args = parser.parse_args()

    app = JamShedApp(soundfont_path=args.soundfont)
    app.run()
