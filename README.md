# Music Recommender — Applied AI System

An explainable music recommendation system that retrieves songs from a catalog,
scores them against a listener's taste profile, and generates a grounded
natural-language explanation of why the playlist fits.

**Extended from:** Module 3 — Music Recommender Simulation
**Course:** AI110 — Applied AI

---

## What This System Does

You describe what you want to hear — genre, mood, energy level, whether you
like acoustic music. The system:

1. **Validates** your input and warns you about anything it can't handle
2. **Retrieves** the song catalog and scores every track against your profile
3. **Ranks** the results using one of five interchangeable scoring strategies
4. **Explains** why each song was picked, with a per-song score breakdown
5. **Narrates** the playlist as a whole using an LLM grounded in the retrieved songs
6. **Reports a confidence score** so you know how well the catalog actually matched you
7. **Logs** every run to a JSON audit trail

The point of the system is not just to rank songs — it is to be **honest about
how good the ranking actually is**. A recommender that returns five bad songs
with no signal that they're bad is worse than one that says "confidence: low."

---

## The AI Feature: RAG + Reliability

This project implements **two** of the required advanced features, both wired
into the main application path rather than bolted on as standalone scripts.

### Retrieval-Augmented Generation

The narrative generator never sees the song catalog. It only sees the songs the
recommender **retrieved and scored** for this specific user, along with the
score breakdown explaining each pick:

```
1. "Library Rain" by Paper Lanterns (lofi, chill, energy=0.35) - score 4.47
   Score breakdown: Genre match: lofi; Mood match: chill; Energy score: 0.97
```

The prompt explicitly forbids inventing songs or musical details not present in
the retrieved evidence, and instructs the model to be honest about weak picks.
This is genuine retrieval-grounded generation: change the retrieval, and the
narrative changes with it.

### Agentic verify-and-correct loop

A prompt asking for grounding is a request, not a guarantee. The system
**checks whether the model complied**, and acts on the answer:

1. **Generate** a narrative from the retrieved songs
2. **Verify** it — every quoted song title and artist must exist in the
   retrieved set, and every cited score must match a real one
3. **Correct** — if verification fails, retry once with the specific violation
   quoted back to the model
4. **Escalate** — if the retry also fails, discard the model output entirely
   and fall back to the deterministic generator

The model plans, acts, and checks its own work, with a safe path when
self-correction doesn't succeed. Observed behavior across all four paths:

| Model behavior | Calls | Result |
|---|---|---|
| Stays grounded | 1 | `gemini:... (verified (2 entities, 0 scores))` |
| Names "Purple Rain", then corrects | 2 | `gemini:... (verified, after 1 correction)` |
| Names "Bohemian Rhapsody" twice | 2 | `template (failed verification: unsupported entities: "Bohemian Rhapsody")` |
| Invents a score of 9.99 | 2 | `template (failed verification: unsupported scores: 9.99)` |

In the failing cases the fabricated song never reaches the user.

**Why the quoting rule exists.** The prompt reserves double quotes for song
titles and artist names only. That contract is what makes the check reliable
rather than heuristic — any other quoted string is a fabrication, not a
guess. The tradeoff is deliberate: if the model quotes a phrase for emphasis
despite the instruction, the system falls back to the template rather than
risk passing an unverified claim through. Erring toward the safe generator is
the correct bias for a trustworthiness feature.

### Reliability and Testing System

| Component | What it does |
|---|---|
| `validate_user_prefs()` | Rejects unrecoverable input (missing fields, energy outside 0–1); warns on soft problems (unknown genre, out-of-range tempo) and continues |
| `confidence_score()` | Scores 0–1 how well the returned playlist matched the stated genre, mood, and energy |
| `confidence_label()` | Buckets that into High / Medium / Low so the user sees it at a glance |
| Adversarial profiles | Three profiles designed to stress specific weaknesses, run as a reliability report in mode 3 |
| `verify_narrative()` | Checks generated narratives against the retrieved songs; unverifiable output never reaches the user |
| `log_run()` | Appends a structured JSON record of every run for later review |
| 70 automated tests | Cover validation boundaries, confidence math, narrative grounding, the correction loop, and API-failure fallback |

---

## Architecture

![System architecture](assets/architecture.png)

Mermaid source: [`diagrams/architecture.mmd`](diagrams/architecture.mmd)

The system is five stages: **input guardrails → retrieval → scoring → RAG
generation → reliability and audit**. Note the fallback edge in stage 4 — if
the LLM call fails, generation degrades to a deterministic template rather than
crashing the run.

---

## Setup

**Requires Python 3.9+**

```bash
git clone https://github.com/yohanakatani/applied-ai-system-final.git
cd applied-ai-system-final
pip install -r requirements.txt
```

### Optional: enable AI narrative generation

The system runs fully without an API key — narrative mode falls back to a
deterministic offline generator. To enable LLM-generated narratives:

1. Get a free Gemini API key at <https://aistudio.google.com/apikey>
   (a valid key starts with `AIza`)
2. Create a `.env` file in the project root:

```
GEMINI_API_KEY=your_key_here
```

Optionally pin a different model:

```
GEMINI_MODEL=gemini-2.0-flash
```

`.env` is gitignored — your key is never committed.

---

## Running It

```bash
python -m src.main
```

You get three modes:

| Mode | What it does |
|---|---|
| **1 — Scoring only** | Enter preferences, get ranked songs with per-song reasons and a confidence score |
| **2 — RAG narrative** | Everything in mode 1, plus a natural-language playlist narrative |
| **3 — Evaluation** | Runs all three adversarial profiles and prints a reliability report |

### Example: mode 3 output

