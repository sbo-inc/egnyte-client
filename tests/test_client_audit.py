from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

import httpx
import pytest
from conftest import API, body, respond

from egnyte_client.async_client import AsyncEgnyteClient
from egnyte_client.client import EgnyteClient
from egnyte_client.errors import EgnyteNotFoundError
from egnyte_client.operations import audit as audit_ops
from egnyte_client.schemas.audit import QualityDocsCategoryFilter

# Egnyte documents the job ID as a string; live it arrives as a number.
JOB: dict[str, Any] = {"id": 103897235}
JOB_LOCATION = f"{API}/v1/audit/jobs/103897235"
REPORT_LOCATION = f"{API}/v1/audit/logins/103897235"

# Shaped after a live login report: `logout_time` is empty while a session is
# open, and rows carry `details`, which the documentation leaves out.
LOGIN_REPORT: dict[str, Any] = {
    "total_count": 15,
    "offset": 0,
    "count": 2,
    "events": [
        {
            "username": "Jane Doe ( jdoe@acme.test )",
            "user_id": 8,
            "event": "Login",
            "ip_address": "198.51.100.7",
            "access": "Web UI",
            "time": "2026-11-05T18:35:12Z",
            "logout_time": "",
            "details": "",
        },
        {
            "username": "Jane Doe ( jdoe@acme.test )",
            "user_id": 8,
            "event": "Login",
            "ip_address": "198.51.100.7",
            "access": "Web UI",
            "time": "2026-11-05T09:00:00Z",
            "logout_time": "2026-11-05T10:15:30Z",
            "details": "",
        },
    ],
}

# The other report shapes follow the documentation's examples.
FILE_ROW: dict[str, Any] = {
    "username": "Jane Doe ( jdoe@acme.test )",
    "user_id": 8,
    "file": "/Shared/Docs/hello world.txt",
    "target_path": "/Shared/Docs/Sub",
    "transaction": "Move File",
    "actionInfo": "N/A",
    "access": "Mobile",
    "time": "2026-11-05T07:58:17Z",
    "ipAddress": "198.51.100.7",
    "file_checksum": "abc",
}
LINK_ROW: dict[str, Any] = {
    "username": "Anonymous access Admin (via link)",
    "user_id": 9,
    "folder": "/Shared/Docs",
    "link": "https://acme.egnyte.com/h-s/20261105/abc",
    "transaction": "Download via Link",
    "actionInfo": "N/A",
    "access": "Web",
    "time": "2026-11-05T08:34:37Z",
    "ipAddress": "198.51.100.7",
    "file_checksum": "N/A",
}
PERMISSION_ROW: dict[str, Any] = {
    "folder": "/Shared/Docs",
    "assignee": "John Roe ( jroe@acme.test )",
    "assignee_id": 9,
    "assigner": "Jane Doe ( jdoe@acme.test )",
    "assigner_id": 8,
    "change": "Editor>>Owner",
    "time": "2026-11-05T18:35Z",
}
USER_ROW: dict[str, Any] = {
    "performed_by": "Jane Doe ( jdoe@acme.test )",
    "performed_by_id": 8,
    "subject": "John Roe ( jroe@acme.test )",
    "subject_id": 9,
    "action": "Create",
    "action_info": "",
    "date_and_time": "2026-11-03T17:13:58Z",
    "action_source": "Web UI",
}
GROUP_ROW: dict[str, Any] = {
    "time": "2026-11-04T23:03:38Z",
    "actor": "Jane Doe ( jdoe@acme.test )",
    "actor_id": 8,
    "group": "Finance",
    "action": "Add Users",
    "action_info": "John Roe ( jroe@acme.test )",
    "source": "Web UI",
}
SETTINGS_ROW: dict[str, Any] = {
    "time": "2026-11-05T23:00:00Z",
    "actor": "Jane Doe ( jdoe@acme.test )",
    "ip_address": "198.51.100.7",
    "setting_screen": "SECURITY",
    "setting_name": "security.externalAuthSettings.samlEnabled",
    "old_value": "false",
    "new_value": "true",
}

