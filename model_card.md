# Model Card: MoodMatch 2.0

**System:** Music Recommender — Applied AI System
**Version:** 2.0 (extends MoodMatch 1.0 from Module 3)

All numbers in this document were measured by running the current system
against `data/songs.csv`. Nothing here is estimated.

---

## 1. Intended Use

MoodMatch suggests songs from a small fixed catalog based on a listener's
stated taste profile, and explains its reasoning in two forms: a per-song
score breakdown, and a natural-language playlist narrative grounded in the
songs it retrieved.

It is built for classroom exploration of explainable recommendation, not for
production use. It has no user history, no collaborative filtering, and does
not learn from feedback. It should not be used to make real recommendations
over a large library.

**What is new in 2.0:** input guardrails, a confidence score reported to the
user, RAG narrative generation with a verify-and-correct loop and an offline
fallback, a JSON audit log, and a 70-test reliability suite.

---

## 2. How It Works

### Retrieval and scoring

Every song in the catalog is scored against the user profile. The score is a
sum of matched criteria, and each contribution is recorded as a human-readable
reason:

| Signal | Contribution |
|---|---|
| Genre match | +2.0 (flat) |
| Mood match / mismatch | +1.0 / −0.5 |
| Energy proximity | `1 − abs(song − target)` |
| Valence, tempo, loudness, popularity proximity | same proximity formula |
| Acoustic preference | +0.5 when the user wants acoustic and `acousticness > 0.6` |
| Decade match | +0.75 |
| Detailed mood tag match | +0.75 |
| Explicit content, when avoided | −1.0 |

Five interchangeable strategies reweight these signals: Balanced, Genre-First,
Mood-First, Energy-Focused, Vibe-Match. An optional greedy re-rank penalizes
repeated artists (−1.0) and genres (−0.5).

Everything is rule-based arithmetic. There is no machine learning in the
ranking.

### Generation

The top-k results — and only those — are passed to the narrative generator
along with their score breakdowns. The prompt forbids inventing songs or
details not present in that retrieved evidence, and reserves double quotes for
song titles and artist names so the output can be checked mechanically.

Generated narratives are then **verified**: every quoted title and artist must
exist in the retrieved set, and every cited score must match a real one within
rounding tolerance. A failure triggers one corrective retry with the specific
violation quoted back to the model; a second failure discards the model output
in favor of the template. If no API key is configured, or the call fails or
returns empty, generation goes straight to the deterministic template.

The system always reports which generator produced the text and whether it
passed verification.

### Confidence

`confidence_score()` returns a 0–1 measure of how well the returned playlist
matched what the user asked for, averaged across the top-k:

```
per song:  0.4 x genre match  +  0.4 x mood match  +  0.2 x energy proximity
```

Reported as High (≥0.75), Medium (≥0.45), or Low.

---

## 3. Data

The catalog contains **18 songs**. Measured distribution:

| Genre | Songs | | Mood | Songs |
|---|---|---|---|---|
| lofi | 3 | | chill | 3 |
| pop, folk, r&b | 2 each | | happy, intense, nostalgic, energetic | 2 each |
| rock, ambient, jazz, synthwave, indie pop, hip-hop, metal, classical, edm | 1 each | | relaxed, moody, focused, sad, romantic, angry, peaceful | 1 each |

- 13 genres, 12 moods across 18 songs
- Only 2 artists have more than one song (Neon Echo, LoRoom — 2 each)
- Energy 0.21–0.97, tempo 58–168 BPM, valence 0.22–0.84
- Decades represented: 2000, 2010, 2020
- 3 songs flagged explicit

**The single most consequential fact about this dataset:** the largest
genre-and-mood pair is **2 songs** (lofi/chill and folk/nostalgic). Every other
combination has at most one. Section 5 shows why this caps the entire system.

---

## 4. Evaluation

Three adversarial profiles, each designed to stress a specific weakness.
Balanced strategy, k=5. Scores below are current measured output.

### Profile 1 — High-Energy Pop → **Medium confidence (51%)**

Target: pop / happy, energy 0.90, valence 0.85