```
============================================================
RELIABILITY EVALUATION — Adversarial Profiles
============================================================

Profile: High-Energy Pop
  Confidence: Medium (51%)
  Top pick: Sunrise City by Neon Echo (score 9.14)

Profile: Chill Lofi
  Confidence: Medium (67%)
  Top pick: Library Rain by Paper Lanterns (score 9.86)

Profile: Deep Intense Rock
  Confidence: Low (43%)
  Top pick: Storm Runner by Voltline (score 9.21)

------------------------------------------------------------
Summary:
  High-Energy Pop        Medium   51%  ##########
  Chill Lofi             Medium   67%  #############
  Deep Intense Rock      Low      43%  ########
```

The Deep Intense Rock profile scoring **Low** is the system working correctly —
the catalog contains exactly one rock song, so it genuinely cannot serve that
listener well, and it says so instead of pretending otherwise.

### Example: narrative output

```
Playlist Narrative:
------------------------------------------------------------
This 5-song playlist is led by "Library Rain" by Paper Lanterns, the strongest
match at a score of 4.47. 3 of 5 picks are actually in your preferred lofi
genre. 3 carry the chill mood you asked for. The average energy of 0.37 sits
right on your 0.38 target. Be aware the tail of the list is weaker: "Cracked
Pavement" scored only 1.00 and is a loose fit.

[generated by: template (API error: ClientError)]
```

Note the `[generated by: ...]` tag. The system **always** tells you which
generator produced the narrative — it never passes template output off as model
output.

---

## Guardrails and Error Handling

The system is designed so that **no single failure stops a run**:

| Failure | Behavior |
|---|---|
| Missing required field | Rejected before scoring, with the field named |
| Energy outside 0–1 | Rejected with the invalid value echoed back |
| Unknown genre or mood | Warned, run continues, warning recorded in the log |
| Non-numeric energy typed at the prompt | Falls back to 0.5 with a notice |
| No `GEMINI_API_KEY` | Narrative mode uses the offline template generator |
| Gemini API error, timeout, or 401 | Caught, falls back to template, error type surfaced in the source tag |
| Model returns empty text | Treated as failure, falls back to template |
| Model names a song that was never retrieved | Caught by verification, one corrective retry, then template fallback |
| Model cites a score that does not exist | Caught by verification, same correction path |
| Windows `cp1252` console | stdout forced to UTF-8 so the CLI renders identically cross-platform |

Every run is appended to `logs/recommendations.log` as one JSON object per line:

```json
{"timestamp": "2026-08-04T15:22:31.441+00:00", "strategy": "balanced",
 "user_prefs": {"genre": "lofi", "mood": "chill", "energy": 0.38, "likes_acoustic": true},
 "confidence": 0.67,
 "top_results": [{"title": "Library Rain", "artist": "Paper Lanterns", "score": 4.47}],
 "warnings": []}
```

---

## Tests

```bash
pytest
```

70 tests, all passing:

| File | Covers |
|---|---|
| `tests/test_recommender.py` | Core ranking and explanation behavior |
| `tests/test_guardrails.py` | Validation boundaries, confidence math, label thresholds |
| `tests/test_narrative.py` | Narrative grounding, honesty about weak picks, API-failure fallback |
| `tests/test_verifier.py` | Quote and score extraction, fabrication detection, the correction loop |
| `tests/test_logger.py` | Audit trail format, append behavior, timezone-aware timestamps |

The verifier tests drive the correction loop with scripted model responses, so
the fabrication path is exercised without needing a live API. The key test is
`test_unverifiable_output_never_reaches_the_user` — it asserts that a model
insisting on a song that was never retrieved results in that song being absent
from what the user sees.

---

## Project Structure

```
applied-ai-system-final/
├── assets/
│   └── architecture.png       # Rendered architecture diagram
├── diagrams/
│   └── architecture.mmd       # Mermaid source (required deliverable)
├── data/
│   └── songs.csv              # 18-song catalog with audio features
├── src/
│   ├── main.py                # CLI: three modes, wires everything together
│   ├── recommender.py         # Scoring strategies, ranking, diversity re-rank
│   ├── guardrails.py          # Input validation + confidence scoring
│   ├── llm_client.py          # RAG generation + verify-and-correct loop
│   ├── verifier.py            # Grounding checks on generated narratives
│   └── logger.py              # JSON audit trail
├── tests/                     # 70 tests
├── logs/                      # Created on first run (gitignored)
├── model_card.md              # Limitations, bias analysis, evaluation
├── ai_interactions.md         # AI-assisted development log
├── requirements.txt
└── .env                       # Your API key (gitignored)
```

---

## Known Limitations

These are real and documented rather than hidden — see `model_card.md` for the
full analysis.

- **The catalog is 18 songs.** Ten genres have only one or two representatives.
  A rock listener will always get the same top pick because there is only one
  rock song. This is why the Deep Intense Rock profile scores Low confidence:
  the limitation is in the data, not the math.
- **Mood matching is binary.** "angry" and "intense" are penalized as harshly
  as "angry" and "chill," even though the first pair is far more similar.
- **Confidence is a heuristic, not a calibrated probability.** It measures
  agreement with the stated profile, not whether the listener will actually
  enjoy the songs.
- **Verification covers entities and scores, not reasoning.** The verifier
  catches a fabricated song, artist, or score. It cannot catch a narrative that
  names only real songs but describes them inaccurately — claiming a track is
  "upbeat" when its valence is 0.22, for instance. Entity grounding is a floor,
  not a guarantee of truthfulness.
- **Strict quoting can cause unnecessary fallbacks.** If the model quotes a
  phrase for emphasis despite being told not to, verification fails and the
  system falls back to the template even though nothing was fabricated. This
  trades some narrative quality for the guarantee that unverified claims are
  never shown.
