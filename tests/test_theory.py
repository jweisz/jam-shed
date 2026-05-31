"""
Tests for jam_shed.theory module.
"""

from jam_shed.core.theory import MusicTheory


def test_get_notes_in_key_c_major():
    """Test C Major (Ionian) scale generation."""
    notes = MusicTheory.get_notes_in_key("C", "Major (Ionian)", octaves=[4])
    # C4 = 60, D4 = 62, E4 = 64, F4 = 65, G4 = 67, A4 = 69, B4 = 71
    expected = [60, 62, 64, 65, 67, 69, 71]
    assert notes == expected


def test_get_notes_in_key_pentatonic_minor():
    """Test Pentatonic Minor scale."""
    notes = MusicTheory.get_notes_in_key("C", "Pentatonic Minor", octaves=[4])
    # C, Eb, F, G, Bb
    expected = [60, 63, 65, 67, 70]
    assert notes == expected


def test_scale_aliases_resolve_to_canonical_scales():
    """Test that common aliases map to the canonical scale definitions."""
    ionian = MusicTheory.get_notes_in_key("C", "Ionian (Major)", octaves=[4])
    aeolian = MusicTheory.get_notes_in_key("C", "Aeolian (Minor)", octaves=[4])

    assert ionian == MusicTheory.get_notes_in_key("C", "Major (Ionian)", octaves=[4])
    assert aeolian == MusicTheory.get_notes_in_key("C", "Minor (Aeolian)", octaves=[4])


def test_scale_options_are_canonical_only():
    """Test that the selectable scale list omits duplicate aliases."""
    assert MusicTheory.SCALE_OPTIONS == list(MusicTheory.SCALES.keys())
    assert "Ionian (Major)" not in MusicTheory.SCALE_OPTIONS
    assert "Aeolian (Minor)" not in MusicTheory.SCALE_OPTIONS


def test_get_notes_in_key_multiple_octaves():
    """Test scale generation across multiple octaves."""
    notes = MusicTheory.get_notes_in_key("C", "Major (Ionian)", octaves=[3, 4])
    assert len(notes) == 14  # 7 notes * 2 octaves


def test_get_chord_notes_c_major():
    """Test C Major chord."""
    notes = MusicTheory.get_chord_notes("C", "Major", octaves=[4])
    # C, E, G
    expected = [60, 64, 67]
    assert notes == expected


def test_get_chord_notes_minor():
    """Test minor chord."""
    notes = MusicTheory.get_chord_notes("A", "Minor", octaves=[4])
    # A, C, E
    expected = [69, 72, 76]
    assert notes == expected


def test_get_progression_chords_blues():
    """Test 12-bar blues progression."""
    chords = MusicTheory.get_progression_chords("C", "Major (Ionian)", "12-Bar Blues")
    assert len(chords) == 12
    # 12-bar blues: I-I-I-I-IV-IV-I-I-V-IV-I-V
    assert chords[0] == ("C", "Major")  # I
    assert chords[4] == ("F", "Major")  # IV
    assert chords[8] == ("G", "Dom7")  # V


def test_get_note_name():
    """Test MIDI note to name conversion."""
    assert MusicTheory.get_note_name(60) == "C"
    assert MusicTheory.get_note_name(61) == "C#"
    assert MusicTheory.get_note_name(62) == "D"
    assert MusicTheory.get_note_name(72) == "C"  # Octave higher


def test_default_octaves():
    """Test that default octaves work correctly."""
    notes = MusicTheory.get_notes_in_key("C", "Major (Ionian)")
    assert len(notes) == 21  # 7 notes * 3 octaves (default [3, 4, 5])


def test_unknown_scale_defaults_to_major():
    """Test that unknown scales default to Major (Ionian)."""
    notes = MusicTheory.get_notes_in_key("C", "Unknown Scale", octaves=[4])
    major_notes = MusicTheory.get_notes_in_key("C", "Major (Ionian)", octaves=[4])
    assert notes == major_notes


def test_unknown_chord_defaults_to_major_triad():
    """Test that unknown chords default to Major triad."""
    notes = MusicTheory.get_chord_notes("C", "Unknown Chord", octaves=[4])
    assert notes == [60, 64, 67]  # C Major triad
