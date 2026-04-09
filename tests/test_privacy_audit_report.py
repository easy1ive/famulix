"""Test privacy audit report generation."""

from famulix.privacy import generate_privacy_audit_report


def test_privacy_audit_report_no_pii():
    """Verify report handles texts with no PII."""
    texts = [
        "This is a normal note about a meeting.",
        "Another note without sensitive information.",
    ]

    report = generate_privacy_audit_report(texts)

    assert report["total_texts"] == 2
    assert report["texts_with_pii"] == 0
    assert report["pii_types_found"] == {}
    assert report["redacted_texts"] == texts


def test_privacy_audit_report_with_pii():
    """Verify report detects and redacts PII."""
    texts = [
        "Contact me at alice@example.com for details.",
        "My phone number is +86 138 1234 5678.",
        "No PII here.",
    ]

    report = generate_privacy_audit_report(texts, redaction_mode="reversible")

    assert report["total_texts"] == 3
    assert report["texts_with_pii"] >= 1
    assert len(report["pii_types_found"]) > 0
    assert len(report["redacted_texts"]) == 3
    assert report["redaction_mode"] == "reversible"


def test_privacy_audit_report_irreversible():
    """Verify irreversible redaction mode is reported correctly."""
    texts = ["Email: bob@example.com"]

    report = generate_privacy_audit_report(texts, redaction_mode="irreversible")

    assert report["redaction_mode"] == "irreversible"
    assert report["texts_with_pii"] >= 1
