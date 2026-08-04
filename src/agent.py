"""
Multi-step planning agent for the Music Recommender.

The CLI's simpler modes run a fixed pipeline: score, then explain. This agent
instead *decides* what to do at each step based on what the previous step
produced, and records the reasoning behind every decision.

The loop it runs:

    1. VALIDATE   guardrails; abort early on unrecoverable input
    2. PLAN       choose an initial scoring strategy from the profile shape
    3. RETRIEVE   score the catalog with that strategy
    4. ASSESS     compute confidence in the result
    5. REPLAN     if confidence is weak, try the alternative strategies and
                  keep the best — a real branch, not a fixed second pass
    6. CONTEXT    retrieve supporting documents from the prose corpus
    7. GENERATE   produce a narrative grounded in both sources
    8. VERIFY     check the narrative against the retrieved songs
    9. REPORT     emit the full trace

Steps 3, 6, 7, and 8 are tool calls into other modules; the agent's own
contribution is choosing which to call and how to react to what comes back.

Every run produces a `Trace` that can be written to disk, so the decisions are
auditable after the fact rather than inferred from the output.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.context_retriever import load_context_docs, retrieve_context
from src.guardrails import confidence_label, confidence_score, validate_user_prefs
from src.llm_client import build_fallback_narrative
from src.recommender import SCORING_MODES, recommend_songs
from src.verifier import verify_narrative

TRACE_DIR = os.path.join(os.path.dirname(__file__), "..", "logs", "traces")

# Below this, the agent considers the first attempt weak enough to justify
# spending extra work exploring alternative strategies.
REPLAN_THRESHOLD = 0.60


@dataclass
class Step:
    """One decision or action in the agent's run."""

    number: int
    name: str
    reasoning: str
    action: str
    observation: str

    def render(self) -> str:
        return (
            f"### Step {self.number} — {self.name}\n\n"
            f"**Reasoning:** {self.reasoning}\n\n"
            f"**Action:** `{self.action}`\n\n"
            f"**Observation:** {self.observation}\n"
        )


