"""Tests for privacy redaction round-trip in reversible mode."""

from famulix.privacy import redact_text, restore_text


def test_redact_email_reversible():
    text = "Contact me at user@example.com for details."
    redacted, mapping = redact_text(text, mode="reversible")
    assert "user@example.com" not in redacted
    restored = restore_text(redacted, mapping)
    assert restored == text


def test_redact_phone_reversible():
    text = "Call me at 555-867-5309 anytime."
    redacted, mapping = redact_text(text, mode="reversible")
    assert "555-867-5309" not in redacted
    restored = restore_text(redacted, mapping)
    assert restored == text


def test_redact_irreversible_not_restorable():
    text = "Email: admin@corp.io"
    redacted, mapping = redact_text(text, mode="irreversible")
    assert "admin@corp.io" not in redacted
    assert mapping is None or mapping == {}


def test_redact_no_pii_unchanged():
    text = "The weather is nice today."
    redacted, mapping = redact_text(text, mode="reversible")
    assert redacted == text


def test_redact_multiple_emails():
    text = "Send to alice@example.com and bob@example.com."
    redacted, mapping = redact_text(text, mode="reversible")
    assert "alice@example.com" not in redacted
    assert "bob@example.com" not in redacted
    restored = restore_text(redacted, mapping)
    assert restored == text


def test_redact_deterministic():
    text = "Contact user@test.com"
    r1, m1 = redact_text(text, mode="reversible")
    r2, m2 = redact_text(text, mode="reversible")
    assert r1 == r2
