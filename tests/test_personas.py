"""
Tests for few-shot style specialization.

Two things need to hold: the persona must actually reach the prompt, and the
style metrics must be able to tell personas apart. The second matters because
"the output is measurably different" is the claim being made, and a metric
that cannot separate hand-written examples cannot separate generated ones.
"""

import os

import pytest

from src.personas import (
    ANALYTICAL,
    BASELINE,
    CONCISE,
    PERSONAS,
    WARM,
    get_persona,
    measure_style,
)


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------

def test_all_personas_registered():
    assert set(PERSONAS) == {"baseline", "concise", "analytical", "warm"}


@pytest.mark.parametrize("key", ["concise", "analytical", "warm", "baseline"])
def test_get_persona_by_key(key):
    assert get_persona(key).key == key


def test_get_persona_is_case_insensitive():
    assert get_persona("CONCISE").key == "concise"


@pytest.mark.parametrize("bad", ["nonsense", "", None])
def test_unknown_persona_falls_back_to_baseline(bad):
    assert get_persona(bad).key == "baseline"


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def test_baseline_adds_nothing_to_the_prompt():
    assert BASELINE.prompt_block().strip() == "" or not BASELINE.examples


@pytest.mark.parametrize("persona", [CONCISE, ANALYTICAL, WARM])
def test_styled_personas_supply_examples(persona):
    block = persona.prompt_block()
    assert len(persona.examples) >= 2
    for example in persona.examples:
        assert example in block


@pytest.mark.parametrize("persona", [CONCISE, ANALYTICAL, WARM])
def test_examples_obey_the_quoting_contract(persona):
    """
    The examples teach by demonstration. If they quoted things that were not
    titles or artists, they would undermine the rule the verifier depends on.
    """
    for example in persona.examples:
        quoted = example.split('"')[1::2]
        assert quoted, "example should quote at least one title"
        for span in quoted:
            # Titles and artist names are short; prose fragments are not.
            assert len(span.split()) <= 4, f"suspicious quoted span: {span!r}"


def test_persona_reaches_the_generation_prompt(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "not-a-real-key")
    from src.llm_client import GeminiClient

    client = GeminiClient()
    recs = [({"title": "T", "artist": "A", "genre": "lofi",
              "mood": "chill", "energy": 0.4}, 5.0, "Genre match: lofi")]
    prefs = {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 0.4}

    baseline = client._build_prompt(prefs, recs, None, "baseline")
    concise = client._build_prompt(prefs, recs, None, "concise")

    assert len(concise) > len(baseline)
    assert CONCISE.examples[0] in concise
    assert CONCISE.examples[0] not in baseline


def test_grounding_rules_survive_every_persona(monkeypatch):
    """Style varies; the constraint that claims trace to retrieved songs does not."""
    monkeypatch.setenv("GEMINI_API_KEY", "not-a-real-key")
    from src.llm_client import GeminiClient

    client = GeminiClient()
    recs = [({"title": "T", "artist": "A", "genre": "lofi",
              "mood": "chill", "energy": 0.4}, 5.0, "Genre match")]
    prefs = {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 0.4}

    for key in PERSONAS:
        prompt = client._build_prompt(prefs, recs, None, key)
        assert "Do not" in prompt and "invent" in prompt
        assert "double quotes around song titles" in prompt


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------

def test_measure_counts_words_and_sentences():
    m = measure_style("One two three. Four five.")
    assert m["words"] == 5
    assert m["sentences"] == 2
    assert m["avg_sentence_len"] == 2.5


def test_measure_handles_empty_text():
    m = measure_style("")
    assert m["words"] == 0
    assert m["avg_sentence_len"] == 0.0


def test_measure_detects_numbers():
    assert measure_style("It scored 4.47 and 3.2.")["numbers"] == 2


def test_measure_detects_second_person():
    assert measure_style("You will like your playlist.")["second_person"] == 2


def test_metrics_separate_the_persona_examples():
    """
    The metrics must distinguish the hand-written examples in the intended
    directions, otherwise they cannot substantiate a claim about generated
    output either.
    """
    concise = measure_style(" ".join(CONCISE.examples))
    analytical = measure_style(" ".join(ANALYTICAL.examples))
    warm = measure_style(" ".join(WARM.examples))

    # Concise writes the shortest sentences.
    assert concise["avg_sentence_len"] < analytical["avg_sentence_len"]

    # Analytical leans hardest on numbers.
    assert analytical["number_density"] > warm["number_density"]

    # Warm addresses the listener directly; the others largely do not.
    assert warm["second_person_density"] > concise["second_person_density"]
    assert warm["second_person_density"] > analytical["second_person_density"]
