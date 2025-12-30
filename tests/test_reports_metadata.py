"""Test report metadata summary."""

from famulix.reports import report_metadata_summary


def test_empty_metadata():
    """Empty metadata should have unknown values."""
    result = report_metadata_summary({})
    assert result["version"] == "unknown"
    assert result["generated_at"] == "unknown"


def test_metadata_summary():
    """Should extract metadata fields."""
    metadata = {
        "version": "0.1.1",
        "generated_at": "2026-11-12T10:00:00",
        "seed": "42",
    }
    result = report_metadata_summary(metadata)
    assert result["version"] == "0.1.1"
    assert result["seed"] == "42"
