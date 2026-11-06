import click

from egnyte_client.cli.context import ClientContext
from egnyte_client.cli.group import CommonClickGroup
from egnyte_client.cli.options import confirm, scim_paging_options, yes_option
from egnyte_client.cli.output import render


@click.group(name="groups", cls=CommonClickGroup)
def group() -> None:
    """
    List, inspect, and manage groups.
    """


@group.command(name="list")
@click.option("--name", "filter_by_name", default=None, help="Exact group name.")
@click.option(
    "--name-contains", "filter_by_name_contains", default=None, help="Name substring."
)
@click.option(
    "--name-starts-with",
    "filter_by_name_starts_with",
    default=None,
    help="Name prefix.",
)
@scim_paging_options
@click.pass_obj
def list_(
    ctx: ClientContext,
    filter_by_name: str | None,
    filter_by_name_contains: str | None,
    filter_by_name_starts_with: str | None,
    start_index: int | None,
    count: int | None,
) -> None:
    """
    List one page of custom groups.
    """
    render(
        ctx.client.list_groups(
            filter_by_name=filter_by_name,
            filter_by_name_contains=filter_by_name_contains,
            filter_by_name_starts_with=filter_by_name_starts_with,
            start_index=start_index,
            count=count,
        )
    )


@group.command(name="get")
@click.argument("group_id")
@click.pass_obj
def get(ctx: ClientContext, group_id: str) -> None:
    """
    Show a group with its members.
    """
    render(ctx.client.get_group(group_id))


@group.command(name="create")
@click.argument("display_name")
@click.option(
    "--member",
    "member_ids",
    type=int,
    multiple=True,
    required=True,
    help="Member user ID (repeatable; at least one).",
)
@click.option("--owner", "owners", multiple=True, help="Owner username (repeatable).")
@click.pass_obj
def create(
    ctx: ClientContext,
    display_name: str,
    member_ids: tuple[int, ...],
    owners: tuple[str, ...],
) -> None:
    """
    Create a group.
    """
    render(
        ctx.client.create_group(
            display_name, list(member_ids), owners=list(owners) or None
        )
    )


@group.command(name="update")
@click.argument("group_id")
@click.option("--name", "display_name", default=None, help="Rename the group.")
@click.option(
    "--add-member", "add_member_ids", type=int, multiple=True, help="User ID to add."
)
@click.option(
    "--remove-member",
    "remove_member_ids",
    type=int,
    multiple=True,
    help="User ID to remove.",
)
@click.option(
    "--add-owner", "add_owners", multiple=True, help="Username to add as owner."
)
@click.pass_obj
def update(
    ctx: ClientContext,
    group_id: str,
    display_name: str | None,
    add_member_ids: tuple[int, ...],
    remove_member_ids: tuple[int, ...],
    add_owners: tuple[str, ...],
) -> None:
    """
    Rename a group, or add and remove members and owners.
    """
    render(
        ctx.client.update_group(
            group_id,
            display_name=display_name,
            add_member_ids=list(add_member_ids) or None,
            remove_member_ids=list(remove_member_ids) or None,
            add_owners=list(add_owners) or None,
        )
    )


@group.command(name="replace")
@click.argument("group_id")
@click.argument("display_name")
@click.option(
    "--member",
    "member_ids",
    type=int,
    multiple=True,
    required=True,
    help="Member user ID (repeatable). Members not listed are removed.",
)
@click.option(
    "--owner", "owners", multiple=True, help="Owner username to add (repeatable)."
)
@yes_option
@click.pass_obj
def replace(
    ctx: ClientContext,
    group_id: str,
    display_name: str,
    member_ids: tuple[int, ...],
    owners: tuple[str, ...],
    yes: bool,
) -> None:
    """
    Overwrite a group's name and full membership.

    Every current member not given with --member is removed; use `update` to
    add or remove members one at a time.
    """
    confirm(
        yes, f"Replace the members of group {group_id} with {len(member_ids)} listed?"
    )
    render(
        ctx.client.replace_group(
            group_id, display_name, list(member_ids), owners=list(owners) or None
        )
    )


@group.command(name="delete")
@click.argument("group_id")
@yes_option
@click.pass_obj
def delete(ctx: ClientContext, group_id: str, yes: bool) -> None:
    """
    Delete a group.
    """
    confirm(yes, f"Delete group {group_id}?")
    ctx.client.delete_group(group_id)
    click.echo(f"Deleted group {group_id}", err=True)
