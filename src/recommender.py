from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

@dataclass
class Song:
    """
    Represents a song and its attributes.
    Required by tests/test_recommender.py
    """
    id: int
    title: str
    artist: str
    genre: str
    mood: str
    energy: float
    tempo_bpm: float
    valence: float
    danceability: float
    acousticness: float
    liveness: float
    speechiness: float
    instrumentalness: float

@dataclass
class UserProfile:
    """
    Represents a user's taste preferences.
    Required by tests/test_recommender.py
    """
    favorite_genre: str
    favorite_mood: str
    target_energy: float
    likes_acoustic: bool

# ---------------------------------------------------------------------------
# Strategy pattern: each scorer is a class with a score() method.
# Subclasses override weight attributes only — the scoring logic lives once
# in ScoringStrategy.score(). To add a new mode, subclass and set weights.
# ---------------------------------------------------------------------------

class ScoringStrategy:
    """
    Default balanced scorer. All signals weighted at baseline.
    genre_w       — flat bonus for genre match
    mood_match_w  — flat bonus for mood match
    mood_mismatch_w — penalty when mood does not match (0 = ignore mismatches)
    energy_w      — multiplier on energy proximity (0–1 base)
    continuous_w  — multiplier on valence, tempo, loudness, popularity proximity
    """
    name = "Balanced"
    genre_w         = 2.0
    mood_match_w    = 1.0
    mood_mismatch_w = -0.5
    energy_w        = 1.0
    continuous_w    = 1.0

    def score(self, user_prefs: Dict, song: Dict) -> Tuple[float, List[str]]:
        score = 0.0
        reasons = []

        if song.get("genre") == user_prefs.get("favorite_genre"):
            score += self.genre_w
            reasons.append(f"Genre match: {song['genre']}")

        if song.get("mood") == user_prefs.get("favorite_mood"):
            score += self.mood_match_w
            reasons.append(f"Mood match: {song['mood']}")
        elif user_prefs.get("favorite_mood") and self.mood_mismatch_w != 0:
            score += self.mood_mismatch_w
            reasons.append(f"Mood mismatch: {song['mood']}")

        target_energy = user_prefs.get("target_energy", 0.5)
        energy_score = self.energy_w * (1.0 - abs(float(song.get("energy", 0.5)) - target_energy))
        score += energy_score
        reasons.append(f"Energy score: {energy_score:.2f}")

        if "target_valence" in user_prefs:
            vs = self.continuous_w * (1.0 - abs(float(song.get("valence", 0.5)) - user_prefs["target_valence"]))
            score += vs
            reasons.append(f"Valence score: {vs:.2f}")

        if "target_tempo" in user_prefs:
            td = abs(float(song.get("tempo_bpm", 120)) - user_prefs["target_tempo"])
            ts = self.continuous_w * max(0.0, 1.0 - td / 60.0)
            score += ts
            reasons.append(f"Tempo score: {ts:.2f}")

        if user_prefs.get("likes_acoustic") and float(song.get("acousticness", 0.0)) > 0.6:
            score += 0.5
            reasons.append("Acoustic preference match")

        if "target_popularity" in user_prefs:
            ps = self.continuous_w * (1.0 - abs(int(song.get("popularity", 50)) - user_prefs["target_popularity"]) / 100)
            score += ps
            reasons.append(f"Popularity score: {ps:.2f}")

        if "preferred_decade" in user_prefs:
            if int(song.get("release_decade", 2020)) == user_prefs["preferred_decade"]:
                score += 0.75
                reasons.append(f"Decade match: {song['release_decade']}s")

        if user_prefs.get("preferred_mood_tag") and song.get("detailed_mood_tag") == user_prefs["preferred_mood_tag"]:
            score += 0.75
            reasons.append(f"Detailed mood match: {song['detailed_mood_tag']}")

        if user_prefs.get("avoid_explicit") and int(song.get("explicit", 0)) == 1:
            score -= 1.0
            reasons.append("Explicit content penalty")

        if "target_loudness" in user_prefs:
            ls = self.continuous_w * (1.0 - abs(float(song.get("loudness", 0.5)) - user_prefs["target_loudness"]))
            score += ls
            reasons.append(f"Loudness score: {ls:.2f}")

        return (score, reasons)


