"""
Playlist narrative generation for the Music Recommender AI system.

This is the generation half of the RAG pipeline. The recommender retrieves
and scores songs from the catalog; this module turns that retrieved evidence
into a natural-language explanation.

Two generators are provided:

  GeminiClient.explain_playlist  — LLM generation, grounded strictly in the
                                   retrieved songs and their score breakdowns.
  build_fallback_narrative       — deterministic template generation, used when
                                   no API key is configured or the API call
                                   fails. Reads the same retrieved evidence.

Both return (narrative_text, source) so callers can always tell the user
which generator produced the text. The system never silently passes off
template output as model output.
"""

import os

from src.verifier import verify_narrative

# Overridable so the project can be pointed at a different Gemini model
# without editing code: set GEMINI_MODEL in .env.
DEFAULT_MODEL_NAME = "gemini-2.0-flash"


def _format_retrieved_songs(recommendations: list) -> str:
    """Render the retrieved song evidence as a numbered block for the prompt."""
    lines = []
    for i, (song, score, explanation) in enumerate(recommendations, 1):
        lines.append(
            f"{i}. \"{song['title']}\" by {song['artist']} "
            f"({song['genre']}, {song['mood']}, energy={float(song['energy']):.2f}) "
            f"- score {score:.2f}\n   Score breakdown: {explanation}"
        )
    return "\n".join(lines)


def build_fallback_narrative(user_prefs: dict, recommendations: list) -> tuple:
    """
    Deterministic narrative built from the retrieved songs, no API required.

    Summarizes which picks matched the stated genre and mood, names the
    strongest and weakest match, and is honest about off-target results.

    Returns (narrative, "template").
    """
    if not recommendations:
        return ("No songs matched your preferences well enough to describe.", "template")

    genre = (user_prefs.get("favorite_genre") or "").lower()
    mood = (user_prefs.get("favorite_mood") or "").lower()
    target_energy = float(user_prefs.get("target_energy", 0.5))

    genre_hits = [s for s, _, _ in recommendations if s.get("genre", "").lower() == genre]
    mood_hits = [s for s, _, _ in recommendations if s.get("mood", "").lower() == mood]

    top_song, top_score, _ = recommendations[0]
    last_song, last_score, _ = recommendations[-1]

    parts = [
        f"This {len(recommendations)}-song playlist is led by "
        f"\"{top_song['title']}\" by {top_song['artist']}, the strongest match "
        f"at a score of {top_score:.2f}."
    ]

    if genre_hits:
        parts.append(
            f"{len(genre_hits)} of {len(recommendations)} picks are actually in "
            f"your preferred {genre} genre."
        )
    else:
        parts.append(
            f"The catalog had no {genre} songs available, so every pick here was "
            f"chosen on feel - energy, mood, and tempo - rather than genre."
        )

    if mood_hits:
        parts.append(
            f"{len(mood_hits)} carry the {mood} mood you asked for."
        )
    else:
        parts.append(
            f"None matched the {mood} mood exactly, so these were ranked on "
            f"audio feel instead."
        )

    energies = [float(s.get("energy", 0.5)) for s, _, _ in recommendations]
    avg_energy = sum(energies) / len(energies)
    drift = avg_energy - target_energy
    if abs(drift) < 0.10:
        parts.append(
            f"The average energy of {avg_energy:.2f} sits right on your "
            f"{target_energy:.2f} target."
        )
    else:
        direction = "higher" if drift > 0 else "lower"
        parts.append(
            f"Average energy is {avg_energy:.2f}, somewhat {direction} than your "
            f"{target_energy:.2f} target - the closest the catalog could get."
        )

    if last_score < top_score * 0.6:
        parts.append(
            f"Be aware the tail of the list is weaker: \"{last_song['title']}\" "
            f"scored only {last_score:.2f} and is a loose fit."
        )

    return (" ".join(parts), "template")


