from collections.abc import Callable
from datetime import datetime
from typing import Literal

import httpx

from egnyte_client.operations.generic import Operation, iso_utc, model, query
from egnyte_client.schemas.trash import (
    TrashActionRequest,
    TrashCount,
    TrashItemStatus,
    TrashMultiStatus,
    TrashPage,
    TrashSortBy,
    TrashSortDirection,
)

# Egnyte restores or purges at most this many trash items per call.
MAX_TRASH_ACTION_IDS = 10


# -----------------------------------------------------------------------------
# OPERATION: list_trash
# -----------------------------------------------------------------------------


def list_trash(
    *,
    sort_by: TrashSortBy | None = None,
    sort_direction: TrashSortDirection | None = None,
    offset: int | None = None,
    count: int | None = None,
    deleted_by: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> Operation[TrashPage]:
    """
    Build one page of the v2 trash listing.

    Returns:
        Operation[TrashPage]: The list trash operation.
    """
    filtered = deleted_by is not None or start_date is not None or end_date is not None
    if filtered and (start_date is None or end_date is None):
        raise ValueError(
            "start_date and end_date are both required to filter the trash"
        )

    return Operation(
        method="GET",
        path="/v2/fs/trash",
        params=query(
            sort_by=sort_by,
            sort_direction=sort_direction,
            offset=offset,
            count=count,
            deletedBy=deleted_by,
            startDate=iso_utc(start_date),
            endDate=iso_utc(end_date),
        ),
        parse=model(TrashPage),
    )


# -----------------------------------------------------------------------------
# OPERATION: count_trash
# -----------------------------------------------------------------------------


def count_trash() -> Operation[int]:
    """
    Build the trash item count.

    Returns:
        Operation[int]: The count trash operation.
    """
    return Operation(
        method="GET",
        path="/v2/fs/trash/totalcount",
        parse=lambda response: (
            TrashCount.model_validate_json(response.content).total_count
        ),
    )


# -----------------------------------------------------------------------------
# OPERATION: trash_action
# -----------------------------------------------------------------------------


def _statuses(
    item_ids: list[str],
) -> Callable[[httpx.Response], list[TrashItemStatus]]:
    """
    Parse a restore or purge answer into one status per item.

    A 200 carries no body and means every item succeeded; a 207 lists each
    item's outcome.

    Returns:
        Callable[[httpx.Response], list[TrashItemStatus]]: The parser.
    """

    def parse(response: httpx.Response) -> list[TrashItemStatus]:
        if response.status_code == 207 and response.content.strip():
            return TrashMultiStatus.model_validate_json(response.content).resources
        return [TrashItemStatus(id=item_id, code=200) for item_id in item_ids]

    return parse


def trash_action(
    action: Literal["RESTORE", "PURGE"], item_ids: list[str]
) -> Operation[list[TrashItemStatus]]:
    """
    Build a restore or permanent purge of up to ten trash items.

    Returns:
        Operation[list[TrashItemStatus]]: The restore or purge operation.
    """
    if not item_ids:
        raise ValueError("No trash item IDs given")
    if len(item_ids) > MAX_TRASH_ACTION_IDS:
        raise ValueError(
            f"Egnyte accepts at most {MAX_TRASH_ACTION_IDS} trash items per call; "
            f"got {len(item_ids)}"
        )

    ids = list(item_ids)
    return Operation(
        method="POST",
        path="/v1/fs/trash",
        body=TrashActionRequest(action=action, ids=ids),
        parse=_statuses(ids),
    )
