"""Central style calibration values for Jam-mode behavior curves.

Tuning notes:
- Keep most multipliers in ~0.75-1.15 to avoid extreme behavior swings.
- Probabilities should stay in [0.0, 1.0].
- Bass tone tuples are (root_weight, fifth_weight, color_weight) and should
    sum to 1.0 for predictable note-selection behavior.
- This file is intentionally the single place to tune style personality.
"""

from jam_shed.agents.base import PlayingStyle

## Lead guitar section multipliers
# Applies on top of lead baseline play probability in Jam mode.
# Higher values = more active/more likely to speak.
LEAD_CONVERSATION_MULTIPLIER = {
    PlayingStyle.ROCK: 0.95,
    PlayingStyle.JAZZ: 1.08,
    PlayingStyle.FUNK: 1.03,
    PlayingStyle.BLUES: 0.98,
    PlayingStyle.HIP_HOP: 0.92,
    PlayingStyle.LATIN: 1.00,
}

LEAD_SPOTLIGHT_MULTIPLIER = {
    PlayingStyle.ROCK: 1.00,
    PlayingStyle.JAZZ: 1.07,
    PlayingStyle.FUNK: 1.05,
    PlayingStyle.BLUES: 1.02,
    PlayingStyle.HIP_HOP: 0.94,
    PlayingStyle.LATIN: 0.98,
}

## Drummer phrase-fill multiplier
# Scales probability of phrase-boundary fills near 8-bar checkpoints.
# Lower values = more restraint at section boundaries.
DRUM_PHRASE_FILL_MULTIPLIER = {
    PlayingStyle.ROCK: 1.00,
    PlayingStyle.JAZZ: 0.85,
    PlayingStyle.FUNK: 0.90,
    PlayingStyle.BLUES: 0.95,
    PlayingStyle.HIP_HOP: 0.80,
    PlayingStyle.LATIN: 0.88,
}

## Bass tone weights by section and style
# Tuple format: (root, fifth, color/other).
# Conversation should usually allow more color motion than Return Groove.
BASS_CONVERSATION_WEIGHTS = {
    PlayingStyle.JAZZ: (0.40, 0.30, 0.30),
    PlayingStyle.FUNK: (0.46, 0.30, 0.24),
    PlayingStyle.ROCK: (0.50, 0.30, 0.20),
    PlayingStyle.BLUES: (0.50, 0.30, 0.20),
    PlayingStyle.HIP_HOP: (0.54, 0.30, 0.16),
    PlayingStyle.LATIN: (0.48, 0.30, 0.22),
}

BASS_RETURN_GROOVE_WEIGHTS = {
    PlayingStyle.JAZZ: (0.66, 0.26, 0.08),
    PlayingStyle.FUNK: (0.70, 0.24, 0.06),
    PlayingStyle.ROCK: (0.74, 0.22, 0.04),
    PlayingStyle.BLUES: (0.73, 0.23, 0.04),
    PlayingStyle.HIP_HOP: (0.76, 0.20, 0.04),
    PlayingStyle.LATIN: (0.70, 0.24, 0.06),
}

## Keyboard chord probabilities
# Conversation: chord-versus-line balance.
# Spotlight support: comping likelihood when keyboard is not the soloist.
KEYS_CONVERSATION_CHORD_PROB = {
    PlayingStyle.ROCK: 0.75,
    PlayingStyle.JAZZ: 0.60,
    PlayingStyle.FUNK: 0.65,
    PlayingStyle.BLUES: 0.70,
    PlayingStyle.HIP_HOP: 0.80,
    PlayingStyle.LATIN: 0.68,
}

KEYS_SPOTLIGHT_SUPPORT_CHORD_PROB = {
    PlayingStyle.ROCK: 0.95,
    PlayingStyle.JAZZ: 0.80,
    PlayingStyle.FUNK: 0.88,
    PlayingStyle.BLUES: 0.90,
    PlayingStyle.HIP_HOP: 0.96,
    PlayingStyle.LATIN: 0.86,
}


def get_lead_section_multiplier(style: PlayingStyle, section: str) -> float:
    """Get lead style multiplier for the given Jam section."""
    if section == "CONVERSATION":
        return LEAD_CONVERSATION_MULTIPLIER.get(style, 1.0)
    if section == "SPOTLIGHT":
        return LEAD_SPOTLIGHT_MULTIPLIER.get(style, 1.0)
    return 1.0


def get_drum_phrase_fill_multiplier(style: PlayingStyle) -> float:
    """Get drummer phrase-boundary fill multiplier for a style."""
    return DRUM_PHRASE_FILL_MULTIPLIER.get(style, 1.0)


def get_bass_tone_weights(
    style: PlayingStyle, section: str, is_supporting_spotlight: bool
) -> tuple[float, float, float]:
    """Get bass note-choice weights for section role and style.

    Returns:
        (root_weight, fifth_weight, color_weight)
    """
    if section == "CONVERSATION":
        return BASS_CONVERSATION_WEIGHTS.get(style, (0.45, 0.30, 0.25))
    if section == "RETURN_GROOVE":
        return BASS_RETURN_GROOVE_WEIGHTS.get(style, (0.72, 0.23, 0.05))
    if section == "SPOTLIGHT" and is_supporting_spotlight:
        return (0.80, 0.18, 0.02)
    if section in ["INTRO", "OUTRO"]:
        return (0.75, 0.20, 0.05)
    return (0.6, 0.3, 0.1)


def get_keys_conversation_chord_probability(style: PlayingStyle) -> float:
    """Get keyboard chord probability in Conversation section."""
    return KEYS_CONVERSATION_CHORD_PROB.get(style, 0.7)


def get_keys_spotlight_support_chord_probability(style: PlayingStyle) -> float:
    """Get keyboard comping probability while supporting Spotlight."""
    return KEYS_SPOTLIGHT_SUPPORT_CHORD_PROB.get(style, 0.9)
