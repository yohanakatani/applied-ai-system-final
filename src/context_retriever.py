"""
Second retrieval source: an unstructured document corpus.

The recommender retrieves *songs* from a structured CSV by numeric scoring.
This module retrieves *explanatory prose* from `data/context/` by term
overlap. The two sources answer different questions:

    songs.csv     -> which tracks match this listener
    data/context/ -> what this genre, mood, or listening situation is like

Both feed the narrative generator. Songs supply the facts; context supplies the
vocabulary and domain reasoning the model would otherwise have to invent.

Retrieval is deliberately simple and inspectable — inverse document frequency
weighting over a small corpus, no embeddings, no external service. At this
corpus size a dense retriever would add a dependency and a failure mode without
changing which documents come back.
"""

import math
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

CONTEXT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "context")

# Words too common in this corpus to carry retrieval signal.
_STOPWORDS = {
    "the", "and", "for", "that", "with", "this", "than", "from", "into",
    "which", "what", "when", "why", "how", "does", "not", "but", "are", "was",
    "its", "it", "a", "an", "of", "to", "in", "is", "or", "on", "at", "as",
    "by", "be", "can", "will", "more", "most", "less", "least", "very",
    "music", "track", "tracks", "song", "songs", "genre", "listening",
    "listener", "listeners",
}

_TOKEN = re.compile(r"[a-z][a-z'-]+")


@dataclass
class ContextDoc:
    """One retrieved document from the corpus."""

    name: str
    title: str
    text: str
    score: float = 0.0

    def snippet(self, max_chars: int = 700) -> str:
        """Body text trimmed to a whole sentence near the limit."""
        body = self.text.strip()
        if len(body) <= max_chars:
            return body
        cut = body[:max_chars]
        last_stop = cut.rfind(". ")
        return (cut[: last_stop + 1] if last_stop > 200 else cut).strip()


def _tokenize(text: str) -> List[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS]


def load_context_docs(context_dir: Optional[str] = None) -> List[ContextDoc]:
    """
    Load every markdown document in the corpus.

    Returns an empty list if the directory is missing, so the system degrades
    to song-only retrieval rather than failing.
    """
    directory = context_dir or CONTEXT_DIR
    if not os.path.isdir(directory):
        return []

    docs = []
    for filename in sorted(os.listdir(directory)):
        if not filename.endswith(".md"):
            continue
        path = os.path.join(directory, filename)
        try:
            with open(path, encoding="utf-8") as f:
                raw = f.read()
        except OSError:
            continue

        lines = raw.splitlines()
        title = lines[0].lstrip("# ").strip() if lines else filename
        docs.append(
            ContextDoc(
                name=os.path.splitext(filename)[0],
                title=title,
                text=raw,
            )
        )
    return docs


def _build_query(user_prefs: Dict) -> Dict[str, float]:
    """
    Turn a taste profile into a weighted retrieval query.

    Terms the listener actually stated (genre, mood) outweigh terms this
    function infers from their energy setting. Without that separation the
    inferred vocabulary swamps the stated genre: a jazz listener at mid energy
    expands to "steady background focus study", which scores the lofi and
    studying documents above the jazz one the listener plainly asked for.
    Found by evaluate.py rather than by reading this function.
    """
    weights: Dict[str, float] = {}

    def add(term: str, weight: float) -> None:
        for token in _tokenize(str(term)):
            weights[token] = max(weights.get(token, 0.0), weight)

    # Stated preferences: what the listener actually told us.
    add(user_prefs.get("favorite_genre", ""), 3.0)
    add(user_prefs.get("favorite_mood", ""), 2.0)

    # Inferred vocabulary: our guess at the listening situation. Useful for
    # surfacing a use-case document, but never enough to outrank the genre.
    energy = float(user_prefs.get("target_energy", 0.5))
    if energy < 0.35:
        inferred = ["calm", "quiet", "relax", "sleep", "peaceful"]
    elif energy < 0.6:
        inferred = ["steady", "background", "focus", "study"]
    else:
        inferred = ["intense", "energetic", "workout", "loud"]
    for term in inferred:
        add(term, 1.0)

    if user_prefs.get("likes_acoustic"):
        for term in ("acoustic", "warm", "organic"):
            add(term, 1.0)

    return weights


def retrieve_context(
    user_prefs: Dict,
    docs: Optional[List[ContextDoc]] = None,
    k: int = 2,
    min_score: float = 0.5,
) -> List[ContextDoc]:
    """
    Return the top-k corpus documents most relevant to this taste profile.

    Scoring is term-frequency weighted by inverse document frequency, with a
    bonus for terms appearing in a document's declared **Keywords:** line —
    those are curated relevance signals rather than incidental word counts.

    Documents scoring below `min_score` are dropped entirely. Returning
    nothing is a valid outcome: an irrelevant document actively hurts
    generation by inviting the model to talk about something the listener did
    not ask for.
    """
    corpus = docs if docs is not None else load_context_docs()
    if not corpus:
        return []

    query_weights = _build_query(user_prefs)
    if not query_weights:
        return []

    total_docs = len(corpus)
    doc_tokens = {d.name: _tokenize(d.text) for d in corpus}

    # Inverse document frequency: a term in every document tells us nothing.
    doc_freq = {
        term: sum(1 for tokens in doc_tokens.values() if term in tokens)
        for term in query_weights
    }

    scored = []
    for doc in corpus:
        tokens = doc_tokens[doc.name]
        if not tokens:
            continue

        keyword_line = ""
        for line in doc.text.splitlines():
            if line.strip().lower().startswith("**keywords:"):
                keyword_line = line.lower()
                break
        keyword_terms = set(_tokenize(keyword_line))

        score = 0.0
        for term, term_weight in query_weights.items():
            count = tokens.count(term)
            if not count:
                continue
            idf = math.log((total_docs + 1) / (doc_freq[term] + 1)) + 1.0
            score += term_weight * (1.0 + math.log(count)) * idf
            if term in keyword_terms:
                score += term_weight * 1.5 * idf

        if score >= min_score:
            scored.append(ContextDoc(doc.name, doc.title, doc.text, round(score, 3)))

    scored.sort(key=lambda d: d.score, reverse=True)
    return scored[:k]


def format_context_block(docs: List[ContextDoc]) -> str:
    """Render retrieved documents for inclusion in a generation prompt."""
    if not docs:
        return ""
    blocks = [f"[{d.title}]\n{d.snippet()}" for d in docs]
    return "\n\n".join(blocks)
