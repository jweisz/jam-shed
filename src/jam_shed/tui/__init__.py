"""
TUI package - Textual user interface components.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jam_shed.tui.app import JamShedApp

__all__ = [
    "JamShedApp",
]


def __getattr__(name: str):
    if name == "JamShedApp":
        from jam_shed.tui.app import JamShedApp

        return JamShedApp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