# Shaped after a live stream page (`cursorExpired` is undocumented), with the
# documentation's file, user, and group events.
STREAM_PAGE: dict[str, Any] = {
    "events": [
        {
            "date": 1793906961000,
            "sourcePath": "/Shared/Docs/hello world.txt",
            "targetPath": "N/A",
            "user": "Jane Doe ( jdoe@acme.test )",
            "userId": "8",
            "action": "Preview",
            "access": "Web UI",
            "ipAddress": "198.51.100.7",
            "actionInfo": "",
            "auditSource": "FILE_AUDIT",
        },
        {
            "date": 1793906962000,
            "actor": "Jane Doe ( jdoe@acme.test )",
            "subject": "John Roe ( jroe@acme.test )",
            "action": "Disable",
            "actionInfo": "",
            "source": "Web UI",
            "auditSource": "USER_AUDIT",
        },
        {
            "date": 1793906963000,
            "actor": "Jane Doe ( jdoe@acme.test )",
            "group": "Finance",
            "action": "Create",
            "actionInfo": "",
            "source": "API",
            "auditSource": "GROUP_AUDIT",
        },
    ],
    "nextCursor": "AAN_lwABAX1zZe9AAAAAAAAAAAAAAAAAAAAAAA",
    "moreEvents": True,
    "cursorExpired": False,
}


def _client(
    make_client: Callable[..., EgnyteClient], response: httpx.Response
) -> tuple[EgnyteClient, list[httpx.Request]]:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return response

    return make_client(handler), sent


START = date(2026, 11, 1)
END = date(2026, 11, 5)
DATES = {"date_start": "2026-11-01", "date_end": "2026-11-05"}


# =============================================================================
# TEST: report creates
# =============================================================================


