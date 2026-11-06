"""
Coverage of the `audit` commands against a mock-transport client.

Every report type's create is asserted on the body it sends, and the job,
report, download, delete, and stream commands on their requests and output.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, get_args

import click
import httpx
import pytest
from click.testing import Result
from conftest import API, body, respond

from egnyte_client.cli.commands import audit
from egnyte_client.schemas import audit as schemas

Runner = Callable[..., tuple[Result, list[httpx.Request]]]

JOB: dict[str, Any] = {"id": 103897235}
REPORT_LOCATION = f"{API}/v1/audit/logins/103897235"

LOGIN_REPORT: dict[str, Any] = {
    "total_count": 15,
    "offset": 5,
    "count": 1,
    "events": [
        {
            "username": "Jane Doe ( jdoe@acme.test )",
            "user_id": 8,
            "event": "Login",
            "ip_address": "198.51.100.7",
            "access": "Web UI",
            "time": "2026-11-05T18:35:12Z",
            "logout_time": "",
        }
    ],
}

STREAM_PAGE: dict[str, Any] = {
    "events": [
        {
            "date": "2026-11-05T18:35:12Z",
            "auditSource": "FILE_AUDIT",
            "action": "Upload",
            "user": "Jane Doe ( jdoe@acme.test )",
            "sourcePath": "/Shared/a.txt",
        }
    ],
    "nextCursor": "cursor-2",
    "moreEvents": True,
}

DATES = ("2026-01-01", "2026-02-01T12:30:00")
RANGE = {"date_start": "2026-01-01T00:00:00Z", "date_end": "2026-02-01T12:30:00Z"}


@pytest.fixture
def run(cli_runner: Callable[..., Runner]) -> Callable[..., Runner]:
    """
    Return a factory for a runner invoking the CLI `audit` group against a handler.

    Returns:
        Callable[..., Runner]: Takes a handler, gives back the runner.
    """
    return lambda handler: cli_runner(handler, prefix=("audit",))


def _json(result: Result) -> Any:
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


@pytest.mark.parametrize(
    ("choice", "literal"),
    [
        (audit.REPORT_TYPES, schemas.AuditReportType),
        (audit.FORMATS, schemas.AuditReportFormat),
        (audit.LOGIN_EVENTS, schemas.LoginAuditEvent),
        (audit.ACCESS_POINTS, schemas.LoginAccessPoint),
        (audit.FILE_TRANSACTIONS, schemas.FileAuditTransaction),
        (audit.USER_ACTIONS, schemas.UserAuditAction),
        (audit.GROUP_ACTIONS, schemas.GroupAuditAction),
        (audit.WORKFLOW_ACTIONS, schemas.WorkflowAuditAction),
        (audit.WORKFLOW_TYPES, schemas.WorkflowAuditType),
        (audit.WORKFLOW_TEMPLATE_ACTIONS, schemas.WorkflowTemplateAuditAction),
        (audit.QUALITY_DOCS_ACTIONS, schemas.QualityDocsAuditAction),
        (audit.QUALITY_DOCS_STATUSES, schemas.QualityDocsStatus),
        (audit.QUALITY_DOCS_CATEGORY_ACTIONS, schemas.QualityDocsCategoryAuditAction),
        (audit.QUALITY_DOCS_COURSE_ACTIONS, schemas.QualityDocsCourseAuditAction),
        (audit.QUALITY_DOCS_COURSE_PARAMETERS, schemas.QualityDocsCourseParameter),
        (audit.ETMF_ACTIONS, schemas.EtmfAuditAction),
        (audit.UPLOAD_REQUEST_ACTIONS, schemas.UploadRequestAuditAction),
        (audit.STREAM_TYPES, schemas.AuditStreamType),
    ],
)
def test_choices_match_the_client_literals(choice: click.Choice, literal: Any) -> None:
    assert choice.choices == get_args(literal.__value__)


def test_every_report_type_has_a_create_command() -> None:
    assert list(audit.create.commands) == list(audit.REPORT_TYPES.choices)


# =============================================================================
# TEST: report creates
# =============================================================================


CREATES: list[tuple[str, tuple[str, ...], dict[str, Any]]] = [
    (
        "logins",
        (
            "--event",
            "logins",
            "--event",
            "failed_attempts",
            "--access-point",
            "web",
            "--user",
            "jdoe",
            "--suppress-emails",
        ),
        {
            "format": "json",
            "events": ["logins", "failed_attempts"],
            "access_points": ["web"],
            "users": ["jdoe"],
            "suppress_emails": True,
        },
    ),
    (
        "files",
        (
            "--folder",
            "/Shared/Finance/",
            "--file",
            "report*.pdf",
            "--user",
            "jdoe",
            "--transaction",
            "upload",
            "--transaction",
            "download",
            "--format",
            "csv",
        ),
        {
            "format": "csv",
            "folders": ["/Shared/Finance"],
            "file": "report*.pdf",
            "users": ["jdoe"],
            "transaction_type": ["upload", "download"],
        },
    ),
    (
        "permissions",
        (
            "--folder",
            "/Shared/Finance",
            "--assigner",
            "admin",
            "--assignee-user",
            "jdoe",
            "--assignee-group",
            "Finance",
            "--suppress-emails",
        ),
        {
            "format": "json",
            "folders": ["/Shared/Finance"],
            "assigners": ["admin"],
            "assignee_users": ["jdoe"],
            "assignee_groups": ["Finance"],
            "suppress_emails": True,
        },
    ),
    (
        "users",
        (
            "--action",
            "CREATE",
            "--action",
            "PASSWORD_RESET",
            "--performed-by",
            "admin",
            "--subject",
            "jdoe",
            "--include-system-actions",
        ),
        {
            "format": "json",
            "action_type": ["CREATE", "PASSWORD_RESET"],
            "performed_by": ["admin"],
            "subject": ["jdoe"],
            "include_system_actions": True,
        },
    ),
    (
        "groups",
        (
            "--action",
            "RENAME",
            "--user",
            "admin",
            "--group",
            "Finance",
            "--exclude-system-actions",
        ),
        {
            "format": "json",
            "action_type": ["RENAME"],
            "users": ["admin"],
            "groups": ["Finance"],
            "include_system_actions": False,
        },
    ),
    (
        "workgroup-settings",
        ("--user", "admin"),
        {"format": "json", "users": ["admin"]},
    ),
    (
        "workflows",
        (
            "--user",
            "jdoe",
            "--file",
            "Contract*",
            "--action",
            "WORKFLOW_CREATED",
            "--workflow-type",
            "APPROVAL",
            "--suppress-emails",
        ),
        {
            "format": "json",
            "users": ["jdoe"],
            "file": "Contract*",
            "workflow_actions": ["WORKFLOW_CREATED"],
            "workflow_types": ["APPROVAL"],
            "suppress_emails": True,
        },
    ),
    (
        "workflow-templates",
        ("--user", "jdoe", "--action", "TEMPLATE_EDITED"),
        {
            "format": "json",
            "users": ["jdoe"],
            "workflow_template_actions": ["TEMPLATE_EDITED"],
        },
    ),
    (
        "quality-docs",
        (
            "--user",
            "jdoe",
            "--document-id",
            "qd-1",
            "--categories",
            '[{"id": "c1", "subcategoryIds": ["s1"]}]',
            "--category",
            "c2",
            "--action",
            "PREVIEW",
            "--status",
            "EFFECTIVE",
            "--suppress-emails",
        ),
        {
            "format": "json",
            "users": ["jdoe"],
            "quality_document_id": "qd-1",
            "quality_docs_categories": [
                {"id": "c1", "subcategoryIds": ["s1"]},
                {"id": "c2"},
            ],
            "quality_docs_actions": ["PREVIEW"],
            "quality_docs_statuses": ["EFFECTIVE"],
            "suppress_emails": True,
        },
    ),
    (
        "quality-docs-categories",
        ("--category", "c1", "--action", "CATEGORY_ADDED"),
        {
            "format": "json",
            "quality_docs_categories": [{"id": "c1"}],
            "quality_docs_categories_actions": ["CATEGORY_ADDED"],
        },
    ),
    (
        "quality-docs-courses",
        (
            "--user",
            "jdoe",
            "--course-id",
            "course-1",
            "--action",
            "COURSE_MODIFIED",
            "--parameter",
            "NAME",
            "--parameter",
            "ASSIGNEES",
        ),
        {
            "format": "json",
            "users": ["jdoe"],
            "quality_docs_courses_ids": ["course-1"],
            "quality_docs_courses_actions": ["COURSE_MODIFIED"],
            "quality_docs_courses_parameters": ["NAME", "ASSIGNEES"],
        },
    ),
    (
        "etmf",
        (
            "--user",
            "jdoe",
            "--action",
            "STUDY_CREATED",
            "--study-id",
            "study-1",
            "--artifact-number",
            "01.01.01",
            "--suppress-emails",
        ),
        {
            "format": "json",
            "users": ["jdoe"],
            "etmf_actions": ["STUDY_CREATED"],
            "etmf_study_ids": ["study-1"],
            "etmf_artifact_number": "01.01.01",
            "suppress_emails": True,
        },
    ),
    (
        "snapshot-restore",
        ("--user", "jdoe", "--exclude-system-actions", "--suppress-emails"),
        {
            "format": "json",
            "users": ["jdoe"],
            "include_system_actions": False,
            "suppress_emails": True,
        },
    ),
    (
        "upload-requests",
        ("--user", "jdoe", "--action", "FILE_UPLOADED"),
        {
            "format": "json",
            "users": ["jdoe"],
            "upload_requests_actions": ["FILE_UPLOADED"],
        },
    ),
]


def test_every_report_type_is_covered() -> None:
    assert [name for name, _, _ in CREATES] == list(audit.REPORT_TYPES.choices)


@pytest.mark.parametrize(
    ("report_type", "args", "expected"), CREATES, ids=[name for name, _, _ in CREATES]
)
def test_create(
    run: Callable[..., Runner],
    report_type: str,
    args: tuple[str, ...],
    expected: dict[str, Any],
) -> None:
    result, sent = run(lambda r: respond(JOB))("create", report_type, *DATES, *args)

    assert _json(result) == {"id": "103897235"}
    assert "audit job 103897235" in result.stderr
    assert sent[0].method == "POST"
    assert sent[0].url.path == f"/pubapi/v1/audit/{report_type}"
    assert body(sent[0]) == {**RANGE, **expected}


@pytest.mark.parametrize(
    "report_type",
    [name for name in audit.REPORT_TYPES.choices if name not in ("logins", "files")],
)
def test_create_with_only_dates(run: Callable[..., Runner], report_type: str) -> None:
    result, sent = run(lambda r: respond(JOB))(
        "create", report_type, "2026-01-01", "2026-01-02"
    )

    assert _json(result)["id"] == "103897235"
    assert body(sent[0]) == {
        "format": "json",
        "date_start": "2026-01-01T00:00:00Z",
        "date_end": "2026-01-02T00:00:00Z",
    }


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (
            ("logins", "2026-02-01", "2026-01-01", "--event", "logins"),
            "END must be after START.",
        ),
        (("logins", "2026-01-01", "2026-02-01"), "Missing option '--event'"),
        (
            ("logins", "2026-01-01", "2026-02-01", "--event", "signins"),
            "Invalid value for '--event'",
        ),
        (("logins", "yesterday", "2026-02-01"), "Invalid value for 'START'"),
        (("files", "2026-01-01", "2026-02-01"), "Give --folder, --file, or both."),
        (
            ("files", "2026-01-01", "2026-02-01", "--file", "*.pdf"),
            "cannot start with the * wildcard",
        ),
        (
            ("workflows", "2026-01-01", "2026-02-01", "--file", "*x"),
            "cannot start with the * wildcard",
        ),
        (
            ("quality-docs", "2026-01-01", "2026-02-01", "--categories", "{oops"),
            "expected a JSON document",
        ),
        (
            ("quality-docs", "2026-01-01", "2026-02-01", "--categories", '[{"x": 1}]'),
            "0.id: Field required",
        ),
        (
            ("users", "2026-01-01", "2026-02-01", "--format", "xml"),
            "Invalid value for '--format'",
        ),
    ],
)
def test_create_refusals(
    run: Callable[..., Runner], args: tuple[str, ...], message: str
) -> None:
    result, sent = run(lambda r: respond(JOB))("create", *args)

    assert result.exit_code == 2, result.output
    assert message in result.stderr
    assert not sent


# =============================================================================
# TEST: jobs and reports
# =============================================================================


def test_job_running(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond({"status": "running"}))("job", "103897235")

    assert _json(result) == {
        "status": "running",
        "location": None,
        "report_type": None,
        "report_id": None,
    }
    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/audit/jobs/103897235"


def test_job_completed(run: Callable[..., Runner]) -> None:
    result, _ = run(
        lambda r: respond({"status": "completed"}, status=303, Location=REPORT_LOCATION)
    )("job", "103897235")

    assert _json(result) == {
        "status": "completed",
        "location": REPORT_LOCATION,
        "report_type": "logins",
        "report_id": "103897235",
    }


def test_get(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(LOGIN_REPORT))(
        "get", "logins", "103897235", "--offset", "5", "--count", "1"
    )

    output = _json(result)
    assert output["total_count"] == 15
    assert output["events"][0]["ip_address"] == "198.51.100.7"
    assert output["events"][0]["logout_time"] is None
    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/audit/logins/103897235"
    assert dict(sent[0].url.params) == {"offset": "5", "count": "1"}


def test_get_rejects_an_unknown_type(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(LOGIN_REPORT))("get", "login", "1")

    assert result.exit_code == 2
    assert "Invalid value for 'TYPE'" in result.stderr
    assert not sent


CSV = b"Username,Event\r\nJane Doe,Login\r\n"


def test_download_to_stdout(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: httpx.Response(200, content=CSV))(
        "download", "files", "103897235", "-o", "-"
    )

    assert result.exit_code == 0, result.output
    assert result.stdout_bytes == CSV
    assert sent[0].method == "GET"
    assert sent[0].url.path == "/pubapi/v1/audit/files/103897235"


def test_download_defaults_to_stdout(run: Callable[..., Runner]) -> None:
    result, _ = run(lambda r: httpx.Response(200, content=CSV))(
        "download", "files", "103897235"
    )

    assert result.stdout_bytes == CSV


def test_download_to_a_file(run: Callable[..., Runner], tmp_path: Path) -> None:
    target = tmp_path / "report.csv"

    result, _ = run(lambda r: httpx.Response(200, content=CSV))(
        "download", "files", "103897235", "--output", str(target)
    )

    assert result.exit_code == 0, result.output
    assert result.stdout_bytes == b""
    assert target.read_bytes() == CSV
    assert f"Wrote {len(CSV)} bytes to {target}" in result.stderr


def test_delete_asks_first(run: Callable[..., Runner]) -> None:
    invoke = run(lambda r: respond())

    declined, sent = invoke("delete", "logins", "103897235", input="n\n")
    assert declined.exit_code == 1
    assert "Delete logins audit report 103897235?" in declined.output
    assert not sent

    confirmed, sent = invoke("delete", "logins", "103897235", "-y")
    assert confirmed.exit_code == 0, confirmed.output
    assert "Deleted logins audit report 103897235" in confirmed.stderr
    assert sent[0].method == "DELETE"
    assert sent[0].url.path == "/pubapi/v1/audit/logins/103897235"


# =============================================================================
# TEST: stream
# =============================================================================


def test_stream_from_a_start_date(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(STREAM_PAGE))(
        "stream",
        "--start-date",
        "2026-11-01T08:00:00",
        "--end-date",
        "2026-11-02",
        "--type",
        "FILE_AUDIT",
        "--type",
        "USER_AUDIT",
    )

    output = _json(result)
    assert output["next_cursor"] == "cursor-2"
    assert output["more_events"] is True
    assert output["events"][0]["source_path"] == "/Shared/a.txt"
    assert sent[0].method == "POST"
    assert sent[0].url.path == "/pubapi/v2/audit/stream"
    assert body(sent[0]) == {
        "startDate": "2026-11-01T08:00:00Z",
        "endDate": "2026-11-02T00:00:00Z",
        "auditType": ["FILE_AUDIT", "USER_AUDIT"],
    }


def test_stream_from_a_cursor(run: Callable[..., Runner]) -> None:
    result, sent = run(lambda r: respond(STREAM_PAGE))("stream", "--cursor", "cursor-1")

    assert _json(result)["next_cursor"] == "cursor-2"
    assert len(sent) == 1
    assert body(sent[0]) == {"nextCursor": "cursor-1"}


@pytest.mark.parametrize(
    "args",
    [(), ("--start-date", "2026-11-01", "--cursor", "cursor-1")],
    ids=["neither", "both"],
)
def test_stream_needs_a_start_date_or_a_cursor(
    run: Callable[..., Runner], args: tuple[str, ...]
) -> None:
    result, sent = run(lambda r: respond(STREAM_PAGE))("stream", *args)

    assert result.exit_code == 2
    assert "Give exactly one of --start-date or --cursor." in result.stderr
    assert not sent