class GenreFirstScorer(ScoringStrategy):
    """Genre match is worth 4x. Mood mismatches are ignored. Continuous signals halved.
    Best for listeners who stay strictly within their genre and treat everything else as noise."""
    name = "Genre-First"
    genre_w         = 4.0
    mood_match_w    = 0.5
    mood_mismatch_w = 0.0
    energy_w        = 0.5
    continuous_w    = 0.5


class MoodFirstScorer(ScoringStrategy):
    """Mood match is worth 3x with a strong mismatch penalty. Genre is a secondary tiebreaker.
    Best for emotionally-driven listeners who want a specific feeling regardless of genre."""
    name = "Mood-First"
    genre_w         = 1.0
    mood_match_w    = 3.0
    mood_mismatch_w = -1.5
    energy_w        = 0.5
    continuous_w    = 0.5


class EnergyFocusedScorer(ScoringStrategy):
    """Energy proximity is the dominant signal at 3x. Genre and mood are minor bonuses.
    Best for workout or focus sessions where the physical feel of the music matters most."""
    name = "Energy-Focused"
    genre_w         = 0.5
    mood_match_w    = 0.5
    mood_mismatch_w = 0.0
    energy_w        = 3.0
    continuous_w    = 0.5


class VibeMatchScorer(ScoringStrategy):
    """All continuous features (energy, valence, tempo, loudness, popularity) at 2x.
    Genre and mood are soft tiebreakers only. Best for cross-genre discovery."""
    name = "Vibe-Match"
    genre_w         = 1.0
    mood_match_w    = 1.0
    mood_mismatch_w = -0.25
    energy_w        = 2.0
    continuous_w    = 2.0


# Registry — add new strategies here to make them available in main.py
SCORING_MODES: Dict[str, ScoringStrategy] = {
    "balanced":      ScoringStrategy(),
    "genre-first":   GenreFirstScorer(),
    "mood-first":    MoodFirstScorer(),
    "energy-focused": EnergyFocusedScorer(),
    "vibe-match":    VibeMatchScorer(),
}


class Recommender:
    """
    OOP implementation of the recommendation logic.
    Required by tests/test_recommender.py
    """
    def __init__(self, songs: List[Song]):
        self.songs = songs

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        user_prefs = {
            "favorite_genre": user.favorite_genre,
            "favorite_mood": user.favorite_mood,
            "target_energy": user.target_energy,
            "likes_acoustic": user.likes_acoustic,
        }
        song_dicts = [s.__dict__ for s in self.songs]
        results = recommend_songs(user_prefs, song_dicts, k)
        result_ids = [r[0]["id"] for r in results]
        song_by_id = {s.id: s for s in self.songs}
        return [song_by_id[sid] for sid in result_ids if sid in song_by_id]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        user_prefs = {
            "favorite_genre": user.favorite_genre,
            "favorite_mood": user.favorite_mood,
            "target_energy": user.target_energy,
            "likes_acoustic": user.likes_acoustic,
        }
        _, reasons = score_song(user_prefs, song.__dict__)
        return "; ".join(reasons) if reasons else "No matching criteria"

def load_songs(csv_path: str) -> List[Dict]:
    """Read songs.csv and return a list of dicts with numeric fields cast to float/int."""
    import csv
    print(f"Loading songs from {csv_path}...")
    songs = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["id"] = int(row["id"])
            for field in ("energy", "tempo_bpm", "valence", "danceability",
                          "acousticness", "liveness", "speechiness", "instrumentalness",
                          "loudness"):
                row[field] = float(row[field])
            row["popularity"] = int(row["popularity"])
            row["release_decade"] = int(row["release_decade"])
            row["explicit"] = int(row["explicit"])
            songs.append(row)
    return songs

def score_song(user_prefs: Dict, song: Dict) -> Tuple[float, List[str]]:
    """Score one song using the default Balanced strategy. Kept for backward compatibility."""
    return ScoringStrategy().score(user_prefs, song)

def recommend_songs(user_prefs: Dict, songs: List[Dict], k: int = 5,
                    strategy: Optional[ScoringStrategy] = None) -> List[Tuple[Dict, float, str]]:
    """Score all songs with the given strategy (default: Balanced), return top-k."""
    if strategy is None:
        strategy = ScoringStrategy()
    scored = []
    for song in songs:
        score, reasons = strategy.score(user_prefs, song)
        explanation = "; ".join(reasons)
        scored.append((song, score, explanation))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]
