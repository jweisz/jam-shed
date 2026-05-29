"""
Shared visual rendering utilities for groove pattern visualization.
"""
from abc import ABC, abstractmethod
from collections import deque
from typing import Dict, List, Tuple
from jam_shed.core.constants import KICK, SNARE, CLOSED_HIHAT, OPEN_HIHAT, RIDE, CRASH


# ── Instrument-to-color mapping ──────────────────────────────────────
HIT_COLORS = {
    "K": "yellow",
    "S": "red",
    "H": "cyan",
    "X": "white",       # kick+snare
    "R": "green",
    "C": "magenta",
    "c": "magenta",
    "1": "#FF8800",     # high tom (orange)
    "2": "#FF8800",     # mid tom
    "3": "#FF8800",     # floor tom
    "CH": "bright_white",
    "N ": "bright_white",
}


def render_scrolling_visual(history: deque) -> str:
    """Render a rolling_visual_history deque as a colored Textual markup string.

    Dots and bar separators are rendered dim; all hit labels (e.g. 'HH', 'N ')
    are rendered bold white for maximum contrast against the dark background.

    Args:
        history: deque of 2-char symbol strings (e.g. ``'. '``, ``'| '``, ``'HH'``)

    Returns:
        Textual markup string starting with a green play marker.
    """
    if not history:
        return "[bold green]▶[/]"

    parts = []
    for symbol in history:
        if symbol == "| ":
            parts.append("[dim]| [/]")
        elif symbol == ". ":
            parts.append("[dim]. [/]")
        else:
            parts.append(f"[bold white]{symbol}[/]")

    return "[bold green]▶[/] " + " ".join(parts)


def render_groove_pattern_rich(
    pattern: Dict[int, List[Tuple[int, int]]],
    current_bar_beat: int,
    current_sub_beat: int,
    beats_per_bar: int = 4,
    subdivision: int = 4,
    step_size: int = 3,
    color: str = "white"
) -> str:
    """
    Generate rich text visualization of a groove pattern with color-coded hits.

    Args:
        pattern: Pattern dict mapping tick index to [(note, velocity), ...]
        current_bar_beat: Current beat in the bar (0-3 for 4/4)
        current_sub_beat: Current sub-beat tick (0-11)
        beats_per_bar: Beats per bar
        subdivision: Visual subdivision (4 = 16th notes displayed as 4 per beat)
        step_size: Ticks per subdivision step (3 ticks = one 16th note)
        color: Base color for hits (used as fallback)

    Returns:
        Textual markup string for visualization
    """
    parts = []

    step_idx = current_sub_beat // step_size
    global_active_idx = (current_bar_beat * subdivision) + step_idx

    for b in range(beats_per_bar):
        beat_parts = []
        for s in range(subdivision):
            start_tick = (b * 12) + (s * step_size)

            # Collect hits in this subdivision
            hits = []
            for t in range(start_tick, start_tick + step_size):
                if t in pattern:
                    hits.extend(pattern[t])

            # Determine display character
            if hits:
                val = _classify_hit(hits)
            else:
                val = "."

            val_str = val.ljust(3)

            # Apply formatting with instrument colors
            current_idx = (b * subdivision) + s
            if current_idx == global_active_idx:
                beat_parts.append(f"[reverse green]{val_str}[/]")
            else:
                if val == ".":
                    beat_parts.append(f"[dim]{val_str}[/]")
                else:
                    hit_color = HIT_COLORS.get(val.strip(), color)
                    beat_parts.append(f"[bold {hit_color}]{val_str}[/]")

        parts.append(f"| {''.join(beat_parts)} |")

    return " ".join(parts)


def render_bouncing_ball(
    current_bar_beat: int,
    current_sub_beat: int,
    beats_per_bar: int = 4,
    subdivision: int = 4,
    step_size: int = 3,
) -> str:
    """
    Render a bouncing ball indicator that moves across the groove pattern.

    Returns a string with ▼ at the active position, aligned with the groove
    pattern columns. Useful for visually tracking tempo changes.

    Args:
        current_bar_beat: Current beat in the bar (0-based)
        current_sub_beat: Current sub-beat tick (0-11)
        beats_per_bar: Beats per bar
        subdivision: Steps per beat
        step_size: Ticks per step

    Returns:
        Textual markup string with the ball marker
    """
    step_idx = current_sub_beat // step_size
    global_active_idx = (current_bar_beat * subdivision) + step_idx

    parts = []
    for b in range(beats_per_bar):
        beat_parts = []
        for s in range(subdivision):
            current_idx = (b * subdivision) + s
            if current_idx == global_active_idx:
                beat_parts.append(f"[bold green]▼  [/]")
            else:
                beat_parts.append("   ")
        # "| " prefix and " |" suffix to align with groove pattern
        parts.append(f"  {''.join(beat_parts)}  ")

    return " ".join(parts)


def render_gauge(value: float, width: int = 20, max_value: float = 100,
                 color: str = "cyan", label: str = "") -> str:
    """
    Render a horizontal gauge/fill bar.

    Args:
        value: Current value
        width: Total bar width in characters
        max_value: Maximum value for scaling
        color: Color for the filled portion
        label: Optional label prefix (e.g. "INT")

    Returns:
        Textual markup string like "INT ████░░░░ 72"
    """
    clamped = max(0, min(value, max_value))
    filled = int((clamped / max_value) * width) if max_value > 0 else 0
    empty = width - filled

    bar = "█" * filled + "░" * empty
    val_str = f"{int(clamped)}" if clamped == int(clamped) else f"{clamped:.1f}"

    prefix = f"{label} " if label else ""
    return f"{prefix}[{color}]{bar}[/] {val_str}"


