#!/usr/bin/env python3
"""Example 07: Session record and replay demonstration."""

from famulix.session import SessionRecorder


def main() -> None:
    """Run session replay demonstration."""
    print("=== Session Record and Replay Demo ===\n")

    recorder = SessionRecorder(seed=42)
    recorder.record_event("user_query", {"text": "What's on my calendar?"})
    recorder.record_decision("tool_selection", {"tool": "calendar_lookup"})

    print("Recorded session:")
    print(f"  Events: {recorder.event_count()}")
    print(f"  Decisions: {recorder.decision_count()}")
    print(f"  Digest: {recorder.digest()}\n")
    print("=== Demo Complete ===")


if __name__ == "__main__":
    main()
