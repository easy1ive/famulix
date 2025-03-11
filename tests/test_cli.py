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
