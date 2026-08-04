# AI Interactions Log

> **Stretch features only.** Only fill in the sections that apply to stretch features you attempted. If you did not attempt a stretch feature, leave its section blank or delete it. This file is not required for the core project.

---

## Agentic Workflow (SF8) — Challenge 1: Advanced Song Features

**What task did you give the agent?**

Add 5 or more complex attributes to the song dataset that are not in the baseline, update `data/songs.csv` with values for all 18 songs, update `src/recommender.py` to score the new attributes, and update the adversarial profiles in `src/main.py` to exercise the new fields.

---

**Prompts used:**

> "Add 5 new song attributes to songs.csv and score them in recommender.py. The attributes should go beyond the baseline features and add meaningful signal for different listener types. Verify the math for each new scoring formula is valid before adding it."

Follow-up after seeing the plan:

> "Go ahead and implement all of it — update the CSV with values for all 18 songs, add the load_songs casting, add all five scoring blocks to score_song, and update the adversarial profiles in main.py to include the new fields."

---

**What the agent generated or changed:**

- `data/songs.csv` — added 5 new columns to all 18 rows:
  - `popularity` (int, 0–100): estimated listener popularity per song, assigned based on genre and energy (e.g., Gym Hero=85, Porch Light=40)
  - `release_decade` (int): decade of release — 1990, 2000, 2010, or 2020, assigned by stylistic era
  - `detailed_mood_tag` (string): finer-grained mood label beyond the existing `mood` field — values include euphoric, dreamy, aggressive, melancholic, ethereal, nostalgic, sensual, peaceful, focused
  - `explicit` (int, 0 or 1): whether the song has explicit content — assigned 1 to 3AM Spiral, Neon Jungle, and Iron Curtain
  - `loudness` (float, 0.0–1.0 normalized): perceived loudness level, correlated with energy but independently assigned

- `src/recommender.py` — updated `load_songs` to cast `popularity` as int, `release_decade` as int, `explicit` as int, and `loudness` as float. Added five new scoring blocks to `score_song`:
  - **Popularity proximity**: `1.0 - abs(song_popularity - target_popularity) / 100` — scaled to 0–1
  - **Decade match**: flat +0.75 bonus for exact decade match
  - **Detailed mood tag match**: flat +0.75 bonus for exact tag match
  - **Explicit penalty**: -1.0 if `avoid_explicit=True` and song is explicit
  - **Loudness proximity**: `1.0 - abs(song_loudness - target_loudness)` — same formula as energy

- `src/main.py` — added the five new fields to all three adversarial profiles so the new scoring signals are exercised on every run.

---

**What was verified manually:**

- **Popularity formula math:** The agent divided by 100 to normalize to 0–1 scale. Verified: `abs(78 - 80) / 100 = 0.02`, so `pop_score = 0.98` for Sunrise City against `target_popularity=80`. Confirmed correct.

- **Loudness formula:** Uses the same `1.0 - abs(a - b)` formula as energy and valence. Verified: both inputs are already in 0–1 range so the result is guaranteed to be in [0, 1]. No clamping needed.

- **Tempo formula uses `max(0.0, ...)` but popularity and loudness don't:** This is intentional — tempo differences can exceed 60 BPM (the normalization window), producing negative values without the clamp. Popularity differences max out at 100 (the denominator), so the result is always ≥ 0. Loudness is bounded 0–1, so the abs difference is also always ≤ 1. Both are safe without clamping.

- **Explicit penalty direction:** Confirmed `-1.0` is applied only when `avoid_explicit=True` AND the song is explicit — not when the user has no preference. The Chill Lofi profile (which sets `avoid_explicit=True`) correctly penalizes the three explicit songs. Verified by checking the terminal output — none of the explicit songs appear in Chill Lofi's top 5.

- **Decade values in CSV:** Spot-checked that all 18 songs have a valid decade value (1990, 2000, 2010, or 2020) and that the decade comparisons in scoring use `int()` casting consistently in both `load_songs` and `score_song`.

