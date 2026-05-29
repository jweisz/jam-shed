from typing import List, Optional

class MusicTheory:
    # MIDI note offsets for common scales, ordered by brightness (bright to dark)
    SCALES = {
        "Lydian": [0, 2, 4, 6, 7, 9, 11],
        "Major (Ionian)": [0, 2, 4, 5, 7, 9, 11],
        "Pentatonic Major": [0, 2, 4, 7, 9],
        "Mixolydian": [0, 2, 4, 5, 7, 9, 10],
        "Blues": [0, 3, 5, 6, 7, 10],
        "Dorian": [0, 2, 3, 5, 7, 9, 10],
        "Pentatonic Minor": [0, 3, 5, 7, 10],
        "Minor (Aeolian)": [0, 2, 3, 5, 7, 8, 10],
        "Phrygian": [0, 1, 3, 5, 7, 8, 10],
        "Locrian": [0, 1, 3, 5, 6, 8, 10],
    }

    SCALE_ALIASES = {
        "Major": "Major (Ionian)",
        "Minor": "Minor (Aeolian)",
        "Ionian (Major)": "Major (Ionian)",
        "Aeolian (Minor)": "Minor (Aeolian)",
    }

    SCALE_OPTIONS = list(SCALES.keys())

    KEYS = {
        "C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
        "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11
    }

    @staticmethod
    def get_notes_in_key(root_note: str, scale_name: str, octaves: Optional[List[int]] = None) -> List[int]:
        if octaves is None:
            octaves = [3, 4, 5]

        root_offset = MusicTheory.KEYS.get(root_note, 0)
        resolved_scale_name = MusicTheory.SCALE_ALIASES.get(scale_name, scale_name)
        scale_offsets = MusicTheory.SCALES.get(resolved_scale_name, MusicTheory.SCALES["Major (Ionian)"])

        notes = []
        for octave in octaves:
            base = (octave + 1) * 12 + root_offset
            for offset in scale_offsets:
                notes.append(base + offset)
        return notes

    @staticmethod
    def get_note_name(midi_note: int) -> str:
        names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        return names[midi_note % 12]

    CHORD_TYPES = {
        "Major": [0, 4, 7],
        "Minor": [0, 3, 7],
        "Dom7": [0, 4, 7, 10],
        "Maj7": [0, 4, 7, 11],
        "Min7": [0, 3, 7, 10]
    }

    # Pre-defined progressions
    PROGRESSIONS = {
        "12-Bar Blues": ["I", "I", "I", "I", "IV", "IV", "I", "I", "V", "IV", "I", "V"],
        "Pop 1 (I-V-vi-IV)": ["I", "V", "vi", "IV"],
        "Jazz 2-5-1": ["ii", "V", "I", "I"]
    }

    @staticmethod
    def get_chord_notes(root: str, chord_type: str, octaves: Optional[List[int]] = None) -> List[int]:
        if octaves is None:
            octaves = [3]

        root_offset = MusicTheory.KEYS.get(root, 0)
        chord_offsets = MusicTheory.CHORD_TYPES.get(chord_type, [0, 4, 7])

        notes = []
        for octave in octaves:
            base = (octave + 1) * 12 + root_offset
            for offset in chord_offsets:
                notes.append(base + offset)
        return notes

    @staticmethod
    def get_progression_chords(key_root: str, scale_name: str, progression_name: str) -> List[tuple]:
        """Returns a list of (root_name, chord_type) for the progression in the given key."""
        progression = MusicTheory.PROGRESSIONS.get(progression_name, ["I", "IV", "V", "IV"])

        # Get scale intervals (0, 2, 4...)
        resolved_scale_name = MusicTheory.SCALE_ALIASES.get(scale_name, scale_name)
        scale_intervals = MusicTheory.SCALES.get(resolved_scale_name, MusicTheory.SCALES["Major (Ionian)"])
        root_base = MusicTheory.KEYS.get(key_root, 0)

        chord_sequence = []
        map_rom = {"i": 0, "ii": 1, "iii": 2, "iv": 3, "v": 4, "vi": 5, "vii": 6}

        for numeral in progression:
            # Determine Chord Type from Case (Uppercase=Major, Lowercase=Minor)
            is_minor = numeral[0].islower()
            chord_type = "Minor" if is_minor else "Major"

            # Simple override for V in blues/pop
            if numeral.upper() == "V": chord_type = "Dom7"
            if numeral.upper() == "I" and "Jazz" in progression_name: chord_type = "Maj7"
            if numeral.lower() == "ii" and "Jazz" in progression_name: chord_type = "Min7"

            # Map Roman Numeral to Scale Degree Index
            degree_idx = map_rom.get(numeral.lower(), 0)

            # Get interval for this degree
            interval = scale_intervals[degree_idx % len(scale_intervals)]

            # Calculate Root Note Name
            current_root_midi = (root_base + interval) % 12
            current_root_name = MusicTheory.get_note_name(current_root_midi)

            chord_sequence.append( (current_root_name, chord_type) )

        return chord_sequence
