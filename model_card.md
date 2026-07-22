# 🎧 Model Card: Music Recommender Simulation

## 1. Model Name  

Give your model a short, descriptive name.  
Example: **VibeFinder 1.0**  

---

## 2. Intended Use  

Describe what your recommender is designed to do and who it is for. 

Prompts:  

- What kind of recommendations does it generate  
- What assumptions does it make about the user  
- Is this for real users or classroom exploration  

---

## 3. How the Model Works  

Explain your scoring approach in simple language.  

Prompts:  

- What features of each song are used (genre, energy, mood, etc.)  
- What user preferences are considered  
- How does the model turn those into a score  
- What changes did you make from the starter logic  

Avoid code here. Pretend you are explaining the idea to a friend who does not program.

---

## 4. Data  

Describe the dataset the model uses.  

Prompts:  

- How many songs are in the catalog  
- What genres or moods are represented  
- Did you add or remove data  
- Are there parts of musical taste missing in the dataset  

---

## 5. Strengths  

Where does your system seem to work well  

Prompts:  

- User types for which it gives reasonable results  
- Any patterns you think your scoring captures correctly  
- Cases where the recommendations matched your intuition  

---

## 6. Limitations and Bias 

Where the system struggles or behaves unfairly. 

Prompts:  

- Features it does not consider  
- Genres or moods that are underrepresented  
- Cases where the system overfits to one preference  
- Ways the scoring might unintentionally favor some users  

**Dataset size creates a filter bubble for minority genres.** Of the 18 songs in the catalog, 10 genres appear only once (rock, ambient, jazz, synthwave, indie pop, hip-hop, metal, classical, edm, and r&b each have 1–2 songs). A user who prefers any of these genres can earn at most one genre-match bonus (+2.0) before exhausting their entire genre pool, meaning songs #2–5 in their recommendations are always from unrelated genres chosen purely on energy, valence, and tempo proximity. A lofi or folk user faces the same problem in a different direction: lofi has 3 songs and folk has 2, so the top results are almost always the same 3–5 songs regardless of the user's other preferences. The system cannot surface variety it doesn't have, and with only one rock song in the catalog, a rock fan will always see "Storm Runner" at #1 with no competition — the score gap to #2 is so large that no amount of weight tuning changes the outcome. This is a dataset sparsity bias, not a scoring bias: the fix is more songs, not better math.

---

## 7. Evaluation  

### Profiles Tested

Four user profiles were tested in total: a baseline R&B/focused listener, and three adversarial profiles designed to stress-test specific gaps in the scoring logic.

- **Baseline (R&B/Focused):** A mid-energy listener who prefers R&B with a focused mood and moderate tempo. Used to confirm the system produces sensible results under normal conditions.
- **High-Energy Pop:** A listener who wants upbeat, happy pop at high energy and bright valence. Designed to test whether the genre bonus overwhelms mood filtering.
- **Chill Lofi:** A listener who wants quiet, acoustic, and heavily instrumental lofi. Designed to test whether `likes_acoustic` and `target_instrumentalness` are both respected — or only one of them.
- **Deep Intense Rock:** A listener who wants loud, dark, fast rock. Designed to test the "conflicting preferences" case where high energy and dark valence coexist, and whether the scorer can distinguish a crushing dirge from a triumphant anthem.

### What Was Surprising

The most unexpected result was how often **"Gym Hero" (pop/intense) appeared in unrelated profiles.** It showed up at #2 in both the High-Energy Pop and Deep Intense Rock lists — not because it was a good fit, but because it has the highest energy in the dataset (0.93) and benefits from either a genre match or a mood match in almost any high-energy query. This revealed that a small catalog combined with a strong flat genre bonus creates a "sticky" song that is nearly impossible to displace from the top 3 regardless of how well it actually fits the user.

A second surprise: adding the **mood mismatch penalty (-0.5)** had a much larger visible effect on songs #3–5 than on #1–2. The top songs were already scoring so high that the penalty barely changed their rank — but it reshaped the bottom of the top-5 list significantly, which is where variety and serendipity actually matter to a real user.

### System Evaluation — Adversarial Profile Results

Three adversarial profiles were run to stress-test the scoring logic. Each was designed to expose a specific gap or unexpected behavior.

**Profile 1 — High-Energy Pop**
*(Target: pop/happy, high energy, bright valence)*

```
Sunrise City (pop/happy) — Score: 5.74
  Because: Genre match: pop; Mood match: happy; Energy score: 0.92; Valence score: 0.99; Tempo score: 0.83
Gym Hero (pop/intense) — Score: 4.82
  Because: Genre match: pop; Energy score: 0.97; Valence score: 0.92; Tempo score: 0.93
Rooftop Lights (indie pop/happy) — Score: 3.75
  Because: Mood match: happy; Energy score: 0.86; Valence score: 0.96; Tempo score: 0.93
Drop Zone (edm/energetic) — Score: 2.74
  Because: Energy score: 0.96; Valence score: 0.95; Tempo score: 0.83
Neon Jungle (hip-hop/energetic) — Score: 2.61
  Because: Energy score: 0.97; Valence score: 0.87; Tempo score: 0.77
```

