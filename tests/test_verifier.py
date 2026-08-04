"""
Tests for narrative grounding verification and the self-correction loop.

The prompt asks the model to stay grounded. These tests check that the claim
is enforced: a narrative naming a song the recommender never retrieved must
be caught, and must never reach the user unflagged.
"""

import pytest

from src.llm_client import GeminiClient
from src.verifier import (
    extract_quoted_spans,
    extract_score_claims,
    verify_narrative,
    allowed_entities,
)


def make_rec(title, artist="Paper Lanterns", score=4.47):
    song = {
        "title": title,
        "artist": artist,
        "genre": "lofi",
        "mood": "chill",
        "energy": 0.35,
    }
    return (song, score, "Genre match: lofi")


RECS = [
    make_rec("Library Rain", "Paper Lanterns", 4.47),
    make_rec("Midnight Coding", "LoRoom", 4.46),
]

PREFS = {
    "favorite_genre": "lofi",
    "favorite_mood": "chill",
    "target_energy": 0.4,
    "likes_acoustic": True,
}


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def test_extracts_straight_quoted_spans():
    assert extract_quoted_spans('Led by "Library Rain" today.') == ["Library Rain"]


def test_extracts_curly_quoted_spans():
    assert extract_quoted_spans("Led by “Library Rain” today.") == ["Library Rain"]


def test_apostrophes_are_not_treated_as_quotes():
    """Single quotes must be ignored or ordinary prose would fail constantly."""
    assert extract_quoted_spans("The song's mood isn't wrong.") == []


def test_extracts_score_claims():
    assert extract_score_claims("It scored 4.47 overall.") == [4.47]
    assert extract_score_claims("with a score of 4.47") == [4.47]


def test_non_score_decimals_are_not_read_as_scores():
    """Energy and valence figures must not be mistaken for score claims."""
    assert extract_score_claims("Average energy of 0.37 and valence 0.60.") == []


def test_allowed_entities_includes_titles_and_artists():
    allowed = allowed_entities(RECS)
    assert "library rain" in allowed
    assert "paper lanterns" in allowed
    assert "loroom" in allowed


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def test_grounded_narrative_passes():
    text = 'Led by "Library Rain", with "Midnight Coding" close behind.'
    result = verify_narrative(text, RECS)
    assert result.ok is True
    assert result.unsupported_entities == []


def test_fabricated_song_is_caught():
    text = 'Led by "Library Rain", plus the classic "Purple Rain".'
    result = verify_narrative(text, RECS)
    assert result.ok is False
    assert "Purple Rain" in result.unsupported_entities


def test_fabricated_artist_is_caught():
    text = 'A calm set from "Library Rain" by "Taylor Swift".'
    result = verify_narrative(text, RECS)
    assert result.ok is False
    assert "Taylor Swift" in result.unsupported_entities


def test_fabricated_score_is_caught():
    text = '"Library Rain" scored 9.99 here.'
    result = verify_narrative(text, RECS)
    assert result.ok is False
    assert 9.99 in result.unsupported_scores


def test_correct_score_passes():
    text = '"Library Rain" scored 4.47 here.'
    assert verify_narrative(text, RECS).ok is True


def test_rounded_score_is_tolerated():
    """A model rounding 4.47 to 4.5 is not a fabrication."""
    text = '"Library Rain" scored 4.5 here.'
    assert verify_narrative(text, RECS).ok is True


def test_matching_is_case_insensitive():
    text = 'Led by "library rain" and "MIDNIGHT CODING".'
    assert verify_narrative(text, RECS).ok is True


def test_trailing_punctuation_inside_quotes_is_tolerated():
    text = 'The standout is "Library Rain."'
    assert verify_narrative(text, RECS).ok is True


def test_empty_narrative_fails_verification():
    assert verify_narrative("", RECS).ok is False
    assert verify_narrative("   ", RECS).ok is False


def test_narrative_with_no_quotes_passes_entity_check():
    """Nothing quoted means nothing to contradict the retrieved set."""
    result = verify_narrative("A calm lofi set for studying.", RECS)
    assert result.ok is True
    assert result.checked_entities == 0


def test_summary_names_the_offending_entity():
    result = verify_narrative('Try "Purple Rain".', RECS)
    assert "Purple Rain" in result.summary()


def test_summary_reports_counts_when_verified():
    result = verify_narrative('"Library Rain" scored 4.47.', RECS)
    assert "verified" in result.summary()


# ---------------------------------------------------------------------------
# Self-correction loop
# ---------------------------------------------------------------------------

class ScriptedModels:
    """Returns a scripted response per call so the loop can be driven."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def generate_content(self, **kwargs):
        self.prompts.append(kwargs.get("contents", ""))
        text = self.responses.pop(0) if self.responses else ""

        class R:
            pass

        r = R()
        r.text = text
        return r


def make_client(monkeypatch, responses):
    monkeypatch.setenv("GEMINI_API_KEY", "not-a-real-key")
    client = GeminiClient()
    models = ScriptedModels(responses)

    class C:
        pass

    c = C()
    c.models = models
    client.client = c
    return client, models


def test_clean_first_response_is_returned_without_retry(monkeypatch):
    client, models = make_client(
        monkeypatch, ['A calm set led by "Library Rain".']
    )
    narrative, source = client.explain_playlist(PREFS, RECS)

    assert narrative == 'A calm set led by "Library Rain".'
    assert source.startswith("gemini:")
    assert "verified" in source
    assert len(models.prompts) == 1


def test_hallucination_triggers_one_retry(monkeypatch):
    client, models = make_client(
        monkeypatch,
        [
            'Led by "Library Rain" and "Purple Rain".',   # fabricated
            'Led by "Library Rain" and "Midnight Coding".',  # corrected
        ],
    )
    narrative, source = client.explain_playlist(PREFS, RECS)

    assert "Purple Rain" not in narrative
    assert "after 1 correction" in source
    assert len(models.prompts) == 2


def test_retry_prompt_names_the_specific_violation(monkeypatch):
    client, models = make_client(
        monkeypatch,
        ['Try "Purple Rain".', 'Try "Library Rain".'],
    )
    client.explain_playlist(PREFS, RECS)

    assert "Purple Rain" in models.prompts[1]
    assert "failed verification" in models.prompts[1]


def test_two_failed_attempts_fall_back_to_template(monkeypatch):
    client, models = make_client(
        monkeypatch,
        ['Try "Purple Rain".', 'Still "Purple Rain".'],
    )
    narrative, source = client.explain_playlist(PREFS, RECS)

    assert "Purple Rain" not in narrative
    assert source.startswith("template")
    assert "failed verification" in source
    assert len(models.prompts) == 2


def test_unverifiable_output_never_reaches_the_user(monkeypatch):
    """The whole point: a fabricated song must not be shown, ever."""
    client, _ = make_client(
        monkeypatch,
        ['"Bohemian Rhapsody" is a great fit.', '"Bohemian Rhapsody" again.'],
    )
    narrative, source = client.explain_playlist(PREFS, RECS)

    assert "Bohemian Rhapsody" not in narrative
    assert not source.startswith("gemini")


def test_empty_retry_falls_back(monkeypatch):
    client, _ = make_client(monkeypatch, ['Try "Purple Rain".', ""])
    narrative, source = client.explain_playlist(PREFS, RECS)

    assert "Purple Rain" not in narrative
    assert source.startswith("template")
