import click

from egnyte_client.cli.context import ClientContext
from egnyte_client.cli.group import CommonClickGroup
from egnyte_client.cli.output import render


@click.group(name="auth", cls=CommonClickGroup)
def group() -> None:
    """
    Inspect the access token.
    """


@group.command(name="whoami")
@click.pass_obj
def whoami(ctx: ClientContext) -> None:
    """
    Show the user the access token belongs to.
    """
    render(ctx.client.get_user_info())


@group.command(name="token-info")
@click.pass_obj
def token_info(ctx: ClientContext) -> None:
    """
    Show what the access token grants: its API key, user, domain, and scopes.

    Empty `scopes` means unscoped (global) access.
    """
    render(ctx.client.get_token_info())