def render_beat_dots(current: int, total: int, label: str = "",
                     active_color: str = "green") -> str:
    """
    Render a dot-based indicator (e.g. for BAR or BEAT position).

    Args:
        current: Current position (0-based)
        total: Total positions
        label: Optional label prefix
        active_color: Color for active dot

    Returns:
        Textual markup string like "BAR ● ○ ○ ○"
    """
    dots = []
    for i in range(total):
        if i <= current:
            dots.append(f"[bold {active_color}]●[/]")
        else:
            dots.append("[dim]○[/]")

    prefix = f"{label} " if label else ""
    return f"{prefix}{' '.join(dots)}"


def _classify_hit(hits: List[Tuple[int, int]]) -> str:
    """
    Classify a hit for visual display.

    Args:
        hits: List of (note, velocity) tuples

    Returns:
        Single character representing the hit type
    """
    if not hits:
        return "."

    notes = [h[0] for h in hits]

    # Drum classification
    has_kick = KICK in notes
    has_snare = SNARE in notes or 40 in notes  # Electric snare
    has_hihat = any(n in [CLOSED_HIHAT, OPEN_HIHAT, 44] for n in notes)  # Pedal hihat

    if has_kick and has_snare:
        return "X"
    elif has_kick:
        return "K"
    elif has_snare:
        return "S"
    elif 49 in notes:  # Crash 1
        return "C"
    elif 57 in notes:  # Crash 2
        return "c"
    elif RIDE in notes:
        return "R"
    elif 48 in notes or 50 in notes:  # High tom
        return "1"
    elif 45 in notes or 47 in notes:  # Mid tom
        return "2"
    elif 41 in notes or 43 in notes:  # Floor tom
        return "3"
    elif has_hihat:
        return "H"

    # For non-drum instruments
    if len(hits) >= 3:
        return "CH"  # Chord
    elif len(hits) > 0:
        return "N "  # Note

    return "."


def strip_rich_markup(text: str) -> str:
    """
    Remove Textual rich markup from a string.

    Args:
        text: Text with markup

    Returns:
        Plain text without markup
    """
    replacements = [
        "[reverse green]",
        "[/]",
        "[dim]",
        "[bold white]",
        "[bold yellow]",
        "[bold cyan]",
        "[bold red]",
        "[bold blue]",
        "[bold green]",
        "[bold magenta]",
        "[bold #FF8800]",
        "[bold bright_white]",
    ]

    result = text
    for markup in replacements:
        result = result.replace(markup, "")

    return result


def create_metronome_visual(current_beat: int, beats_per_bar: int = 4) -> str:
    """
    Create a simple visual metronome display.

    Args:
        current_beat: Current beat (0-based)
        beats_per_bar: Total beats per bar

    Returns:
        Formatted metronome string
    """
    parts = []
    for beat in range(beats_per_bar):
        if beat == current_beat:
            parts.append("[reverse green] ● [/]")
        else:
            parts.append("[dim] ○ [/]")

    return " ".join(parts)


# ── Session Visualizers (ABC pattern) ────────────────────────────────

class SessionVisualizer(ABC):
    """Base class for session-mode visualizers.

    Visualizers are shown in the Jam mode banner area (or wherever the
    app decides to place them).  They receive periodic state updates and
    render a single line of Textual rich-text markup.

    Subclass this to add new visualization styles (e.g. heatmap, spectrum).
    """

    @abstractmethod
    def update(self, brain_state: dict) -> None:
        """Feed new data into the visualizer.

        Args:
            brain_state: dictionary from brain.get_state() / get_current_state(),
                         typically containing 'intensity', 'complexity', 'bpm', etc.
        """
        ...

    @abstractmethod
    def render(self, width: int) -> str:
        """Return a Textual markup string of the given character width.

        Args:
            width: target width in terminal columns
        """
        ...


class EnergyWaveformVisualizer(SessionVisualizer):
    """Scrolling energy waveform using block characters.

    Shows a scrolling left-to-right bar chart of recent hit intensity,
    using ▁▂▃▄▅▆▇█ to represent energy levels. Useful for drummers to
    see their overall energy arc at a glance.
    """

    BLOCKS = " ▁▂▃▄▅▆▇█"

    def __init__(self, max_history: int = 64):
        self._history: deque[float] = deque(maxlen=max_history)

    def update(self, brain_state: dict) -> None:
        intensity = brain_state.get("intensity", 0)
        # Normalize 0-127 → 0.0-1.0
        energy = min(1.0, max(0.0, intensity / 127.0))
        self._history.append(energy)

    def render(self, width: int) -> str:
        if not self._history:
            return "[dim]" + "▁" * width + "[/]"

        # Take the most recent `width` samples (or pad with zeros on the left)
        samples = list(self._history)
        if len(samples) < width:
            samples = [0.0] * (width - len(samples)) + samples
        else:
            samples = samples[-width:]

        parts = []
        for energy in samples:
            idx = int(energy * (len(self.BLOCKS) - 1))
            char = self.BLOCKS[idx]
            # Color gradient: dim → cyan → green → yellow → red
            if energy < 0.25:
                parts.append(f"[dim]{char}[/]")
            elif energy < 0.5:
                parts.append(f"[cyan]{char}[/]")
            elif energy < 0.75:
                parts.append(f"[green]{char}[/]")
            elif energy < 0.9:
                parts.append(f"[yellow]{char}[/]")
            else:
                parts.append(f"[bold red]{char}[/]")

        return "".join(parts)