CREATES: list[tuple[str, str, dict[str, Any], dict[str, Any]]] = [
    (
        "create_login_audit_report",
        "logins",
        {
            "events": ["logins", "failed_attempts"],
            "access_points": ["web", "ftp"],
            "users": ["jdoe"],
            "suppress_emails": True,
        },
        {
            "format": "json",
            "events": ["logins", "failed_attempts"],
            "access_points": ["web", "ftp"],
            "users": ["jdoe"],
            "suppress_emails": True,
        },
    ),
    (
        "create_file_audit_report",
        "files",
        {
            "folders": ["Shared//Docs/", "/Shared/Finance"],
            "file": "report*.pdf",
            "format": "csv",
            "users": ["jdoe"],
            "transaction_types": ["download", "preview"],
            "suppress_emails": False,
        },
        {
            "format": "csv",
            "folders": ["/Shared/Docs", "/Shared/Finance"],
            "file": "report*.pdf",
            "users": ["jdoe"],
            "transaction_type": ["download", "preview"],
            "suppress_emails": False,
        },
    ),
    (
        "create_permissions_audit_report",
        "permissions",
        {
            "folders": ["/Shared/Docs"],
            "assigners": ["jdoe"],
            "assignee_users": ["jroe"],
            "assignee_groups": ["Finance"],
            "suppress_emails": True,
        },
        {
            "format": "json",
            "folders": ["/Shared/Docs"],
            "assigners": ["jdoe"],
            "assignee_users": ["jroe"],
            "assignee_groups": ["Finance"],
            "suppress_emails": True,
        },
    ),
    (
        "create_user_audit_report",
        "users",
        {
            "action_types": ["CREATE", "PASSWORD_RESET"],
            "performed_by": ["jdoe"],
            "subjects": ["jroe"],
            "include_system_actions": True,
        },
        {
            "format": "json",
            "action_type": ["CREATE", "PASSWORD_RESET"],
            "performed_by": ["jdoe"],
            "subject": ["jroe"],
            "include_system_actions": True,
        },
    ),
    (
        "create_group_audit_report",
        "groups",
        {
            "action_types": ["CREATE", "ADD_USERS"],
            "users": ["jdoe"],
            "groups": ["Finance"],
            "include_system_actions": False,
        },
        {
            "format": "json",
            "action_type": ["CREATE", "ADD_USERS"],
            "users": ["jdoe"],
            "groups": ["Finance"],
            "include_system_actions": False,
        },
    ),
    (
        "create_workgroup_settings_audit_report",
        "workgroup-settings",
        {"users": ["jdoe"]},
        {"format": "json", "users": ["jdoe"]},
    ),
    (
        "create_workflow_audit_report",
        "workflows",
        {
            "users": ["jdoe"],
            "file": "Contract*",
            "workflow_actions": ["WORKFLOW_CREATED", "WORKFLOW_COMPLETED"],
            "workflow_types": ["APPROVAL", "REVIEW"],
            "suppress_emails": True,
        },
        {
            "format": "json",
            "users": ["jdoe"],
            "file": "Contract*",
            "workflow_actions": ["WORKFLOW_CREATED", "WORKFLOW_COMPLETED"],
            "workflow_types": ["APPROVAL", "REVIEW"],
            "suppress_emails": True,
        },
    ),
    (
        "create_workflow_template_audit_report",
        "workflow-templates",
        {
            "users": ["jdoe"],
            "workflow_template_actions": ["TEMPLATE_CREATED", "TEMPLATE_EDITED"],
            "suppress_emails": True,
        },
        {
            "format": "json",
            "users": ["jdoe"],
            "workflow_template_actions": ["TEMPLATE_CREATED", "TEMPLATE_EDITED"],
            "suppress_emails": True,
        },
    ),
    (
        "create_quality_docs_audit_report",
        "quality-docs",
        {
            "users": ["jdoe"],
            "quality_document_id": "qd-1",
            "quality_docs_categories": [
                QualityDocsCategoryFilter(id="cat-1", subcategory_ids=["sub-1"]),
                QualityDocsCategoryFilter(id="cat-2"),
            ],
            "quality_docs_actions": ["DOCUMENT_ADDED", "TRAINING_COMPLETED"],
            "quality_docs_statuses": ["EFFECTIVE"],
            "suppress_emails": True,
        },
        {
            "format": "json",
            "users": ["jdoe"],
            "quality_document_id": "qd-1",
            "quality_docs_categories": [
                {"id": "cat-1", "subcategoryIds": ["sub-1"]},
                {"id": "cat-2"},
            ],
            "quality_docs_actions": ["DOCUMENT_ADDED", "TRAINING_COMPLETED"],
            "quality_docs_statuses": ["EFFECTIVE"],
            "suppress_emails": True,
        },
    ),
    (
        "create_quality_docs_categories_audit_report",
        "quality-docs-categories",
        {
            "users": ["jdoe"],
            "quality_docs_categories": [QualityDocsCategoryFilter(id="cat-1")],
            "quality_docs_categories_actions": ["CATEGORY_ADDED"],
            "suppress_emails": True,
        },
        {
            "format": "json",
            "users": ["jdoe"],
            "quality_docs_categories": [{"id": "cat-1"}],
            "quality_docs_categories_actions": ["CATEGORY_ADDED"],
            "suppress_emails": True,
        },
    ),
    (
        "create_quality_docs_courses_audit_report",
        "quality-docs-courses",
        {
            "users": ["jdoe"],
            "quality_docs_courses_ids": ["course-1"],
            "quality_docs_courses_actions": ["COURSE_CREATED"],
            "quality_docs_courses_parameters": ["NAME", "DOCUMENT_STATUS"],
            "suppress_emails": True,
        },
        {
            "format": "json",
            "users": ["jdoe"],
            "quality_docs_courses_ids": ["course-1"],
            "quality_docs_courses_actions": ["COURSE_CREATED"],
            "quality_docs_courses_parameters": ["NAME", "DOCUMENT_STATUS"],
            "suppress_emails": True,
        },
    ),
    (
        "create_etmf_audit_report",
        "etmf",
        {
            "users": ["jdoe"],
            "etmf_actions": ["STUDY_CREATED", "DOCUMENT_ADDED"],
            "etmf_study_ids": ["study-001"],
            "etmf_artifact_number": "01.01.01",
            "suppress_emails": True,
        },
        {
            "format": "json",
            "users": ["jdoe"],
            "etmf_actions": ["STUDY_CREATED", "DOCUMENT_ADDED"],
            "etmf_study_ids": ["study-001"],
            "etmf_artifact_number": "01.01.01",
            "suppress_emails": True,
        },
    ),
    (
        "create_snapshot_restore_audit_report",
        "snapshot-restore",
        {"users": ["jdoe"], "include_system_actions": False, "suppress_emails": True},
        {
            "format": "json",
            "users": ["jdoe"],
            "include_system_actions": False,
            "suppress_emails": True,
        },
    ),
    (
        "create_upload_requests_audit_report",
        "upload-requests",
        {
            "users": ["jdoe"],
            "upload_requests_actions": ["REQUEST_CREATED", "FILE_UPLOADED"],
            "suppress_emails": True,
        },
        {
            "format": "json",
            "users": ["jdoe"],
            "upload_requests_actions": ["REQUEST_CREATED", "FILE_UPLOADED"],
            "suppress_emails": True,
        },
    ),
]