| # | Song | Artist | Genre/Mood | Energy | Score |
|---|---|---|---|---|---|
| 1 | Sunrise City | Neon Echo | pop/happy | 0.82 | 9.14 |
| 2 | Gym Hero | Max Pulse | pop/intense | 0.93 | 7.69 |
| 3 | Rooftop Lights | Indigo Parade | indie pop/happy | 0.76 | 7.09 |
| 4 | Drop Zone | Flux State | edm/energetic | 0.94 | 5.64 |
| 5 | Neon Jungle | BVSSLINE | hip-hop/energetic | 0.87 | 4.82 |

**Finding:** "Gym Hero" ranks #2 with the *wrong mood*. The flat +2.0 genre
bonus outweighs the −0.5 mood mismatch penalty by 4x, so any pop song with
decent energy will beat a correct-mood song from another genre. This is the
weakness the profile was built to expose, and it reproduces exactly.

### Profile 2 — Chill Lofi → **Medium confidence (67%)**

Target: lofi / chill, energy 0.38, acoustic preferred

| # | Song | Artist | Genre/Mood | Energy | Score |
|---|---|---|---|---|---|
| 1 | Library Rain | Paper Lanterns | lofi/chill | 0.35 | 9.86 |
| 2 | Midnight Coding | LoRoom | lofi/chill | 0.42 | 9.79 |
| 3 | Focus Flow | LoRoom | lofi/focused | 0.40 | 7.51 |
| 4 | Spacewalk Thoughts | Orbit Bloom | ambient/chill | 0.28 | 5.85 |
| 5 | Porch Light | Wren & Oak | folk/nostalgic | 0.33 | 4.68 |

**Finding:** This is the system's best case and it still only reaches 67%. The
top 2 are genuinely correct. Positions 3–5 degrade in a legible way: #3 is the
right genre but wrong mood, #4 is the right mood but wrong genre, #5 matches
neither and is carried entirely by the acoustic bonus and energy proximity.

### Profile 3 — Deep Intense Rock → **Low confidence (43%)**

Target: rock / intense, energy 0.92, valence 0.35 (dark)

| # | Song | Artist | Genre/Mood | Energy | Valence | Score |
|---|---|---|---|---|---|---|
| 1 | Storm Runner | Voltline | rock/intense | 0.91 | 0.48 | 9.21 |
| 2 | Iron Curtain | Deadweight | metal/angry | 0.97 | 0.22 | 5.48 |
| 3 | Gym Hero | Max Pulse | pop/intense | 0.93 | 0.77 | 4.99 |
| 4 | Neon Jungle | BVSSLINE | hip-hop/energetic | 0.87 | 0.72 | 4.38 |
| 5 | Drop Zone | Flux State | edm/energetic | 0.94 | 0.80 | 3.58 |

**Finding:** The Low label is the system working correctly. There is exactly
one rock song in the catalog, so after position 1 there is nothing left to
serve this listener. A 3.73-point gap separates #1 from #2. Valence scoring
does its job — "Iron Curtain" (valence 0.22, genuinely dark) beats brighter
tracks — but the listener still ends up with a pop gym track at #3.

---

## 5. Reliability Experiments

### Experiment A — Do the five scoring strategies actually change anything?

Ran the Deep Intense Rock profile through all five strategies.

| Strategy | Top-5 order | Confidence |
|---|---|---|
| Balanced | Storm Runner, Iron Curtain, Gym Hero, Neon Jungle, Drop Zone | 43% |
| Genre-First | Storm Runner, Iron Curtain, Neon Jungle, Gym Hero, Drop Zone | 43% |
| Mood-First | Storm Runner, Gym Hero, Iron Curtain, Neon Jungle, Drop Zone | 43% |
| Energy-Focused | Storm Runner, Iron Curtain, Neon Jungle, Gym Hero, Drop Zone | 43% |
| Vibe-Match | Storm Runner, Iron Curtain, Gym Hero, Neon Jungle, Drop Zone | 43% |

**Result: 5 strategies produced 3 distinct orderings but exactly 1 distinct
set of songs.** Confidence was identical at 43% for all five.

This was the most uncomfortable finding in the evaluation. The strategy
feature — the largest piece of engineering carried over from Module 3 — is
close to cosmetic at this catalog size. Reweighting changes what order you see
the same five songs in; it never changes which five you get. The strategies
are not broken; there is simply nothing for them to choose between.

