#!/usr/bin/env python
"""
Evaluation harness for the Music Recommender AI system.

Runs the system against a fixed suite of inputs and reports pass/fail per
check, plus aggregate confidence statistics. Unlike the pytest suite — which
tests functions in isolation — this exercises the assembled system end to end
and reports on the *quality* of its behavior, not just its correctness.

Runs fully offline. LLM checks are skipped with a clear notice when no API key
is configured, so the harness is reproducible for anyone who clones the repo.

    python evaluate.py            # full suite
    python evaluate.py --verbose  # show detail for every case

Exit code is 0 when every check passes, 1 otherwise, so this is usable in CI.
"""

import argparse
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv()

from src.recommender import load_songs, recommend_songs, SCORING_MODES
from src.guardrails import validate_user_prefs, confidence_score, confidence_label
from src.context_retriever import load_context_docs, retrieve_context
from src.verifier import verify_narrative

DATA_PATH = "data/songs.csv"

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


class Results:
    """Collects check outcomes and renders the summary."""

    def __init__(self):
        self.rows = []

    def record(self, section, name, status, detail=""):
        self.rows.append((section, name, status, detail))

    @property
    def passed(self):
        return sum(1 for r in self.rows if r[2] == PASS)

    @property
    def failed(self):
        return sum(1 for r in self.rows if r[2] == FAIL)

    @property
    def skipped(self):
        return sum(1 for r in self.rows if r[2] == SKIP)

    def print_section(self, section, verbose=False):
        rows = [r for r in self.rows if r[0] == section]
        if not rows:
            return
        print(f"\n{section}")
        print("-" * 72)
        for _, name, status, detail in rows:
            marker = {PASS: "[ok]", FAIL: "[XX]", SKIP: "[--]"}[status]
            line = f"  {marker}  {name}"
            if detail and (verbose or status == FAIL):
                line += f"\n         {detail}"
            print(line)

    def summary(self):
        total = len(self.rows)
        print("\n" + "=" * 72)
        print("SUMMARY")
        print("=" * 72)
        print(f"  checks run : {total}")
        print(f"  passed     : {self.passed}")
        print(f"  failed     : {self.failed}")
        print(f"  skipped    : {self.skipped}")
        verdict = "ALL CHECKS PASSED" if self.failed == 0 else f"{self.failed} CHECK(S) FAILED"
        print(f"\n  {verdict}")
        return 0 if self.failed == 0 else 1


def check(results, section, name, condition, detail=""):
    results.record(section, name, PASS if condition else FAIL, detail)
    return condition


# ---------------------------------------------------------------------------
# 1. Guardrails
# ---------------------------------------------------------------------------