- **Deep Intense Rock ranking improvement:** "Iron Curtain" moved from #3 to #2 (score 5.48 vs. Gym Hero's 4.99) after the new attributes were added. This is correct — Iron Curtain matches the preferred decade (2010s) and detailed mood tag (aggressive) for that profile, while Gym Hero does not. The new signals are doing meaningful work.

---

## Agentic Workflow (SF8) — Challenge 3: Diversity and Fairness Logic

**What task did you give the agent?**

Add a diversity penalty that prevents the recommender from surfacing too many songs from the same artist or genre in the top results.

---

**Prompt used:**

> "In `recommender.py`, after all songs are scored and sorted, I want a `diversify()` function that greedily re-ranks the results to prevent the same artist or genre from dominating the top-k. The rule: each time a song is selected, any remaining candidate that shares the same artist gets a `-1.0` penalty applied to its score, and any candidate that shares the same genre gets a `-0.5` penalty. The function should take the full sorted scored list and return k songs by greedily picking the highest adjusted score at each step. The penalties should be configurable parameters. Verify the greedy selection never drops below 0 candidates and that penalties stack correctly when a song matches both artist and genre of already-selected songs."

---

**What the agent generated or changed:**

- `src/recommender.py` — added `diversify(scored, k, artist_penalty, genre_penalty)`. Uses a greedy loop: at each step, applies accumulated penalties to all remaining candidates (using `list.count()` on `selected_artists` and `selected_genres`), picks the highest adjusted score, then appends the original (un-penalized) score to the output so callers see real scores. Updated `recommend_songs` to accept `diversity=False`, `artist_penalty=1.0`, and `genre_penalty=0.5` parameters.
- `src/main.py` — added `run_diversity_comparison()` helper and calls it for all three adversarial profiles, printing without vs. with penalty side-by-side.

---

**What was verified manually:**

- **Penalties stack correctly:** If a song shares the artist of one selected song (+1.0 penalty) AND the genre of another selected song (+0.5 penalty), it takes a combined -1.5 hit. Verified by tracing the Chill Lofi case: after Library Rain (Paper Lanterns/lofi) and Midnight Coding (LoRoom/lofi) are selected, Focus Flow (LoRoom/lofi) takes -1.0 (artist=LoRoom, already seen once) plus -1.0 (genre=lofi, already seen twice, each at -0.5), for a total of -1.5. Adjusted score: 7.51 - 1.5 = 6.01. Spacewalk Thoughts (Orbit Bloom/ambient) takes no penalty at that point, so its adjusted 5.85 loses to Focus Flow's 6.01 — Focus Flow still comes third, but Spacewalk Thoughts advances to #3 before Focus Flow in the greedy pass because genre lofi has a -0.5 applied at step 3 that puts Focus Flow behind.

- **No candidates ever exhausted early:** With 18 songs and k=5, the remaining list always has at least 13 candidates at the first pick, shrinking by 1 each step. The `while remaining and len(selected) < k` guard handles edge cases if the catalog were smaller than k.

- **Original scores preserved in output:** The function pops candidates by adjusted score for ordering, but appends `chosen_score` (the original) to `selected` — verified by checking that the printed scores in the diversity comparison match the non-diversity run exactly (same song, same score, just reordered).

- **Observable effect in output:** Chill Lofi is the clearest case — Focus Flow (LoRoom/lofi) drops from #3 to #4 because Midnight Coding (LoRoom) is already at #2, triggering the artist penalty. In the current 18-song catalog most artists appear only once, so the genre penalty (-0.5) does more visible work than the artist penalty for most profiles.

---

## Agentic Workflow (SF8) — Challenge 2: Multiple Scoring Modes

**What task did you give the agent?**

Design and implement two or more ranking strategies so a user can switch scoring modes in `main.py`. The design should keep the code modular so adding a new strategy in the future doesn't require touching the existing scoring logic.

