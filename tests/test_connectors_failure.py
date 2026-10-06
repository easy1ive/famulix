"""Tests for connector hub and graceful failure handling."""

from famulix.connectors import ConnectorHub


def test_empty_hub():
    hub = ConnectorHub(connectors=[])
    batches = hub.collect()
    assert len(batches) == 0


def test_hub_collect_partial_tolerates_failures():
    """collect_partial returns failed sources instead of raising."""
    hub = ConnectorHub(connectors=[])
    batches, failed = hub.collect_partial()
    assert len(batches) == 0
    assert len(failed) == 0


def test_hub_deterministic_empty():
    h1 = ConnectorHub(connectors=[])
    h2 = ConnectorHub(connectors=[])
    b1 = h1.collect()
    b2 = h2.collect()
    assert b1 == b2
