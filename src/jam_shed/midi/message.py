"""
MIDI message utilities and dataclasses.
"""

from dataclasses import dataclass
from typing import List

from jam_shed.core.constants import MIDICommand


@dataclass
class MIDIMessage:
    """Structured representation of a MIDI message."""

    command: MIDICommand
    channel: int  # 0-15
    data1: int  # Note number or controller number
    data2: int = 0  # Velocity or controller value

    @classmethod
    def from_bytes(cls, message: List[int]) -> "MIDIMessage":
        """
        Create MIDIMessage from raw MIDI bytes.

        Args:
            message: List of MIDI bytes [status, data1, data2]

        Returns:
            MIDIMessage instance
        """
        if not message or len(message) < 1:
            raise ValueError("Invalid MIDI message: empty")

        status = message[0]
        command = MIDICommand(status & 0xF0)
        channel = status & 0x0F
        data1 = message[1] if len(message) > 1 else 0
        data2 = message[2] if len(message) > 2 else 0

        return cls(command=command, channel=channel, data1=data1, data2=data2)

    def to_bytes(self) -> List[int]:
        """
        Convert to raw MIDI bytes.

        Returns:
            List of MIDI bytes [status, data1, data2]
        """
        status = self.command | self.channel

        # Some commands only have 1 data byte
        if self.command in [MIDICommand.PROGRAM_CHANGE, MIDICommand.CHANNEL_AFTERTOUCH]:
            return [status, self.data1]

        return [status, self.data1, self.data2]

    @classmethod
    def note_on(cls, channel: int, note: int, velocity: int) -> "MIDIMessage":
        """
        Create a NoteOn message.

        Args:
            channel: MIDI channel (0-15)
            note: Note number (0-127)
            velocity: Velocity (1-127, 0 is treated as note off)

        Returns:
            MIDIMessage instance
        """
        return cls(command=MIDICommand.NOTE_ON, channel=channel, data1=note, data2=velocity)

    @classmethod
    def note_off(cls, channel: int, note: int, velocity: int = 64) -> "MIDIMessage":
        """
        Create a NoteOff message.

        Args:
            channel: MIDI channel (0-15)
            note: Note number (0-127)
            velocity: Release velocity (0-127)

        Returns:
            MIDIMessage instance
        """
        return cls(command=MIDICommand.NOTE_OFF, channel=channel, data1=note, data2=velocity)

    @classmethod
    def control_change(cls, channel: int, controller: int, value: int) -> "MIDIMessage":
        """
        Create a ControlChange message.

        Args:
            channel: MIDI channel (0-15)
            controller: Controller number (0-127)
            value: Controller value (0-127)

        Returns:
            MIDIMessage instance
        """
        return cls(command=MIDICommand.CONTROL_CHANGE, channel=channel, data1=controller, data2=value)

    @classmethod
    def program_change(cls, channel: int, program: int) -> "MIDIMessage":
        """
        Create a ProgramChange message.

        Args:
            channel: MIDI channel (0-15)
            program: Program number (0-127)

        Returns:
            MIDIMessage instance
        """
        return cls(command=MIDICommand.PROGRAM_CHANGE, channel=channel, data1=program, data2=0)

    @property
    def is_note_on(self) -> bool:
        """Check if this is a NoteOn message with non-zero velocity."""
        return self.command == MIDICommand.NOTE_ON and self.data2 > 0

    @property
    def is_note_off(self) -> bool:
        """Check if this is a NoteOff message or NoteOn with zero velocity."""
        return self.command == MIDICommand.NOTE_OFF or (self.command == MIDICommand.NOTE_ON and self.data2 == 0)

    @property
    def note(self) -> int:
        """Get note number (for note on/off messages)."""
        return self.data1

    @property
    def velocity(self) -> int:
        """Get velocity (for note on/off messages)."""
        return self.data2

    def __repr__(self) -> str:
        """String representation."""
        cmd_name = self.command.name
        if self.is_note_on:
            return f"NoteOn(ch={self.channel}, note={self.note}, vel={self.velocity})"
        elif self.is_note_off:
            return f"NoteOff(ch={self.channel}, note={self.note})"
        else:
            return f"{cmd_name}(ch={self.channel}, d1={self.data1}, d2={self.data2})"


def parse_midi_message(message: List[int]) -> MIDIMessage:
    """
    Parse raw MIDI bytes into a MIDIMessage.

    Args:
        message: Raw MIDI bytes

    Returns:
        Parsed MIDIMessage
    """
    return MIDIMessage.from_bytes(message)