---

**Prompts used:**

> "Look at recommender.py. I want to add multiple scoring modes — like Genre-First, Mood-First, and Energy-Focused — so a user can switch between them. Suggest a design pattern that keeps this modular and doesn't duplicate the scoring logic. Verify the math stays valid across modes."

The agent proposed the **Strategy pattern**: a base class `ScoringStrategy` with a `score()` method, where subclasses override weight attributes but inherit the full scoring logic. This avoids repeating the formula for energy proximity, valence proximity, etc. in every mode — each subclass just sets different multipliers.

---

**Design pattern chosen: Strategy**

Each scoring mode is a class that inherits from `ScoringStrategy`. The base class holds the complete `score()` method. Subclasses declare five weight attributes and override nothing else:

```
ScoringStrategy (base)
├── genre_w         = 2.0   # flat bonus for genre match
├── mood_match_w    = 1.0   # flat bonus for mood match
├── mood_mismatch_w = -0.5  # penalty for mood mismatch (0 = ignore)
├── energy_w        = 1.0   # multiplier on energy proximity
└── continuous_w    = 1.0   # multiplier on valence/tempo/loudness/popularity

GenreFirstScorer   → genre_w=4.0, continuous_w=0.5, mood_mismatch_w=0.0
MoodFirstScorer    → mood_match_w=3.0, mood_mismatch_w=-1.5, genre_w=1.0
EnergyFocusedScorer → energy_w=3.0, genre_w=0.5, mood_mismatch_w=0.0
VibeMatchScorer    → energy_w=2.0, continuous_w=2.0, genre_w=1.0
```

A `SCORING_MODES` dict maps string keys (`"genre-first"`, `"mood-first"`, etc.) to instances, so `main.py` can select a mode by name. `recommend_songs()` accepts an optional `strategy` parameter; it defaults to `ScoringStrategy()` for full backward compatibility.

---

**What the agent generated or changed:**

- `src/recommender.py` — replaced the standalone `score_song` logic with `ScoringStrategy.score()`. Added `GenreFirstScorer`, `MoodFirstScorer`, `EnergyFocusedScorer`, `VibeMatchScorer` as subclasses. Added `SCORING_MODES` registry dict. Updated `recommend_songs` signature to accept `strategy`. Kept `score_song` as a one-liner that delegates to `ScoringStrategy()` for test compatibility.
- `src/main.py` — added a scoring-mode comparison loop that runs the Deep Intense Rock profile through all five modes and prints the top-5 results with the active weights.

---

**What was verified manually:**

- **Math validity across modes:** Every proximity score is computed as `weight * (1.0 - abs(a - b))`. Since `abs(a - b)` is in [0, 1] for all normalized features, the base value before the multiplier is in [0, 1]. Multiplying by any positive weight keeps the result non-negative. The only way to get a negative score is the mood mismatch penalty and the explicit penalty — both intentional.

- **`mood_mismatch_w = 0.0` in Genre-First and Energy-Focused:** Confirmed this correctly skips the penalty branch — the `elif` condition checks `self.mood_mismatch_w != 0` before applying, so mismatches are silently ignored in these modes as intended.

- **`score_song` backward compatibility:** The existing `Recommender.explain_recommendation` calls `score_song`. After the refactor, `score_song` delegates to `ScoringStrategy().score()` — verified the output is identical to the original by running the baseline profile and checking that "Velvet Static" still tops the list with the same explanation string format.

- **Mode comparison output (Deep Intense Rock):**
  - *Genre-First*: Storm Runner dominates even more; Gym Hero drops to #4 because without mood mismatch penalty and with halved continuous weights, genre is the only real differentiator
  - *Mood-First*: Gym Hero rises to #2 (it matches `intense` mood); Iron Curtain drops to #3 despite being a better genre/vibe fit, because `angry` ≠ `intense`
  - *Energy-Focused*: Iron Curtain jumps to #2 (energy=0.97 is almost perfect); rankings tighten because genre no longer dominates
  - *Vibe-Match*: Scores inflate due to 2x multipliers but relative order makes intuitive sense — Storm Runner still #1, continuous-feature similarity drives the rest

