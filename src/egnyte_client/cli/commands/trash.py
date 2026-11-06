from datetime import datetime

import click

from egnyte_client.cli.context import ClientContext
from egnyte_client.cli.group import CommonClickGroup
from egnyte_client.cli.options import confirm, paging_options, yes_option
from egnyte_client.cli.output import render
from egnyte_client.operations.trash import MAX_TRASH_ACTION_IDS
from egnyte_client.schemas.trash import TrashItemStatus

SORT_FIELDS = click.Choice(
    [
        "date_deleted",
        "name",
        "deleted_by",
        "purge_date",
        "orig_location",
        "owner",
        "type",
    ]
)

# =============================================================================
# FUNCTION: _check_ids
# =============================================================================


def _check_ids(item_ids: tuple[str, ...]) -> list[str]:
    """
    Refuse more trash item IDs than Egnyte takes in one call.

    Checked before any prompt, so a purge is not confirmed only to fail.

    Returns:
        list[str]: The IDs.
    """
    if len(item_ids) > MAX_TRASH_ACTION_IDS:
        raise click.UsageError(
            f"Give at most {MAX_TRASH_ACTION_IDS} trash item IDs at a time; "
            f"got {len(item_ids)}."
        )
    return list(item_ids)


# =============================================================================
# FUNCTION: _report
# =============================================================================


def _report(statuses: list[TrashItemStatus], verb: str) -> None:
    """
    Print each item's status, and fail when any item was not acted on.

    Egnyte answers a partial failure with per-item statuses rather than an
    error, so the exit status is set here for scripts to see.
    """
    render(statuses)
    failed = [status.id for status in statuses if not status.succeeded]
    if failed:
        raise click.ClickException(
            f"{len(failed)} of {len(statuses)} items were not {verb}: "
            + ", ".join(failed)
        )


# =============================================================================
# GROUP: trash
# =============================================================================


@click.group(name="trash", cls=CommonClickGroup)
def group() -> None:
    """
    List, restore, and purge deleted files and folders.

    Needs an admin, or a power user allowed to manage the trash.
    """


@group.command(name="list")
@click.option(
    "--sort-by", type=SORT_FIELDS, default=None, help="Sort the items by this field."
)
@click.option(
    "--sort-direction",
    type=click.Choice(["asc", "desc"]),
    default=None,
    help="Sort direction; newest deletion first by default.",
)
@click.option(
    "--deleted-by",
    default=None,
    help="Items deleted by a user with this first or last name "
    "(needs --start-date and --end-date).",
)
@click.option(
    "--start-date",
    type=click.DateTime(),
    default=None,
    help="Earliest deletion time (YYYY-MM-DD or ISO 8601, UTC).",
)
@click.option(
    "--end-date",
    type=click.DateTime(),
    default=None,
    help="Latest deletion time (YYYY-MM-DD or ISO 8601, UTC).",
)
@paging_options
@click.pass_obj
def list_(
    ctx: ClientContext,
    sort_by: str | None,
    sort_direction: str | None,
    deleted_by: str | None,
    start_date: datetime | None,
    end_date: datetime | None,
    offset: int | None,
    count: int | None,
) -> None:
    """
    List one page of the trash, with `has_more`.

    Filtering by --deleted-by or by date needs both --start-date and
    --end-date. Pages hold 50 items unless --count says otherwise.
    """
    filtered = deleted_by is not None or start_date is not None or end_date is not None
    if filtered and (start_date is None or end_date is None):
        raise click.UsageError(
            "Give both --start-date and --end-date to filter the trash."
        )
    render(
        ctx.client.list_trash(
            sort_by=sort_by,  # type: ignore[arg-type]
            sort_direction=sort_direction,  # type: ignore[arg-type]
            offset=offset,
            count=count,
            deleted_by=deleted_by,
            start_date=start_date,
            end_date=end_date,
        )
    )


@group.command(name="count")
@click.pass_obj
def count(ctx: ClientContext) -> None:
    """
    Print the number of items in the trash.
    """
    render(ctx.client.count_trash())


@group.command(name="restore")
@click.argument("item_ids", nargs=-1, required=True, metavar="ITEM_ID...")
@click.pass_obj
def restore(ctx: ClientContext, item_ids: tuple[str, ...]) -> None:
    """
    Restore up to ten trash items to where they were deleted from.

    Takes trash item IDs, as `trash list` shows them. Prints each item's
    status, and exits non-zero if any item was not restored.
    """
    _report(ctx.client.restore_trash_items(_check_ids(item_ids)), "restored")


@group.command(name="purge")
@click.argument("item_ids", nargs=-1, required=True, metavar="ITEM_ID...")
@yes_option
@click.pass_obj
def purge(ctx: ClientContext, item_ids: tuple[str, ...], yes: bool) -> None:
    """
    Permanently delete up to ten trash items. This cannot be undone.

    Takes trash item IDs, as `trash list` shows them. Prints each item's
    status, and exits non-zero if any item was not purged.
    """
    ids = _check_ids(item_ids)
    confirm(
        yes,
        f"Permanently delete trash item(s) {', '.join(ids)}? This cannot be undone.",
    )
    _report(ctx.client.purge_trash_items(ids), "purged")