### Experiment B — Does diversity re-ranking do anything?

| Profile | Effect of enabling diversity |
|---|---|
| High-Energy Pop | No change |
| Chill Lofi | Swaps positions 3 and 4 (Focus Flow ↔ Spacewalk Thoughts) |
| Deep Intense Rock | No change |

**Result: no effect on 2 of 3 profiles.** The artist penalty can only fire when
one artist holds multiple top-k slots, and only two artists in the entire
catalog have more than one song. The one change observed is real — LoRoom held
both #2 and #3 for Chill Lofi, so the penalty correctly demoted the second.

### Experiment C — Why does nothing ever reach High confidence?

Swept all 13 genres × 12 moods at k=3 and k=5 — 312 combinations.

**Result: 1 of 312 combinations reached High (≥75%).** Best observed was 84%,
at lofi/chill with k=3.

Watching a single profile as k shrinks explains it:

| k | lofi/chill confidence |
|---|---|
| 1 | 99% — High |
| 2 | 99% — High |
| 3 | 86% — High |
| 5 | 67% — Medium |

The thresholds are not miscalibrated. The catalog is. Since the largest
genre+mood pair is 2 songs, any request for 5 recommendations *must* pad
positions 3–5 with partial matches, which drags the average down. At the size
the system actually runs (k=5), High confidence is unreachable for every
profile in the catalog.

This is worth stating plainly: **the confidence score is measuring a real
limitation, but the High band is dead code at k=5.** Either the catalog needs
to grow, or the bands need recalibrating for small-catalog use.

### Experiment D — Guardrails and failure handling

| Input / condition | Observed behavior |
|---|---|
| `target_energy = 99` | Rejected before scoring: "must be a number between 0.0 and 1.0, got: 99.0" |
| `target_energy = "loud"` | Rejected |
| Missing `favorite_genre` | Rejected, field named |
| Genre "polka", mood "smug" | 2 warnings, run continued, confidence 18%, warnings recorded in log |
| Non-numeric energy at prompt | Falls back to 0.5 with notice |
| Expired API key (real 401) | Caught, fell back to template, tagged `template (API error: ClientError)` |
| Simulated network failure | Caught, tagged `template (API error: ConnectionError)` |
| Model returns empty string | Treated as failure, fell back, tagged `model returned empty response` |
| No API key at all | Template generator, no crash |

No tested condition produced an unhandled exception.

### Experiment E — Does the grounding claim survive a model that ignores it?

The prompt tells the model to use only the retrieved songs. Experiment E tests
what happens when it doesn't, by driving the generator with scripted responses
containing deliberate fabrications.

| Scripted model behavior | API calls | Outcome |
|---|---|---|
| Names only retrieved songs | 1 | Accepted, tagged `verified (2 entities, 0 scores)` |
| Names "Purple Rain", then corrects on retry | 2 | Accepted, tagged `verified ..., after 1 correction` |
| Names "Bohemian Rhapsody" on both attempts | 2 | Rejected, fell back to template, violation named in tag |
| Cites a score of 9.99 that does not exist | 2 | Rejected, fell back, `unsupported scores: 9.99` |

**Result: in both failing cases the fabricated song never appeared in the text
shown to the user.** The system detects the violation, gives the model one
chance to correct itself with the specific problem quoted back, and discards
the output entirely if it fails again.

This closes the gap between asking for grounding and enforcing it. Version 1.0
had neither; the earlier draft of 2.0 asked but did not check.

---

## 6. Limitations and Bias

**Catalog sparsity is the dominant limitation, and it is not a scoring
problem.** Nine of thirteen genres have exactly one song. A listener who
prefers any of them can earn the genre bonus once, then positions 2–5 are
filled by unrelated songs chosen on numeric proximity alone. Experiments A, B,
and C above all trace back to this single cause: strategies cannot
differentiate, diversity has nothing to penalize, and confidence cannot reach
High. Adding songs would fix all three. Tuning weights would fix none of them.

**The genre bonus overwhelms mood.** +2.0 for genre against −0.5 for a mood
mismatch means genre wins by 4x. Profile 1 demonstrates this concretely: a
pop/intense track outranks an indie-pop/happy track for a listener who asked
for pop/happy.