GUARDRAIL_CASES = [
    ("rejects energy above range",
     {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 99}, False),
    ("rejects negative energy",
     {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": -1}, False),
    ("rejects non-numeric energy",
     {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": "loud"}, False),
    ("rejects missing genre",
     {"favorite_mood": "chill", "target_energy": 0.4}, False),
    ("accepts energy at lower bound",
     {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 0.0}, True),
    ("accepts energy at upper bound",
     {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 1.0}, True),
    ("accepts valid profile",
     {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 0.4}, True),
]


def run_guardrails(results):
    section = "1. INPUT GUARDRAILS"
    for name, prefs, should_pass in GUARDRAIL_CASES:
        is_valid, warnings = validate_user_prefs(prefs)
        check(results, section, name, is_valid == should_pass,
              f"expected valid={should_pass}, got {is_valid}: {warnings}")

    # Unknown values must warn without rejecting.
    prefs = {"favorite_genre": "polka", "favorite_mood": "smug", "target_energy": 0.5}
    is_valid, warnings = validate_user_prefs(prefs)
    check(results, section, "unknown genre and mood warn but do not reject",
          is_valid and len(warnings) == 2,
          f"valid={is_valid}, warnings={len(warnings)}")


# ---------------------------------------------------------------------------
# 2. Recommendation quality
# ---------------------------------------------------------------------------

QUALITY_CASES = [
    # label, prefs, min_conf, max_conf, must_contain_genre_at_top
    ("lofi/chill is well served",
     {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 0.35,
      "likes_acoustic": True}, 0.55, 1.00, "lofi"),
    ("rock/intense is poorly served (catalog has 1 rock song)",
     {"favorite_genre": "rock", "favorite_mood": "intense", "target_energy": 0.90,
      "likes_acoustic": False}, 0.00, 0.50, "rock"),
    ("pop/happy is moderately served",
     {"favorite_genre": "pop", "favorite_mood": "happy", "target_energy": 0.85,
      "likes_acoustic": False}, 0.35, 0.75, "pop"),
]


def run_quality(results, songs, verbose=False):
    section = "2. RECOMMENDATION QUALITY"
    confidences = []

    for label, prefs, lo, hi, top_genre in QUALITY_CASES:
        recs = recommend_songs(prefs, songs, k=5)
        conf = confidence_score(recs, prefs)
        confidences.append((label, conf))

        check(results, section, f"{label}: returns 5 songs", len(recs) == 5,
              f"got {len(recs)}")
        check(results, section, f"{label}: top pick matches requested genre",
              recs[0][0]["genre"] == top_genre,
              f"top was {recs[0][0]['genre']}, expected {top_genre}")
        check(results, section, f"{label}: confidence in [{lo:.2f}, {hi:.2f}]",
              lo <= conf <= hi, f"confidence was {conf:.2f} ({confidence_label(conf)})")
        check(results, section, f"{label}: results ranked descending",
              all(recs[i][1] >= recs[i + 1][1] for i in range(len(recs) - 1)),
              "scores not monotonically decreasing")

    # The system must distinguish a well-served request from a poorly-served one.
    lofi_conf = confidences[0][1]
    rock_conf = confidences[1][1]
    check(results, section, "confidence separates served from unserved requests",
          lofi_conf > rock_conf + 0.10,
          f"lofi={lofi_conf:.2f} vs rock={rock_conf:.2f} — too close to distinguish")

    return confidences


# ---------------------------------------------------------------------------
# 3. Determinism
# ---------------------------------------------------------------------------

def run_determinism(results, songs):
    section = "3. DETERMINISM"
    prefs = {"favorite_genre": "lofi", "favorite_mood": "chill",
             "target_energy": 0.35, "likes_acoustic": True}

    runs = [recommend_songs(prefs, songs, k=5) for _ in range(3)]
    titles = [tuple(s["title"] for s, _, _ in r) for r in runs]
    scores = [tuple(round(sc, 6) for _, sc, _ in r) for r in runs]

    check(results, section, "identical input yields identical ranking",
          len(set(titles)) == 1, f"got {len(set(titles))} distinct orderings")
    check(results, section, "identical input yields identical scores",
          len(set(scores)) == 1, f"got {len(set(scores))} distinct score vectors")


# ---------------------------------------------------------------------------
# 4. Context retrieval (RAG source 2)
# ---------------------------------------------------------------------------

RETRIEVAL_CASES = [
    ("lofi/chill retrieves the lofi note",
     {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 0.35}, "genre-lofi"),
    ("rock/intense retrieves the rock note",
     {"favorite_genre": "rock", "favorite_mood": "intense", "target_energy": 0.90}, "genre-rock"),
    ("metal/angry retrieves the metal note",
     {"favorite_genre": "metal", "favorite_mood": "angry", "target_energy": 0.95}, "genre-metal"),
    ("jazz/relaxed retrieves the jazz note",
     {"favorite_genre": "jazz", "favorite_mood": "relaxed", "target_energy": 0.40}, "genre-jazz"),
]


def run_retrieval(results, verbose=False):
    section = "4. CONTEXT RETRIEVAL"
    docs = load_context_docs()

    if not check(results, section, "corpus loads", len(docs) > 0,
                 "data/context/ is empty or missing"):
        return

    for label, prefs, expected in RETRIEVAL_CASES:
        got = retrieve_context(prefs, docs, k=2)
        names = [d.name for d in got]
        check(results, section, label, expected in names,
              f"retrieved {names}, expected to include {expected}")

    # High-energy requests should surface the workout note, not the study note.
    workout = retrieve_context(
        {"favorite_genre": "rock", "favorite_mood": "intense", "target_energy": 0.95},
        docs, k=2)
    study = retrieve_context(
        {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 0.30},
        docs, k=2)
    check(results, section, "energy level steers use-case retrieval",
          any("workout" in d.name for d in workout)
          and any("study" in d.name or "relax" in d.name for d in study),
          f"high-energy got {[d.name for d in workout]}, "
          f"low-energy got {[d.name for d in study]}")

    check(results, section, "retrieval returns at most k documents",
          len(retrieve_context(RETRIEVAL_CASES[0][1], docs, k=2)) <= 2)


# ---------------------------------------------------------------------------
# 5. Narrative verification
# ---------------------------------------------------------------------------

def run_verification(results, songs):
    section = "5. NARRATIVE VERIFICATION"
    prefs = {"favorite_genre": "lofi", "favorite_mood": "chill",
             "target_energy": 0.35, "likes_acoustic": True}
    recs = recommend_songs(prefs, songs, k=3)
    real_title = recs[0][0]["title"]
    real_score = round(recs[0][1], 2)

    cases = [
        ("grounded narrative passes", f'Led by "{real_title}".', True),
        ("fabricated song is caught", 'Try "Purple Rain" instead.', False),
        ("fabricated artist is caught", 'A set by "Taylor Swift".', False),
        ("fabricated score is caught", f'"{real_title}" scored 99.9 here.', False),
        ("correct score passes", f'"{real_title}" scored {real_score}.', True),
        ("unquoted prose passes", "A calm set for studying.", True),
        ("empty narrative fails", "", False),
    ]

    for name, text, should_pass in cases:
        result = verify_narrative(text, recs)
        check(results, section, name, result.ok == should_pass,
              f"expected ok={should_pass}, got {result.ok}: {result.summary()}")


# ---------------------------------------------------------------------------
# 6. Live LLM generation (skipped without a key)
# ---------------------------------------------------------------------------

def run_llm(results, songs, verbose=False):
    section = "6. LIVE LLM GENERATION"
    try:
        from src.llm_client import GeminiClient
        client = GeminiClient()
    except Exception as e:
        results.record(section, "live generation",
                       SKIP, f"no usable API key ({type(e).__name__}) — offline checks unaffected")
        return

    docs = load_context_docs()
    profiles = [
        ("lofi/chill", {"favorite_genre": "lofi", "favorite_mood": "chill",
                        "target_energy": 0.35, "likes_acoustic": True}),
        ("rock/intense", {"favorite_genre": "rock", "favorite_mood": "intense",
                          "target_energy": 0.90, "likes_acoustic": False}),
    ]

    for label, prefs in profiles:
        recs = recommend_songs(prefs, songs, k=5)
        ctx = retrieve_context(prefs, docs, k=2)
        try:
            narrative, source = client.explain_playlist(prefs, recs, context_docs=ctx)
        except Exception as e:
            results.record(section, f"{label}: generation", FAIL, f"{type(e).__name__}: {e}")
            continue

        if source.startswith("template"):
            results.record(section, f"{label}: generation", SKIP,
                           f"fell back to template — {source}")
            continue

        result = verify_narrative(narrative, recs)
        check(results, section, f"{label}: live output passes verification",
              result.ok, f"{result.summary()}")
        check(results, section, f"{label}: narrative names at least two songs",
              result.checked_entities >= 2, f"only {result.checked_entities} entities quoted")
        if verbose:
            print(f"         {narrative[:150]}...")
        time.sleep(5)


def main():
    parser = argparse.ArgumentParser(description="Evaluate the music recommender system.")
    parser.add_argument("--verbose", action="store_true", help="show detail for passing checks")
    parser.add_argument("--no-llm", action="store_true",
                        help="skip live API checks (offline suite only)")
    args = parser.parse_args()

    print("=" * 72)
    print("MUSIC RECOMMENDER — EVALUATION HARNESS")
    print("=" * 72)

    songs = load_songs(DATA_PATH)
    print(f"catalog: {len(songs)} songs")

    results = Results()
    run_guardrails(results)
    confidences = run_quality(results, songs, args.verbose)
    run_determinism(results, songs)
    run_retrieval(results, args.verbose)
    run_verification(results, songs)
    if args.no_llm:
        results.record("6. LIVE LLM GENERATION", "live generation", SKIP,
                       "skipped via --no-llm")
    else:
        run_llm(results, songs, args.verbose)

    for section in ["1. INPUT GUARDRAILS", "2. RECOMMENDATION QUALITY",
                    "3. DETERMINISM", "4. CONTEXT RETRIEVAL",
                    "5. NARRATIVE VERIFICATION", "6. LIVE LLM GENERATION"]:
        results.print_section(section, args.verbose)

    print("\nCONFIDENCE BY PROFILE")
    print("-" * 72)
    for label, conf in confidences:
        bar = "#" * int(conf * 30)
        short = label.split(" is ")[0]
        print(f"  {short:<16} {confidence_label(conf):<7} {conf:5.0%}  {bar}")

    return results.summary()


if __name__ == "__main__":
    sys.exit(main())
