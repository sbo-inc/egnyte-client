"""
The command group, its order, and the switch that hides commands.
"""

import click
import pytest
from click.testing import CliRunner

from egnyte_client.cli import cli


def _command_names(output: str) -> list[str]:
    section = output.split("Commands:", 1)[1]
    return [line.split()[0] for line in section.splitlines() if line.startswith("  ")]


def test_lists_commands_in_registration_order() -> None:
    names = _command_names(CliRunner().invoke(cli, ["--help"]).output)

    # The everyday groups come first, ahead of alphabetical order.
    assert names[:3] == ["auth", "fs", "search"]


def test_hides_a_disabled_command_from_the_help(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EGNYTE_CLI_DISABLE", "fs.rm")

    output = CliRunner().invoke(cli, ["fs", "--help"]).output

    assert "rm" not in _command_names(output)
    assert "ls" in _command_names(output)


def test_rejects_a_disabled_command_at_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EGNYTE_CLI_DISABLE", "fs.rm")

    result = CliRunner().invoke(
        cli, ["fs", "rm", "/Shared/x", "--yes"], standalone_mode=False
    )

    assert result.exit_code != 0
    assert isinstance(result.exception, click.UsageError)


def test_hides_a_whole_group(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EGNYTE_CLI_DISABLE", "users, groups")

    names = _command_names(CliRunner().invoke(cli, ["--help"]).output)

    assert "users" not in names
    assert "groups" not in names
    assert "fs" in names


def test_version_names_the_command() -> None:
    output = CliRunner().invoke(cli, ["--version"]).output

    assert output.startswith("egnyte-client, version ")
