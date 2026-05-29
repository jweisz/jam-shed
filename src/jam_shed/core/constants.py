"""
Constants and enums for jam-shed.
Centralizes magic numbers, MIDI values, and configuration constants.
"""
from enum import Enum, IntEnum


class MIDICommand(IntEnum):
    """MIDI command bytes."""
    NOTE_OFF = 0x80
    NOTE_ON = 0x90
    POLYPHONIC_AFTERTOUCH = 0xA0
    CONTROL_CHANGE = 0xB0
    PROGRAM_CHANGE = 0xC0
    CHANNEL_AFTERTOUCH = 0xD0
    PITCH_BEND = 0xE0


class DrumNote(IntEnum):
    """General MIDI drum note mappings (channel 10)."""
    # Bass/Kick Drums
    ACOUSTIC_BASS_DRUM = 35
    BASS_DRUM_1 = 36  # Standard kick
    SIDE_STICK = 37

    # Snare Drums
    ACOUSTIC_SNARE = 38
    HAND_CLAP = 39
    ELECTRIC_SNARE = 40

    # Toms
    LOW_FLOOR_TOM = 41
    CLOSED_HI_HAT = 42
    HIGH_FLOOR_TOM = 43
    PEDAL_HI_HAT = 44
    LOW_TOM = 45
    OPEN_HI_HAT = 46
    LOW_MID_TOM = 47
    HI_MID_TOM = 48
    CRASH_CYMBAL_1 = 49
    HIGH_TOM = 50
    RIDE_CYMBAL_1 = 51

    # Cymbals
    CHINESE_CYMBAL = 52
    RIDE_BELL = 53
    TAMBOURINE = 54
    SPLASH_CYMBAL = 55
    COWBELL = 56
    CRASH_CYMBAL_2 = 57
    VIBRASLAP = 58
    RIDE_CYMBAL_2 = 59

    # More Percussion
    HI_BONGO = 60
    LOW_BONGO = 61
    MUTE_HI_CONGA = 62
    OPEN_HI_CONGA = 63
    LOW_CONGA = 64
    HIGH_TIMBALE = 65
    LOW_TIMBALE = 66
    HIGH_AGOGO = 67
    LOW_AGOGO = 68
    CABASA = 69
    MARACAS = 70
    SHORT_WHISTLE = 71
    LONG_WHISTLE = 72
    SHORT_GUIRO = 73
    LONG_GUIRO = 74
    CLAVES = 75
    HI_WOOD_BLOCK = 76
    LOW_WOOD_BLOCK = 77
    MUTE_CUICA = 78
    OPEN_CUICA = 79
    MUTE_TRIANGLE = 80
    OPEN_TRIANGLE = 81


# Commonly used drum shortcuts
KICK = DrumNote.BASS_DRUM_1
SNARE = DrumNote.ACOUSTIC_SNARE
CLOSED_HIHAT = DrumNote.CLOSED_HI_HAT
OPEN_HIHAT = DrumNote.OPEN_HI_HAT
RIDE = DrumNote.RIDE_CYMBAL_1
CRASH = DrumNote.CRASH_CYMBAL_1
LOW_TOM = DrumNote.LOW_TOM
MID_TOM = DrumNote.HI_MID_TOM
HIGH_TOM = DrumNote.HIGH_TOM


class BPMMode(Enum):
    """BPM tracking modes."""
    FIXED = "fixed"
    ADAPTIVE = "adaptive"


class RecordingMode(Enum):
    """Brain recording modes."""
    GROOVE = "groove"
    FILL = "fill"


# MIDI Constants
MIDI_CHANNEL_DRUMS = 9  # Channel 10 in 1-indexed (9 in 0-indexed)
MIDI_MAX_VELOCITY = 127
MIDI_MIN_VELOCITY = 0
MIDI_DEFAULT_VELOCITY = 80

# Timing Constants (in seconds)
DEFAULT_NOTE_DURATION = 0.1
DRUM_NOTE_DURATION = 0.05
CHORD_NOTE_DURATION = 0.3
STACCATO_DURATION = 0.15

# Subdivision Constants
TICKS_PER_BEAT = 12
SIXTEENTH_NOTE_TICKS = 3  # 12 / 4
EIGHTH_NOTE_TICKS = 6     # 12 / 2
QUARTER_NOTE_TICKS = 12

# BPM Constants
MIN_BPM = 40
MAX_BPM = 240
DEFAULT_BPM = 120
BPM_CALCULATION_WINDOW = 16  # Number of beats to average for BPM

# Musical Constants
DEFAULT_BEATS_PER_BAR = 4
DEFAULT_KEY = "C"
DEFAULT_SCALE = "Pentatonic Minor"
DEFAULT_PROGRESSION = "12-Bar Blues"

# Velocity Ranges
GHOST_NOTE_VELOCITY_FACTOR = 0.5
MIN_PLAYABLE_VELOCITY = 40
MAX_PLAYABLE_VELOCITY = 127

# Agent Defaults
DEFAULT_REACTIVITY = 0.8
DEFAULT_COMPLEXITY_BIAS = 0.5
DEFAULT_DENSITY = 0.3

# UI Constants
JAM_MODE = "Jam"
SHED_MODE = "Shed"

# MIDI Port Placeholders
SELECT_INPUT_PLACEHOLDER = "Select Input..."
SELECT_OUTPUT_PLACEHOLDER = "Select Output..."
LOCAL_FLUIDSYNTH = "Local (Fluidsynth)"

# Thread Sleep Times (in seconds)
MIDI_PORT_SETTLE_TIME = 0.1
TICK_CALLBACK_INTERVAL = 0.01

# Octave Ranges
LOW_OCTAVE_RANGE = [2, 3]
MID_OCTAVE_RANGE = [3, 4]
HIGH_OCTAVE_RANGE = [4, 5]
EXTENDED_OCTAVE_RANGE = [3, 4, 5]
