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

## Design Pattern (SF10)

> Document how AI helped you choose or implement a design pattern.

**Which design pattern did you use?**

<!-- e.g., Strategy, Factory, Observer, etc. -->

**How did AI help you brainstorm or implement it?**

<!-- Describe the conversation or suggestions that led to your decision -->

**How does the pattern appear in your final code?**

<!-- Point to the relevant class or method -->
