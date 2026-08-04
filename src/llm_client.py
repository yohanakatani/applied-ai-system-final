"""
Gemini client for the Music Recommender AI system.

Takes the top-k scored songs (retrieved by the recommender) and the user's
taste profile, then uses Gemini to generate a natural-language playlist
narrative — the RAG generation step.
"""

import os
from google import genai

GEMINI_MODEL_NAME = "gemma-4-31b-it"

KNOWN_GENRES = {
    "pop", "lofi", "rock", "r&b", "folk", "jazz", "metal",
    "edm", "hip-hop", "ambient", "synthwave", "indie pop", "classical"
}
KNOWN_MOODS = {
    "chill", "happy", "intense", "focused", "relaxed", "moody",
    "nostalgic", "energetic", "angry", "dreamy", "euphoric", "aggressive"
}


class GeminiClient:
    """
    Wraps the Gemini API for playlist explanation generation.

    Usage:
        client = GeminiClient()
        narrative = client.explain_playlist(user_prefs, recommendations)
    """

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Missing GEMINI_API_KEY environment variable. "
                "Set it in your .env file to enable AI explanation features."
            )
        self.client = genai.Client(api_key=api_key)

    def explain_playlist(self, user_prefs: dict, recommendations: list) -> str:
        """
        RAG generation step: given retrieved song data and user preferences,
        generate a natural-language playlist narrative.

        recommendations: list of (song_dict, score, explanation) tuples
        """
        if not recommendations:
            return "No songs matched your preferences well enough to explain."

        song_lines = []
        for i, (song, score, explanation) in enumerate(recommendations, 1):
            song_lines.append(
                f"{i}. \"{song['title']}\" by {song['artist']} "
                f"({song['genre']}, {song['mood']}, energy={song['energy']:.2f}) "
                f"— score {score:.2f}\n   Why it scored: {explanation}"
            )
        songs_block = "\n".join(song_lines)

        prompt = f"""You are a music curator helping a listener understand their personalized playlist.

The listener's preferences:
- Favorite genre: {user_prefs.get('favorite_genre', 'any')}
- Favorite mood: {user_prefs.get('favorite_mood', 'any')}
- Target energy level: {user_prefs.get('target_energy', 0.5)} (0=very calm, 1=very intense)
- Likes acoustic music: {user_prefs.get('likes_acoustic', False)}

The recommender system retrieved and scored these songs from the catalog:
{songs_block}

Your job:
- Write a short, friendly 3-5 sentence narrative explaining why this playlist fits the listener.
- Reference specific songs by name.
- Be honest if some picks are imperfect matches and briefly say why they still made the list.
- Do not invent songs or details not present above. Only describe what is in the retrieved list.
- End with one sentence suggesting when or where this playlist would work best.
"""

        try:
            response = self.client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=prompt
            )
            return (response.text or "").strip()
        except Exception as e:
            return f"Could not generate playlist narrative. ({type(e).__name__}: {e})"
