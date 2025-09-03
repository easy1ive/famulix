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


@pytest.mark.parametrize(
    "argv",
    [
        ["demo", "--days", "0"],
        ["eval", "--budget", "-1"],
        ["recall", "-k", "nope"],
        ["context", "--days", "-4"],
    ],
)
def test_positive_cli_limits_fail_with_argument_error(argv: list[str], capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(argv)

    assert excinfo.value.code == 2
    assert "greater than zero" in capsys.readouterr().err


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
    assert data["schema_version"] == 1
    assert data["nodes"]
    assert data["edges"]


def test_export_jsonl(capsys):
    rc = main(["export", "--format", "jsonl"])
    assert rc == 0
    captured = capsys.readouterr()
    lines = [line for line in captured.out.strip().split("\n") if line]
    assert len(lines) > 0
    import json

    records = [json.loads(line) for line in lines]
    assert records[0] == {"record_type": "graph", "schema_version": 1}
    assert {record["record_type"] for record in records[1:]} == {"node", "edge"}


def test_ingest_reads_and_projects_event_envelopes(tmp_path, capsys) -> None:
    from famulix.events import note_event

    event = note_event(1_700_000_000, "notes", "Alice will lead the review")
    path = tmp_path / "events.jsonl"
    path.write_text(event.to_envelope().to_jsonl_line() + "\n", encoding="utf-8")

    assert main(["ingest", str(path)]) == 0
    output = capsys.readouterr().out
    assert "Ingested 1 events" in output
    assert "Facts:    1" in output


def test_ingest_reports_invalid_event_file(tmp_path, capsys) -> None:
    path = tmp_path / "invalid.jsonl"
    path.write_text("not json\n", encoding="utf-8")

    assert main(["ingest", str(path)]) == 2
    assert "famulix ingest:" in capsys.readouterr().err


def test_replay_and_diff_verify_session_files(tmp_path, capsys) -> None:
    import json

    from famulix.session import SessionRecorder

    left = SessionRecorder(session_id="fixture", seed=9)
    left.record("decision", {"selection": "agenda"}, 12)
    right = SessionRecorder(session_id="fixture", seed=9)
    right.record("decision", {"selection": "agenda"}, 12)
    path_a = tmp_path / "a.jsonl"
    path_b = tmp_path / "b.jsonl"
    left.save(path_a)
    right.save(path_b)

    assert main(["replay", str(path_a)]) == 0
    assert "Verified session fixture: 1 frames" in capsys.readouterr().out
    assert main(["diff", str(path_a), str(path_b)]) == 0
    assert json.loads(capsys.readouterr().out)["identical"] is True


def test_replay_rejects_corrupt_session_file(tmp_path, capsys) -> None:
    path = tmp_path / "corrupt.jsonl"
    path.write_text("{}\n", encoding="utf-8")

    assert main(["replay", str(path)]) == 2
    assert "famulix replay:" in capsys.readouterr().err


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


def test_cli_unknown_subcommand_exits_with_error() -> None:
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "famulix.cli", "nonexistent_command"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


def test_cli_help_exits_cleanly() -> None:
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "famulix.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "famulix" in result.stdout.lower() or "usage" in result.stdout.lower()


def test_cli_ingest_requires_path_argument() -> None:
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "famulix.cli", "ingest"],
        capture_output=True,
        text=True,
    )
    assert (
        result.returncode != 0
        or "required" in result.stderr.lower()
        or "error" in result.stderr.lower()
    )


def test_cli_demo_runs_end_to_end() -> None:
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "famulix.cli", "demo"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0
    assert len(result.stdout) > 0
