"""
Few-shot style specialization for narrative generation.

The base prompt constrains *content* — stay grounded, be honest about weak
picks. It says nothing about *voice*, so the model defaults to a middling
explanatory register.

This module adds voice control through few-shot examples rather than through
adjectives. Telling a model to "be concise" is a weak instruction; showing it
two concise outputs is a strong one, because the example carries sentence
length, punctuation habits, and structure all at once.

Every persona inherits the same grounding rules. Style varies; the constraint
that each factual claim traces to a retrieved song does not. The examples
themselves obey the quoting contract, so they reinforce it by demonstration
instead of only by instruction.

`measure_style()` exists because "the output is different" is a claim that
should be checkable rather than asserted.
"""

import re
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class Persona:
    """A named output style defined by instruction plus worked examples."""

    key: str
    name: str
    description: str
    instruction: str
    examples: List[str]

    def prompt_block(self) -> str:
        """Render the style directive and its examples for the prompt."""
        shots = "\n\n".join(f"Example {i}:\n{ex}" for i, ex in enumerate(self.examples, 1))
        return (
            f"\nWrite in this specific voice: {self.instruction}\n\n"
            f"Match the style of these examples exactly — their length, rhythm, "
            f"and structure. Do not copy their content; the songs below are "
            f"different.\n\n{shots}\n"
        )


BASELINE = Persona(
    key="baseline",
    name="Baseline",
    description="No style directive. The model's default explanatory register.",
    instruction="",
    examples=[],
)

CONCISE = Persona(
    key="concise",
    name="Concise DJ",
    description="Clipped radio-style delivery. Short sentences, minimal hedging.",
    instruction=(
        "Terse and punchy, like a radio DJ reading a set list. Short sentences. "
        "No hedging, no filler, no throat-clearing. Two or three sentences total."
    ),
    examples=[
        'Opening with "Night Drive" by "Vector Pines" at 5.20 — pure synthwave. '
        '"Chrome Alley" by "Vector Pines" keeps the pulse going. Late-night '
        'driving music, nothing else.',

        '"Paper Boats" by "Hollow Bell" leads at 6.10. "Slow Tide" by "Marsh '
        'Kite" follows, softer but on-target. Built for a quiet evening.',
    ],
)

ANALYTICAL = Persona(
    key="analytical",
    name="Analytical",
    description="Data-forward. Leads with numbers and names the trade-offs.",
    instruction=(
        "Precise and quantitative, like a technical reviewer. Lead with the "
        "numbers. Name the trade-off in every ranking decision. Neutral tone, "
        "no enthusiasm, no sales language."
    ),
    examples=[
        'The top two results cluster tightly at 5.20 and 5.05, both matching '
        'genre and mood, so the ranking between them is effectively a tie. '
        '"Night Drive" by "Vector Pines" takes the lead on energy proximity '
        'alone. Below position two the scores fall sharply to 2.10, indicating '
        'the catalog holds only two strong candidates for this profile. The '
        'remaining entries are filling slots rather than matching intent.',

        '"Paper Boats" by "Hollow Bell" scores 6.10, driven by an exact genre '
        'match plus close energy proximity. The 1.9-point gap to second place '
        'is wider than typical and indicates low competition in this genre. '
        'Positions three through five match on energy but not genre, so their '
        'inclusion reflects catalog scarcity rather than fit.',
    ],
)

WARM = Persona(
    key="warm",
    name="Warm Guide",
    description="Conversational and second-person. Explains without jargon.",
    instruction=(
        "Warm and conversational, like a friend recommending music. Address the "
        "listener as 'you'. Explain why something fits in plain language rather "
        "than by citing numbers. Stay honest about the weaker picks."
    ),
    examples=[
        'I think you will settle into "Night Drive" by "Vector Pines" right '
        'away — it has exactly the late-night pulse you were after. "Chrome '
        'Alley" by "Vector Pines" carries that same feeling a little further. '
        'The last couple of picks wander off your genre, and you may well skip '
        'them, but they hold the mood steady. Save this one for a long drive '
        'after dark.',

        'You asked for something quiet, and "Paper Boats" by "Hollow Bell" is '
        'about as close as this catalog gets. "Slow Tide" by "Marsh Kite" sits '
        'right beside it. I will be honest that the tail of this list is '
        'thinner than I would like. Put it on when you want the room to settle.',
    ],
)

PERSONAS: Dict[str, Persona] = {
    p.key: p for p in (BASELINE, CONCISE, ANALYTICAL, WARM)
}


def get_persona(key: str) -> Persona:
    """Look up a persona, falling back to baseline for an unknown key."""
    return PERSONAS.get((key or "").strip().lower(), BASELINE)


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------

_SENTENCE = re.compile(r"[.!?]+(?:\s|$)")
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_SECOND_PERSON = re.compile(r"\b(you|your|you'll|you're|yours)\b", re.IGNORECASE)


def measure_style(text: str) -> Dict[str, float]:
    """
    Quantify the stylistic properties a persona is meant to control.

    Returns metrics that should move in predictable directions if the few-shot
    examples are doing anything: Concise the lowest word count, Analytical the
    most numbers, Warm the most second-person address and no numbers at all.

    Both absolute counts and per-word densities are reported. Prefer the counts
    when comparing personas of different lengths — density divides by word
    count, so a terse persona's brevity inflates its density even when it cites
    fewer numbers than a verbose one. That confound made Concise appear more
    number-heavy than Analytical in one run despite using fewer numbers.
    """
    words = _WORD.findall(text)
    sentences = [s for s in _SENTENCE.split(text) if s.strip()]
    word_count = len(words)

    return {
        "words": word_count,
        "sentences": len(sentences),
        "avg_sentence_len": round(word_count / len(sentences), 1) if sentences else 0.0,
        "numbers": len(_NUMBER.findall(text)),
        "number_density": round(len(_NUMBER.findall(text)) / word_count * 100, 2)
        if word_count else 0.0,
        "second_person": len(_SECOND_PERSON.findall(text)),
        "second_person_density": round(
            len(_SECOND_PERSON.findall(text)) / word_count * 100, 2
        ) if word_count else 0.0,
    }
