"""Test privacy redaction roundtrip for reversible mode."""

from famulix.privacy import redact_text, restore_text


def test_redaction_roundtrip_email():
    text = "Contact me at test@example.com for details"

    redacted, mapping = redact_text(text, mode="reversible")

    assert "test@example.com" not in redacted
    assert "<PII:" in redacted

    restored = restore_text(redacted, mapping)

    assert restored == text


def test_redaction_roundtrip_phone():
    text = "Call me at 555-123-4567"

    redacted, mapping = redact_text(text, mode="reversible")

    assert "555-123-4567" not in redacted

    restored = restore_text(redacted, mapping)

    assert restored == text


def test_redaction_irreversible_no_mapping():
    text = "Contact me at test@example.com"

    redacted, mapping = redact_text(text, mode="irreversible")

    assert "test@example.com" not in redacted
    assert mapping == {}
