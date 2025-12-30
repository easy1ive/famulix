"""Test utility helper functions."""

from famulix.utils import slugify, truncate_text


def test_truncate_short():
    """Short text should not be truncated."""
    assert truncate_text("short", max_length=100) == "short"


def test_truncate_long():
    """Long text should be truncated with ellipsis."""
    result = truncate_text("a" * 200, max_length=100)
    assert len(result) == 100
    assert result.endswith("...")


def test_truncate_exact():
    """Text at exact length should not be truncated."""
    assert truncate_text("a" * 100, max_length=100) == "a" * 100


def test_slugify():
    """Should convert text to slug."""
    assert slugify("Hello World!") == "hello-world"
    assert slugify("  Multiple   Spaces  ") == "multiple-spaces"
    assert slugify("Special @#$ Characters") == "special-characters"
