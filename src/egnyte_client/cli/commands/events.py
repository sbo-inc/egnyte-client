import click

from egnyte_client.cli.context import ClientContext
from egnyte_client.cli.group import CommonClickGroup
from egnyte_client.cli.output import render

EVENT_TYPES = click.Choice(["file_system", "note", "permission_change"])
SUPPRESS = click.Choice(["app", "user", "none"])


@click.group(name="events", cls=CommonClickGroup)
def group() -> None:
    """
    Read the domain's event stream, one page at a time.

    Run `events cursor` once for a starting ID, then `events list` with it.
    Each page carries `latest_id`, the START_ID for the next call; a script
    loops on that, waiting at least 5 minutes between polls as Egnyte asks.
    """


@group.command(name="cursor")
@click.pass_obj
def cursor(ctx: ClientContext) -> None:
    """
    Show the newest and oldest event IDs in the stream.

    Start `events list` from `latest_event_id` to see what happens from now on.
    """
    render(ctx.client.get_event_cursor())


@group.command(name="list")
@click.argument("start_id", type=int)
@click.option(
    "--count",
    type=click.IntRange(1, 100),
    default=None,
    help="Page size, 1 to 100 (default 50).",
)
@click.option(
    "--folder",
    "filter_by_folder",
    default=None,
    help="Only events in this folder and below.",
)
@click.option(
    "--type",
    "filter_by_types",
    type=EVENT_TYPES,
    multiple=True,
    help="Only events of this type (repeatable). Defaults to every type.",
)
@click.option(
    "--suppress",
    type=SUPPRESS,
    default=None,
    help="Leave out what this application (app) or the caller (user) did.",
)
@click.option(
    "--reverse",
    is_flag=True,
    default=False,
    help="Walk backwards: the COUNT events ending at START_ID.",
)
@click.pass_obj
def list_(
    ctx: ClientContext,
    start_id: int,
    count: int | None,
    filter_by_folder: str | None,
    filter_by_types: tuple[str, ...],
    suppress: str | None,
    reverse: bool,
) -> None:
    """
    List one page of events after START_ID.

    Prints the page with `latest_id`, the START_ID of the next page. When
    nothing follows START_ID, the page is empty and `latest_id` is START_ID.
    """
    render(
        ctx.client.list_events(
            start_id,
            count=count,
            filter_by_folder=filter_by_folder,
            filter_by_types=list(filter_by_types) or None,  # type: ignore[arg-type]
            suppress=suppress,  # type: ignore[arg-type]
            reverse=reverse or None,
        )
    )
