"""
Tests for the input-validation and confidence-scoring guardrails.

These cover the reliability layer: bad input must be caught before it reaches
the scorer, and the confidence score must honestly reflect how well the
catalog matched what the user asked for.
"""

import pytest

from src.guardrails import (
    validate_user_prefs,
    confidence_score,
    confidence_label,
)


def make_song(genre="lofi", mood="chill", energy=0.4, title="T", artist="A"):
    return {"title": title, "artist": artist, "genre": genre, "mood": mood, "energy": energy}


# ---------------------------------------------------------------------------
# validate_user_prefs
# ---------------------------------------------------------------------------

def test_valid_prefs_pass_with_no_warnings():
    prefs = {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 0.4}
    is_valid, warnings = validate_user_prefs(prefs)
    assert is_valid is True
    assert warnings == []


@pytest.mark.parametrize("missing", ["favorite_genre", "favorite_mood", "target_energy"])
def test_missing_required_field_is_rejected(missing):
    prefs = {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 0.4}
    del prefs[missing]
    is_valid, warnings = validate_user_prefs(prefs)
    assert is_valid is False
    assert missing in warnings[0]


@pytest.mark.parametrize("bad_energy", [-0.1, 1.5, 42, "loud", None])
def test_out_of_range_energy_is_rejected(bad_energy):
    prefs = {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": bad_energy}
    is_valid, _ = validate_user_prefs(prefs)
    assert is_valid is False


@pytest.mark.parametrize("boundary", [0.0, 1.0])
def test_energy_boundaries_are_accepted(boundary):
    prefs = {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": boundary}
    is_valid, _ = validate_user_prefs(prefs)
    assert is_valid is True


def test_unknown_genre_warns_but_does_not_reject():
    prefs = {"favorite_genre": "polka", "favorite_mood": "chill", "target_energy": 0.4}
    is_valid, warnings = validate_user_prefs(prefs)
    assert is_valid is True
    assert any("polka" in w for w in warnings)


def test_unknown_mood_warns_but_does_not_reject():
    prefs = {"favorite_genre": "lofi", "favorite_mood": "smug", "target_energy": 0.4}
    is_valid, warnings = validate_user_prefs(prefs)
    assert is_valid is True
    assert any("smug" in w for w in warnings)


def test_out_of_range_tempo_warns_but_does_not_reject():
    prefs = {
        "favorite_genre": "lofi",
        "favorite_mood": "chill",
        "target_energy": 0.4,
        "target_tempo": 900,
    }
    is_valid, warnings = validate_user_prefs(prefs)
    assert is_valid is True
    assert any("tempo" in w.lower() for w in warnings)


# ---------------------------------------------------------------------------
# confidence_score
# ---------------------------------------------------------------------------

def test_perfect_match_scores_near_one():
    prefs = {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 0.4}
    recs = [(make_song(energy=0.4), 5.0, "") for _ in range(3)]
    assert confidence_score(recs, prefs) == pytest.approx(1.0, abs=0.01)


def test_total_mismatch_scores_low():
    prefs = {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 0.0}
    recs = [(make_song(genre="metal", mood="angry", energy=1.0), 1.0, "")]
    # No genre credit, no mood credit, worst possible energy proximity.
    assert confidence_score(recs, prefs) == pytest.approx(0.0, abs=0.01)


def test_empty_recommendations_score_zero():
    prefs = {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 0.4}
    assert confidence_score([], prefs) == 0.0


def test_genre_only_match_scores_between_mismatch_and_perfect():
    prefs = {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 0.4}
    genre_only = [(make_song(genre="lofi", mood="angry", energy=0.4), 3.0, "")]
    both = [(make_song(genre="lofi", mood="chill", energy=0.4), 5.0, "")]
    neither = [(make_song(genre="metal", mood="angry", energy=0.4), 1.0, "")]

    assert confidence_score(neither, prefs) < confidence_score(genre_only, prefs)
    assert confidence_score(genre_only, prefs) < confidence_score(both, prefs)


def test_confidence_is_case_insensitive():
    prefs = {"favorite_genre": "LoFi", "favorite_mood": "CHILL", "target_energy": 0.4}
    recs = [(make_song(genre="lofi", mood="chill", energy=0.4), 5.0, "")]
    assert confidence_score(recs, prefs) == pytest.approx(1.0, abs=0.01)


# ---------------------------------------------------------------------------
# confidence_label
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "score,expected",
    [(1.0, "High"), (0.75, "High"), (0.74, "Medium"), (0.45, "Medium"), (0.44, "Low"), (0.0, "Low")],
)
def test_confidence_label_boundaries(score, expected):
    assert confidence_label(score) == expected
