from datetime import UTC, datetime

from egnyte_client.schemas.filesystem import File
from egnyte_client.schemas.link import Link


def test_http_date_last_modified_is_parsed() -> None:
    file = File.model_validate(
        {
            "name": "a.txt",
            "path": "/Shared/a.txt",
            "group_id": "g",
            "last_modified": "Fri, 06 Nov 2026 00:22:45 GMT",
            "uploaded": 1793924565939,
        }
    )

    assert file.last_modified == datetime(2026, 11, 6, 0, 22, 45, tzinfo=UTC)
    assert file.uploaded == datetime(2026, 11, 6, 0, 22, 45, 939000, tzinfo=UTC)


def test_link_keeps_a_flat_id_over_issued_links() -> None:
    link = Link.model_validate(
        {
            "id": "flat",
            "url": "https://acme.egnyte.com/dl/flat",
            "path": "/Shared",
            "type": "folder",
            "links": [{"id": "other", "url": "https://acme.egnyte.com/dl/other"}],
        }
    )

    assert link.id == "flat"
    assert link.url == "https://acme.egnyte.com/dl/flat"


def test_unknown_fields_are_ignored() -> None:
    link = Link.model_validate({"path": "/Shared", "type": "folder", "brand_new": 1})

    assert link.id == ""
    assert not hasattr(link, "brand_new")
