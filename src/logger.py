"""
Logs every recommendation run to logs/recommendations.log.
Each entry captures the user profile, top results, confidence score, and timestamp.
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Tuple

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
LOG_FILE = os.path.join(LOG_DIR, "recommendations.log")


def _get_logger() -> logging.Logger:
    logger = logging.getLogger("music_recommender")
    if logger.handlers:
        return logger

    os.makedirs(LOG_DIR, exist_ok=True)
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


def log_run(
    user_prefs: Dict,
    recommendations: List[Tuple],
    confidence: float,
    strategy_name: str = "balanced",
    warnings: List[str] = None,
) -> None:
    """
    Write one structured log entry for a recommendation run.
    """
    logger = _get_logger()

    top_songs = [
        {"title": s["title"], "artist": s["artist"], "score": round(sc, 3)}
        for s, sc, _ in recommendations
    ]

    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "strategy": strategy_name,
        "user_prefs": {
            "genre": user_prefs.get("favorite_genre"),
            "mood": user_prefs.get("favorite_mood"),
            "energy": user_prefs.get("target_energy"),
            "likes_acoustic": user_prefs.get("likes_acoustic", False),
        },
        "confidence": confidence,
        "top_results": top_songs,
        "warnings": warnings or [],
    }

    logger.info(json.dumps(entry))
