import httpx

from egnyte_client.operations.generic import Operation, model, normalize_path, query
from egnyte_client.schemas.event import EventCursor, EventPage, EventSuppress, EventType

# -----------------------------------------------------------------------------
# OPERATION: get_event_cursor
# -----------------------------------------------------------------------------


def get_event_cursor() -> Operation[EventCursor]:
    """
    Build the event cursor read.

    Returns:
        Operation[EventCursor]: The get event cursor operation.
    """
    return Operation(method="GET", path="/v1/events/cursor", parse=model(EventCursor))


# -----------------------------------------------------------------------------
# OPERATION: list_events
# -----------------------------------------------------------------------------


def list_events(
    start_id: int,
    *,
    count: int | None = None,
    filter_by_folder: str | None = None,
    filter_by_types: list[EventType] | None = None,
    suppress: EventSuppress | None = None,
    reverse: bool | None = None,
) -> Operation[EventPage]:
    """
    Build one page of the v2 event stream after a cursor.

    Egnyte answers 204 with no body when nothing follows the cursor; that
    parses as an empty page whose `latest_id` is `start_id`, so the next
    cursor is always `latest_id`.

    Returns:
        Operation[EventPage]: The list events operation.
    """

    def parse(response: httpx.Response) -> EventPage:
        if response.status_code == 204 or not response.content:
            return EventPage(latest_id=start_id)
        return EventPage.model_validate_json(response.content)

    return Operation(
        method="GET",
        path="/v2/events",
        params=query(
            id=start_id,
            folder=normalize_path(filter_by_folder) if filter_by_folder else None,
            suppress=suppress,
            type="|".join(filter_by_types) if filter_by_types else None,
            count=count,
            reverse=int(reverse) if reverse is not None else None,
        ),
        parse=parse,
    )
