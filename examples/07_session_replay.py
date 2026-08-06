#!/usr/bin/env python3
"""Example 07: Session record and replay demonstration.

Shows how the session recorder captures events, decisions, and tool
calls into a checksummed JSONL log, and how replay produces byte-identical
traces from the same seed and inputs.
"""

import tempfile
from pathlib import Path

from famulix.session import SessionRecorder, session_diff


def main() -> None:
    """Run session replay demonstration."""
    print("=== Session Record and Replay Demo ===\n")

    # Create a recorder with a session id and seed
    recorder = SessionRecorder(session_id="demo-session-001", seed=42)
    recorder.record("user_query", {"text": "What's on my calendar?"}, timestamp_s=1000)
    recorder.record("tool_selection", {"tool": "calendar_lookup"}, timestamp_s=1001)
    recorder.record("tool_result", {"events": ["Meeting at 3pm"]}, timestamp_s=1002)
    recorder.record("response", {"text": "You have a meeting at 3pm."}, timestamp_s=1003)

    print("Recorded session:")
    print(f"  Session ID: {recorder.session_id}")
    print(f"  Entries: {recorder.entry_count()}")
    print(f"  Kinds: {recorder.kinds_seen()}")
    print(f"  Digest: {recorder.digest()}")
    print(f"  Verified: {recorder.verify()}\n")

    # Replay: save and reload, verify byte-equality
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "session.jsonl"
        recorder.save(str(path))
        replayed = SessionRecorder.load(str(path))

    print("Replay verification:")
    print(f"  Digest match: {recorder.digest() == replayed.digest()}")
    print(f"  Entry count match: {recorder.entry_count() == replayed.entry_count()}")
    print(f"  Replayed verified: {replayed.verify()}")

    # Show diff between two sessions
    other = SessionRecorder(session_id="demo-session-002", seed=42)
    other.record("user_query", {"text": "What's the weather?"}, timestamp_s=1000)
    other.record("response", {"text": "Sunny, 22C."}, timestamp_s=1001)
    diff = session_diff(recorder, other)
    print("\nSession diff (001 vs 002):")
    print(f"  Identical: {diff['identical']}")
    print(f"  Length A: {diff['a_length']}, Length B: {diff['b_length']}")
    print(f"  Length diff: {diff['length_diff']}")
    print(f"  First difference at frame: {diff['first_difference']}")

    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    main()