**Mood matching is binary.** "angry" and "intense" are penalized identically
to "angry" and "chill," though the first pair describes a far more similar
listening experience. The system has no notion of adjacent moods.

**Confidence is a heuristic, not a calibrated probability.** It measures
agreement with the stated profile, not predicted enjoyment. A listener who
describes their taste inaccurately will receive a high-confidence playlist
they dislike, and the system has no way to detect that.

**Several profile fields are still never scored.** `target_danceability`,
`target_speechiness`, `target_liveness`, `target_instrumentalness`, and
`likes_instrumental` are accepted by the profile but read by no scorer. A
listener who sets `target_instrumentalness: 0.90` gets identical results to one
who ignores it. This was documented in version 1.0 and remains unfixed.

**Verification covers entities, not reasoning.** `verify_narrative()` checks
that every quoted song title, artist, and cited score exists in the retrieved
set, and unverifiable output is discarded rather than shown. What it cannot
catch is a narrative that names only real songs but characterizes them wrongly
— describing a track as "uplifting" when its valence is 0.22 would pass. Entity
grounding is a floor, not a guarantee of truthfulness.

**Strict quoting can trigger unnecessary fallbacks.** The verifier treats any
quoted string that is not a retrieved title or artist as a fabrication, which
depends on the model honoring the instruction to quote nothing else. A model
that quotes a phrase for emphasis will fail verification and be replaced by the
template even though it invented nothing. This is a deliberate bias toward the
safe generator: a needless fallback costs some narrative quality, while a
missed fabrication costs the user's trust.

---

## 7. Future Work

1. **Expand the catalog to 8–10 songs per genre.** This is the single change
   that would unlock the strategy comparison, diversity re-ranking, and the
   High confidence band simultaneously. Everything else is secondary.

2. **Verify the narrative's characterizations, not just its entities.**
   Verification now catches fabricated songs, artists, and scores
   (Experiment E). It does not check whether the adjectives match the data. A
   narrative calling a valence-0.22 track "uplifting" passes today. Comparing
   claimed descriptors against the song's actual feature values would close
   the remaining gap.

3. **Score the five ignored profile fields**, reusing the existing proximity
   formula. Small change, direct benefit to lofi, ambient, and classical
   listeners who care about instrumentalness.

4. **Add genre and mood adjacency.** Partial credit for near misses
   (rock↔metal, lofi↔ambient, intense↔angry) would make positions 3–5 far more
   defensible than the current all-or-nothing matching.

5. **Recalibrate the confidence bands for small catalogs**, or report
   confidence relative to the best achievable score for that request rather
   than an absolute scale.

---

## 8. Reflection and Ethics

### 8.1 What are the limitations and biases in this system?

Section 6 covers these in full. The short version, in order of severity:

**Catalog sparsity is the dominant bias, and it is a data problem wearing a
scoring problem's clothes.** Nine of thirteen genres have exactly one song. A
listener who prefers any of them gets one genuine match and four songs selected
on numeric proximity alone. This single fact explains three separate findings:
the scoring strategies cannot differentiate (Experiment A), diversity
re-ranking has nothing to penalize (Experiment B), and High confidence is
unreachable (Experiment C). No amount of weight tuning fixes any of them.

**The genre bonus structurally outweighs mood** by 4× (+2.0 against −0.5), so a
wrong-mood song from the right genre beats a right-mood song from a neighboring
one. Profile 1 demonstrates it: a pop/intense gym track ranks #2 for a listener
who asked for pop/happy.

**Mood is binary.** "angry" and "intense" are penalized exactly as hard as
"angry" and "chill," despite describing far more similar listening experiences.

**Confidence measures agreement, not enjoyment.** It compares results against
the *stated* profile. A listener who describes their taste inaccurately gets a
confident playlist they dislike, and the system cannot detect this.

**Verification covers entities, not characterizations.** A narrative naming
only real songs but calling a valence-0.22 track "uplifting" passes. Entity
grounding is a floor.

