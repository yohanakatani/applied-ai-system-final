"""
Command line runner for the Music Recommender Simulation.

This file helps you quickly run and test your recommender.

You will implement the functions in recommender.py:
- load_songs
- score_song
- recommend_songs
"""

from src.recommender import load_songs, recommend_songs


def main() -> None:
    songs = load_songs("data/songs.csv")

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

    print("\nTop recommendations:\n")
    for rec in recommendations:
        # You decide the structure of each returned item.
        # A common pattern is: (song, score, explanation)
        song, score, explanation = rec
        print(f"{song['title']} - Score: {score:.2f}")
        print(f"Because: {explanation}")
        print()


if __name__ == "__main__":
    main()
