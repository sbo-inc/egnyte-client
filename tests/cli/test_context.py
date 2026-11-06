import subprocess
import sys

import httpx
import pytest

from egnyte_client.cli.context import ClientContext
from egnyte_client.client import DEFAULT_TIMEOUT


def test_client_reads_connection_settings_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EGNYTE_DOMAIN", "acme")
    monkeypatch.setenv("EGNYTE_ACCESS_TOKEN", "token")
    monkeypatch.setenv("EGNYTE_API_HEADERS", '{"X-Trace": "abc"}')

    client = ClientContext().client

    assert client.base_url == "https://acme.egnyte.com"
    assert client.access_token == "token"
    assert client.http.headers["X-Trace"] == "abc"


def test_client_reads_timeout_and_retries_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EGNYTE_API_TIMEOUT", "45")
    monkeypatch.setenv("EGNYTE_API_RETRIES", "2")

    client = ClientContext().client

    assert client.timeout == 45.0
    transport = client.http._transport
    assert isinstance(transport, httpx.HTTPTransport)
    assert transport._pool._retries == 2


def test_client_defaults_without_env() -> None:
    client = ClientContext().client

    assert client.timeout == DEFAULT_TIMEOUT
    assert "X-Trace" not in client.http.headers


def test_client_is_built_once() -> None:
    context = ClientContext()

    assert context.client is context.client


def test_main_reports_errors_without_a_traceback() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "egnyte_client.cli", "auth", "whoami"],
        capture_output=True,
        text=True,
        env={"PATH": ""},
    )

    assert result.returncode == 1
    assert result.stderr.strip() == "Error: No Egnyte domain provided"
