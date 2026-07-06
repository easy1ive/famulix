"""Test encoding session segmentation configuration."""

from famulix.encoding import configure_session_segmentation


def test_session_segmentation_config_defaults():
    config = configure_session_segmentation()

    assert config["max_gap_seconds"] > 0
    assert config["min_events_per_session"] >= 1


def test_session_segmentation_config_custom():
    config = configure_session_segmentation(
        max_gap_seconds=1800,
        min_events_per_session=3,
    )

    assert config["max_gap_seconds"] == 1800
    assert config["min_events_per_session"] == 3
