"""
The package's logging follows the library pattern.

Importing attaches only a NullHandler, building a client never touches levels
or handlers, and only the CLI's `--log` configures output.
"""

import logging
import subprocess
import sys
from collections.abc import Callable, Iterator

import httpx
import pytest
from click.testing import CliRunner
from conftest import respond

from egnyte_client.async_client import AsyncEgnyteClient
from egnyte_client.cli import LOG_HANDLER_NAME, cli
from egnyte_client.client import EgnyteClient

PACKAGE = logging.getLogger("egnyte_client")


@pytest.fixture(autouse=True)
def restore_logger() -> Iterator[None]:
    """
    Undo any handler or level a test leaves on the package logger.
    """
    handlers, level = list(PACKAGE.handlers), PACKAGE.level
    yield
    PACKAGE.handlers[:] = handlers
    PACKAGE.setLevel(level)


def test_import_attaches_only_a_null_handler() -> None:
    # A fresh interpreter, so no earlier test has touched the logger.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import logging, egnyte_client;"
            "logger = logging.getLogger('egnyte_client');"
            "print([type(h).__name__ for h in logger.handlers], logger.level)",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "['NullHandler'] 0"


def test_building_clients_leaves_the_logger_alone() -> None:
    PACKAGE.setLevel(logging.DEBUG)
    handlers = list(PACKAGE.handlers)

    EgnyteClient("acme", "t")
    AsyncEgnyteClient("acme", "t")

    assert PACKAGE.level == logging.DEBUG
    assert PACKAGE.handlers == handlers


def test_requests_log_at_debug_and_retries_at_info(
    make_client: Callable[..., EgnyteClient], caplog: pytest.LogCaptureFixture
) -> None:
    spike = {
        "fault": {"detail": {"errorcode": "policies.ratelimit.SpikeArrestViolation"}}
    }
    responses = iter([respond(spike, 429), respond({"id": 1, "username": "jdoe"})])
    client = make_client(lambda request: next(responses))

    with caplog.at_level(logging.DEBUG, logger="egnyte_client"):
        client.get_user_info()

    levels = {record.levelname: record.getMessage() for record in caplog.records}
    assert "rate limited" in levels["INFO"]
    assert levels["DEBUG"] == "GET /pubapi/v1/userinfo -> 200"


def test_nothing_is_printed_without_configuration(
    make_client: Callable[..., EgnyteClient], capsys: pytest.CaptureFixture[str]
) -> None:
    make_client(lambda request: respond({"id": 1, "username": "jdoe"})).get_user_info()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_cli_log_flag_writes_requests_to_stderr_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return respond({"id": 1, "username": "jdoe"})

    original = httpx.Client.__init__

    def mocked(self: httpx.Client, *args: object, **kwargs: object) -> None:
        kwargs["transport"] = httpx.MockTransport(handler)
        original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(httpx.Client, "__init__", mocked)
    monkeypatch.setenv("EGNYTE_DOMAIN", "acme")
    monkeypatch.setenv("EGNYTE_ACCESS_TOKEN", "t")

    for _ in range(2):  # a second run in one process must not duplicate lines
        result = CliRunner().invoke(cli, ["--log", "auth", "whoami"])
        assert result.exit_code == 0, result.output
        assert result.stderr.count("egnyte-client: GET /pubapi/v1/userinfo -> 200") == 1

    named = [h for h in PACKAGE.handlers if h.get_name() == LOG_HANDLER_NAME]
    assert len(named) == 1