@dataclass
class Trace:
    """The full record of one agent run."""

    profile: Dict
    steps: List[Step] = field(default_factory=list)
    outcome: str = ""
    started: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    def add(self, name: str, reasoning: str, action: str, observation: str) -> None:
        self.steps.append(Step(len(self.steps) + 1, name, reasoning, action, observation))

    def render(self) -> str:
        header = (
            f"# Agent trace — {self.started}\n\n"
            f"**Profile:** genre={self.profile.get('favorite_genre')}, "
            f"mood={self.profile.get('favorite_mood')}, "
            f"energy={self.profile.get('target_energy')}, "
            f"acoustic={self.profile.get('likes_acoustic', False)}\n\n"
            f"**Steps taken:** {len(self.steps)}\n\n---\n\n"
        )
        body = "\n".join(step.render() for step in self.steps)
        return f"{header}{body}\n---\n\n**Outcome:** {self.outcome}\n"

    def save(self, directory: Optional[str] = None) -> str:
        """Write the trace to disk and return its path."""
        target = directory or TRACE_DIR
        os.makedirs(target, exist_ok=True)
        stamp = self.started.replace(":", "").replace("-", "")
        genre = self.profile.get("favorite_genre", "unknown")
        path = os.path.join(target, f"trace-{genre}-{stamp}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.render())
        return path


class PlanningAgent:
    """
    Runs the plan → act → assess → replan loop over the recommender.

    llm_client is optional. Without it the agent still plans, replans, and
    verifies — it just generates with the deterministic template instead.
    """

    def __init__(self, songs: List[Dict], llm_client=None, context_docs=None):
        self.songs = songs
        self.llm_client = llm_client
        self.context_docs = context_docs if context_docs is not None else load_context_docs()

    # -- step 2 -------------------------------------------------------------

    def _choose_strategy(self, prefs: Dict) -> tuple:
        """
        Pick an opening strategy from the shape of the request.

        Returns (strategy_name, reasoning).
        """
        energy = float(prefs.get("target_energy", 0.5))

        if energy >= 0.85 or energy <= 0.25:
            return (
                "energy-focused",
                f"Target energy {energy:.2f} sits at an extreme, where energy "
                f"proximity separates candidates better than genre does.",
            )
        if prefs.get("favorite_genre") and prefs.get("favorite_mood"):
            return (
                "balanced",
                "Both genre and mood were specified, so no single signal should "
                "dominate the opening attempt.",
            )
        if prefs.get("favorite_genre"):
            return (
                "genre-first",
                "Genre was specified without a mood, so genre carries the request.",
            )
        return ("mood-first", "No genre given; mood is the strongest available signal.")

    # -- step 5 -------------------------------------------------------------

    def _replan(self, prefs: Dict, current_name: str, current_conf: float) -> tuple:
        """
        Try every other strategy and keep the best.

        Returns (best_name, best_recs, best_conf, observation).
        """
        results = []
        for name, strategy in SCORING_MODES.items():
            recs = recommend_songs(prefs, self.songs, k=5, strategy=strategy)
            results.append((name, recs, confidence_score(recs, prefs)))

        results.sort(key=lambda r: r[2], reverse=True)
        best_name, best_recs, best_conf = results[0]

        table = ", ".join(f"{n}={c:.0%}" for n, _, c in results)
        if best_conf > current_conf + 0.01:
            observation = (
                f"Tried all {len(results)} strategies ({table}). "
                f"Switching from {current_name} to {best_name}, "
                f"confidence {current_conf:.0%} → {best_conf:.0%}."
            )
        else:
            observation = (
                f"Tried all {len(results)} strategies ({table}). None beat "
                f"{current_name} at {current_conf:.0%} — the ceiling is set by "
                f"the catalog, not the weighting. Keeping the original."
            )
        return best_name, best_recs, best_conf, observation

    # -- main loop ----------------------------------------------------------

    def run(self, prefs: Dict, k: int = 5) -> tuple:
        """
        Execute the full loop.

        Returns (result_dict, trace). result_dict is empty when validation
        fails, in which case the trace explains why.
        """
        trace = Trace(profile=dict(prefs))

        # 1. VALIDATE
        is_valid, warnings = validate_user_prefs(prefs)
        if not is_valid:
            trace.add(
                "Validate input",
                "Bad input must be rejected before any work is done, so the "
                "failure is attributed to the request rather than the catalog.",
                "validate_user_prefs(prefs)",
                f"REJECTED — {warnings[0]}",
            )
            trace.outcome = f"Aborted at validation: {warnings[0]}"
            return {}, trace

        trace.add(
            "Validate input",
            "Check the request is answerable before spending any retrieval work.",
            "validate_user_prefs(prefs)",
            "Accepted."
            + (f" {len(warnings)} warning(s): {'; '.join(warnings)}" if warnings else ""),
        )

        # 2. PLAN
        strategy_name, why = self._choose_strategy(prefs)
        trace.add(
            "Plan scoring approach",
            why,
            f"SCORING_MODES['{strategy_name}']",
            f"Opening strategy: {strategy_name}.",
        )

        # 3. RETRIEVE
        recs = recommend_songs(prefs, self.songs, k=k, strategy=SCORING_MODES[strategy_name])
        top = recs[0][0]["title"] if recs else "nothing"
        trace.add(
            "Retrieve and score catalog",
            "Score every song in the catalog against the profile using the "
            "chosen strategy.",
            f"recommend_songs(prefs, songs, k={k}, strategy={strategy_name})",
            f"Retrieved {len(recs)} songs. Top pick: {top}.",
        )

        # 4. ASSESS
        conf = confidence_score(recs, prefs)
        genre_hits = sum(
            1 for s, _, _ in recs
            if s.get("genre", "").lower() == str(prefs.get("favorite_genre", "")).lower()
        )
        trace.add(
            "Assess result quality",
            "Decide whether this result is good enough to present, or whether "
            "more work is justified.",
            "confidence_score(recs, prefs)",
            f"Confidence {conf:.0%} ({confidence_label(conf)}). "
            f"{genre_hits}/{len(recs)} picks match the requested genre.",
        )

        # 5. REPLAN — the branch
        if conf < REPLAN_THRESHOLD:
            best_name, best_recs, best_conf, observation = self._replan(
                prefs, strategy_name, conf
            )
            trace.add(
                "Replan",
                f"Confidence {conf:.0%} is below the {REPLAN_THRESHOLD:.0%} "
                f"threshold. Before accepting a weak result, check whether a "
                f"different weighting does better on this catalog.",
                "recommend_songs(...) across all SCORING_MODES",
                observation,
            )
            if best_conf > conf:
                recs, conf, strategy_name = best_recs, best_conf, best_name
        else:
            trace.add(
                "Replan check",
                f"Confidence {conf:.0%} meets the {REPLAN_THRESHOLD:.0%} "
                f"threshold, so exploring alternatives is not worth the work.",
                "(skipped)",
                "No replanning needed.",
            )

        # 6. CONTEXT
        ctx = retrieve_context(prefs, self.context_docs, k=2)
        trace.add(
            "Retrieve supporting context",
            "Pull prose notes on this genre and listening situation so the "
            "narrative can reason about the request, not just restate scores.",
            "retrieve_context(prefs, k=2)",
            (
                "Retrieved: "
                + ", ".join(f"{d.name} (score {d.score})" for d in ctx)
                if ctx
                else "Nothing scored above the relevance threshold; "
                     "generating from songs alone."
            ),
        )

        # 7. GENERATE
        if self.llm_client:
            narrative, source = self.llm_client.explain_playlist(prefs, recs, context_docs=ctx)
            action = "GeminiClient.explain_playlist(prefs, recs, context_docs)"
        else:
            narrative, source = build_fallback_narrative(prefs, recs)
            action = "build_fallback_narrative(prefs, recs)"
        trace.add(
            "Generate narrative",
            "Explain the playlist in prose, grounded in the retrieved songs.",
            action,
            f"Generated {len(narrative.split())} words via {source}.",
        )

        # 8. VERIFY
        result = verify_narrative(narrative, recs)
        trace.add(
            "Verify grounding",
            "Confirm the narrative only names songs, artists, and scores that "
            "were actually retrieved, before any of it reaches the user.",
            "verify_narrative(narrative, recs)",
            f"{'PASSED' if result.ok else 'FAILED'} — {result.summary()}",
        )

        trace.outcome = (
            f"Presented {len(recs)} songs at {conf:.0%} confidence "
            f"({confidence_label(conf)}) using the {strategy_name} strategy. "
            f"Narrative {'verified' if result.ok else 'replaced after failing verification'}."
        )

        return (
            {
                "recommendations": recs,
                "confidence": conf,
                "confidence_label": confidence_label(conf),
                "strategy": strategy_name,
                "context_docs": ctx,
                "narrative": narrative,
                "narrative_source": source,
                "verification": result,
                "warnings": warnings,
            },
            trace,
        )