class GeminiClient:
    """
    Wraps the Gemini API for playlist narrative generation.

    Raises RuntimeError at construction if no API key is configured, so the
    caller can fall back to template generation before any request is made.
    """

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Missing GEMINI_API_KEY. Add it to your .env file to enable "
                "AI narrative generation. Get a free key at "
                "https://aistudio.google.com/apikey"
            )

        try:
            from google import genai
        except ImportError as e:
            raise RuntimeError(
                "google-genai is not installed. Run: pip install -r requirements.txt"
            ) from e

        self.model_name = os.getenv("GEMINI_MODEL", DEFAULT_MODEL_NAME)
        self.client = genai.Client(api_key=api_key)

    def _build_prompt(self, user_prefs: dict, recommendations: list) -> str:
        """
        Compose the grounded generation prompt.

        The quoting rule matters: reserving double quotes for titles and
        artists is what lets verify_narrative() treat any other quoted string
        as a fabrication instead of guessing.
        """
        return f"""You are a music curator explaining a personalized playlist to a listener.

The listener asked for:
- Genre: {user_prefs.get('favorite_genre', 'any')}
- Mood: {user_prefs.get('favorite_mood', 'any')}
- Energy level: {user_prefs.get('target_energy', 0.5)} on a 0-1 scale, where 0 is very calm and 1 is very intense
- Prefers acoustic music: {user_prefs.get('likes_acoustic', False)}

The recommender retrieved and scored exactly these songs from its catalog:
{_format_retrieved_songs(recommendations)}

Write a 3-5 sentence narrative explaining why this playlist fits the listener.

Rules:
- Use only the songs and score breakdowns listed above. Do not invent songs,
  artists, albums, or musical details that are not shown.
- Refer to at least two songs by name.
- Put double quotes around song titles and artist names, and around nothing
  else. Do not use double quotes for emphasis or for any other phrase.
- If you cite a score, use the exact number shown above.
- If a pick is a weak or off-target match, say so honestly and explain what
  earned it a place anyway.
- End with one sentence on when or where this playlist would work best.
"""

    def _generate(self, prompt: str) -> str:
        """One raw model call. Returns stripped text, possibly empty."""
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
        )
        return (response.text or "").strip()

    def explain_playlist(self, user_prefs: dict, recommendations: list) -> tuple:
        """
        RAG generation with a verify-and-correct loop.

        Generates a narrative, checks it against the retrieved songs, and if
        the model named something it was never given, retries once with the
        specific violation quoted back to it. If the retry still fails
        verification, falls back to the deterministic generator rather than
        showing the user an unverifiable claim.

        recommendations: list of (song_dict, score, explanation) tuples.

        Returns (narrative, source). The source always states which generator
        produced the text and whether it passed verification. Never raises.
        """
        if not recommendations:
            return ("No songs matched your preferences well enough to describe.", "none")

        prompt = self._build_prompt(user_prefs, recommendations)

        try:
            text = self._generate(prompt)
            if not text:
                narrative, _ = build_fallback_narrative(user_prefs, recommendations)
                return (narrative, "template (model returned empty response)")

            result = verify_narrative(text, recommendations)
            if result.ok:
                return (text, f"gemini:{self.model_name} ({result.summary()})")

            # The model named something outside the retrieved set. Tell it
            # exactly what, and give it one chance to correct itself.
            retry_prompt = (
                f"{prompt}\n"
                f"Your previous attempt failed verification: {result.summary()}.\n"
                f"Those do not appear in the retrieved songs above. Rewrite the "
                f"narrative using only the songs, artists, and scores listed, "
                f"and quote nothing else."
            )

            retry_text = self._generate(retry_prompt)
            if retry_text:
                retry_result = verify_narrative(retry_text, recommendations)
                if retry_result.ok:
                    return (
                        retry_text,
                        f"gemini:{self.model_name} "
                        f"({retry_result.summary()}, after 1 correction)",
                    )

            # Two failed attempts. Do not show the user unverifiable output.
            narrative, _ = build_fallback_narrative(user_prefs, recommendations)
            return (
                narrative,
                f"template (model output failed verification: {result.summary()})",
            )

        except Exception as e:
            # Never let an API failure break the run. Fall back to the
            # deterministic generator and tell the caller what went wrong.
            narrative, _ = build_fallback_narrative(user_prefs, recommendations)
            return (narrative, f"template (API error: {type(e).__name__})")
