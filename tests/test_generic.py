from datetime import UTC, datetime, timedelta, timezone

from egnyte_client.operations.generic import as_utc, epoch_ms, iso_utc
from egnyte_client.operations.link import list_links

PLUS_TWO = timezone(timedelta(hours=2))


def test_as_utc_reads_naive_as_utc_and_converts_aware() -> None:
    assert as_utc(datetime(2026, 1, 1, 12)) == datetime(2026, 1, 1, 12, tzinfo=UTC)
    converted = as_utc(datetime(2026, 1, 1, 12, tzinfo=PLUS_TWO))
    assert converted == datetime(2026, 1, 1, 10, tzinfo=UTC)
    assert converted.tzinfo is UTC


def test_iso_utc() -> None:
    assert iso_utc(datetime(2026, 4, 18, 18, 11, 38, tzinfo=PLUS_TWO)) == (
        "2026-04-18T16:11:38Z"
    )
    assert iso_utc(None) is None


def test_epoch_ms() -> None:
    assert epoch_ms(datetime(2026, 1, 1)) == 1767225600000
    assert epoch_ms(datetime(2026, 1, 1, 2, tzinfo=PLUS_TWO)) == 1767225600000
    assert epoch_ms(None) is None


def test_link_filters_send_naive_datetimes_as_utc() -> None:
    operation = list_links(filter_by_created_after=datetime(2026, 1, 1))

    assert operation.params["created_after"] == "2026-01-01T00:00:00+00:00"
