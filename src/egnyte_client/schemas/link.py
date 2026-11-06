from datetime import date, datetime
from typing import Literal, Self

from pydantic import Field, model_validator

from egnyte_client.schemas.generic import GenericBaseModel

type LinkType = Literal["file", "folder", "upload"]
type LinkAccessibility = Literal["anyone", "password", "domain", "recipients"]
type LinkProtection = Literal["PREVIEW", "NONE"]

# =============================================================================
# CLASS: LinkUrl
# =============================================================================


class LinkUrl(GenericBaseModel):
    """
    One URL a create call issued; one per recipient when emailed.
    """

    id: str = Field(
        description="Link ID.",
    )
    url: str = Field(
        description="The shareable URL.",
    )
    recipients: list[str] = Field(
        default_factory=list,
        description="Recipients this URL was issued to.",
    )


# =============================================================================
# CLASS: Link
# =============================================================================


class Link(GenericBaseModel):
    """
    A shared link to a file or folder.

    Creating a link answers with a `links` array of issued URLs, while reading
    or listing one answers with a flat `id` and `url`. Both arrive as this
    model: when only `links` is present, `id` and `url` are taken from its
    first entry, so `link.id` is always set.
    """

    id: str = Field(
        default="",
        description="Link ID.",
    )
    url: str | None = Field(
        default=None,
        description="The shareable URL.",
    )
    path: str = Field(
        description="Absolute path of the linked item.",
    )
    type: LinkType = Field(
        description="file, folder, or upload.",
    )
    accessibility: LinkAccessibility | None = Field(
        default=None,
        description="Who may open the link.",
    )
    protection: LinkProtection | None = Field(
        default=None,
        description="PREVIEW for preview-only links, otherwise NONE.",
    )
    recipients: list[str] = Field(
        default_factory=list,
        description="Recipients the link was sent to.",
    )
    notify: bool | None = Field(
        default=None,
        description="Whether the creator is notified when the link is opened.",
    )
    link_to_current: bool | None = Field(
        default=None,
        description="Whether a file link is pinned to the version it was made for.",
    )
    creation_date: datetime | None = Field(
        default=None,
        description="When the link was created.",
    )
    created_by: str | None = Field(
        default=None,
        description="Username that created the link.",
    )
    expiry_date: datetime | None = Field(
        default=None,
        description="When the link expires, if it does.",
    )
    expiry_clicks: int | None = Field(
        default=None,
        description="Number of opens after which the link expires, if set.",
    )
    last_accessed: datetime | None = Field(
        default=None,
        description="When the link was last opened.",
    )
    resource_id: str | None = Field(
        default=None,
        description="File group ID or folder ID of the linked item (listings only).",
    )
    links: list[LinkUrl] = Field(
        default_factory=list,
        description="The URLs issued by a create call.",
    )

    @model_validator(mode="after")
    def _lift_first_link(self) -> Self:
        if not self.id and self.links:
            self.id = self.links[0].id
            self.url = self.url or self.links[0].url
        return self


# =============================================================================
# CLASS: ListLinksResponse
# =============================================================================


class ListLinksResponse(GenericBaseModel):
    """
    Response body of the v2 link listing.
    """

    links: list[Link] = Field(default_factory=list)
    count: int = Field(default=0)


# =============================================================================
# CLASS: CreateLinkRequest
# =============================================================================


class CreateLinkRequest(GenericBaseModel):
    """
    Request body for creating a link.
    """

    path: str
    type: LinkType
    accessibility: LinkAccessibility | None = None
    use_default_settings: bool | None = Field(default=None, alias="useDefaultSettings")
    send_email: bool | None = None
    recipients: list[str] | None = None
    message: str | None = None
    copy_me: bool | None = None
    notify: bool | None = None
    link_to_current: bool | None = None
    expiry_date: date | None = None
    expiry_clicks: int | None = None
    add_file_name: bool | None = None
    password: str | None = None
    protection: LinkProtection | None = None
    folder_per_recipient: bool | None = None
