import time
from typing import Any, Callable, List, Optional, Protocol, cast

import rtmidi

# Import AudioEngine lazily or here if safe
from jam_shed.core.audio import AudioEngine


class MidiInLike(Protocol):
    def get_ports(self) -> List[str]: ...

    def open_port(self, port: int) -> None: ...

    def close_port(self) -> None: ...

    def is_port_open(self) -> bool: ...

    def ignore_types(self, sysex: bool, timing: bool, sensing: bool) -> None: ...

    def set_callback(self, callback: Callable[..., Any]) -> None: ...


class MidiOutLike(Protocol):
    def get_ports(self) -> List[str]: ...

    def open_port(self, port: int) -> None: ...

    def close_port(self) -> None: ...

    def is_port_open(self) -> bool: ...

    def send_message(self, message: List[int]) -> None: ...


class MIDIEngine:
    def __init__(self, soundfont_path: Optional[str] = None):
        self.midi_in: Optional[MidiInLike] = None
        self.midi_out: Optional[MidiOutLike] = None

        try:
            midi_in_cls = getattr(rtmidi, "MidiIn", None)
            if midi_in_cls is None:
                raise AttributeError("rtmidi.MidiIn is unavailable")
            self.midi_in = cast(MidiInLike, midi_in_cls())
        except Exception as e:
            print(f"Warning: Could not initialize MIDI Input: {e}")
            self.midi_in = None

        try:
            midi_out_cls = getattr(rtmidi, "MidiOut", None)
            if midi_out_cls is None:
                raise AttributeError("rtmidi.MidiOut is unavailable")
            self.midi_out = cast(MidiOutLike, midi_out_cls())
        except Exception as e:
            print(f"Warning: Could not initialize MIDI Output: {e}")
            self.midi_out = None

        self.soundfont_path = soundfont_path
        self.in_port_index: Optional[int] = None
        self.out_port_index: Optional[int] = None
        self._in_open = False
        self._out_open = False
        self.log_callback: Optional[Callable[[str], None]] = None

        # Local Synthesis
        self.audio = None
        self._use_local = False
        # Default Program Mapping (done once)
        self._programs_set = False

    def _ensure_audio(self):
        if not self.audio:
            try:
                self.audio = AudioEngine(soundfont_path=self.soundfont_path)
                self._log("AudioEngine initialized successfully.")
            except Exception as e:
                self._log(f"Failed to initialize AudioEngine: {e}")

    def _log(self, message: str):
        if self.log_callback:
            self.log_callback(message)
        print(message)

    def is_in_open(self) -> bool:
        return self._in_open

    def is_out_open(self) -> bool:
        return self._out_open or (self._use_local and self.audio is not None)

    def get_input_ports(self) -> List[str]:
        if not self.midi_in:
            return []
        ports = self.midi_in.get_ports()
        return [p for p in ports if p]

    def get_output_ports(self) -> List[str]:
        ports = self.midi_out.get_ports() if self.midi_out else []
        # Add Virtual Port
        return [p for p in ports if p] + ["Local (Fluidsynth)"]

    def open_input(self, port_name: str, callback: Optional[Callable] = None) -> bool:
        if not self.midi_in or not port_name or port_name == "Select Input...":
            return False

        try:
            self._log(f"DEBUG: Attempting to open Input: {port_name}")
            if self.midi_in.is_port_open():
                self.midi_in.close_port()
            self._in_open = False

            ports = self.get_input_ports()
            self._log(f"DEBUG: Available Input Ports: {ports}")

            target_index = -1
            if port_name in ports:
                target_index = ports.index(port_name)
            else:
                stripped = port_name.strip()
                for i, p in enumerate(ports):
                    if p.strip() == stripped or stripped in p:
                        target_index = i
                        port_name = p
                        break

            if target_index == -1:
                self._log(f"ERROR: Could not find port '{port_name}'")
                return False

            self.in_port_index = target_index
            self.midi_in.open_port(self.in_port_index)
            time.sleep(0.1)

            if callback:
                self.midi_in.ignore_types(False, False, False)
                self.midi_in.set_callback(callback)
            self._in_open = True
            self._log(f"SUCCESS: Connected to Input '{port_name}'")
            return True
        except Exception as e:
            self._log(f"ERROR: Failed to open Input: {e}")
            return False

    def open_output(self, port_name: str) -> bool:
        if not port_name or port_name == "Select Output...":
            return False

        # Handle Local Synth
        if port_name == "Local (Fluidsynth)":
            self._ensure_audio()
            if self.audio and self.audio.sf_id != -1:
                self._use_local = True
                self._init_local_programs()
                self._log("SUCCESS: Connected to Local Audio Synthesis")
                # Ensure physical port is closed
                if self.midi_out and self.midi_out.is_port_open():
                    self.midi_out.close_port()
                return True
            else:
                self._log("ERROR: Could not initialize Local Audio")
                return False

        # Handle Physical Ports
        self._use_local = False
        if not self.midi_out:
            self._log("ERROR: MIDI output is not available")
            return False
        try:
            if self.midi_out.is_port_open():
                self.midi_out.close_port()
            self._out_open = False

            ports = self.midi_out.get_ports()  # Don't use get_output_ports() here to avoid recursion/virtual entries
            target_index = -1
            if port_name in ports:
                target_index = ports.index(port_name)
            else:
                stripped = port_name.strip()
                for i, p in enumerate(ports):
                    if p.strip() == stripped or stripped in p:
                        target_index = i
                        port_name = p
                        break

            if target_index == -1:
                return False  # Should fail gracefully

            self.out_port_index = target_index
            self.midi_out.open_port(self.out_port_index)
            time.sleep(0.1)

            if self.midi_out.is_port_open():
                self._out_open = True
                self._log(f"SUCCESS: Connected to Output '{port_name}'")
                return True
            else:
                return False
        except Exception as e:
            self._log(f"ERROR: Output Open Failed: {e}")
            return False

    def is_port_open(self, device_type: str) -> bool:
        if device_type == "in":
            return self.midi_in.is_port_open() if self.midi_in else False
        return self.midi_out.is_port_open() if self.midi_out else False

    def _init_local_programs(self):
        """Sets GM instruments for our channels. Matches agent definitions."""
        if not self.audio or self._programs_set:
            return

        # NOTE: Channels here match agent.channel (0-indexed)
        # We use explicit General MIDI (GM) program numbers:
        # 29: Overdriven Guitar
        # 27: Electric Guitar (clean)
        # 33: Electric Bass (finger)
        # 4:  Electric Piano 1 (Rhodes)
        # 24: Acoustic Guitar (nylon)

        self.audio.program_change(0, 24)  # Human Input (usually piano/acoustic guitar)
        self.audio.program_change(1, 29)  # Lead Guitar (Ch 1)
        self.audio.program_change(2, 27)  # Rhythm Guitar (Ch 2)
        self.audio.program_change(3, 33)  # Bass (Ch 3)
        self.audio.program_change(4, 4)  # Keyboardist (Ch 4)

        # Drums are traditionally on Channel 10 (index 9)
        self.audio.set_drums(9)
        self.audio.set_drums(10)  # Spare drum channel
        self._programs_set = True

    def send_message(self, message: List[int]):
        if self._use_local and self.audio:
            # Parse MIDI message [status, data1, data2]
            status = message[0]
            channel = status & 0x0F
            cmd = status & 0xF0

            if cmd == 0x90:  # Note On
                note = message[1]
                velocity = message[2]
                if velocity > 0:
                    # debug
                    # print(f"MIDI Local: On Ch{channel} n{note} v{velocity}")
                    self.audio.note_on(channel, note, velocity)
                else:
                    self.audio.note_off(channel, note)
            elif cmd == 0x80:  # Note Off
                note = message[1]
                self.audio.note_off(channel, note)
            elif cmd == 0xB0:  # Control Change
                cc_num = message[1]
                if cc_num == 123:  # All Notes Off
                    self.audio.all_notes_off(channel)
            return

        # Physical MIDI
        if self.midi_out and self.midi_out.is_port_open():
            self.midi_out.send_message(message)

    def all_notes_off(self, channel: int):
        """Send MIDI CC 123 (All Notes Off) on a specific channel."""
        self.send_message([0xB0 | (channel & 0x0F), 123, 0])

    def panic(self):
        """Stop all notes on all channels."""
        for i in range(16):
            self.all_notes_off(i)

    def close(self):
        if self.midi_in:
            self.midi_in.close_port()
        if self.midi_out:
            self.midi_out.close_port()
        if self.audio:
            self.audio.close()


if __name__ == "__main__":
    # Quick debug script
    engine = MIDIEngine()
    print("In Ports:", engine.get_input_ports())
    print("Out Ports:", engine.get_output_ports())