A bias worth naming that is *not* in the data: the weights encode one person's
assumptions about what matters in music. Deciding that genre is worth 2.0 and
mood 1.0 is a taste judgment presented as arithmetic. The explanation strings
make the arithmetic visible, but they do not make it neutral.

### 8.2 Could this system be misused, and how would I prevent it?

**The most serious risk is undisclosed ranking manipulation, and this system's
explainability makes it worse rather than better.** The scoring weights are
class attributes in `recommender.py`. Someone deploying this could add a term
favoring specific artists — a label paying for placement — and the system would
keep emitting confident, legitimate-looking reasons for every pick. A
manipulated ranking that explains itself fluently is more persuasive than a
manipulated ranking that stays silent. Explanation is a trust-building
mechanism, which makes it a trust-exploiting mechanism in the wrong hands.

What already resists this: explanation strings are built *inside* the scoring
function, at the moment each point is awarded, so the displayed reason cannot
diverge from the computation without editing both. `log_run()` records the
strategy used and the resulting picks, so patterns are auditable after the
fact.

What does not resist it, honestly: **the log records the strategy's name, not
its weights.** A modified `GenreFirstScorer` would still log as
`"genre-first"` while behaving differently. The fix is to log the actual weight
vector with each run so the audit trail captures what the system did rather
than what it called itself. I would consider this required before any real
deployment.

**Second risk: stripping the confidence signal.** A Low-confidence 43% playlist
still receives a well-written narrative. Anyone building a UI on this could
display the narrative and omit the confidence label, converting an honest
"we can't serve you well" into an unqualified recommendation. Confidence is
computed independently of the narrative and logged separately, but nothing
forces a downstream interface to show it. A stricter design would refuse to
emit a narrative at all below a confidence floor, rather than trusting the
caller to display the caveat.

**Third risk: repurposing the generator for promotional copy.** The narrative
layer is a fluent music-writing engine. This is the risk the architecture
handles best: the generator only ever receives retrieved catalog entries, and
`verify_narrative()` rejects any output naming something outside that set. It
structurally cannot write about a song that is not in the data.

**Fourth risk: homogenization at scale.** The flat genre bonus concentrates
listening toward whatever is well-represented in the catalog. Diversity
re-ranking exists as a countermeasure but is nearly inert here (Experiment B),
so it is a mitigation on paper more than in practice at this size.

**A forward-looking one:** the catalog is synthetic and no personal data is
collected, so privacy exposure is currently minimal. That changes the moment
this runs on real listeners — `logs/recommendations.log` would become a record
of individual taste profiles with timestamps. It would need retention limits
and access controls, neither of which exist today because nothing yet warrants
them.

### 8.3 What surprised me while testing reliability?

**That a working feature can accomplish almost nothing.** Experiment A was the
genuinely uncomfortable result. Five scoring strategies, real differences in
their weight vectors, careful implementation — and running the same profile
through all five produced *one distinct set of songs*, at identical 43%
confidence. Only the ordering changed. Nothing was broken; the code did exactly
what it claimed. The catalog simply never handed it a decision to make.

What makes this the most useful thing I learned is how nearly I missed it. The
obvious test is whether the strategies produce different rankings — and they
do, so that test passes and reports success. Measuring the *set* rather than
the *ordering* is what exposed it. The assertion you reach for first is often
the one that confirms what you already believe.

**That a scoring band could be unreachable.** I expected the confidence
thresholds to be roughly calibrated. Sweeping all 312 genre × mood × k
combinations returned exactly one that reached High. Watching a single profile
as k shrinks explained why — 99% at k=1, 86% at k=3, 67% at k=5 — because the
largest genre+mood pair in the catalog is two songs, so any request for five
results must pad the tail with partial matches. The thresholds were fine. The
band was dead at the size the system actually runs.

**That my documentation was confidently wrong.** The previous model card cited
Sunrise City at 5.74 against a current 9.14. Nothing had regressed; the
Challenge 1 attributes had added scoring signals and the document had never
been re-measured. I also had Porch Light's energy recorded as 0.38 when the CSV
says 0.33 — caught only because I checked my own draft against the data.

**That reading code finds almost nothing.** Every real defect surfaced on
execution: both inherited tests failing because `Song` required fields they
never passed, the `UnicodeEncodeError` that killed the Windows CLI mid-print,
the 401 from a credential that was never an API key, and the first version
printing an exception string under the heading **AI Playlist Narrative**. I had
read all of that code. None of it looked wrong.

