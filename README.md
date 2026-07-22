# 🎵 Music Recommender Simulation

## Project Summary

In this project you will build and explain a small music recommender system.

Your goal is to:

- Represent songs and a user "taste profile" as data
- Design a scoring rule that turns that data into recommendations
- Evaluate what your system gets right and wrong
- Reflect on how this mirrors real world AI recommenders

Replace this paragraph with your own summary of what your version does.

---

## How The System Works

Real-world recommenders like Spotify's Discover Weekly use a combination of collaborative filtering (finding users with similar listening histories) and content-based filtering (matching audio features of songs you've liked to new songs). At scale they process millions of implicit signals — skips, replays, playlist adds — and use embedding models to place songs and users in a shared vector space. This simulation prioritizes the content-based half of that picture: it uses explicit audio features and a hand-crafted scoring formula to match songs to a stated user preference, with no historical play data. The tradeoff is transparency — every recommendation score can be explained in plain English — at the cost of personalization depth a real system would achieve over time.

**`Song` features used:**
- `genre` (categorical) — musical style; lofi, pop, rock, ambient, jazz, synthwave, indie pop
- `mood` (categorical) — intended emotional tone; chill, happy, intense, focused, relaxed, moody
- `energy` (float 0–1) — overall intensity of the track
- `valence` (float 0–1) — musical positiveness; high = uplifting, low = dark/melancholic
- `tempo_bpm` (float) — speed in beats per minute, normalized for scoring
- `acousticness` (float 0–1) — how organic vs. electronic the track sounds
- `danceability` (float 0–1) — rhythmic drive; included but low-weighted due to correlation with energy

**`UserProfile` fields used:**
- `favorite_genre` — secondary categorical match signal
- `favorite_mood` — highest-weighted match signal; captures listening intent
- `target_energy` — numeric target; scored by proximity, not magnitude
- `likes_acoustic` — boolean; rewards high `acousticness` when true

**Algorithm Recipe — Finalized Scoring Logic:**

Each song is scored independently against the user profile. The score is the sum of all matched criteria; songs are ranked highest-to-lowest and the top `k` are returned.

| Criterion | Rule | Points |
|---|---|---|
| Genre match | `song.genre == favorite_genre` | **+2.0** |
| Mood match | `song.mood == favorite_mood` | **+1.0** |
| Energy similarity | `1.0 - abs(song.energy - target_energy)` | **0.0 – 1.0** (continuous) |
| Acoustic preference | `likes_acoustic == True` and `song.acousticness > 0.6` | **+0.5** |

**Maximum possible score: 4.5** (genre + mood + perfect energy + acoustic bonus)

**Why this weighting:** Genre is the hardest structural boundary — most users won't accept a metal song when they asked for lofi, regardless of mood. Mood is a softer preference that matters within a genre. Energy uses smooth partial credit rather than all-or-nothing, so a song with energy 0.45 still scores well against a 0.40 target. The acoustic bonus is small but meaningful for users who explicitly flag it.

**Known biases and limitations:**

- **Genre over-dominance:** At +2.0 points, a genre match is worth twice a perfect mood match. A genuinely great song in a different genre but identical mood and energy will almost never beat a mediocre genre-match. This could cause the system to recommend weak lofi tracks over excellent adjacent-genre tracks the user might actually love.
- **Catalog sparsity amplifies genre bias:** With only 18 songs, some genres have 1–2 entries. If a user's favorite genre has few options, the top-k results will include lower-quality same-genre songs ranked above clearly better songs in other genres.
- **No history or feedback loop:** The same profile always produces the same results regardless of what the user has already heard or skipped. Real systems decay repeated recommendations.
- **Acoustic threshold is hard-edged:** The `acousticness > 0.6` cutoff means a song at 0.59 gets zero bonus while a song at 0.61 gets +0.5. A continuous formula would be more fair.

**How recommendations are chosen:**
- Every song in the catalog is scored by `score_song(user_prefs, song)`
- All `(song, score, explanation)` tuples are collected, sorted descending by score, and the top `k` are returned (default `k = 5`)

---

## Getting Started

### Setup

1. Create a virtual environment (optional but recommended):

   ```bash
   python -m venv .venv
   source .venv/bin/activate      # Mac or Linux
   .venv\Scripts\activate         # Windows

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Run the app:

```bash
python -m src.main
```

### Running Tests

Run the starter tests with:

```bash
pytest
```

You can add more tests in `tests/test_recommender.py`.

---

## Sample Recommendation Output

Paste a sample of your recommender's output here as a text block so a reader can see what it produces:

```
# e.g.:
# User profile: genre=indie, mood=chill, energy=low
# Recommendations:
#   1. ...
#   2. ...
#   3. ...
```

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or demo video link here -->

---

## Experiments You Tried

Use this section to document the experiments you ran. For example:

- What happened when you changed the weight on genre from 2.0 to 0.5
- What happened when you added tempo or valence to the score
- How did your system behave for different types of users

---

## Limitations and Risks

Summarize some limitations of your recommender.

Examples:

- It only works on a tiny catalog
- It does not understand lyrics or language
- It might over favor one genre or mood

You will go deeper on this in your model card.

---

## Reflection

Read and complete `model_card.md`:

[**Model Card**](model_card.md)

Write 1 to 2 paragraphs here about what you learned:

- about how recommenders turn data into predictions
- about where bias or unfairness could show up in systems like this



