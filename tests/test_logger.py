"""
Tests for the run logger.

Every recommendation run must leave a machine-readable audit trail so the
system's behavior can be reviewed after the fact.
"""

import json

import pytest

from src import logger as logger_module


@pytest.fixture
def log_path(tmp_path, monkeypatch):
    """Redirect the logger at a temp file and give it a clean handler."""
    path = tmp_path / "recommendations.log"
    monkeypatch.setattr(logger_module, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(logger_module, "LOG_FILE", str(path))

    # Drop any handler cached from an earlier test so the new path takes effect.
    cached = logger_module.logging.getLogger("music_recommender")
    for handler in list(cached.handlers):
        handler.close()
        cached.removeHandler(handler)

    yield path

    for handler in list(cached.handlers):
        handler.close()
        cached.removeHandler(handler)


def make_recs():
    song = {"title": "Library Rain", "artist": "Paper Lanterns", "genre": "lofi",
            "mood": "chill", "energy": 0.35}
    return [(song, 4.47, "Genre match: lofi")]


PREFS = {
    "favorite_genre": "lofi",
    "favorite_mood": "chill",
    "target_energy": 0.4,
    "likes_acoustic": True,
}


def read_entries(path):
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_log_run_writes_one_valid_json_line(log_path):
    logger_module.log_run(PREFS, make_recs(), 0.87, "balanced", [])
    entries = read_entries(log_path)
    assert len(entries) == 1


def test_log_entry_captures_prefs_and_confidence(log_path):
    logger_module.log_run(PREFS, make_recs(), 0.87, "mood-first", [])
    entry = read_entries(log_path)[0]

    assert entry["confidence"] == 0.87
    assert entry["strategy"] == "mood-first"
    assert entry["user_prefs"]["genre"] == "lofi"
    assert entry["user_prefs"]["mood"] == "chill"


def test_log_entry_captures_top_results(log_path):
    logger_module.log_run(PREFS, make_recs(), 0.87, "balanced", [])
    entry = read_entries(log_path)[0]

    assert entry["top_results"][0]["title"] == "Library Rain"
    assert entry["top_results"][0]["artist"] == "Paper Lanterns"
    assert entry["top_results"][0]["score"] == pytest.approx(4.47)


def test_log_entry_records_warnings(log_path):
    logger_module.log_run(PREFS, make_recs(), 0.5, "balanced", ["Unknown genre 'polka'"])
    entry = read_entries(log_path)[0]
    assert entry["warnings"] == ["Unknown genre 'polka'"]


def test_log_entry_has_timezone_aware_timestamp(log_path):
    from datetime import datetime

    logger_module.log_run(PREFS, make_recs(), 0.87, "balanced", [])
    entry = read_entries(log_path)[0]

    parsed = datetime.fromisoformat(entry["timestamp"])
    assert parsed.tzinfo is not None


def test_repeated_runs_append_rather_than_overwrite(log_path):
    logger_module.log_run(PREFS, make_recs(), 0.5, "balanced", [])
    logger_module.log_run(PREFS, make_recs(), 0.9, "vibe-match", [])

    entries = read_entries(log_path)
    assert len(entries) == 2
    assert [e["confidence"] for e in entries] == [0.5, 0.9]
