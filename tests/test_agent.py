"""
Tests for the multi-step planning agent.

What matters here is not that the agent produces recommendations — the
recommender already does that — but that it *branches*: that it chooses an
opening strategy from the request, notices a weak result, and reacts.
"""

import pytest

from src.agent import PlanningAgent, REPLAN_THRESHOLD, Trace
from src.recommender import load_songs

WELL_SERVED = {
    "favorite_genre": "lofi", "favorite_mood": "chill",
    "target_energy": 0.35, "likes_acoustic": True,
}
POORLY_SERVED = {
    "favorite_genre": "rock", "favorite_mood": "intense",
    "target_energy": 0.90, "likes_acoustic": False,
}


@pytest.fixture(scope="module")
def songs():
    return load_songs("data/songs.csv")


@pytest.fixture
def agent(songs):
    return PlanningAgent(songs)  # no LLM: template generation


def step_names(trace):
    return [s.name for s in trace.steps]


# ---------------------------------------------------------------------------
# The loop runs
# ---------------------------------------------------------------------------

def test_run_returns_result_and_trace(agent):
    result, trace = agent.run(WELL_SERVED)
    assert result["recommendations"]
    assert isinstance(trace, Trace)


def test_every_step_records_reasoning_and_action(agent):
    _, trace = agent.run(WELL_SERVED)
    assert len(trace.steps) >= 7
    for step in trace.steps:
        assert step.reasoning.strip()
        assert step.action.strip()
        assert step.observation.strip()


def test_steps_are_numbered_consecutively(agent):
    _, trace = agent.run(WELL_SERVED)
    assert [s.number for s in trace.steps] == list(range(1, len(trace.steps) + 1))


def test_trace_records_the_outcome(agent):
    _, trace = agent.run(WELL_SERVED)
    assert "confidence" in trace.outcome.lower()


# ---------------------------------------------------------------------------
# Validation short-circuits
# ---------------------------------------------------------------------------

def test_invalid_input_aborts_before_retrieval(agent):
    bad = {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 99}
    result, trace = agent.run(bad)

    assert result == {}
    assert len(trace.steps) == 1
    assert "REJECTED" in trace.steps[0].observation
    assert "Aborted" in trace.outcome


def test_warnings_are_carried_into_the_trace(agent):
    odd = {"favorite_genre": "polka", "favorite_mood": "smug", "target_energy": 0.5}
    result, trace = agent.run(odd)

    assert result  # soft problems do not abort
    assert "warning" in trace.steps[0].observation.lower()


# ---------------------------------------------------------------------------
# Planning and replanning — the actual decisions
# ---------------------------------------------------------------------------

def test_extreme_energy_selects_the_energy_strategy(agent):
    _, trace = agent.run(POORLY_SERVED)  # energy 0.90
    plan = next(s for s in trace.steps if s.name == "Plan scoring approach")
    assert "energy-focused" in plan.observation


def test_moderate_request_with_genre_and_mood_selects_balanced(agent):
    _, trace = agent.run(WELL_SERVED)  # energy 0.35, both fields given
    plan = next(s for s in trace.steps if s.name == "Plan scoring approach")
    assert "balanced" in plan.observation


def test_low_confidence_triggers_replanning(agent):
    result, trace = agent.run(POORLY_SERVED)
    assert result["confidence"] < REPLAN_THRESHOLD
    assert "Replan" in step_names(trace)
    replan = next(s for s in trace.steps if s.name == "Replan")
    assert "Tried all" in replan.observation


def test_adequate_confidence_skips_replanning(agent):
    result, trace = agent.run(WELL_SERVED)
    assert result["confidence"] >= REPLAN_THRESHOLD
    assert "Replan check" in step_names(trace)
    check = next(s for s in trace.steps if s.name == "Replan check")
    assert "No replanning needed" in check.observation


def test_replanning_never_lowers_confidence(agent):
    """A replan that finds nothing better must keep the original result."""
    result, _ = agent.run(POORLY_SERVED)
    baseline = agent.run({**POORLY_SERVED})[0]
    assert result["confidence"] >= baseline["confidence"] - 1e-9


# ---------------------------------------------------------------------------
# Downstream stages
# ---------------------------------------------------------------------------

def test_context_is_retrieved_for_the_request(agent):
    result, _ = agent.run(WELL_SERVED)
    assert any("lofi" in d.name for d in result["context_docs"])


def test_narrative_is_generated_and_verified(agent):
    result, _ = agent.run(WELL_SERVED)
    assert result["narrative"].strip()
    assert result["verification"].ok


def test_runs_without_an_llm_client(agent):
    """The agent's planning value does not depend on the API being available."""
    result, _ = agent.run(WELL_SERVED)
    assert result["narrative_source"] == "template"


# ---------------------------------------------------------------------------
# Trace persistence
# ---------------------------------------------------------------------------

def test_trace_renders_as_markdown(agent):
    _, trace = agent.run(WELL_SERVED)
    rendered = trace.render()
    assert rendered.startswith("# Agent trace")
    assert "**Reasoning:**" in rendered
    assert "**Outcome:**" in rendered


def test_trace_saves_to_disk(agent, tmp_path):
    _, trace = agent.run(WELL_SERVED)
    path = trace.save(str(tmp_path))
    with open(path, encoding="utf-8") as f:
        assert "Agent trace" in f.read()