@pytest.mark.parametrize(
    ("method", "report_type", "kwargs", "expected"),
    CREATES,
    ids=[create[1] for create in CREATES],
)
def test_every_report_create_sends_its_fields(
    make_client: Callable[..., EgnyteClient],
    method: str,
    report_type: str,
    kwargs: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    client, sent = _client(make_client, respond(JOB, status=202, Location=JOB_LOCATION))

    job = getattr(client, method)(START, END, **kwargs)

    assert sent[0].method == "POST"
    assert sent[0].url.path == f"/pubapi/v1/audit/{report_type}"
    assert sent[0].url.query == b""
    assert sent[0].headers["Content-Type"] == "application/json"
    assert body(sent[0]) == {**DATES, **expected}
    assert job.id == "103897235"


@pytest.mark.parametrize(
    ("method", "report_type"),
    [
        (create[0], create[1])
        for create in CREATES
        if create[1] not in ("logins", "files")
    ],
)
def test_optional_filters_are_left_out(
    make_client: Callable[..., EgnyteClient], method: str, report_type: str
) -> None:
    client, sent = _client(make_client, respond(JOB, status=202))

    getattr(client, method)(START, END)

    assert sent[0].url.path == f"/pubapi/v1/audit/{report_type}"
    assert body(sent[0]) == {"format": "json", **DATES}


def test_datetimes_are_sent_as_utc_timestamps(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond(JOB, status=202))

    client.create_login_audit_report(
        datetime(2026, 11, 4, 22, 30),
        datetime(2026, 11, 5, 1, 0, tzinfo=timezone(timedelta(hours=2))),
        events=["logins"],
    )

    # A naive datetime is UTC; an aware one is converted.
    assert body(sent[0])["date_start"] == "2026-11-04T22:30:00Z"
    assert body(sent[0])["date_end"] == "2026-11-04T23:00:00Z"


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (date(2026, 11, 5), date(2026, 11, 5)),
        (date(2026, 11, 5), date(2026, 11, 4)),
        (datetime(2026, 11, 5, 12, tzinfo=UTC), date(2026, 11, 5)),
    ],
)
def test_end_date_must_follow_start_date(
    start: date | datetime, end: date | datetime
) -> None:
    with pytest.raises(ValueError, match="end_date must be after start_date"):
        audit_ops.create_group_audit_report(start, end)


def test_login_report_needs_an_event() -> None:
    with pytest.raises(ValueError, match="at least one"):
        audit_ops.create_login_audit_report(START, END, events=[])


def test_file_report_needs_folders_or_a_file() -> None:
    with pytest.raises(ValueError, match="folders or a file"):
        audit_ops.create_file_audit_report(START, END)
    with pytest.raises(ValueError, match="folders or a file"):
        audit_ops.create_file_audit_report(START, END, folders=[])

    operation = audit_ops.create_file_audit_report(START, END, file="budget.xlsx")
    assert operation.body is not None
    assert operation.body.model_dump(exclude_none=True) == {
        "format": "json",
        **DATES,
        "file": "budget.xlsx",
    }


@pytest.mark.parametrize(
    "build",
    [
        lambda: audit_ops.create_file_audit_report(START, END, file="*.pdf"),
        lambda: audit_ops.create_workflow_audit_report(START, END, file="*Contract"),
    ],
)
def test_file_patterns_cannot_start_with_a_wildcard(
    build: Callable[[], object],
) -> None:
    with pytest.raises(ValueError, match="wildcard"):
        build()


# =============================================================================
# TEST: job status
# =============================================================================


def test_running_job(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond({"status": "running"}))

    status = client.get_audit_job("103897235")

    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/audit/jobs/103897235"
    assert status.status == "running"
    assert not status.is_complete
    assert status.report_id is None
    assert status.report_type is None


