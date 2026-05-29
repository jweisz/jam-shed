import time
import os
import fluidsynth

class AudioEngine:
    """
    Handles local audio synthesis using FluidSynth.
    Loads a GM SoundFont and provides methods for NoteOn/Off and Program Change.
    """
    def __init__(self, soundfont_path: str = None):
        self.fs = fluidsynth.Synth()

        # Start the driver first (CoreAudio on macOS)
        # Note: on some systems, start() might be blocking or fail if driver not found.
        # "coreaudio" is standard for macOS.
        self.fs.start(driver="coreaudio")

        # Load default soundfont if none provided
        if not soundfont_path:
            # Look in standard assets location
            # audio.py is at src/jam_shed/core/audio.py
            # We need to go up 4 levels to get to project root
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            soundfont_path = os.path.join(base_dir, "assets", "soundfonts", "FluidR3Mono_GM.sf3")

        if os.path.exists(soundfont_path):
            self.sf_id = self.fs.sfload(soundfont_path)
            print(f"AudioEngine: Loaded SoundFont from {soundfont_path}")
        else:
            print(f"AudioEngine: ERROR - SoundFont not found at {soundfont_path}")
            self.sf_id = -1

        # Preset Mapping (Channel -> (Bank, Preset))
        # Initialize standard GM mapping
        # Lead Guitar (Ch 0) = Overdrive Guitar (29)
        # Rhythm Guitar (Ch 1) = Clean Guitar (27)
        # Bass (Ch 2) = Electric Bass (33)
        # Keys (Ch 3) = Electric Piano 1 (4)
        # Percussion (Ch 4) = Marimba (12) ?? Or generic
        # Drums (Ch 9) = Standard Kit (Bank 128, Preset 0)

        # Note: FluidSynth channels are 0-15.

        # Allow program changes to override these defaults.

    def note_on(self, channel: int, note: int, velocity: int):
        # debug
        # print(f"Audio: Ch{channel} n{note} v{velocity}")
        self.fs.noteon(channel, note, velocity)

    def note_off(self, channel: int, note: int):
        self.fs.noteoff(channel, note)

    def program_change(self, channel: int, program: int):
        self.fs.program_select(channel, self.sf_id, 0, program)

    def set_drums(self, channel: int):
        # Bank 128 is usually drums in GM SoundFonts
        self.fs.program_select(channel, self.sf_id, 128, 0)

    def all_notes_off(self, channel: int):
        """Turn off all notes on a specific channel."""
        self.fs.all_notes_off(channel)

    def panic(self):
        """Panic: reset the entire synth."""
        self.fs.system_reset()

    def close(self):
        self.fs.delete()
