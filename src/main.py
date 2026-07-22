"""
Command line runner for the Music Recommender Simulation.

This file helps you quickly run and test your recommender.

You will implement the functions in recommender.py:
- load_songs
- score_song
- recommend_songs
"""

from src.recommender import load_songs, recommend_songs


# ---------------------------------------------------------------------------
# Adversarial / edge-case profiles for System Evaluation
#
# Each profile is designed to stress-test a specific gap in score_song():
#
#  1. High-Energy Pop  — genre bonus dominates; a wrong-mood pop song can
#                        outscore a perfect-energy, perfect-mood non-pop song.
#                        Watch for pop/intense songs beating pop/happy ones.
#
#  2. Chill Lofi       — likes_acoustic fires a +0.5 bonus, but
#                        likes_instrumental and target_instrumentalness are
#                        completely ignored. A song with instrumentalness=0.01
#                        scores the same as one at 0.99.
#
#  3. Deep Intense Rock — conflicting-preference blind spot: target_valence=0.35
#                         (dark/negative feel) is never read. A triumphant
#                         rock anthem (valence=0.95) scores identically to a
#                         crushing dirge — the scorer can't tell them apart.
# ---------------------------------------------------------------------------
ADVERSARIAL_PROFILES = [
    {
        "name": "High-Energy Pop",
        "favorite_genre": "pop",
        "favorite_mood":  "happy",
        "target_energy":           0.90,
        "target_valence":          0.85,
        "target_tempo":            128,
        "target_acousticness":     0.10,
        "target_instrumentalness": 0.02,
        "target_speechiness":      0.07,
        "target_danceability":     0.88,
        "target_liveness":         0.14,
        "likes_acoustic":    False,
        "likes_instrumental": False,
    },
    {
        "name": "Chill Lofi",
        "favorite_genre": "lofi",
        "favorite_mood":  "chill",
        "target_energy":           0.38,
        "target_valence":          0.58,
        "target_tempo":            75,
        "target_acousticness":     0.80,
        "target_instrumentalness": 0.90,
        "target_speechiness":      0.02,
        "target_danceability":     0.58,
        "target_liveness":         0.07,
        "likes_acoustic":    True,
        "likes_instrumental": True,
    },
    {
        "name": "Deep Intense Rock",
        "favorite_genre": "rock",
        "favorite_mood":  "intense",
        "target_energy":           0.92,
        "target_valence":          0.35,
        "target_tempo":            155,
        "target_acousticness":     0.08,
        "target_instrumentalness": 0.10,
        "target_speechiness":      0.06,
        "target_danceability":     0.65,
        "target_liveness":         0.25,
        "likes_acoustic":    False,
        "likes_instrumental": False,
    },
]


def run_profile(songs, profile, k=5):
    name = profile["name"]
    print(f"\n{'='*60}")
    print(f"Profile: {name}")
    print(f"{'='*60}")
    recommendations = recommend_songs(profile, songs, k=k)
    for song, score, explanation in recommendations:
        print(f"  {song['title']} ({song['genre']}/{song['mood']}) — Score: {score:.2f}")
        print(f"    Because: {explanation}")
    print()


def main() -> None:
    songs = load_songs("data/songs.csv")

    # Original baseline profile
    user_prefs = {
        "favorite_genre": "r&b",
        "favorite_mood":  "focused",
        "target_energy":           0.55,
        "target_valence":          0.65,
        "target_tempo":            95,
        "target_acousticness":     0.50,
        "target_instrumentalness": 0.60,
        "target_speechiness":      0.05,
        "target_danceability":     0.65,
        "target_liveness":         0.12,
        "likes_acoustic":    False,
        "likes_instrumental": True,
    }

    recommendations = recommend_songs(user_prefs, songs, k=5)

    print("\nTop recommendations (baseline profile):\n")
    for rec in recommendations:
        song, score, explanation = rec
        print(f"{song['title']} - Score: {score:.2f}")
        print(f"Because: {explanation}")
        print()

    # --- System Evaluation: adversarial profiles ---
    print("\n\n*** SYSTEM EVALUATION — ADVERSARIAL PROFILES ***")
    for profile in ADVERSARIAL_PROFILES:
        run_profile(songs, profile, k=5)


if __name__ == "__main__":
    main()
