"""
Mock MIDI engine for testing without real MIDI hardware.

Allows queuing MIDI messages to be replayed and logging output messages.
"""

import threading
import time
from typing import Callable, List, Optional, Tuple


class MockMIDIEngine:
    """
    Mock MIDI engine that simulates MIDI I/O for testing.

    Allows tests to:
    - Queue MIDI input messages to be replayed on a background thread
    - Log MIDI output messages sent by agents
    - Verify agent interactions without hardware
    """

    def __init__(self):
        self.input_buffer: List[Tuple[float, List[int]]] = []  # (delay_seconds, midi_bytes)
        self.output_log: List[Tuple[float, List[int]]] = []  # (timestamp, midi_bytes)
        self.in_open = False
        self.out_open = False
        self.input_callback: Optional[Callable[[List[int], None], None]] = None
        self._replay_thread: Optional[threading.Thread] = None
        self._stop_replay = False

    def open_input(self, device_name: str) -> None:
        """Open MIDI input."""
        self.in_open = True

    def open_output(self, device_name: str) -> None:
        """Open MIDI output."""
        self.out_open = True

    def is_in_open(self) -> bool:
        """Check if input is open."""
        return self.in_open

    def is_out_open(self) -> bool:
        """Check if output is open."""
        return self.out_open

    def close_input(self) -> None:
        """Close MIDI input."""
        self.in_open = False

    def close_output(self) -> None:
        """Close MIDI output."""
        self.out_open = False

    def send_message(self, msg: List[int]) -> None:
        """
        Log an outgoing MIDI message.

        Called by agents when they want to play notes.
        """
        self.output_log.append((time.time(), msg))

    def set_input_callback(self, callback: Callable[[List[int], None], None]) -> None:
        """Set the callback to receive MIDI input messages."""
        self.input_callback = callback

    def queue_input(self, delay: float, midi_bytes: List[int]) -> None:
        """
        Queue a MIDI input message to be replayed after delay.

        Args:
            delay: Time in seconds to wait before replaying this message
            midi_bytes: The MIDI message bytes (e.g., [0x90, 60, 100] for Note On)
        """
        self.input_buffer.append((delay, midi_bytes))

    def replay_inputs(self) -> None:
        """
        Replay all queued input messages on a background thread.

        Each message is replayed after its specified delay. Calls the
        input callback for each message, simulating incoming MIDI data.
        """

        def player():
            total_time = 0.0
            for delay, midi_bytes in self.input_buffer:
                if self._stop_replay:
                    break
                time.sleep(delay)
                total_time += delay
                if self.input_callback:
                    self.input_callback(midi_bytes, None)

        self._stop_replay = False
        self._replay_thread = threading.Thread(target=player, daemon=True)
        self._replay_thread.start()

    def stop_replay(self) -> None:
        """Stop replay and wait for replay thread to finish."""
        self._stop_replay = True
        if self._replay_thread:
            self._replay_thread.join(timeout=5.0)

    def get_output_messages(self, channel: Optional[int] = None) -> List[Tuple[float, List[int]]]:
        """
        Get logged output messages, optionally filtered by MIDI channel.

        Args:
            channel: If provided, only return messages on this channel (0-15)

        Returns:
            List of (timestamp, midi_bytes) tuples
        """
        if channel is None:
            return self.output_log

        # Filter by channel from status byte (lower 4 bits)
        return [(ts, msg) for ts, msg in self.output_log if len(msg) > 0 and (msg[0] & 0x0F) == channel]

    def get_note_on_messages(self, channel: Optional[int] = None) -> List[Tuple[float, int, int]]:
        """
        Get all Note On messages (0x90).

        Args:
            channel: If provided, only return messages on this channel

        Returns:
            List of (timestamp, note_number, velocity) tuples
        """
        notes = []
        for ts, msg in self.get_output_messages(channel):
            if len(msg) >= 3 and (msg[0] & 0xF0) == 0x90:  # Note On status
                notes.append((ts, msg[1], msg[2]))
        return notes

    def get_notes_by_pitch(self, pitch: int) -> List[Tuple[float, int]]:
        """
        Get all Note On messages for a specific pitch.

        Args:
            pitch: MIDI note number (0-127)

        Returns:
            List of (timestamp, velocity) tuples
        """
        return [(ts, vel) for ts, note, vel in self.get_note_on_messages() if note == pitch]

    def clear_output_log(self) -> None:
        """Clear the output message log."""
        self.output_log.clear()

    def clear_input_buffer(self) -> None:
        """Clear the input buffer."""
        self.input_buffer.clear()

    def reset(self) -> None:
        """Reset all state (stop replay, clear buffers/logs)."""
        self.stop_replay()
        self.clear_input_buffer()
        self.clear_output_log()
        self.in_open = False
        self.out_open = False
