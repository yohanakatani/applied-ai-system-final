"""
Music Recommender AI System — CLI runner.

Modes:
  1) Scoring only  — rule-based recommendations with confidence score
  2) RAG           — scoring + Gemini narrative explanation
  3) Evaluation    — run adversarial profiles and print a reliability report
"""

import os
from dotenv import load_dotenv

load_dotenv()

from src.recommender import load_songs, recommend_songs, SCORING_MODES
from src.guardrails import validate_user_prefs, confidence_score, confidence_label
from src.logger import log_run

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "songs.csv")

ADVERSARIAL_PROFILES = [
    {
        "name": "High-Energy Pop",
        "favorite_genre": "pop",
        "favorite_mood": "happy",
        "target_energy": 0.90,
        "target_valence": 0.85,
        "target_tempo": 128,
        "likes_acoustic": False,
        "target_popularity": 80,
        "preferred_decade": 2020,
        "preferred_mood_tag": "euphoric",
        "avoid_explicit": False,
        "target_loudness": 0.80,
    },
    {
        "name": "Chill Lofi",
        "favorite_genre": "lofi",
        "favorite_mood": "chill",
        "target_energy": 0.38,
        "target_valence": 0.58,
        "target_tempo": 75,
        "likes_acoustic": True,
        "target_popularity": 60,
        "preferred_decade": 2020,
        "preferred_mood_tag": "dreamy",
        "avoid_explicit": True,
        "target_loudness": 0.30,
    },
    {
        "name": "Deep Intense Rock",
        "favorite_genre": "rock",
        "favorite_mood": "intense",
        "target_energy": 0.92,
        "target_valence": 0.35,
        "target_tempo": 155,
        "likes_acoustic": False,
        "target_popularity": 65,
        "preferred_decade": 2010,
        "preferred_mood_tag": "aggressive",
        "avoid_explicit": False,
        "target_loudness": 0.88,
    },
]


def try_create_llm_client():
    try:
        from src.llm_client import GeminiClient
        client = GeminiClient()
        return client, True
    except RuntimeError as e:
        print(f"Warning: RAG mode disabled — {e}\n")
        return None, False
    except Exception as e:
        print(f"Warning: Could not load Gemini client — {e}\n")
        return None, False


def run_scoring_mode(songs, llm_client=None):
    print("\nEnter your music preferences:")
    genre = input("  Favorite genre (e.g. lofi, pop, rock): ").strip().lower()
    mood = input("  Favorite mood (e.g. chill, happy, intense): ").strip().lower()
    energy_raw = input("  Target energy 0.0–1.0 (e.g. 0.5): ").strip()
    acoustic_raw = input("  Likes acoustic? (y/n): ").strip().lower()

    try:
        energy = float(energy_raw)
    except ValueError:
        print("Invalid energy value. Using 0.5.")
        energy = 0.5

    user_prefs = {
        "favorite_genre": genre,
        "favorite_mood": mood,
        "target_energy": energy,
        "likes_acoustic": acoustic_raw == "y",
    }

    is_valid, warnings = validate_user_prefs(user_prefs)
    if not is_valid:
        print(f"\nInvalid input: {warnings[0]}")
        return

    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"  ! {w}")

    strategy_name = input(
        "\nScoring strategy (balanced / genre-first / mood-first / energy-focused / vibe-match) [balanced]: "
    ).strip().lower() or "balanced"

    strategy = SCORING_MODES.get(strategy_name, SCORING_MODES["balanced"])
    recommendations = recommend_songs(user_prefs, songs, k=5, strategy=strategy)

    conf = confidence_score(recommendations, user_prefs)
    label = confidence_label(conf)

    print(f"\n{'='*60}")
    print(f"Top 5 recommendations  |  Confidence: {label} ({conf:.0%})")
    print(f"{'='*60}")
    for song, score, explanation in recommendations:
        print(f"  {song['title']} by {song['artist']}")
        print(f"    Genre: {song['genre']}  Mood: {song['mood']}  Energy: {song['energy']:.2f}")
        print(f"    Score: {score:.2f}  |  Because: {explanation}")
        print()

    log_run(user_prefs, recommendations, conf, strategy_name, warnings)

    if llm_client:
        print("Generating playlist narrative...\n")
        narrative = llm_client.explain_playlist(user_prefs, recommendations)
        print("AI Playlist Narrative:")
        print("-" * 60)
        print(narrative)
        print()


def run_evaluation_mode(songs):
    print(f"\n{'='*60}")
    print("RELIABILITY EVALUATION — Adversarial Profiles")
    print(f"{'='*60}\n")

    results = []
    for profile in ADVERSARIAL_PROFILES:
        name = profile["name"]
        prefs = {k: v for k, v in profile.items() if k != "name"}

        is_valid, warnings = validate_user_prefs(prefs)
        recs = recommend_songs(prefs, songs, k=5)
        conf = confidence_score(recs, prefs)
        label = confidence_label(conf)

        results.append((name, conf, label, recs))
        log_run(prefs, recs, conf, "balanced", warnings)

        print(f"Profile: {name}")
        print(f"  Confidence: {label} ({conf:.0%})")
        print(f"  Top pick: {recs[0][0]['title']} by {recs[0][0]['artist']} (score {recs[0][1]:.2f})")
        print()

    print(f"{'─'*60}")
    print("Summary:")
    for name, conf, label, _ in results:
        bar = "█" * int(conf * 20)
        print(f"  {name:<22} {label:<8} {conf:.0%}  {bar}")
    print()


def main():
    print("Music Recommender AI System")
    print("===========================\n")

    songs = load_songs(DATA_PATH)
    llm_client, has_llm = try_create_llm_client()

    while True:
        print("Choose a mode:")
        print("  1) Scoring only   — get recommendations with confidence score")
        if has_llm:
            print("  2) RAG            — scoring + AI playlist narrative (Gemini)")
        else:
            print("  2) RAG            — unavailable (no GEMINI_API_KEY)")
        print("  3) Evaluation     — run adversarial profiles + reliability report")
        print("  q) Quit")

        choice = input("\nEnter choice: ").strip().lower()

        if choice == "q":
            print("Goodbye.")
            break
        elif choice == "1":
            run_scoring_mode(songs, llm_client=None)
        elif choice == "2":
            if has_llm:
                run_scoring_mode(songs, llm_client=llm_client)
            else:
                print("\nRAG mode is not available. Set GEMINI_API_KEY in your .env file.\n")
        elif choice == "3":
            run_evaluation_mode(songs)
        else:
            print("\nUnknown choice. Enter 1, 2, 3, or q.\n")


if __name__ == "__main__":
    main()
