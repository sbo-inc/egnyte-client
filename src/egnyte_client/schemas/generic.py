from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

# =============================================================================
# TYPE: HttpDate
# =============================================================================


def _parse_http_date(value: object) -> object:
    """
    Parse an RFC 1123 date (`Fri, 06 Nov 2026 00:22:45 GMT`) into a datetime.

    The file system API reports a file's `last_modified` in the HTTP header
    format rather than ISO 8601, which Pydantic does not read on its own. Any
    other value passes through for the default datetime validation.
    """
    if isinstance(value, str) and "," in value:
        return parsedate_to_datetime(value)
    return value


type HttpDate = Annotated[datetime, BeforeValidator(_parse_http_date)]


# =============================================================================
# CLASS: GenericBaseModel
# =============================================================================


class GenericBaseModel(BaseModel):
    """
    A generic base model with common Pydantic configuration
    """

    model_config = ConfigDict(
        validate_by_alias=True,
        validate_by_name=True,
        extra="ignore",
    )


# =============================================================================
# CLASS: ScimListResponse
# =============================================================================


class ScimListResponse[T](GenericBaseModel):
    """
    The SCIM-style page the v2 user and group listings answer with.
    """

    total_results: int = Field(
        default=0,
        alias="totalResults",
        description="Total number of records matching the request.",
    )
    items_per_page: int = Field(
        default=0,
        alias="itemsPerPage",
        description="Number of records in this page.",
    )
    start_index: int = Field(
        default=1,
        alias="startIndex",
        description="1-based index of the first record in this page.",
    )
    resources: list[T] = Field(
        default_factory=list,
        description="The records in this page.",
    )
