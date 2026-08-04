"""
Grounding verification for generated playlist narratives.

The prompt tells the model to stay grounded in the retrieved songs. This
module checks whether it actually did, so the claim is enforced rather than
merely requested.

Two checks run against the retrieved evidence:

  Entity grounding — every quoted span in the narrative must be the title or
                     artist of a song that was actually retrieved. The prompt
                     establishes the contract that double quotes are reserved
                     for song titles and artist names, which makes any other
                     quoted string a fabrication rather than a false positive.

  Score grounding  — any number the narrative presents as a score must match a
                     real score from the retrieved set, within rounding
                     tolerance.

A failed verification is not treated as a crash. The caller retries once with
the specific violation named, then falls back to the deterministic generator.
"""

import re
from dataclasses import dataclass, field
from typing import List, Set

# Double quotes only. Single quotes are excluded because apostrophes in
# ordinary prose ("the song's mood") would produce constant false positives.
_STRAIGHT_QUOTED = re.compile(r'"([^"\n]{1,80})"')
_CURLY_QUOTED = re.compile('“([^”\n]{1,80})”')

# Numbers the narrative presents as a score: "score of 4.47", "scored 4.47",
# "scoring 4.47". Deliberately narrow so that unrelated decimals (energy
# averages, valence values) are not misread as score claims.
_SCORE_CLAIM = re.compile(r'scor\w*\s+(?:of\s+|at\s+)?(\d+(?:\.\d+)?)', re.IGNORECASE)

# Tolerance for a claimed score against a real one. Covers a model rounding
# 4.47 to 4.5, but not inventing 8.2 where 4.47 was supplied.
_SCORE_TOLERANCE = 0.06


def _normalize(text: str) -> str:
    """Casefold, collapse whitespace, and drop trailing punctuation."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = cleaned.strip(".,;:!?")
    return cleaned.casefold()


def extract_quoted_spans(narrative: str) -> List[str]:
    """Return every double-quoted span in the narrative, straight or curly."""
    spans = _STRAIGHT_QUOTED.findall(narrative)
    spans.extend(_CURLY_QUOTED.findall(narrative))
    return [s.strip() for s in spans if s.strip()]


def extract_score_claims(narrative: str) -> List[float]:
    """Return every number the narrative presents as a score."""
    claims = []
    for raw in _SCORE_CLAIM.findall(narrative):
        try:
            claims.append(float(raw))
        except ValueError:
            continue
    return claims


@dataclass
class VerificationResult:
    """Outcome of checking one narrative against its retrieved evidence."""

    ok: bool
    unsupported_entities: List[str] = field(default_factory=list)
    unsupported_scores: List[float] = field(default_factory=list)
    checked_entities: int = 0
    checked_scores: int = 0

    def summary(self) -> str:
        """One-line description of what failed, for logs and source tags."""
        if self.ok:
            return (
                f"verified ({self.checked_entities} entities, "
                f"{self.checked_scores} scores)"
            )
        problems = []
        if self.unsupported_entities:
            named = ", ".join(f'"{e}"' for e in self.unsupported_entities)
            problems.append(f"unsupported entities: {named}")
        if self.unsupported_scores:
            named = ", ".join(str(s) for s in self.unsupported_scores)
            problems.append(f"unsupported scores: {named}")
        return "; ".join(problems)


def allowed_entities(recommendations: List) -> Set[str]:
    """Titles and artists the narrative is permitted to name."""
    allowed = set()
    for song, _, _ in recommendations:
        title = song.get("title")
        artist = song.get("artist")
        if title:
            allowed.add(_normalize(title))
        if artist:
            allowed.add(_normalize(artist))
    return allowed


def verify_narrative(narrative: str, recommendations: List) -> VerificationResult:
    """
    Check a narrative against the songs that were actually retrieved.

    Returns a VerificationResult. Never raises: an unverifiable narrative is a
    result to act on, not an error condition.
    """
    if not narrative or not narrative.strip():
        return VerificationResult(ok=False, unsupported_entities=["<empty narrative>"])

    allowed = allowed_entities(recommendations)
    real_scores = [round(float(score), 2) for _, score, _ in recommendations]

    spans = extract_quoted_spans(narrative)
    unsupported_entities = [
        span for span in spans if _normalize(span) not in allowed
    ]

    claims = extract_score_claims(narrative)
    unsupported_scores = [
        claim
        for claim in claims
        if not any(abs(claim - real) <= _SCORE_TOLERANCE for real in real_scores)
    ]

    return VerificationResult(
        ok=not unsupported_entities and not unsupported_scores,
        unsupported_entities=unsupported_entities,
        unsupported_scores=unsupported_scores,
        checked_entities=len(spans),
        checked_scores=len(claims),
    )
