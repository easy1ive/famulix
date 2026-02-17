"""Test factory manifest summary."""

from famulix.factory import HistoryManifest, factory_manifest_summary


def test_manifest_summary():
    """Should extract manifest fields."""
    manifest = HistoryManifest(
        persona_id="alex",
        seed=42,
        days=90,
        start_date="2026-01-01",
        end_date="2026-03-31",
        event_count=500,
    )
    result = factory_manifest_summary(manifest)
    assert result["persona_id"] == "alex"
    assert result["seed"] == 42
    assert result["days"] == 90
    assert result["event_count"] == 500
