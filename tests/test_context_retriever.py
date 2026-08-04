"""
Tests for the second retrieval source — the prose document corpus.

The retriever's job is to surface documents that match what the listener
*stated*, not what the system inferred from their energy setting. That
distinction is the one that broke in practice, so it is tested directly.
"""

import pytest

from src.context_retriever import (
    ContextDoc,
    format_context_block,
    load_context_docs,
    retrieve_context,
)


@pytest.fixture(scope="module")
def docs():
    loaded = load_context_docs()
    assert loaded, "context corpus is empty — data/context/ missing?"
    return loaded


def prefs(genre="lofi", mood="chill", energy=0.35, acoustic=False):
    return {
        "favorite_genre": genre,
        "favorite_mood": mood,
        "target_energy": energy,
        "likes_acoustic": acoustic,
    }


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def test_corpus_loads_documents(docs):
    assert len(docs) >= 8


def test_documents_have_titles_and_text(docs):
    for d in docs:
        assert d.title and not d.title.startswith("#")
        assert len(d.text) > 100


def test_missing_directory_returns_empty_not_error(tmp_path):
    """A missing corpus degrades to song-only retrieval rather than crashing."""
    assert load_context_docs(str(tmp_path / "nonexistent")) == []


# ---------------------------------------------------------------------------
# Relevance
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "genre,mood,energy,expected",
    [
        ("lofi", "chill", 0.35, "genre-lofi"),
        ("rock", "intense", 0.90, "genre-rock"),
        ("metal", "angry", 0.95, "genre-metal"),
        ("jazz", "relaxed", 0.40, "genre-jazz"),
        ("ambient", "chill", 0.25, "genre-ambient"),
        ("pop", "happy", 0.85, "genre-pop"),
    ],
)
def test_stated_genre_retrieves_its_document(docs, genre, mood, energy, expected):
    names = [d.name for d in retrieve_context(prefs(genre, mood, energy), docs, k=2)]
    assert expected in names


def test_stated_genre_outranks_inferred_energy_vocabulary(docs):
    """
    Regression test.

    A jazz listener at mid energy expands to "steady background focus study",
    which previously scored the lofi and studying documents above the jazz one
    the listener actually asked for. Stated terms must outweigh inferred ones.
    """
    results = retrieve_context(prefs("jazz", "relaxed", 0.40), docs, k=2)
    assert results[0].name == "genre-jazz"


def test_energy_steers_the_use_case_document(docs):
    high = [d.name for d in retrieve_context(prefs("rock", "intense", 0.95), docs, k=2)]
    low = [d.name for d in retrieve_context(prefs("lofi", "chill", 0.25), docs, k=2)]

    assert any("workout" in n for n in high)
    assert any("relax" in n or "study" in n for n in low)


def test_respects_k(docs):
    assert len(retrieve_context(prefs(), docs, k=1)) == 1
    assert len(retrieve_context(prefs(), docs, k=3)) <= 3


def test_results_are_sorted_by_score(docs):
    results = retrieve_context(prefs(), docs, k=3)
    scores = [d.score for d in results]
    assert scores == sorted(scores, reverse=True)


def test_high_threshold_suppresses_weak_matches(docs):
    """Returning nothing beats returning an irrelevant document."""
    assert retrieve_context(prefs(), docs, k=2, min_score=10_000) == []


def test_empty_corpus_returns_nothing():
    assert retrieve_context(prefs(), [], k=2) == []


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def test_snippet_respects_length_budget():
    doc = ContextDoc("x", "X", "word. " * 500)
    assert len(doc.snippet(max_chars=300)) <= 300


def test_snippet_ends_on_a_sentence_when_it_can():
    doc = ContextDoc("x", "X", "First sentence here. " * 60)
    assert doc.snippet(max_chars=400).endswith(".")


def test_format_context_block_includes_titles(docs):
    block = format_context_block(retrieve_context(prefs(), docs, k=2))
    assert "[" in block and "]" in block


def test_format_context_block_empty_is_empty_string():
    assert format_context_block([]) == ""