*Observation:* "Gym Hero" (pop/**intense**) ranks #2 despite the wrong mood. The genre bonus (+2.0) is large enough that a mood mismatch cannot push it out of the top results.

---

**Profile 2 — Chill Lofi**
*(Target: lofi/chill, low energy, high acousticness and instrumentalness)*

```
Library Rain (lofi/chill) — Score: 6.40
  Because: Genre match: lofi; Mood match: chill; Energy score: 0.97; Valence score: 0.98; Tempo score: 0.95; Acoustic preference match
Midnight Coding (lofi/chill) — Score: 6.39
  Because: Genre match: lofi; Mood match: chill; Energy score: 0.96; Valence score: 0.98; Tempo score: 0.95; Acoustic preference match
Focus Flow (lofi/focused) — Score: 5.39
  Because: Genre match: lofi; Energy score: 0.98; Valence score: 0.99; Tempo score: 0.92; Acoustic preference match
Spacewalk Thoughts (ambient/chill) — Score: 4.08
  Because: Mood match: chill; Energy score: 0.90; Valence score: 0.93; Tempo score: 0.75; Acoustic preference match
Porch Light (folk/nostalgic) — Score: 3.40
  Because: Energy score: 0.95; Valence score: 0.97; Tempo score: 0.98; Acoustic preference match
```

*Observation:* Top results are intuitive, but `target_instrumentalness: 0.90` is never scored — a song with near-zero instrumentalness would rank identically to a fully instrumental one.

---

**Profile 3 — Deep Intense Rock**
*(Target: rock/intense, very high energy, dark valence)*

```
Storm Runner (rock/intense) — Score: 5.81
  Because: Genre match: rock; Mood match: intense; Energy score: 0.99; Valence score: 0.87; Tempo score: 0.95
Gym Hero (pop/intense) — Score: 3.19
  Because: Mood match: intense; Energy score: 0.99; Valence score: 0.58; Tempo score: 0.62
Iron Curtain (metal/angry) — Score: 2.60
  Because: Energy score: 0.95; Valence score: 0.87; Tempo score: 0.78
Neon Jungle (hip-hop/energetic) — Score: 2.36
  Because: Energy score: 0.95; Valence score: 0.63; Tempo score: 0.78
Drop Zone (edm/energetic) — Score: 2.25
  Because: Energy score: 0.98; Valence score: 0.55; Tempo score: 0.72
```

*Observation:* Valence scoring meaningfully separates the results — "Iron Curtain" (genuinely dark, valence=0.22) correctly surfaces above brighter-sounding songs. Adding valence scoring directly improved this profile's output.

---

### Profile Pair Comparisons

**High-Energy Pop vs. Chill Lofi**

These two profiles sit at opposite ends of the energy spectrum and produce almost completely non-overlapping results, which is the correct behavior. The Pop profile fills its top 5 with fast, bright, high-valence songs (energy 0.75–0.93); the Lofi profile fills its top 5 with slow, acoustic, low-energy songs (energy 0.21–0.42). The one shared characteristic is that both profiles reward high valence scores — the Pop user wants happy brightness (target 0.85) and the Lofi user wants calm contentment (target 0.58) — but the energy gap is so large that no song satisfies both simultaneously. This confirms that energy is the most effective differentiator between these two listener types in the current scoring system.

**High-Energy Pop vs. Deep Intense Rock**

Both profiles want high energy (0.90 and 0.92 respectively) and fast tempo, so their lower-ranked results overlap heavily — "Gym Hero," "Drop Zone," and "Neon Jungle" appear in both top-5 lists. The key difference is valence: the Pop profile targets bright, happy valence (0.85) while the Rock profile targets dark, heavy valence (0.35). This means "Sunrise City" (valence=0.84, pop/happy) dominates the Pop list but would score poorly for Rock, while "Storm Runner" (valence=0.48, rock/intense) tops the Rock list. Without valence scoring, these two profiles would have produced nearly identical results despite describing completely different listeners. This pair demonstrates why adding valence as a scored signal was a meaningful improvement.

**Chill Lofi vs. Deep Intense Rock**

These profiles are the most different of the three pairs and produce zero overlapping songs in their top 5. The Lofi profile gravitates toward slow, acoustic, ambient tracks (Library Rain, Midnight Coding, Spacewalk Thoughts) while the Rock profile gravitates toward loud, high-tempo, low-valence tracks (Storm Runner, Iron Curtain). The contrast also reveals how the `likes_acoustic` bonus shapes the Lofi list — "Porch Light" (folk/nostalgic) reaches #5 purely because it is acoustic, slow, and melodically calm, even though its genre and mood don't match at all. The Rock profile has no equivalent wildcard bonus, so its #3–5 slots are filled by pure numeric proximity on energy and valence alone.

---

## 8. Future Work  

Ideas for how you would improve the model next.  

Prompts:  

- Additional features or preferences  
- Better ways to explain recommendations  
- Improving diversity among the top results  
- Handling more complex user tastes  

---

## 9. Personal Reflection  

A few sentences about your experience.  

Prompts:  

- What you learned about recommender systems  
- Something unexpected or interesting you discovered  
- How this changed the way you think about music recommendation apps  
