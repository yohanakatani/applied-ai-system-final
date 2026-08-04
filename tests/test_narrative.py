"""
Tests for the RAG generation layer.

The narrative must stay grounded in the songs the recommender actually
retrieved, and the system must keep working when the LLM API is unavailable.
"""

import pytest

from src.llm_client import build_fallback_narrative, GeminiClient


def make_rec(title, artist="A", genre="lofi", mood="chill", energy=0.4, score=5.0):
    song = {
        "title": title,
        "artist": artist,
        "genre": genre,
        "mood": mood,
        "energy": energy,
    }
    return (song, score, "Genre match: lofi; Mood match: chill")


PREFS = {
    "favorite_genre": "lofi",
    "favorite_mood": "chill",
    "target_energy": 0.4,
    "likes_acoustic": True,
}


def test_fallback_names_the_top_song():
    recs = [make_rec("Library Rain", score=6.0), make_rec("Midnight Coding", score=5.0)]
    narrative, source = build_fallback_narrative(PREFS, recs)
    assert "Library Rain" in narrative
    assert source == "template"


def test_fallback_reports_genre_match_count():
    recs = [
        make_rec("A", genre="lofi"),
        make_rec("B", genre="lofi"),
        make_rec("C", genre="metal"),
    ]
    narrative, _ = build_fallback_narrative(PREFS, recs)
    assert "2 of 3" in narrative


def test_fallback_is_honest_when_no_genre_matched():
    recs = [make_rec("A", genre="metal"), make_rec("B", genre="jazz")]
    narrative, _ = build_fallback_narrative(PREFS, recs)
    assert "no lofi songs" in narrative.lower()


def test_fallback_is_honest_when_no_mood_matched():
    recs = [make_rec("A", mood="angry"), make_rec("B", mood="intense")]
    narrative, _ = build_fallback_narrative(PREFS, recs)
    assert "chill" in narrative.lower()
    assert "none matched" in narrative.lower()


def test_fallback_flags_a_weak_tail_pick():
    recs = [make_rec("Strong", score=10.0), make_rec("Weak", score=1.0)]
    narrative, _ = build_fallback_narrative(PREFS, recs)
    assert "Weak" in narrative
    assert "loose fit" in narrative


def test_fallback_does_not_flag_a_consistent_list():
    recs = [make_rec("A", score=5.0), make_rec("B", score=4.8)]
    narrative, _ = build_fallback_narrative(PREFS, recs)
    assert "loose fit" not in narrative


def test_fallback_reports_energy_drift_honestly():
    high_energy = [make_rec("Loud", energy=0.95), make_rec("Louder", energy=0.98)]
    narrative, _ = build_fallback_narrative(PREFS, high_energy)
    assert "higher" in narrative.lower()


def test_fallback_handles_empty_recommendations():
    narrative, source = build_fallback_narrative(PREFS, [])
    assert narrative
    assert source == "template"


def test_fallback_never_invents_songs():
    """Every capitalized song title in the narrative must come from the input."""
    recs = [make_rec("Library Rain"), make_rec("Midnight Coding")]
    narrative, _ = build_fallback_narrative(PREFS, recs)
    # The generator only ever quotes titles it was given.
    quoted = [seg for seg in narrative.split('"')[1::2]]
    for title in quoted:
        assert title in {"Library Rain", "Midnight Coding"}


# ---------------------------------------------------------------------------
# Graceful degradation
# ---------------------------------------------------------------------------

def test_missing_api_key_raises_runtime_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        GeminiClient()


def test_api_failure_falls_back_instead_of_raising(monkeypatch):
    """A broken API must degrade to the template, never crash the run."""
    monkeypatch.setenv("GEMINI_API_KEY", "not-a-real-key")

    client = GeminiClient()

    class BoomModels:
        def generate_content(self, **kwargs):
            raise ConnectionError("simulated network failure")

    class BoomClient:
        models = BoomModels()

    client.client = BoomClient()

    recs = [make_rec("Library Rain")]
    narrative, source = client.explain_playlist(PREFS, recs)

    assert "Library Rain" in narrative
    assert source.startswith("template")
    assert "ConnectionError" in source


def test_empty_model_response_falls_back(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "not-a-real-key")
    client = GeminiClient()

    class EmptyResponse:
        text = "   "

    class EmptyModels:
        def generate_content(self, **kwargs):
            return EmptyResponse()

    class EmptyClient:
        models = EmptyModels()

    client.client = EmptyClient()

    narrative, source = client.explain_playlist(PREFS, [make_rec("Library Rain")])
    assert "Library Rain" in narrative
    assert "empty response" in source


def test_successful_generation_is_labeled_as_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "not-a-real-key")
    client = GeminiClient()

    class OkResponse:
        text = "A calm lofi set led by Library Rain."

    class OkModels:
        def generate_content(self, **kwargs):
            return OkResponse()

    class OkClient:
        models = OkModels()

    client.client = OkClient()

    narrative, source = client.explain_playlist(PREFS, [make_rec("Library Rain")])
    assert narrative == "A calm lofi set led by Library Rain."
    assert source.startswith("gemini:")
