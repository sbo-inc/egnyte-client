from datetime import datetime

import click

from egnyte_client.cli.context import ClientContext
from egnyte_client.cli.group import CommonClickGroup
from egnyte_client.cli.options import confirm, paging_options, yes_option
from egnyte_client.cli.output import render


@click.group(name="comments", cls=CommonClickGroup)
def group() -> None:
    """
    Add, list, inspect, and delete comments on files.
    """


@group.command(name="create")
@click.argument("path")
@click.argument("message")
@click.pass_obj
def create(ctx: ClientContext, path: str, message: str) -> None:
    """
    Add a comment to a file.
    """
    render(ctx.client.create_comment(path, message))


@group.command(name="list")
@click.option(
    "--path",
    "filter_by_path",
    default=None,
    help="Comments on this file. Without it, every comment (admins only).",
)
@click.option(
    "--start-time",
    "filter_by_start_time",
    type=click.DateTime(),
    default=None,
    help="Made at or after (YYYY-MM-DD or ISO 8601, UTC).",
)
@click.option(
    "--end-time",
    "filter_by_end_time",
    type=click.DateTime(),
    default=None,
    help="Made before (YYYY-MM-DD or ISO 8601, UTC).",
)
@paging_options
@click.pass_obj
def list_(
    ctx: ClientContext,
    filter_by_path: str | None,
    filter_by_start_time: datetime | None,
    filter_by_end_time: datetime | None,
    offset: int | None,
    count: int | None,
) -> None:
    """
    List one page of comments, on one file or across the domain.
    """
    if (
        filter_by_start_time is not None
        and filter_by_end_time is not None
        and filter_by_start_time >= filter_by_end_time
    ):
        raise click.UsageError("--start-time must be before --end-time.")

    render(
        ctx.client.list_comments(
            filter_by_path=filter_by_path,
            filter_by_start_time=filter_by_start_time,
            filter_by_end_time=filter_by_end_time,
            offset=offset,
            count=count,
        )
    )


@group.command(name="get")
@click.argument("comment_id")
@click.pass_obj
def get(ctx: ClientContext, comment_id: str) -> None:
    """
    Show a comment.
    """
    render(ctx.client.get_comment(comment_id))


@group.command(name="delete")
@click.argument("comment_id")
@yes_option
@click.pass_obj
def delete(ctx: ClientContext, comment_id: str, yes: bool) -> None:
    """
    Delete a comment.
    """
    confirm(yes, f"Delete comment {comment_id}?")
    ctx.client.delete_comment(comment_id)
    click.echo(f"Deleted comment {comment_id}", err=True)
