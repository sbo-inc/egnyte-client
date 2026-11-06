from datetime import datetime

import click

from egnyte_client.cli.context import ClientContext
from egnyte_client.cli.group import CommonClickGroup
from egnyte_client.cli.options import confirm, paging_options, yes_option
from egnyte_client.cli.output import render

LINK_TYPES = click.Choice(["file", "folder", "upload"])
ACCESSIBILITY = click.Choice(["anyone", "password", "domain", "recipients"])


@click.group(name="links", cls=CommonClickGroup)
def group() -> None:
    """
    Create, list, inspect, and delete shared links.
    """


@group.command(name="list")
@click.option("--path", "filter_by_path", default=None, help="Links to this path.")
@click.option(
    "--username", "filter_by_username", default=None, help="Links made by this user."
)
@click.option("--type", "filter_by_type", type=LINK_TYPES, default=None)
@click.option(
    "--accessibility", "filter_by_accessibility", type=ACCESSIBILITY, default=None
)
@click.option(
    "--created-after",
    "filter_by_created_after",
    type=click.DateTime(),
    default=None,
    help="Earliest creation time (YYYY-MM-DD or ISO 8601).",
)
@click.option(
    "--created-before",
    "filter_by_created_before",
    type=click.DateTime(),
    default=None,
    help="Latest creation time (YYYY-MM-DD or ISO 8601).",
)
@paging_options
@click.pass_obj
def list_(
    ctx: ClientContext,
    filter_by_path: str | None,
    filter_by_username: str | None,
    filter_by_type: str | None,
    filter_by_accessibility: str | None,
    filter_by_created_after: datetime | None,
    filter_by_created_before: datetime | None,
    offset: int | None,
    count: int | None,
) -> None:
    """
    List links, with their details.
    """
    render(
        ctx.client.list_links(
            filter_by_path=filter_by_path,
            filter_by_username=filter_by_username,
            filter_by_type=filter_by_type,  # type: ignore[arg-type]
            filter_by_accessibility=filter_by_accessibility,  # type: ignore[arg-type]
            filter_by_created_after=filter_by_created_after,
            filter_by_created_before=filter_by_created_before,
            offset=offset,
            count=count,
        )
    )


@group.command(name="get")
@click.argument("link_id")
@click.pass_obj
def get(ctx: ClientContext, link_id: str) -> None:
    """
    Show a link's details.
    """
    render(ctx.client.get_link(link_id))


@group.command(name="create")
@click.argument("path")
@click.option("--type", "type_", type=LINK_TYPES, required=True)
@click.option("--accessibility", type=ACCESSIBILITY, default=None)
@click.option(
    "--expiry-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="Expire the link on this date (YYYY-MM-DD).",
)
@click.option(
    "--expiry-clicks",
    type=click.IntRange(1, 10),
    default=None,
    help="Expire the link after this many opens.",
)
@click.option(
    "--notify", is_flag=True, default=None, help="Notify me when the link is opened."
)
@click.pass_obj
def create(
    ctx: ClientContext,
    path: str,
    type_: str,
    accessibility: str | None,
    expiry_date: datetime | None,
    expiry_clicks: int | None,
    notify: bool | None,
) -> None:
    """
    Create a link to a file or folder.
    """
    render(
        ctx.client.create_link(
            path,
            type_,  # type: ignore[arg-type]
            accessibility=accessibility,  # type: ignore[arg-type]
            expiry_date=expiry_date.date() if expiry_date else None,
            expiry_clicks=expiry_clicks,
            notify=notify,
        )
    )


@group.command(name="delete")
@click.argument("link_id")
@yes_option
@click.pass_obj
def delete(ctx: ClientContext, link_id: str, yes: bool) -> None:
    """
    Delete a link; anyone holding its URL loses access.
    """
    confirm(yes, f"Delete link {link_id}?")
    ctx.client.delete_link(link_id)
    click.echo(f"Deleted link {link_id}", err=True)
