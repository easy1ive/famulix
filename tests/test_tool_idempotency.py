"""Test tool idempotency key generation."""

from famulix.tool_idempotency import generate_idempotency_key, is_idempotent_tool


def test_idempotency_key_deterministic():
    key1 = generate_idempotency_key("fetch", {"url": "http://example.com"}, seed=42)
    key2 = generate_idempotency_key("fetch", {"url": "http://example.com"}, seed=42)

    assert key1 == key2


def test_idempotency_key_varies_with_args():
    key1 = generate_idempotency_key("fetch", {"url": "http://a.com"}, seed=42)
    key2 = generate_idempotency_key("fetch", {"url": "http://b.com"}, seed=42)

    assert key1 != key2


def test_idempotency_key_varies_with_seed():
    key1 = generate_idempotency_key("fetch", {"url": "http://a.com"}, seed=1)
    key2 = generate_idempotency_key("fetch", {"url": "http://a.com"}, seed=2)

    assert key1 != key2


def test_is_idempotent_tool():
    assert is_idempotent_tool("read_file")
    assert is_idempotent_tool("query")
    assert not is_idempotent_tool("send_email")
    assert not is_idempotent_tool("delete_file")
