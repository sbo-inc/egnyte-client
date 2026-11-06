from datetime import datetime
from typing import Literal

from pydantic import Field, JsonValue

from egnyte_client.schemas.generic import GenericBaseModel

type EventType = Literal["file_system", "note", "permission_change"]
type EventSuppress = Literal["app", "user", "none"]
type PermissionPriv = Literal[
    "NONE", "VIEWER_ONLY", "READ", "READWRITE", "RWD", "MODIFY"
]

# =============================================================================
# CLASS: EventCursor
# =============================================================================


class EventCursor(GenericBaseModel):
    """
    The current position of the domain's event stream.
    """

    latest_event_id: int = Field(
        description="ID of the newest event; the starting cursor for polling.",
    )
    oldest_event_id: int = Field(
        description="ID of the oldest event still kept in the stream.",
    )
    timestamp: datetime | None = Field(
        default=None,
        description="When the newest event was recorded.",
    )


# =============================================================================
# CLASS: EventData
# =============================================================================


class EventData(GenericBaseModel):
    """
    The type-specific `data` of an event.

    Which fields are set depends on the event: file system events carry the
    target (and, for a copy or move, the source) path and IDs; note events
    carry `note_id`; permission change events carry `target_path` and
    `is_folder`.
    """

    target_path: str | None = Field(
        default=None,
        description="Path of the affected item, or the destination of a copy or move.",
    )
    target_id: str | None = Field(
        default=None,
        description="Version (entry) ID of the file at the target path.",
    )
    target_group_id: str | None = Field(
        default=None,
        description="File group ID of the file at the target path.",
    )
    source_path: str | None = Field(
        default=None,
        description="Original path of a copied or moved item.",
    )
    source_id: str | None = Field(
        default=None,
        description="Version (entry) ID of the file at the source path.",
    )
    source_group_id: str | None = Field(
        default=None,
        description="File group ID of the file at the source path.",
    )
    is_folder: bool | None = Field(
        default=None,
        description="Whether the item is a folder.",
    )
    note_id: str | None = Field(
        default=None,
        description="ID of the comment, for note events.",
    )


# =============================================================================
# CLASS: PermissionEntry
# =============================================================================


class PermissionEntry(GenericBaseModel):
    """
    One subject and privilege in a permission change.
    """

    subject: str = Field(
        description="User or group the change applies to, as `/user/6` or `/group/<id>`.",
    )
    priv: PermissionPriv = Field(
        description=(
            "Internal privilege name: NONE, VIEWER_ONLY, READ (Viewer), "
            "READWRITE (Editor), RWD (Full), or MODIFY (Owner)."
        ),
    )


# =============================================================================
# CLASS: ChangedPermission
# =============================================================================


class ChangedPermission(GenericBaseModel):
    """
    One added or removed permission entry.
    """

    action: Literal["ADD", "DELETE"] = Field(
        description="ADD or DELETE.",
    )
    entry: PermissionEntry = Field(
        description="The entry added or removed.",
    )


# =============================================================================
# CLASS: ChangePermissionEvent
# =============================================================================


class ChangePermissionEvent(GenericBaseModel):
    """
    The permission entries a permission change added and removed.
    """

    changed_permissions: list[ChangedPermission] = Field(
        default_factory=list,
        alias="changedPermissions",
        description="The entries added and removed.",
    )


# =============================================================================
# CLASS: PermissionChangeAttributes
# =============================================================================


class PermissionChangeAttributes(GenericBaseModel):
    """
    The details a `permission_change` event carries beside its `data`.
    """

    change_group_events: list[JsonValue] = Field(
        default_factory=list,
        alias="changeGroupEvents",
        description="Changes to user groups; undocumented shape.",
    )
    change_permission_event: ChangePermissionEvent | None = Field(
        default=None,
        alias="changePermissionEvent",
        description="The permission entries added and removed.",
    )
    change_context: dict[str, JsonValue] | None = Field(
        default=None,
        alias="changeContext",
        description="Context of the change, such as a snapshot-restore ID.",
    )
    target_folder_id: str | None = Field(
        default=None,
        alias="targetFolderId",
        description="ID of the folder whose permissions changed.",
    )
    group_change: bool | None = Field(
        default=None,
        alias="groupChange",
        description="Whether `change_group_events` has at least one entry.",
    )


# =============================================================================
# CLASS: Event
# =============================================================================


class Event(GenericBaseModel):
    """
    One entry of the domain's event stream.
    """

    id: int = Field(
        description="Event ID; the stream's cursor position.",
    )
    timestamp: datetime = Field(
        description="When the event was recorded.",
    )
    type: EventType = Field(
        description="file_system, note, or permission_change.",
    )
    action: str = Field(
        description=(
            "What happened: create, delete, restore, move (including "
            "renames), or copy; permission_change for permission events."
        ),
    )
    action_source: str | None = Field(
        default=None,
        description=(
            "Where the action came from: WebUI, SyncEngine, Mobile, PublicAPI, "
            "WebEdit, System, VPC, or another integration name."
        ),
    )
    actor: int | None = Field(
        default=None,
        description="Numeric ID of the user who acted.",
    )
    object_detail: str | None = Field(
        default=None,
        description="URL of the affected file or comment, when it still exists.",
    )
    data: EventData = Field(
        default_factory=EventData,
        description="Type-specific details.",
    )
    event_type_specific_attributes: PermissionChangeAttributes | None = Field(
        default=None,
        alias="eventTypeSpecificAttributes",
        description="Permission change details, for permission_change events.",
    )


# =============================================================================
# CLASS: EventPage
# =============================================================================


class EventPage(GenericBaseModel):
    """
    One page of the event stream after a cursor.
    """

    latest_id: int = Field(
        description="ID of the newest event in the page; the next cursor.",
    )
    oldest_id: int | None = Field(
        default=None,
        description="ID of the oldest event in the page.",
    )
    count: int = Field(
        default=0,
        description="Number of events in the page.",
    )
    events: list[Event] = Field(
        default_factory=list,
        description="The events in the page.",
    )