---

## Design Pattern (SF10)

**Which design pattern did you use?**

Strategy pattern, for the five scoring modes.

**How did AI help you brainstorm or implement it?**

The original scoring function had grown a long chain of conditionals, and the
plan was to add scoring modes by copying it and changing the constants. The
assistant pointed out that the *logic* was identical across modes and only the
weights differed, so subclassing with overridden weight attributes would keep
the scoring logic in exactly one place. That avoided five near-duplicate
copies of `score_song` that would have drifted apart with every later change.

**How does the pattern appear in your final code?**

`ScoringStrategy` in `src/recommender.py` holds the scoring logic in
`score()`. Each subclass — `GenreFirstScorer`, `MoodFirstScorer`,
`EnergyFocusedScorer`, `VibeMatchScorer` — overrides only weight attributes
and inherits the logic. The `SCORING_MODES` registry maps mode names to
instances so the CLI can offer them without knowing the class names.

> **A caveat found later.** Experiment A in `model_card.md` measured whether
> the strategies actually change results, and found that all five produce the
> same *set* of top-5 songs at this catalog size — only the ordering differs.
> The pattern is implemented correctly; the catalog is too small to give it
> anything to decide. Documented rather than removed, because the finding is
> more useful than the feature.

---

# Final Project — Applied AI System

The sections above cover the Module 3 stretch features. The sections below
cover extending that prototype into a full AI system.

---

## RAG Narrative Generation and Graceful Degradation

**What task did you give the agent?**

Add LLM-generated playlist narratives grounded in the retrieved songs, using
the Gemini client pattern from my Module 4 DocuBot project.

**Prompts used:**

> "Add a RAG layer that feeds the top-k scored songs into Gemini and generates
> a natural-language explanation of the playlist. Reuse the llm_client pattern
> from Module 4."

After the first end-to-end run failed:

> "Test that Gemini key."

**What the agent generated or changed:**

- `src/llm_client.py` — `GeminiClient.explain_playlist()` builds a prompt
  containing only the retrieved songs and their score breakdowns, with rules
  forbidding invented songs.
- `build_fallback_narrative()` — a deterministic generator that composes a
  narrative from the same retrieved evidence with no API call.
- Both generators return `(text, source)` so the caller can always report
  which one produced the output.
- `requirements.txt` — added `google-genai` and `python-dotenv`.
- `.gitignore` — added `.env` and `logs/`.

**What was verified manually:**

- **The inherited API key does not work.** The first live call returned
  `401 UNAUTHENTICATED`. Tested twice — once listing models, once generating
  content — to confirm it was an authentication failure rather than a bad
  model name or a quota limit. Both failed identically.

- **My explanation for *why* it failed was wrong, and I published it.** From the
  `AQ.` prefix I concluded the value was an expired OAuth token rather than an
  API key, on the reasoning that real Gemini keys begin `AIza`. That is false —
  `AQ.` is AI Studio's current API key format. Confirmed later when a different
  `AQ.` key authenticated and listed 58 models, and definitively when the AI
  Studio key page showed an `AQ.` value labeled **API Key**. The key was simply
  dead, probably revoked. Corrected across all three documents.

- **`gemma-4-31b-it` was a valid model all along.** I claimed it was not a real
  identifier, having been unable to check it while authentication was failing.
  Once a working key was available, listing the models showed both
  `gemma-4-31b-it` and `gemma-4-26b-a4b-it`. The Module 4 model name was never
  the problem. The default was still changed to `gemini-2.0-flash` and made
  overridable via `GEMINI_MODEL`, which is the right design regardless.