def test_completed_job_is_not_followed(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(
        make_client,
        respond({"status": "completed"}, status=303, Location=REPORT_LOCATION),
    )

    status = client.get_audit_job("103897235")

    # The report is not downloaded: only the poll goes out.
    assert len(sent) == 1
    assert status.is_complete
    assert status.report_id == "103897235"
    assert status.report_type == "logins"
    assert status.location == REPORT_LOCATION


def test_job_errors_still_raise(make_client: Callable[..., EgnyteClient]) -> None:
    client, _ = _client(
        make_client,
        respond(
            {
                "Errors": [
                    {"description": "Audit report does not exist.", "code": "404"}
                ]
            },
            status=404,
        ),
    )

    with pytest.raises(EgnyteNotFoundError, match="Audit report does not exist"):
        client.get_audit_job("1")


def test_303_parses_the_report_location() -> None:
    response = httpx.Response(
        303, json={"status": "completed"}, headers={"Location": REPORT_LOCATION}
    )

    status = audit_ops.parse_job_status(response)

    assert status.is_complete
    assert status.location == REPORT_LOCATION
    assert status.report_type == "logins"
    assert status.report_id == "103897235"


@pytest.mark.parametrize(
    ("location", "report_type", "report_id"),
    [
        ("/pubapi/v1/audit/workgroup-settings/77/", "workgroup-settings", "77"),
        (f"{API}/v1/audit/brand-new-type/78", None, "78"),
        (f"{API}/v1/something/else", None, None),
    ],
)
def test_303_without_a_body(
    location: str, report_type: str | None, report_id: str | None
) -> None:
    status = audit_ops.parse_job_status(
        httpx.Response(303, headers={"Location": location})
    )

    assert status.status == "completed"
    assert status.location == location
    assert status.report_type == report_type
    assert status.report_id == report_id


# =============================================================================
# TEST: reports
# =============================================================================


def test_get_login_report_page(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(LOGIN_REPORT))

    report = client.get_audit_report("logins", "103897235", offset=0, count=2)

    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/audit/logins/103897235"
    assert dict(sent[0].url.params) == {"offset": "0", "count": "2"}
    assert report.total_count == 15
    assert len(report.events) == 2
    open_session, closed_session = report.events
    assert open_session.event == "Login"
    assert open_session.user_id == 8
    assert open_session.time == datetime(2026, 11, 5, 18, 35, 12, tzinfo=UTC)
    assert open_session.logout_time is None
    assert closed_session.logout_time == datetime(2026, 11, 5, 10, 15, 30, tzinfo=UTC)


def test_get_whole_report_sends_no_paging(
    make_client: Callable[..., EgnyteClient],
) -> None:
    client, sent = _client(make_client, respond({**LOGIN_REPORT, "count": 0}))

    client.get_audit_report("logins", "103897235")

    assert sent[0].url.query == b""


def test_report_rows_of_each_documented_type(
    make_client: Callable[..., EgnyteClient],
) -> None:
    rows = [FILE_ROW, LINK_ROW, PERMISSION_ROW, USER_ROW, GROUP_ROW, SETTINGS_ROW]
    client, _ = _client(
        make_client,
        respond({"total_count": 6, "offset": 0, "count": 6, "events": rows}),
    )

    moved, linked, permission, user, group, setting = client.get_audit_report(
        "files", "1"
    ).events

    # The file report mixes camelCase into its snake_case rows.
    assert moved.ip_address == "198.51.100.7"
    assert moved.action_info == "N/A"
    assert moved.target_path == "/Shared/Docs/Sub"
    assert moved.transaction == "Move File"
    assert linked.link == "https://acme.egnyte.com/h-s/20261105/abc"
    assert linked.folder == "/Shared/Docs"
    assert permission.change == "Editor>>Owner"
    assert permission.assignee_id == 9
    assert permission.time == datetime(2026, 11, 5, 18, 35, tzinfo=UTC)
    assert user.date_and_time == datetime(2026, 11, 3, 17, 13, 58, tzinfo=UTC)
    assert user.subject_id == 9
    assert user.action_source == "Web UI"
    assert group.group == "Finance"
    assert group.action_info == "John Roe ( jroe@acme.test )"
    assert setting.setting_name == "security.externalAuthSettings.samlEnabled"
    assert setting.new_value == "true"


def test_undocumented_report_fields_are_kept(
    make_client: Callable[..., EgnyteClient],
) -> None:
    row = {"time": "2026-11-05T08:00:00Z", "workflow_name": "Contract review"}
    client, sent = _client(make_client, respond({"total_count": 1, "events": [row]}))

    (record,) = client.get_audit_report("workflows", "5").events

    assert sent[0].url.path == "/pubapi/v1/audit/workflows/5"
    assert record.model_extra == {"workflow_name": "Contract review"}


def test_download_csv_report(make_client: Callable[..., EgnyteClient]) -> None:
    csv = b'Username,Event,IP Address,Access,Time\n"Jane Doe (jdoe@acme.test)",Login,198.51.100.7,Web,2026-11-05T18:35Z\n'
    client, sent = _client(
        make_client,
        httpx.Response(200, content=csv, headers={"Content-Type": "text/csv"}),
    )

    assert client.download_audit_report("logins", "103897235") == csv
    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/audit/logins/103897235"
    assert sent[0].url.query == b""


def test_delete_report(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(status=204))

    assert client.delete_audit_report("quality-docs-courses", "103897235") is None
    assert sent[0].method == "DELETE"
    assert sent[0].url.path == "/pubapi/v1/audit/quality-docs-courses/103897235"


# =============================================================================
# TEST: v2 stream
# =============================================================================


def test_stream_from_a_start_date(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(make_client, respond(STREAM_PAGE))

    page = client.stream_audit_events(
        start_date=datetime(2026, 11, 4),
        end_date=date(2026, 11, 5),
        audit_types=["FILE_AUDIT", "USER_AUDIT", "GROUP_AUDIT"],
    )

    assert sent[0].method == "POST"
    assert sent[0].url.path == "/pubapi/v2/audit/stream"
    assert body(sent[0]) == {
        "startDate": "2026-11-04T00:00:00Z",
        "endDate": "2026-11-05",
        "auditType": ["FILE_AUDIT", "USER_AUDIT", "GROUP_AUDIT"],
    }
    assert page.next_cursor == "AAN_lwABAX1zZe9AAAAAAAAAAAAAAAAAAAAAAA"
    assert page.more_events is True
    assert page.cursor_expired is False
    preview, disabled, created = page.events
    assert preview.audit_source == "FILE_AUDIT"
    assert preview.date == datetime(2026, 11, 5, 19, 29, 21, tzinfo=UTC)
    assert preview.source_path == "/Shared/Docs/hello world.txt"
    assert preview.user_id == "8"
    assert preview.ip_address == "198.51.100.7"
    assert disabled.subject == "John Roe ( jroe@acme.test )"
    assert disabled.action == "Disable"
    assert created.group == "Finance"
    assert created.source == "API"


def test_stream_from_a_cursor(make_client: Callable[..., EgnyteClient]) -> None:
    client, sent = _client(
        make_client,
        respond({"events": [], "nextCursor": "next", "moreEvents": False}),
    )

    page = client.stream_audit_events(next_cursor="AAN_lw")

    assert body(sent[0]) == {"nextCursor": "AAN_lw"}
    assert page.events == []
    assert page.more_events is False
    assert page.cursor_expired is None


@pytest.mark.parametrize(
    "kwargs",
    [{}, {"start_date": date(2026, 11, 4), "next_cursor": "AAN_lw"}],
)
def test_stream_takes_a_start_date_or_a_cursor(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="start_date or next_cursor"):
        audit_ops.stream_audit_events(**kwargs)


# =============================================================================
# TEST: async client
# =============================================================================


async def test_async_create_poll_read_delete(
    make_async_client: Callable[..., AsyncEgnyteClient],
) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if request.method == "POST":
            return respond(JOB, status=202, Location=JOB_LOCATION)
        if request.method == "DELETE":
            return respond(status=204)
        if request.url.path.startswith("/pubapi/v1/audit/jobs/"):
            return respond(
                {"status": "completed"}, status=303, Location=REPORT_LOCATION
            )
        return respond(LOGIN_REPORT)

    async with make_async_client(handler) as client:
        job = await client.create_login_audit_report(
            START, END, events=["logins"], format="json"
        )
        status = await client.get_audit_job(job.id)
        assert status.is_complete
        assert status.report_id is not None
        report = await client.get_audit_report("logins", status.report_id, count=2)
        await client.delete_audit_report("logins", status.report_id)

    assert [(r.method, r.url.path) for r in sent] == [
        ("POST", "/pubapi/v1/audit/logins"),
        ("GET", "/pubapi/v1/audit/jobs/103897235"),
        ("GET", "/pubapi/v1/audit/logins/103897235"),
        ("DELETE", "/pubapi/v1/audit/logins/103897235"),
    ]
    assert body(sent[0]) == {"format": "json", **DATES, "events": ["logins"]}
    assert report.events[0].event == "Login"


async def test_async_running_job_and_stream(
    make_async_client: Callable[..., AsyncEgnyteClient],
) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if request.url.path == "/pubapi/v2/audit/stream":
            return respond(STREAM_PAGE)
        return respond({"status": "running"})

    client = make_async_client(handler)

    assert (await client.get_audit_job("1")).status == "running"
    page = await client.stream_audit_events(next_cursor="AAN_lw")
    assert len(page.events) == 3
    assert body(sent[1]) == {"nextCursor": "AAN_lw"}


async def test_async_report_download(
    make_async_client: Callable[..., AsyncEgnyteClient],
) -> None:
    client = make_async_client(lambda request: httpx.Response(200, content=b"a,b\n"))

    assert await client.download_audit_report("etmf", "9") == b"a,b\n"
