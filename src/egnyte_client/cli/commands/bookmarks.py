import click

from egnyte_client.cli.context import ClientContext
from egnyte_client.cli.group import CommonClickGroup
from egnyte_client.cli.options import confirm, exactly_one, paging_options, yes_option
from egnyte_client.cli.output import render


@click.group(name="bookmarks", cls=CommonClickGroup)
def group() -> None:
    """
    Bookmark folders, and list, inspect, and delete your bookmarks.
    """


@group.command(name="create")
@click.argument("path", required=False)
@click.option(
    "--folder-id",
    default=None,
    help="Bookmark the folder with this ID, in place of PATH.",
)
@click.pass_obj
def create(ctx: ClientContext, path: str | None, folder_id: str | None) -> None:
    """
    Bookmark a folder, by PATH or by --folder-id (exactly one).
    """
    exactly_one(("PATH", path), ("--folder-id", folder_id))

    render(ctx.client.create_bookmark(path=path, folder_id=folder_id))


@group.command(name="list")
@paging_options
@click.pass_obj
def list_(ctx: ClientContext, offset: int | None, count: int | None) -> None:
    """
    List one page of your bookmarks.
    """
    render(ctx.client.list_bookmarks(offset=offset, count=count))


@group.command(name="get")
@click.argument("bookmark_id", type=int)
@click.pass_obj
def get(ctx: ClientContext, bookmark_id: int) -> None:
    """
    Show a bookmark.
    """
    render(ctx.client.get_bookmark(bookmark_id))


@group.command(name="delete")
@click.argument("bookmark_id", type=int)
@yes_option
@click.pass_obj
def delete(ctx: ClientContext, bookmark_id: int, yes: bool) -> None:
    """
    Delete a bookmark; the folder itself is untouched.
    """
    confirm(yes, f"Delete bookmark {bookmark_id}?")
    ctx.client.delete_bookmark(bookmark_id)
    click.echo(f"Deleted bookmark {bookmark_id}", err=True)
