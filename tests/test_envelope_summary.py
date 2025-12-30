"""Test envelope summary helper."""

from famulix.envelope import Envelope, envelope_summary


def test_empty_envelopes():
    """Empty list should have zero count."""
    result = envelope_summary([])
    assert result["count"] == 0
    assert result["versions"] == []


def test_envelope_summary():
    """Should compute correct statistics."""
    envs = [
        Envelope(schema_version=1, kind="note", payload={"source": "phone"}, checksum="abc"),
        Envelope(schema_version=1, kind="note", payload={"source": "laptop"}, checksum="def"),
    ]
    result = envelope_summary(envs)
    assert result["count"] == 2
    assert 1 in result["versions"]
