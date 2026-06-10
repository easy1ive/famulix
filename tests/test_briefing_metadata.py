"""Test briefing run metadata embedding."""

from famulix.briefing import embed_run_metadata


def test_embed_run_metadata_includes_version():
    meta = embed_run_metadata(
        version="0.1.4",
        seed=42,
        config_hash="abc123",
    )

    assert meta["version"] == "0.1.4"
    assert meta["seed"] == 42
    assert meta["config_hash"] == "abc123"


def test_embed_run_metadata_deterministic():
    m1 = embed_run_metadata(version="0.1.4", seed=42, config_hash="x")
    m2 = embed_run_metadata(version="0.1.4", seed=42, config_hash="x")

    assert m1 == m2
