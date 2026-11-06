"""
Coverage of the `auth` commands against a mock-transport client.

Named apart from `tests/test_auth.py`, as the test directories are not
packages and pytest needs unique module names.
"""

import json

import click
import httpx
from click.testing import CliRunner
from conftest import respond

from egnyte_client.cli.commands import auth
from egnyte_client.cli.context import ClientContext
from egnyte_client.client import EgnyteClient

TOKEN_INFO = {
    "clientId": "id",
    "username": "jdoe",
    "domain": "acme",
    "scopes": ["Egnyte.filesystem", "Egnyte.link"],
}


def test_token_info() -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return respond(TOKEN_INFO)

    client = EgnyteClient(domain="acme", access_token="token")
    client.close()
    client._http = httpx.Client(transport=httpx.MockTransport(handler))
    context = ClientContext()
    context._client = client

    @click.group()
    @click.pass_context
    def root(ctx: click.Context) -> None:
        ctx.obj = context

    root.add_command(auth.group)

    result = CliRunner().invoke(root, ["auth", "token-info"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "client_id": "id",
        "username": "jdoe",
        "domain": "acme",
        "scopes": ["Egnyte.filesystem", "Egnyte.link"],
    }
    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/whoami"


def test_no_token_grant_commands() -> None:
    assert set(auth.group.commands) == {"whoami", "token-info"}
