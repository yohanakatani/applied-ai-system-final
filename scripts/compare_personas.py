#!/usr/bin/env python
"""
Measure whether the few-shot personas actually change generated output.

Runs the same playlist through every persona and reports style metrics
side by side, so "the output is different" becomes a checkable claim rather
than an assertion.

    python scripts/compare_personas.py

Results are written to persona_results.json for inclusion in the model card.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv()

from src.context_retriever import load_context_docs, retrieve_context
from src.personas import PERSONAS, measure_style
from src.recommender import load_songs, recommend_songs
from src.verifier import verify_narrative

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "persona_results.json")

PROFILE = {
    "favorite_genre": "lofi",
    "favorite_mood": "chill",
    "target_energy": 0.35,
    "likes_acoustic": True,
}


def main():
    from src.llm_client import GeminiClient

    songs = load_songs(os.path.join(os.path.dirname(__file__), "..", "data", "songs.csv"))
    docs = load_context_docs()
    recs = recommend_songs(PROFILE, songs, k=5)
    ctx = retrieve_context(PROFILE, docs, k=2)

    client = GeminiClient()
    print(f"model: {client.model_name}")
    print(f"profile: {PROFILE['favorite_genre']}/{PROFILE['favorite_mood']}")
    print(f"context: {', '.join(d.name for d in ctx)}\n")

    results = {}
    for key in PERSONAS:
        print(f"[{key}] generating...", flush=True)
        try:
            narrative, source = client.explain_playlist(
                PROFILE, recs, context_docs=ctx, persona_key=key
            )
        except Exception as e:
            print(f"[{key}] ERROR {type(e).__name__}", flush=True)
            results[key] = {"error": f"{type(e).__name__}: {e}"[:200]}
            continue

        verified = verify_narrative(narrative, recs)
        results[key] = {
            "text": narrative,
            "source": source,
            "verified": verified.ok,
            "metrics": measure_style(narrative),
        }
        m = results[key]["metrics"]
        print(
            f"[{key}] {m['words']}w, {m['sentences']}s, "
            f"avg {m['avg_sentence_len']}, nums {m['numbers']}, "
            f"you {m['second_person']}, verified={verified.ok}",
            flush=True,
        )
        time.sleep(8)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)

    print(f"\n{'persona':<12}{'words':>7}{'sents':>7}{'avg':>7}{'nums':>6}{'num%':>7}{'you%':>7}  ok")
    print("-" * 62)
    for key, data in results.items():
        if "metrics" not in data:
            print(f"{key:<12}  ERROR")
            continue
        m = data["metrics"]
        print(
            f"{key:<12}{m['words']:>7}{m['sentences']:>7}{m['avg_sentence_len']:>7}"
            f"{m['numbers']:>6}{m['number_density']:>7}{m['second_person_density']:>7}"
            f"  {data['verified']}"
        )
    print(f"\nwritten to {os.path.relpath(OUT_PATH)}")


if __name__ == "__main__":
    main()