### 8.4 How I collaborated with AI tools

I used an AI coding assistant throughout this build, in a pattern that settled
into: describe the goal, let it draft, then **run the result before believing
it**. That last step turned out to be the one that mattered. The assistant was
consistently good at producing plausible, well-organized code and consistently
willing to describe that code as working before anything had been executed.
Nearly every real defect in this project was found by running the system, not
by reading what had been written.

I also used it deliberately for adversarial thinking — asking it to design
profiles and experiments meant to *break* the recommender rather than confirm
it worked. That produced Experiments A through C, two of which found genuine
problems I would not have gone looking for.

#### An AI suggestion that was genuinely helpful

When I decided to verify the LLM narrative against the retrieved songs, my
plan was to write a checker that extracted quoted song titles and looked them
up. The assistant pointed out that this could not work on its own: given a
narrative containing `"deep focus"`, no checker can tell whether that is a
fabricated song title or just a phrase in quotes for emphasis. Any rule I wrote
would either flag ordinary prose or let real fabrications through.

The suggestion was to change the **prompt** at the same time — reserve double
quotes for song titles and artist names and nothing else — so that any other
quoted string is a fabrication by definition rather than a judgment call. That
turned an unreliable heuristic into a lookup, and it is the reason
`verify_narrative()` works at all. It reframed the problem: the check and the
prompt are one mechanism, not a checker bolted onto an existing prompt.

#### An AI suggestion that was flawed or incorrect

When adding LLM support, the assistant proposed reusing the `llm_client.py`
from my Module 4 project wholesale — carrying over both the model name
`gemma-4-31b-it` and the API key from that project's `.env`. It then wrote
setup documentation stating the system ran correctly, before any of it had been
executed.

Three things were wrong simultaneously:

1. The API key was not an API key. It was an expired OAuth access token
   (prefix `AQ.`, where real Gemini keys begin `AIza`), so every request
   returned `401 UNAUTHENTICATED` at the authentication layer.
2. `gemma-4-31b-it` is not a valid Gemini model identifier.
3. The claim that the system "runs correctly and reproducibly" was written
   before a single run had happened.

The same first pass also had `explain_playlist()` return the API error message
as its return value — meaning a failed call would have printed the string
`"Could not generate playlist narrative. (ClientError: 401...)"` to the user
directly beneath the heading **AI Playlist Narrative**, formatted exactly as
though the error text were the narrative.

All of this surfaced within seconds of actually running the code. The fix was
the offline fallback generator, the `(narrative, source)` return signature so
template output can never be mistaken for model output, and making the model
name configurable rather than hardcoded from another project.

The lesson I took from it: an AI assistant will reproduce your own prior work
faithfully, including the parts that were already broken, and will describe the
result confidently. Inherited code is not verified code. Neither is generated
code, and neither is documentation about code that has never been run.

### 8.5 What this project taught me about AI and problem-solving

The most valuable thing this version added was not the RAG narrative — it was
the confidence score, because it converted a silent failure into a visible one.
Version 1.0 presented a rock listener's five results exactly as it presented a
lofi listener's, though it could genuinely serve one and not the other. The
rankings were never wrong. The absence of any signal about ranking *quality*
was the actual defect, and it took building the measurement to see it.

The verification work changed how I read prompt instructions. This document
previously said the narrative was "grounded." It was not. It was *requested* to
be grounded, which is a different claim, and I could not tell the difference
because nothing checked. Building `verify_narrative()` meant deciding what
evidence would settle the question — and the answer required changing the
prompt too, so the check could be mechanical rather than guesswork. An
instruction you cannot verify is a hope.

The broader pattern across all of it: I was repeatedly wrong in the direction
of assuming things worked. The inherited tests, the Windows CLI, the API key,
the scoring strategies, my own model card. In every case the code looked
correct and the documentation sounded confident. What separated the working
parts from the broken ones was never how carefully they were written — it was
whether anyone had run them and checked the result against something
independent. Building the AI features was the easy half of this project.
Establishing that they actually did what I claimed was the real work.
