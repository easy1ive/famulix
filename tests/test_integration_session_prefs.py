"""Integration test: session recording, replay, and preference learning.

Verifies that session recording captures all events with checksums,
save/load is deterministic, and preference learning works across the pipeline.
"""

import tempfile
from pathlib import Path

from famulix.factory import generate_history
from famulix.preferences import PreferenceProfile
from famulix.session import SessionRecorder


def test_session_record_save_load_determinism():
    """Verify session recording, save, and load produce identical traces."""
    events, _manifest = generate_history(persona_id="alex", seed=42, days=5)

    # Record a session
    recorder = SessionRecorder(session_id="test-session", seed=42)

    # Record events as they're processed
    for event in events[:10]:
        recorder.record(
            kind="event",
            payload={"event_id": event.event_id, "timestamp_s": event.timestamp_s},
            timestamp_s=event.timestamp_s,
        )

    # Verify checksum
    assert recorder.verify(), "Session checksum should be valid"

    # Save and reload
    with tempfile.TemporaryDirectory() as tmpdir:
        session_path = Path(tmpdir) / "session.jsonl"
        recorder.save(session_path)

        loaded = SessionRecorder.load(session_path)

        # Verify loaded session matches
        assert loaded.entry_count() == recorder.entry_count()
        assert loaded.digest() == recorder.digest()
        assert loaded.verify(), "Loaded session should verify"


def test_session_recorder_checkpoint_resume():
    """Verify session can be checkpointed and resumed from a saved copy."""
    recorder = SessionRecorder(session_id="checkpoint-test", seed=99)

    # Record first batch
    for i in range(5):
        recorder.record(kind="step", payload={"step": i}, timestamp_s=1000 + i)

    # Save checkpoint and session
    with tempfile.TemporaryDirectory() as tmpdir:
        path1 = Path(tmpdir) / "session1.jsonl"
        recorder.save(path1)
        checkpoint = recorder.checkpoint()
        assert checkpoint["next_seq"] == 5

        # Load the saved session
        loaded = SessionRecorder.load(path1)
        assert loaded.entry_count() == 5

        # Resume from checkpoint (verify the loaded session matches the checkpoint)
        resumed = SessionRecorder.resume_from(checkpoint, loaded)
        assert resumed.entry_count() == 5
        assert resumed.verify()

        # Continue recording on the resumed session
        for i in range(5, 10):
            resumed.record(kind="step", payload={"step": i}, timestamp_s=1000 + i)

        assert resumed.entry_count() == 10
        assert resumed.verify()


def test_preference_learning_from_feedback():
    """Verify preference learning from synthetic feedback signals."""
    # Create a preference profile and learn from feedback
    profile = PreferenceProfile()

    # Simulate feedback signals
    now_s = 1000000
    profile.add_feedback("tone", "concise", signal="up", timestamp_s=now_s - 1000, confidence=0.9)
    profile.add_feedback(
        "tone", "concise", signal="accept", timestamp_s=now_s - 500, confidence=0.8
    )
    profile.add_feedback(
        "tone", "verbose", signal="decline", timestamp_s=now_s - 200, confidence=0.7
    )
    profile.add_feedback("format", "markdown", signal="up", timestamp_s=now_s - 100, confidence=0.9)

    # Get current preferences
    prefs = profile.current_preferences(now_s=now_s, min_confidence=0.1)

    # Verify preferences were learned
    assert "tone" in prefs, "Should have learned tone preference"
    tone_value, tone_conf = prefs["tone"]
    assert tone_value == "concise", "Should prefer concise tone"
    assert 0.0 <= tone_conf <= 1.0, "Confidence should be in [0, 1]"


def test_preference_profile_cold_start_defaults():
    """Verify preference profile returns empty when no feedback given."""
    profile = PreferenceProfile()
    now_s = 1000000

    # No feedback yet
    prefs = profile.current_preferences(now_s=now_s, min_confidence=0.1)
    assert prefs == {}, "Empty profile should return no preferences"

    # With high min_confidence, even learned prefs might not show
    profile.add_feedback("tone", "concise", signal="up", timestamp_s=now_s, confidence=0.3)
    prefs_high = profile.current_preferences(now_s=now_s, min_confidence=0.9)
    assert "tone" not in prefs_high, "Low confidence should be filtered"