- **Free-tier quota is per model, per day.** With a working key,
  `gemini-2.0-flash` returned `429` with quota id
  `GenerateRequestsPerDayPerProjectPerModel-FreeTier`. Waiting through two
  25-second backoffs did not clear it, because the exhausted bucket was daily
  rather than per-minute. Switching `GEMINI_MODEL` to `gemma-4-26b-a4b-it`
  worked immediately — separate model, separate daily bucket.

- **The first implementation would have shown users an error as if it were a
  narrative.** `explain_playlist()` originally returned the exception string
  as its return value, so a failed call printed
  `"Could not generate playlist narrative. (ClientError: 401...)"` directly
  beneath the heading **AI Playlist Narrative**. Caught by running mode 2 and
  reading the output. Fixed by falling back to the template generator and
  returning a source tag instead.

- **Fallback verified end-to-end.** Ran mode 2 with the dead key. The system
  caught the 401, produced a template narrative naming real songs, and
  labeled it `[generated by: template (API error: ClientError)]`.

---

## Input Guardrails and Confidence Scoring

**What task did you give the agent?**

Add input validation and a measure of how well the returned playlist actually
matched what the user asked for.

**Prompts used:**

> "Add guardrails that validate user input and a confidence score so the user
> knows how good the match actually is. Hard errors should stop the run; soft
> problems like an unknown genre should warn and continue."

**What the agent generated or changed:**

- `src/guardrails.py` — `validate_user_prefs()` returns
  `(is_valid, warnings)`. Missing required fields and out-of-range energy are
  rejected; unknown genres, unknown moods, and out-of-range tempo warn and
  continue.
- `confidence_score()` — 0.4 genre + 0.4 mood + 0.2 energy proximity,
  averaged over the top-k.
- `confidence_label()` — High ≥0.75, Medium ≥0.45, Low below.
- `src/logger.py` — appends one JSON object per run to
  `logs/recommendations.log`.

**What was verified manually:**

- **Rejection path:** entered `99` for energy. Run stopped with
  `"target_energy must be a number between 0.0 and 1.0, got: 99.0"`.

- **Warning path:** entered genre `polka`, mood `smug`. Both warned, the run
  continued, confidence came back 18%, and both warnings appeared in the log
  entry. Confirmed the warning path does not silently discard the problem.

- **Confidence tracks reality:** compared lofi/chill (Medium 67%) against
  rock/intense (Low 43%). The catalog has three lofi songs and one rock song,
  so the ordering is correct.

- **Deprecation fixed:** `datetime.utcnow()` is deprecated as of Python 3.12.
  Changed to `datetime.now(timezone.utc)` and added a test asserting the
  logged timestamp is timezone-aware.

- **Log format:** parsed `logs/recommendations.log` back with `json.loads`
  line by line to confirm every entry is valid JSON and that repeated runs
  append rather than overwrite.

---

## Narrative Verification and Self-Correction Loop

**What task did you give the agent?**

The prompt tells the model not to invent songs, but nothing checks whether it
complied. Build the check.

**Prompts used:**

> "The narrative is grounded by prompt but not verified by code. A
> hallucinated song would reach the user unflagged. Build the verification."

**What the agent generated or changed:**

- `src/verifier.py` — `verify_narrative()` checks that every double-quoted
  span is the title or artist of a retrieved song, and that every number
  presented as a score matches a real one within 0.06.
- `src/llm_client.py` — `explain_playlist()` became a loop: generate, verify,
  retry once with the violation quoted back, then fall back to the template if
  the retry also fails.
- The prompt gained a rule reserving double quotes for titles and artists.

**What was verified manually:**

- **The prompt had to change for the check to work.** My initial plan was to
  extract quoted titles and look them up. The assistant pointed out this
  cannot work alone: given `"deep focus"` in a narrative, nothing distinguishes
  a fabricated song title from a phrase quoted for emphasis. Reserving quotes
  for titles in the prompt is what makes any other quoted string a fabrication
  by definition. Verified the reasoning by writing
  `test_apostrophes_are_not_treated_as_quotes` — single quotes had to be
  excluded entirely or every apostrophe in ordinary prose would fail.

