"""Tests for the famulix CLI."""

from __future__ import annotations

import pytest

from famulix.cli import build_parser, main


def test_build_parser_returns_parser():
    parser = build_parser()
    assert parser is not None
    assert parser.prog == "famulix"


def test_no_args_prints_help():
    rc = main([])
    assert rc == 0


def test_version_flag():
    import sys
    from io import StringIO

    from famulix import __version__

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        rc = main(["--version"])
        output = sys.stdout.getvalue().strip()
    finally:
        sys.stdout = old_stdout
    assert rc == 0
    assert output == __version__


def test_unknown_command_returns_error():
    with pytest.raises(SystemExit) as excinfo:
        main(["nonexistent_command"])
    assert excinfo.value.code == 2


def test_demo_command_runs(capsys):
    rc = main(["demo"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "famulix demo" in captured.out.lower() or "demo" in captured.out.lower()


def test_recall_command_returns_zero(capsys):
    rc = main(["recall"])
    assert rc == 0


def test_brief_command_returns_zero(capsys):
    rc = main(["brief"])
    assert rc == 0


def test_eval_command_returns_zero(capsys):
    rc = main(["eval"])
    assert rc == 0


def test_subcommand_help_does_not_crash():
    with pytest.raises(SystemExit) as excinfo:
        main(["demo", "--help"])
    assert excinfo.value.code == 0


def test_demo_json_flag():
    import json
    import sys
    from io import StringIO

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        rc = main(["demo", "--days", "3", "--json"])
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout
    assert rc == 0
    data = json.loads(output)
    assert "persona_id" in data
    assert "recall_at_k" in data


def test_eval_json_flag():
    import json
    import sys
    from io import StringIO

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        rc = main(["eval", "--days", "3", "--json"])
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout
    assert rc == 0
    data = json.loads(output)
    assert "contradiction_accuracy" in data
    assert "citation_coverage" in data


def test_context_command_returns_zero(capsys):
    rc = main(["context", "test query", "--days", "3"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "context" in captured.out.lower()


def test_remember_command(capsys):
    rc = main(["remember", "my fact", "fact body text"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Memory id" in captured.out


def test_forget_command(capsys):
    rc = main(["forget", "mem_test123"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "mem_test123" in captured.out


def test_privacy_detect_mode(capsys):
    rc = main(["privacy", "email me at test@example.com", "--mode", "detect"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "PII" in captured.out or "email" in captured.out.lower()


def test_privacy_redact_mode(capsys):
    rc = main(["privacy", "call 555-123-4567", "--mode", "redact"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Redacted" in captured.out


def test_export_json(capsys):
    rc = main(["export", "--format", "json"])
    assert rc == 0
    captured = capsys.readouterr()
    import json

    data = json.loads(captured.out)
    assert isinstance(data, list)


def test_export_jsonl(capsys):
    rc = main(["export", "--format", "jsonl"])
    assert rc == 0
    captured = capsys.readouterr()
    lines = [line for line in captured.out.strip().split("\n") if line]
    assert len(lines) > 0
    import json

    for line in lines:
        json.loads(line)  # must be valid JSON per line


def test_demo_with_persona_flag():
    rc = main(["demo", "--persona", "bailey", "--days", "3"])
    assert rc == 0


def test_recall_with_k_flag(capsys):
    rc = main(["recall", "meeting", "-k", "3", "--days", "3"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Top 3" in captured.out


def test_prefs_command(capsys):
    rc = main(["prefs", "--days", "3"])
    assert rc == 0


def test_triggers_command(capsys):
    rc = main(["triggers", "--days", "3"])
    assert rc == 0
