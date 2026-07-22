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
                          "acousticness", "liveness", "speechiness", "instrumentalness"):
                row[field] = float(row[field])
            songs.append(row)
    return songs

def score_song(user_prefs: Dict, song: Dict) -> Tuple[float, List[str]]:
    """Score one song against user preferences; return (total_score, reasons)."""
    score = 0.0
    reasons = []

    if song.get("genre") == user_prefs.get("favorite_genre"):
        score += 2.0
        reasons.append(f"Genre match: {song['genre']}")

    if song.get("mood") == user_prefs.get("favorite_mood"):
        score += 1.0
        reasons.append(f"Mood match: {song['mood']}")
    elif user_prefs.get("favorite_mood"):
        score -= 0.5
        reasons.append(f"Mood mismatch: {song['mood']}")

    target_energy = user_prefs.get("target_energy", 0.5)
    energy_score = 1.0 - abs(float(song.get("energy", 0.5)) - target_energy)
    score += energy_score
    reasons.append(f"Energy score: {energy_score:.2f}")

    if "target_valence" in user_prefs:
        valence_score = 1.0 - abs(float(song.get("valence", 0.5)) - user_prefs["target_valence"])
        score += valence_score
        reasons.append(f"Valence score: {valence_score:.2f}")

    if "target_tempo" in user_prefs:
        tempo_diff = abs(float(song.get("tempo_bpm", 120)) - user_prefs["target_tempo"])
        tempo_score = max(0.0, 1.0 - tempo_diff / 60.0)
        score += tempo_score
        reasons.append(f"Tempo score: {tempo_score:.2f}")

    if user_prefs.get("likes_acoustic") and float(song.get("acousticness", 0.0)) > 0.6:
        score += 0.5
        reasons.append("Acoustic preference match")

    return (score, reasons)

def recommend_songs(user_prefs: Dict, songs: List[Dict], k: int = 5) -> List[Tuple[Dict, float, str]]:
    """Score all songs, sort by score descending, and return the top-k as (song, score, explanation)."""
    scored = []
    for song in songs:
        score, reasons = score_song(user_prefs, song)
        explanation = "; ".join(reasons)
        scored.append((song, score, explanation))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]
