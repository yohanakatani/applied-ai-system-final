"""
Input validation and confidence scoring for the Music Recommender.

Guardrails catch bad inputs before they reach the scoring engine and
compute a confidence score on the output so the user knows how well
the catalog actually matched their preferences.
"""

from typing import Dict, List, Tuple

KNOWN_GENRES = {
    "pop", "lofi", "rock", "r&b", "folk", "jazz", "metal",
    "edm", "hip-hop", "ambient", "synthwave", "indie pop", "classical"
}
KNOWN_MOODS = {
    "chill", "happy", "intense", "focused", "relaxed", "moody",
    "nostalgic", "energetic", "angry", "dreamy", "euphoric", "aggressive"
}


def validate_user_prefs(prefs: Dict) -> Tuple[bool, List[str]]:
    """
    Validate user preference inputs.

    Returns (is_valid, list_of_warning_messages).
    is_valid is False only for unrecoverable errors (missing required fields).
    Warnings are returned for soft issues (unknown genre, out-of-range values).
    """
    warnings = []

    # Required fields
    required = ["favorite_genre", "favorite_mood", "target_energy"]
    for field in required:
        if field not in prefs:
            return False, [f"Missing required field: '{field}'"]

    genre = prefs["favorite_genre"].strip().lower()
    if genre not in KNOWN_GENRES:
        warnings.append(
            f"Unknown genre '{genre}'. Known genres: {', '.join(sorted(KNOWN_GENRES))}. "
            "Results may be sparse."
        )

    mood = prefs["favorite_mood"].strip().lower()
    if mood not in KNOWN_MOODS:
        warnings.append(
            f"Unknown mood '{mood}'. Known moods: {', '.join(sorted(KNOWN_MOODS))}. "
            "Results may be sparse."
        )

    energy = prefs["target_energy"]
    if not isinstance(energy, (int, float)) or not (0.0 <= float(energy) <= 1.0):
        return False, [f"target_energy must be a number between 0.0 and 1.0, got: {energy}"]

    for field in ("target_valence", "target_acousticness"):
        if field in prefs:
            val = prefs[field]
            if not isinstance(val, (int, float)) or not (0.0 <= float(val) <= 1.0):
                warnings.append(f"'{field}' should be between 0.0 and 1.0, got {val}. Ignoring.")

    if "target_tempo" in prefs:
        tempo = prefs["target_tempo"]
        if not isinstance(tempo, (int, float)) or not (40 <= float(tempo) <= 220):
            warnings.append(f"target_tempo should be between 40 and 220 BPM, got {tempo}.")

    return True, warnings


def confidence_score(recommendations: List[Tuple], user_prefs: Dict) -> float:
    """
    Compute a 0.0–1.0 confidence score for the recommendation set.

    Higher score means the catalog matched the user's stated preferences well.
    Based on: fraction of top-k results that match genre, mood, and energy range.
    """
    if not recommendations:
        return 0.0

    genre = user_prefs.get("favorite_genre", "").lower()
    mood = user_prefs.get("favorite_mood", "").lower()
    target_energy = float(user_prefs.get("target_energy", 0.5))

    total = 0.0
    for song, score, _ in recommendations:
        song_score = 0.0
        if song.get("genre", "").lower() == genre:
            song_score += 0.4
        if song.get("mood", "").lower() == mood:
            song_score += 0.4
        energy_proximity = 1.0 - abs(float(song.get("energy", 0.5)) - target_energy)
        song_score += 0.2 * energy_proximity
        total += song_score

    return round(total / len(recommendations), 2)


def confidence_label(score: float) -> str:
    if score >= 0.75:
        return "High"
    elif score >= 0.45:
        return "Medium"
    else:
        return "Low"
