# Reading the audio features

**Keywords:** energy, valence, tempo, acousticness, features, score, explain, mood

How to interpret the numbers this system scores against.

**Energy (0–1)** — perceived intensity: loudness, density, activity. It is not
volume and not tempo. A dense quiet track can read higher than a sparse loud one.

**Valence (0–1)** — musical positivity, measured from harmonic and timbral
brightness rather than lyrics. This is the feature most likely to disagree with
a listener's judgment, because a cheerful-sounding arrangement carrying bleak
lyrics scores high.

**Tempo (BPM)** — beats per minute. Reliable for rhythmic genres, close to
meaningless for ambient or rubato performance.

**Acousticness (0–1)** — confidence the recording is acoustic rather than
electronic. High acousticness correlates with intimacy and perceived warmth.

**The pairing that carries the most information is energy against valence.**
Either alone is ambiguous; together they separate the four quadrants listeners
actually distinguish — calm-bright, calm-dark, intense-bright, intense-dark.
High energy with low valence is heavy or aggressive; high energy with high
valence is euphoric. Neither is recoverable from energy alone, which is why a
system scoring only energy cannot tell a triumphant anthem from a crushing one.
