from datetime import datetime
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, JsonValue

from egnyte_client.schemas.generic import GenericBaseModel

type WebhookStatus = Literal["enabled", "disabled"]
type WebhookEventType = Literal[
    "fs:*",
    "fs:add_file",
    "fs:add_folder",
    "fs:upload_link",
    "fs:copy_file",
    "fs:copy_folder",
    "fs:delete_file",
    "fs:delete_folder",
    "fs:delete_from_trash",
    "fs:move_file",
    "fs:move_folder",
    "fs:restore_from_trash",
    "fs:lock_file",
    "fs:unlock_file",
    "fs:folder_project_activity",
    "link:*",
    "link:create",
    "link:create_download_link",
    "link:create_upload_link",
    "link:delete",
    "link:delete_download_link",
    "link:delete_upload_link",
    "comment:*",
    "comment:set_comment",
    "comment:remove_comment",
    "permission:*",
    "permission:permission_change",
    "meta:*",
    "meta:add_metadata_key",
    "meta:delete_metadata_key",
    "workflow:created",
    "workflow:completed",
    "workflow:approvaltask_approved",
    "workflow:approvaltask_rejected",
    "group:create",
    "group:delete",
    "group:rename",
    "group:add_members",
    "group:remove_members",
    "group:add_owner",
    "group:remove_owner",
]

MAX_WEBHOOK_PATHS = 100


def _split_paths(value: object) -> object:
    """
    Split the comma-separated `path` filter Egnyte stores into a list.
    """
    if isinstance(value, str):
        return [path for path in value.split(",") if path]
    return value


type PathList = Annotated[list[str], BeforeValidator(_split_paths)]

# =============================================================================
# CLASS: Webhook
# =============================================================================


class Webhook(GenericBaseModel):
    """
    A webhook's identity and state, as the listing and status calls return it.
    """

    webhook_id: str = Field(
        alias="webhookId",
        description="Webhook ID.",
    )
    status: str | None = Field(
        default=None,
        description="Delivery state: enabled or disabled.",
    )
    expires: datetime | None = Field(
        default=None,
        description="When the registration expires.",
    )


# =============================================================================
# CLASS: WebhookDetails
# =============================================================================


class WebhookDetails(Webhook):
    """
    A webhook with its full configuration.
    """

    url: str | None = Field(
        default=None,
        description="HTTPS endpoint the events are posted to.",
    )
    event_types: list[str] = Field(
        default_factory=list,
        alias="eventType",
        description="Subscribed event types; empty means every event.",
    )
    paths: PathList = Field(
        default_factory=list,
        alias="path",
        description="Folders watched; empty means the whole domain.",
    )
    auth_header: str | None = Field(
        default=None,
        alias="authHeader",
        description="Value Egnyte sends in each delivery's Authorization header.",
    )


# =============================================================================
# CLASS: WebhookRequest
# =============================================================================


class WebhookRequest(GenericBaseModel):
    """
    Request body for registering or reconfiguring a webhook.
    """

    url: str
    event_type: list[WebhookEventType] | None = Field(default=None, alias="eventType")
    path: str | None = None
    auth_header: str | None = Field(default=None, alias="authHeader")
    status: WebhookStatus | None = None


class WebhookStatusRequest(GenericBaseModel):
    """
    Request body for enabling or disabling a webhook.
    """

    status: WebhookStatus


# =============================================================================
# CLASS: WebhookEventUser
# =============================================================================


class WebhookEventUser(GenericBaseModel):
    """
    The user whose action raised a webhook event.
    """

    id: int | None = Field(
        default=None,
        description="Numeric user ID.",
    )
    display_name: str | None = Field(
        default=None,
        alias="displayName",
        description="Display name.",
    )
    username: str | None = Field(
        default=None,
        description="Username.",
    )
    email: str | None = Field(
        default=None,
        description="Email address.",
    )
    client_id_hash: str | None = Field(
        default=None,
        alias="clientIdHash",
        description="SHA-1 of the API client ID that acted, if any.",
    )
    impersonated_by: str | None = Field(
        default=None,
        alias="impersonatedBy",
        description="Admin username acting on the user's behalf.",
    )


# =============================================================================
# CLASS: WebhookEvent
# =============================================================================


class WebhookEvent(GenericBaseModel):
    """
    One event in a webhook delivery.
    """

    event_id: str = Field(
        alias="eventId",
        description="Event ID, unique in the domain; use it to drop duplicates.",
    )
    event_type: str = Field(
        alias="eventType",
        description="Most specific event type, such as `fs:add_file`.",
    )
    webhook_id: str | None = Field(
        default=None,
        alias="webhookId",
        description="Webhook the event was delivered for.",
    )
    domain: str | None = Field(
        default=None,
        description="Egnyte domain.",
    )
    timestamp: datetime | None = Field(
        default=None,
        description="When the event happened.",
    )
    user: WebhookEventUser | None = Field(
        default=None,
        description="Who acted.",
    )
    action_source: str | None = Field(
        default=None,
        alias="actionSource",
        description="Client or API the action came from.",
    )
    custom_properties: dict[str, JsonValue] = Field(
        default_factory=dict,
        alias="customProperties",
        description="Extra context, such as project IDs.",
    )
    data: dict[str, JsonValue] = Field(
        default_factory=dict,
        description="Event-specific fields, such as `targetPath`.",
    )


# =============================================================================
# CLASS: WebhookDelivery
# =============================================================================


class WebhookDelivery(GenericBaseModel):
    """
    The JSON body Egnyte posts to a webhook endpoint.

    Answer 200 to acknowledge it; anything else is retried (immediately, then
    after 1 minute, 10 minutes, and 1 hour) before the webhook is disabled.
    """

    data: list[WebhookEvent] = Field(
        default_factory=list,
        description="The events delivered.",
    )
