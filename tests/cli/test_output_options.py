"""
The shared CLI helpers.

Output rendering, downloads, JSON input, confirmation, and the entry point's
error handling.
"""

import json
import subprocess
import sys
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from egnyte_client.cli.options import confirm, parse_json, yes_option
from egnyte_client.cli.output import render, write_bytes
from egnyte_client.schemas.auth import TokenInfo


def _capture(fn: object) -> str:
    @click.command()
    def command() -> None:
        fn()  # type: ignore[operator]

    return CliRunner().invoke(command).output


# =============================================================================
# TEST: render
# =============================================================================


def test_render_prints_models_as_json_with_field_names() -> None:
    info = TokenInfo.model_validate(
        {"clientId": "id", "username": "jdoe", "domain": "acme", "scopes": []}
    )

    output = _capture(lambda: render(info, exclude={"scopes"}))

    assert json.loads(output) == {
        "client_id": "id",
        "username": "jdoe",
        "domain": "acme",
    }


def test_render_prints_lists_and_mappings_as_json() -> None:
    info = TokenInfo(client_id="id", username="jdoe", domain="acme")

    assert json.loads(_capture(lambda: render([info])))[0]["username"] == "jdoe"
    assert json.loads(_capture(lambda: render({"a": 1}))) == {"a": 1}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("plain text", "plain text\n"),
        (42, "42\n"),
        (True, "true\n"),
        (False, "false\n"),
        (None, ""),
    ],
)
def test_render_prints_scalars_bare(value: object, expected: str) -> None:
    assert _capture(lambda: render(value)) == expected  # type: ignore[arg-type]


# =============================================================================
# TEST: write_bytes
# =============================================================================


def test_write_bytes_to_a_file(tmp_path: Path) -> None:
    target = tmp_path / "out.bin"

    @click.command()
    def command() -> None:
        write_bytes(b"\x00\x01data", str(target))

    result = CliRunner().invoke(command)

    assert target.read_bytes() == b"\x00\x01data"
    assert "Wrote 6 bytes" in result.stderr
    assert result.stdout == ""


def test_write_bytes_to_stdout_keeps_binary_content() -> None:
    @click.command()
    def command() -> None:
        write_bytes(b"\x00\xffdata", "-")

    assert CliRunner().invoke(command).stdout_bytes == b"\x00\xffdata"


# =============================================================================
# TEST: parse_json and confirm
# =============================================================================


def test_parse_json() -> None:
    assert parse_json('{"a": [1, 2]}') == {"a": [1, 2]}
    assert parse_json(None) is None
    with pytest.raises(click.BadParameter, match="expected a JSON document"):
        parse_json("{not json")


def test_confirm_aborts_on_no_and_is_skipped_by_yes() -> None:
    calls: list[str] = []

    @click.command()
    @yes_option
    def command(yes: bool) -> None:
        confirm(yes, "Delete /Shared/x?")
        calls.append("ran")

    declined = CliRunner().invoke(command, input="n\n")
    assert declined.exit_code == 1
    assert "Delete /Shared/x?" in declined.stderr
    assert declined.stdout == ""
    assert calls == []

    skipped = CliRunner().invoke(command, ["-y"])
    assert skipped.exit_code == 0
    assert calls == ["ran"]


# =============================================================================
# TEST: main
# =============================================================================


def test_main_reports_package_errors_without_a_traceback() -> None:
    # A missing token raises EgnyteConfigurationError before any request.
    result = subprocess.run(
        [sys.executable, "-m", "egnyte_client.cli", "auth", "whoami"],
        capture_output=True,
        text=True,
        env={"PATH": "", "EGNYTE_DOMAIN": "acme"},
    )

    assert result.returncode == 1
    assert result.stderr.strip() == "Error: No Egnyte access token provided"
    assert "Traceback" not in result.stderr