- **All four paths driven with scripted model responses:**

  | Scripted behavior | Calls | Result |
  |---|---|---|
  | Names only retrieved songs | 1 | Accepted, `verified (2 entities, 0 scores)` |
  | Names "Purple Rain", then corrects | 2 | Accepted, `after 1 correction` |
  | Names "Bohemian Rhapsody" twice | 2 | Rejected, template, violation named |
  | Cites a fabricated score of 9.99 | 2 | Rejected, `unsupported scores: 9.99` |

  Confirmed by inspection that the fabricated titles are absent from the
  returned text in both failing cases.

- **Score tolerance checked in both directions:** `4.5` against a real `4.47`
  passes (a model rounding is not a fabrication); `9.99` fails. Verified the
  score regex does not catch unrelated decimals — `"average energy of 0.37"`
  produces no score claims.

- **Retry prompt names the specific violation.** Asserted that the second
  prompt sent to the model contains the string `Purple Rain`, so the model is
  told what was wrong rather than just being asked again.

---

## Reliability Experiments

**What task did you give the agent?**

Design experiments that try to break the recommender rather than confirm it
works, and report what they actually find.

**Prompts used:**

> "The model card documents scores from before the Challenge 1 attributes were
> added, so every number is stale. Regenerate it against actual current output."

**What the agent generated or changed:**

- A throwaway analysis script that ran every adversarial profile, swept all
  genre/mood combinations, and compared scoring strategies and diversity
  settings.
- `model_card.md` — rewritten around five experiments with measured results.

**What was verified manually:**

- **Every number was regenerated by running the system.** The previous model
  card listed Sunrise City at 5.74; current output is 9.14, because the
  Challenge 1 attributes each add points. Confirmed the discrepancy was stale
  documentation rather than a regression by checking that the extra signals
  in the explanation string account for the difference.

- **One error caught in my own draft.** I had written Porch Light's energy as
  0.38 in a results table. Checked against the CSV: it is 0.33. Corrected
  before committing.

- **The scoring strategies barely matter.** Ran Deep Intense Rock through all
  five modes and compared the *sets* of returned songs, not just the ordering.
  Result: three distinct orderings, one distinct set, identical 43% confidence
  across all five. Checking orderings alone would have looked like success.

- **Diversity re-ranking is nearly inert.** No change for two of three
  profiles. Traced the cause: only two artists in the catalog have more than
  one song, so the artist penalty almost never fires.

- **"High" confidence is unreachable.** Swept 13 genres × 12 moods at k=3 and
  k=5 — 312 combinations, of which exactly 1 reached High. Confirmed the cause
  by watching one profile as k shrinks: lofi/chill scores 99% at k=1, 86% at
  k=3, and 67% at k=5. The largest genre+mood pair in the catalog is 2 songs,
  so k=5 must pad with partial matches.

---

## Bugs Found by Running the System

Recorded separately because every one of these was invisible from reading the
code and appeared immediately on execution.

| Bug | How it surfaced | Fix |
|---|---|---|
| Both inherited tests failing | Ran `pytest` for the first time | `Song` required three fields the tests never supplied; gave optional audio features neutral defaults |
| `UnicodeEncodeError` crash on Windows | Ran mode 3; it died mid-print | `cp1252` cannot encode `─` or `█`; forced stdout to UTF-8 and used ASCII for the bar chart |
| API key returns 401 | First live Gemini call | Key was dead; built the offline fallback |
| Wrong diagnosis of that 401 published as fact | AI Studio key page showed an `AQ.` key labeled **API Key** | `AQ.` is a real key format; corrected README, model card, and this log |
| Error string shown as narrative | Read mode 2 output | Returned `(text, source)` and fell back to the template instead |
| `datetime.utcnow()` deprecated | Python 3.14 deprecation | Switched to `datetime.now(timezone.utc)` |
