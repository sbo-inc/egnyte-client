from datetime import date, datetime

from egnyte_client.operations.generic import (
    Operation,
    as_utc,
    empty,
    encode_id,
    model,
    normalize_path,
    query,
)
from egnyte_client.schemas.link import (
    CreateLinkRequest,
    Link,
    LinkAccessibility,
    LinkProtection,
    LinkType,
    ListLinksResponse,
)

# -----------------------------------------------------------------------------
# OPERATION: create_link
# -----------------------------------------------------------------------------


def create_link(
    path: str,
    type: LinkType,
    *,
    accessibility: LinkAccessibility | None = None,
    use_default_settings: bool | None = None,
    send_email: bool | None = None,
    recipients: list[str] | None = None,
    message: str | None = None,
    copy_me: bool | None = None,
    notify: bool | None = None,
    link_to_current: bool | None = None,
    expiry_date: date | None = None,
    expiry_clicks: int | None = None,
    add_file_name: bool | None = None,
    password: str | None = None,
    protection: LinkProtection | None = None,
    folder_per_recipient: bool | None = None,
) -> Operation[Link]:
    """
    Build the link create.

    Returns:
        Operation[Link]: The create link operation.
    """
    if expiry_date is not None and expiry_clicks is not None:
        raise ValueError("expiry_date and expiry_clicks cannot be combined")

    return Operation(
        method="POST",
        path="/v1/links",
        body=CreateLinkRequest(
            path=normalize_path(path),
            type=type,
            accessibility=accessibility,
            use_default_settings=use_default_settings,
            send_email=send_email,
            recipients=recipients,
            message=message,
            copy_me=copy_me,
            notify=notify,
            link_to_current=link_to_current,
            expiry_date=expiry_date,
            expiry_clicks=expiry_clicks,
            add_file_name=add_file_name,
            password=password,
            protection=protection,
            folder_per_recipient=folder_per_recipient,
        ),
        parse=model(Link),
    )


# -----------------------------------------------------------------------------
# OPERATION: get_link
# -----------------------------------------------------------------------------


def get_link(link_id: str) -> Operation[Link]:
    """
    Build the link read.

    Returns:
        Operation[Link]: The get link operation.
    """
    return Operation(
        method="GET", path=f"/v1/links/{encode_id(link_id)}", parse=model(Link)
    )


# -----------------------------------------------------------------------------
# OPERATION: list_links
# -----------------------------------------------------------------------------


def _iso(value: datetime | None) -> str | None:
    """
    Format a datetime as ISO 8601 with its UTC offset; naive means UTC.

    Returns:
        str | None: The stamp, or None.
    """
    return as_utc(value).isoformat() if value is not None else None


def list_links(
    *,
    filter_by_path: str | None = None,
    filter_by_username: str | None = None,
    filter_by_type: LinkType | None = None,
    filter_by_accessibility: LinkAccessibility | None = None,
    filter_by_created_after: datetime | None = None,
    filter_by_created_before: datetime | None = None,
    offset: int | None = None,
    count: int | None = None,
) -> Operation[list[Link]]:
    """
    Build the v2 link listing, which returns each link's details.

    Returns:
        Operation[list[Link]]: The list links operation.
    """
    return Operation(
        method="GET",
        path="/v2/links",
        params=query(
            path=normalize_path(filter_by_path) if filter_by_path else None,
            username=filter_by_username,
            type=filter_by_type,
            accessibility=filter_by_accessibility,
            created_after=_iso(filter_by_created_after),
            created_before=_iso(filter_by_created_before),
            offset=offset,
            count=count,
        ),
        parse=lambda response: (
            ListLinksResponse.model_validate_json(response.content).links
        ),
    )


# -----------------------------------------------------------------------------
# OPERATION: delete_link
# -----------------------------------------------------------------------------


def delete_link(link_id: str) -> Operation[None]:
    """
    Build the link delete.

    Returns:
        Operation[None]: The delete link operation.
    """
    return Operation(
        method="DELETE", path=f"/v1/links/{encode_id(link_id)}", parse=empty
    )
