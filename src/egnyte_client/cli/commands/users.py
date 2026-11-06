import click

from egnyte_client.cli.context import ClientContext
from egnyte_client.cli.group import CommonClickGroup
from egnyte_client.cli.options import confirm, scim_paging_options, yes_option
from egnyte_client.cli.output import render

AUTH_TYPES = click.Choice(["egnyte", "sso", "ad"])
USER_TYPES = click.Choice(["admin", "power", "standard"])


@click.group(name="users", cls=CommonClickGroup)
def group() -> None:
    """
    List, inspect, and manage users.
    """


@group.command(name="list")
@click.option("--user-name", "filter_by_user_name", default=None)
@click.option("--email", "filter_by_email", default=None)
@click.option("--external-id", "filter_by_external_id", default=None)
@scim_paging_options
@click.pass_obj
def list_(
    ctx: ClientContext,
    filter_by_user_name: str | None,
    filter_by_email: str | None,
    filter_by_external_id: str | None,
    start_index: int | None,
    count: int | None,
) -> None:
    """
    List one page of users, optionally filtered by one exact attribute.
    """
    render(
        ctx.client.list_users(
            filter_by_user_name=filter_by_user_name,
            filter_by_email=filter_by_email,
            filter_by_external_id=filter_by_external_id,
            start_index=start_index,
            count=count,
        )
    )


@group.command(name="get")
@click.argument("user_id", type=int)
@click.pass_obj
def get(ctx: ClientContext, user_id: int) -> None:
    """
    Show a user.
    """
    render(ctx.client.get_user(user_id))


@group.command(name="create")
@click.argument("user_name")
@click.option("--email", required=True)
@click.option("--given-name", required=True)
@click.option("--family-name", required=True)
@click.option("--auth-type", type=AUTH_TYPES, required=True)
@click.option("--user-type", type=USER_TYPES, required=True)
@click.option(
    "--send-invite/--no-send-invite",
    default=None,
    help="Email an invitation (always sent for egnyte authentication).",
)
@click.pass_obj
def create(
    ctx: ClientContext,
    user_name: str,
    email: str,
    given_name: str,
    family_name: str,
    auth_type: str,
    user_type: str,
    send_invite: bool | None,
) -> None:
    """
    Create a user.
    """
    render(
        ctx.client.create_user(
            user_name,
            email,
            given_name,
            family_name,
            auth_type=auth_type,  # type: ignore[arg-type]
            user_type=user_type,  # type: ignore[arg-type]
            send_invite=send_invite,
        )
    )


@group.command(name="update")
@click.argument("user_id", type=int)
@click.option("--email", default=None)
@click.option("--given-name", default=None)
@click.option("--family-name", default=None)
@click.option("--active/--inactive", default=None)
@click.option("--user-type", type=USER_TYPES, default=None)
@click.pass_obj
def update(
    ctx: ClientContext,
    user_id: int,
    email: str | None,
    given_name: str | None,
    family_name: str | None,
    active: bool | None,
    user_type: str | None,
) -> None:
    """
    Update a user; only the options given change.
    """
    render(
        ctx.client.update_user(
            user_id,
            email=email,
            given_name=given_name,
            family_name=family_name,
            active=active,
            user_type=user_type,  # type: ignore[arg-type]
        )
    )


@group.command(name="delete")
@click.argument("user_id", type=int)
@yes_option
@click.pass_obj
def delete(ctx: ClientContext, user_id: int, yes: bool) -> None:
    """
    Delete a user.
    """
    confirm(yes, f"Delete user {user_id}?")
    ctx.client.delete_user(user_id)
    click.echo(f"Deleted user {user_id}", err=True)
