"""
Music Recommender AI System — CLI runner.

Modes:
  1) Scoring only  — rule-based recommendations with confidence score
  2) RAG           — scoring + Gemini narrative explanation
  3) Evaluation    — run adversarial profiles and print a reliability report
"""

import os
import sys

from dotenv import load_dotenv

# Windows consoles default to cp1252, which cannot encode the em dashes and
# box-drawing characters used in this CLI. Force UTF-8 so the app runs
# identically on Windows, macOS, and Linux.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

from src.recommender import load_songs, recommend_songs, SCORING_MODES
from src.guardrails import validate_user_prefs, confidence_score, confidence_label
from src.llm_client import build_fallback_narrative
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
    """
    Build a GeminiClient if a key is configured.

    Returns (client_or_None, has_llm). A None client is not fatal: narrative
    mode still runs using the deterministic template generator.
    """
    try:
        from src.llm_client import GeminiClient
        return GeminiClient(), True
    except RuntimeError as e:
        print(f"Note: {e}")
        print("Narrative mode will use the offline template generator instead.\n")
        return None, False
    except Exception as e:
        print(f"Note: could not initialize Gemini ({type(e).__name__}: {e}).")
        print("Narrative mode will use the offline template generator instead.\n")
        return None, False


def run_scoring_mode(songs, llm_client=None, narrate=False):
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

    if narrate:
        print("Generating playlist narrative...\n")
        if llm_client:
            narrative, source = llm_client.explain_playlist(user_prefs, recommendations)
        else:
            narrative, source = build_fallback_narrative(user_prefs, recommendations)

        print("Playlist Narrative:")
        print("-" * 60)
        print(narrative)
        print(f"\n[generated by: {source}]\n")


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

    print(f"{'-'*60}")
    print("Summary:")
    for name, conf, label, _ in results:
        bar = "#" * int(conf * 20)
        print(f"  {name:<22} {label:<8} {conf:.0%}  {bar}")
    print()


def run_agent_mode(songs, llm_client):
    """Mode 4: run the planning agent and show its reasoning trace."""
    from src.agent import PlanningAgent
    from src.personas import PERSONAS

    print("\nEnter your music preferences:")
    genre = input("  Favorite genre: ").strip().lower()
    mood = input("  Favorite mood: ").strip().lower()
    energy_raw = input("  Target energy 0.0–1.0: ").strip()
    acoustic_raw = input("  Likes acoustic? (y/n): ").strip().lower()

    try:
        energy = float(energy_raw)
    except ValueError:
        print("Invalid energy value. Using 0.5.")
        energy = 0.5

    prefs = {
        "favorite_genre": genre,
        "favorite_mood": mood,
        "target_energy": energy,
        "likes_acoustic": acoustic_raw == "y",
    }

    agent = PlanningAgent(songs, llm_client=llm_client)
    result, trace = agent.run(prefs)

    print(f"\n{'='*66}")
    print("AGENT REASONING TRACE")
    print(f"{'='*66}")
    for step in trace.steps:
        print(f"\n  Step {step.number}: {step.name}")
        print(f"    why    : {step.reasoning}")
        print(f"    action : {step.action}")
        print(f"    result : {step.observation}")

    print(f"\n{'-'*66}")
    print(f"OUTCOME: {trace.outcome}")

    if not result:
        print()
        return

    print(f"\n{'='*66}")
    print(f"RECOMMENDATIONS  |  Confidence: {result['confidence_label']} "
          f"({result['confidence']:.0%})")
    print(f"{'='*66}")
    for song, score, explanation in result["recommendations"]:
        print(f"  {song['title']} by {song['artist']} "
              f"({song['genre']}/{song['mood']}) — {score:.2f}")

    print(f"\nNarrative:\n{'-'*66}")
    print(result["narrative"])
    print(f"\n[generated by: {result['narrative_source']}]")

    path = trace.save()
    print(f"\nTrace written to: {os.path.relpath(path)}\n")

    log_run(prefs, result["recommendations"], result["confidence"],
            result["strategy"], result["warnings"])


def main():
    print("Music Recommender AI System")
    print("===========================\n")

    songs = load_songs(DATA_PATH)
    llm_client, has_llm = try_create_llm_client()

    generator = "Gemini" if has_llm else "offline template"

    while True:
        print("Choose a mode:")
        print("  1) Scoring only   — recommendations + confidence score")
        print(f"  2) RAG narrative  — scoring + playlist narrative ({generator})")
        print("  3) Evaluation     — adversarial profiles + reliability report")
        print("  4) Agent          — multi-step planning with a reasoning trace")
        print("  q) Quit")

        choice = input("\nEnter choice: ").strip().lower()

        if choice == "q":
            print("Goodbye.")
            break
        elif choice == "1":
            run_scoring_mode(songs, llm_client=None, narrate=False)
        elif choice == "2":
            run_scoring_mode(songs, llm_client=llm_client, narrate=True)
        elif choice == "3":
            run_evaluation_mode(songs)
        elif choice == "4":
            run_agent_mode(songs, llm_client)
        else:
            print("\nUnknown choice. Enter 1, 2, 3, 4, or q.\n")


if __name__ == "__main__":
    main()
