from datetime import UTC, date, datetime
from urllib.parse import unquote

import httpx
from pydantic import ValidationError

from egnyte_client.operations.generic import (
    Operation,
    content,
    empty,
    encode_id,
    model,
    normalize_path,
    query,
)
from egnyte_client.schemas.audit import (
    AuditEventPage,
    AuditJob,
    AuditJobState,
    AuditJobStatus,
    AuditReport,
    AuditReportFormat,
    AuditReportRequest,
    AuditReportType,
    AuditStreamRequest,
    AuditStreamType,
    EtmfAuditAction,
    EtmfAuditRequest,
    FileAuditRequest,
    FileAuditTransaction,
    GroupAuditAction,
    GroupAuditRequest,
    LoginAccessPoint,
    LoginAuditEvent,
    LoginAuditRequest,
    PermissionsAuditRequest,
    QualityDocsAuditAction,
    QualityDocsAuditRequest,
    QualityDocsCategoriesAuditRequest,
    QualityDocsCategoryAuditAction,
    QualityDocsCategoryFilter,
    QualityDocsCourseAuditAction,
    QualityDocsCourseParameter,
    QualityDocsCoursesAuditRequest,
    QualityDocsStatus,
    SnapshotRestoreAuditRequest,
    UploadRequestAuditAction,
    UploadRequestsAuditRequest,
    UserAuditAction,
    UserAuditRequest,
    WorkflowAuditAction,
    WorkflowAuditRequest,
    WorkflowAuditType,
    WorkflowTemplateAuditAction,
    WorkflowTemplateAuditRequest,
    WorkgroupSettingsAuditRequest,
)

# =============================================================================
# FUNCTIONS: Dates
# =============================================================================


def _as_utc(value: date | datetime) -> datetime:
    """
    Read a date as midnight UTC and a naive datetime as UTC.

    Returns:
        datetime: An aware datetime in UTC.
    """
    if not isinstance(value, datetime):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _audit_date(value: date | datetime) -> str:
    """
    Format a date as `YYYY-MM-DD` and a datetime as `YYYY-MM-DDTHH:MM:SSZ`.

    These are the two forms the audit APIs take; a naive datetime is read as
    UTC.

    Returns:
        str: The date as the audit APIs take it.
    """
    if not isinstance(value, datetime):
        return value.isoformat()
    return _as_utc(value).strftime("%Y-%m-%dT%H:%M:%SZ")


def _date_range(
    start_date: date | datetime, end_date: date | datetime
) -> tuple[str, str]:
    """
    Check and format a report's date range, which must not be empty.

    Returns:
        tuple[str, str]: The start and end, as the audit APIs take them.
    """
    if _as_utc(end_date) <= _as_utc(start_date):
        raise ValueError("end_date must be after start_date")
    return _audit_date(start_date), _audit_date(end_date)


def _create(
    report_type: AuditReportType, request: AuditReportRequest
) -> Operation[AuditJob]:
    return Operation(
        method="POST",
        path=f"/v1/audit/{report_type}",
        body=request,
        parse=model(AuditJob),
    )


def _paths(folders: list[str] | None) -> list[str] | None:
    return (
        [normalize_path(folder) for folder in folders] if folders is not None else None
    )


# -----------------------------------------------------------------------------
# OPERATION: create_login_audit_report
# -----------------------------------------------------------------------------


def create_login_audit_report(
    start_date: date | datetime,
    end_date: date | datetime,
    *,
    events: list[LoginAuditEvent],
    format: AuditReportFormat = "json",
    access_points: list[LoginAccessPoint] | None = None,
    users: list[str] | None = None,
    suppress_emails: bool | None = None,
) -> Operation[AuditJob]:
    """
    Build the login audit report create.

    Returns:
        Operation[AuditJob]: The create operation.
    """
    if not events:
        raise ValueError("events needs at least one login event")
    date_start, date_end = _date_range(start_date, end_date)
    return _create(
        "logins",
        LoginAuditRequest(
            format=format,
            date_start=date_start,
            date_end=date_end,
            events=events,
            access_points=access_points,
            users=users,
            suppress_emails=suppress_emails,
        ),
    )


# -----------------------------------------------------------------------------
# OPERATION: create_file_audit_report
# -----------------------------------------------------------------------------


def create_file_audit_report(
    start_date: date | datetime,
    end_date: date | datetime,
    *,
    folders: list[str] | None = None,
    file: str | None = None,
    format: AuditReportFormat = "json",
    users: list[str] | None = None,
    transaction_types: list[FileAuditTransaction] | None = None,
    suppress_emails: bool | None = None,
) -> Operation[AuditJob]:
    """
    Build the file audit report create.

    Returns:
        Operation[AuditJob]: The create operation.
    """
    if not folders and not file:
        raise ValueError("the file audit report needs folders or a file")
    if file is not None and file.startswith("*"):
        raise ValueError("file cannot start with the * wildcard")
    date_start, date_end = _date_range(start_date, end_date)
    return _create(
        "files",
        FileAuditRequest(
            format=format,
            date_start=date_start,
            date_end=date_end,
            folders=_paths(folders),
            file=file,
            users=users,
            transaction_type=transaction_types,
            suppress_emails=suppress_emails,
        ),
    )


# -----------------------------------------------------------------------------
# OPERATION: create_permissions_audit_report
# -----------------------------------------------------------------------------


def create_permissions_audit_report(
    start_date: date | datetime,
    end_date: date | datetime,
    *,
    format: AuditReportFormat = "json",
    folders: list[str] | None = None,
    assigners: list[str] | None = None,
    assignee_users: list[str] | None = None,
    assignee_groups: list[str] | None = None,
    suppress_emails: bool | None = None,
) -> Operation[AuditJob]:
    """
    Build the permissions audit report create.

    Returns:
        Operation[AuditJob]: The create operation.
    """
    date_start, date_end = _date_range(start_date, end_date)
    return _create(
        "permissions",
        PermissionsAuditRequest(
            format=format,
            date_start=date_start,
            date_end=date_end,
            folders=_paths(folders),
            assigners=assigners,
            assignee_users=assignee_users,
            assignee_groups=assignee_groups,
            suppress_emails=suppress_emails,
        ),
    )


# -----------------------------------------------------------------------------
# OPERATION: create_user_audit_report
# -----------------------------------------------------------------------------


def create_user_audit_report(
    start_date: date | datetime,
    end_date: date | datetime,
    *,
    format: AuditReportFormat = "json",
    action_types: list[UserAuditAction] | None = None,
    performed_by: list[str] | None = None,
    subjects: list[str] | None = None,
    include_system_actions: bool | None = None,
) -> Operation[AuditJob]:
    """
    Build the user provisioning audit report create.

    Returns:
        Operation[AuditJob]: The create operation.
    """
    date_start, date_end = _date_range(start_date, end_date)
    return _create(
        "users",
        UserAuditRequest(
            format=format,
            date_start=date_start,
            date_end=date_end,
            action_type=action_types,
            performed_by=performed_by,
            subject=subjects,
            include_system_actions=include_system_actions,
        ),
    )


# -----------------------------------------------------------------------------
# OPERATION: create_group_audit_report
# -----------------------------------------------------------------------------


def create_group_audit_report(
    start_date: date | datetime,
    end_date: date | datetime,
    *,
    format: AuditReportFormat = "json",
    action_types: list[GroupAuditAction] | None = None,
    users: list[str] | None = None,
    groups: list[str] | None = None,
    include_system_actions: bool | None = None,
) -> Operation[AuditJob]:
    """
    Build the group provisioning audit report create.

    Returns:
        Operation[AuditJob]: The create operation.
    """
    date_start, date_end = _date_range(start_date, end_date)
    return _create(
        "groups",
        GroupAuditRequest(
            format=format,
            date_start=date_start,
            date_end=date_end,
            action_type=action_types,
            users=users,
            groups=groups,
            include_system_actions=include_system_actions,
        ),
    )


# -----------------------------------------------------------------------------
# OPERATION: create_workgroup_settings_audit_report
# -----------------------------------------------------------------------------


def create_workgroup_settings_audit_report(
    start_date: date | datetime,
    end_date: date | datetime,
    *,
    format: AuditReportFormat = "json",
    users: list[str] | None = None,
) -> Operation[AuditJob]:
    """
    Build the configuration settings audit report create.

    Returns:
        Operation[AuditJob]: The create operation.
    """
    date_start, date_end = _date_range(start_date, end_date)
    return _create(
        "workgroup-settings",
        WorkgroupSettingsAuditRequest(
            format=format,
            date_start=date_start,
            date_end=date_end,
            users=users,
        ),
    )


# -----------------------------------------------------------------------------
# OPERATION: create_workflow_audit_report
# -----------------------------------------------------------------------------


def create_workflow_audit_report(
    start_date: date | datetime,
    end_date: date | datetime,
    *,
    format: AuditReportFormat = "json",
    users: list[str] | None = None,
    file: str | None = None,
    workflow_actions: list[WorkflowAuditAction] | None = None,
    workflow_types: list[WorkflowAuditType] | None = None,
    suppress_emails: bool | None = None,
) -> Operation[AuditJob]:
    """
    Build the workflow audit report create.

    Returns:
        Operation[AuditJob]: The create operation.
    """
    if file is not None and file.startswith("*"):
        raise ValueError("file cannot start with the * wildcard")
    date_start, date_end = _date_range(start_date, end_date)
    return _create(
        "workflows",
        WorkflowAuditRequest(
            format=format,
            date_start=date_start,
            date_end=date_end,
            users=users,
            file=file,
            workflow_actions=workflow_actions,
            workflow_types=workflow_types,
            suppress_emails=suppress_emails,
        ),
    )


# -----------------------------------------------------------------------------
# OPERATION: create_workflow_template_audit_report
# -----------------------------------------------------------------------------


def create_workflow_template_audit_report(
    start_date: date | datetime,
    end_date: date | datetime,
    *,
    format: AuditReportFormat = "json",
    users: list[str] | None = None,
    workflow_template_actions: list[WorkflowTemplateAuditAction] | None = None,
    suppress_emails: bool | None = None,
) -> Operation[AuditJob]:
    """
    Build the workflow templates audit report create.

    Returns:
        Operation[AuditJob]: The create operation.
    """
    date_start, date_end = _date_range(start_date, end_date)
    return _create(
        "workflow-templates",
        WorkflowTemplateAuditRequest(
            format=format,
            date_start=date_start,
            date_end=date_end,
            users=users,
            workflow_template_actions=workflow_template_actions,
            suppress_emails=suppress_emails,
        ),
    )


# -----------------------------------------------------------------------------
# OPERATION: create_quality_docs_audit_report
# -----------------------------------------------------------------------------


def create_quality_docs_audit_report(
    start_date: date | datetime,
    end_date: date | datetime,
    *,
    format: AuditReportFormat = "json",
    users: list[str] | None = None,
    quality_document_id: str | None = None,
    quality_docs_categories: list[QualityDocsCategoryFilter] | None = None,
    quality_docs_actions: list[QualityDocsAuditAction] | None = None,
    quality_docs_statuses: list[QualityDocsStatus] | None = None,
    suppress_emails: bool | None = None,
) -> Operation[AuditJob]:
    """
    Build the Quality Docs audit report create.

    Returns:
        Operation[AuditJob]: The create operation.
    """
    date_start, date_end = _date_range(start_date, end_date)
    return _create(
        "quality-docs",
        QualityDocsAuditRequest(
            format=format,
            date_start=date_start,
            date_end=date_end,
            users=users,
            quality_document_id=quality_document_id,
            quality_docs_categories=quality_docs_categories,
            quality_docs_actions=quality_docs_actions,
            quality_docs_statuses=quality_docs_statuses,
            suppress_emails=suppress_emails,
        ),
    )


# -----------------------------------------------------------------------------
# OPERATION: create_quality_docs_categories_audit_report
# -----------------------------------------------------------------------------


def create_quality_docs_categories_audit_report(
    start_date: date | datetime,
    end_date: date | datetime,
    *,
    format: AuditReportFormat = "json",
    users: list[str] | None = None,
    quality_docs_categories: list[QualityDocsCategoryFilter] | None = None,
    quality_docs_categories_actions: list[QualityDocsCategoryAuditAction] | None = None,
    suppress_emails: bool | None = None,
) -> Operation[AuditJob]:
    """
    Build the Quality Docs categories audit report create.

    Returns:
        Operation[AuditJob]: The create operation.
    """
    date_start, date_end = _date_range(start_date, end_date)
    return _create(
        "quality-docs-categories",
        QualityDocsCategoriesAuditRequest(
            format=format,
            date_start=date_start,
            date_end=date_end,
            users=users,
            quality_docs_categories=quality_docs_categories,
            quality_docs_categories_actions=quality_docs_categories_actions,
            suppress_emails=suppress_emails,
        ),
    )


# -----------------------------------------------------------------------------
# OPERATION: create_quality_docs_courses_audit_report
# -----------------------------------------------------------------------------


def create_quality_docs_courses_audit_report(
    start_date: date | datetime,
    end_date: date | datetime,
    *,
    format: AuditReportFormat = "json",
    users: list[str] | None = None,
    quality_docs_courses_ids: list[str] | None = None,
    quality_docs_courses_actions: list[QualityDocsCourseAuditAction] | None = None,
    quality_docs_courses_parameters: list[QualityDocsCourseParameter] | None = None,
    suppress_emails: bool | None = None,
) -> Operation[AuditJob]:
    """
    Build the Quality Docs courses audit report create.

    Returns:
        Operation[AuditJob]: The create operation.
    """
    date_start, date_end = _date_range(start_date, end_date)
    return _create(
        "quality-docs-courses",
        QualityDocsCoursesAuditRequest(
            format=format,
            date_start=date_start,
            date_end=date_end,
            users=users,
            quality_docs_courses_ids=quality_docs_courses_ids,
            quality_docs_courses_actions=quality_docs_courses_actions,
            quality_docs_courses_parameters=quality_docs_courses_parameters,
            suppress_emails=suppress_emails,
        ),
    )


# -----------------------------------------------------------------------------
# OPERATION: create_etmf_audit_report
# -----------------------------------------------------------------------------


def create_etmf_audit_report(
    start_date: date | datetime,
    end_date: date | datetime,
    *,
    format: AuditReportFormat = "json",
    users: list[str] | None = None,
    etmf_actions: list[EtmfAuditAction] | None = None,
    etmf_study_ids: list[str] | None = None,
    etmf_artifact_number: str | None = None,
    suppress_emails: bool | None = None,
) -> Operation[AuditJob]:
    """
    Build the eTMF audit report create.

    Returns:
        Operation[AuditJob]: The create operation.
    """
    date_start, date_end = _date_range(start_date, end_date)
    return _create(
        "etmf",
        EtmfAuditRequest(
            format=format,
            date_start=date_start,
            date_end=date_end,
            users=users,
            etmf_actions=etmf_actions,
            etmf_study_ids=etmf_study_ids,
            etmf_artifact_number=etmf_artifact_number,
            suppress_emails=suppress_emails,
        ),
    )


# -----------------------------------------------------------------------------
# OPERATION: create_snapshot_restore_audit_report
# -----------------------------------------------------------------------------


def create_snapshot_restore_audit_report(
    start_date: date | datetime,
    end_date: date | datetime,
    *,
    format: AuditReportFormat = "json",
    users: list[str] | None = None,
    include_system_actions: bool | None = None,
    suppress_emails: bool | None = None,
) -> Operation[AuditJob]:
    """
    Build the snapshot restore audit report create.

    Returns:
        Operation[AuditJob]: The create operation.
    """
    date_start, date_end = _date_range(start_date, end_date)
    return _create(
        "snapshot-restore",
        SnapshotRestoreAuditRequest(
            format=format,
            date_start=date_start,
            date_end=date_end,
            users=users,
            include_system_actions=include_system_actions,
            suppress_emails=suppress_emails,
        ),
    )


# -----------------------------------------------------------------------------
# OPERATION: create_upload_requests_audit_report
# -----------------------------------------------------------------------------


def create_upload_requests_audit_report(
    start_date: date | datetime,
    end_date: date | datetime,
    *,
    format: AuditReportFormat = "json",
    users: list[str] | None = None,
    upload_requests_actions: list[UploadRequestAuditAction] | None = None,
    suppress_emails: bool | None = None,
) -> Operation[AuditJob]:
    """
    Build the upload requests audit report create.

    Returns:
        Operation[AuditJob]: The create operation.
    """
    date_start, date_end = _date_range(start_date, end_date)
    return _create(
        "upload-requests",
        UploadRequestsAuditRequest(
            format=format,
            date_start=date_start,
            date_end=date_end,
            users=users,
            upload_requests_actions=upload_requests_actions,
            suppress_emails=suppress_emails,
        ),
    )


# -----------------------------------------------------------------------------
# OPERATION: get_audit_job
# -----------------------------------------------------------------------------


def _report_location(location: str) -> tuple[str, str] | None:
    """
    Split a report URL, `.../pubapi/v1/audit/{type}/{id}`, into type and ID.

    Returns:
        tuple[str, str] | None: The report type and ID, or None if the URL is
        not a report's.
    """
    parts = httpx.URL(location).path.rstrip("/").split("/")
    if len(parts) < 4 or parts[-4:-2] != ["v1", "audit"]:
        return None
    return unquote(parts[-2]), unquote(parts[-1])


def parse_job_status(response: httpx.Response) -> AuditJobStatus:
    """
    Read a job poll: a 200 while running, or a 303 to the finished report.

    The redirect is not followed. Its `Location` gives the report's type and
    ID; a type this client does not know leaves `report_type` None.

    Returns:
        AuditJobStatus: Where the job stands.
    """
    location = response.headers.get("Location")
    state: AuditJobState = (
        "completed" if response.status_code == 303 or location else "running"
    )
    if response.content:
        state = AuditJobStatus.model_validate_json(response.content).status

    report = _report_location(location) if location else None
    if report is None:
        return AuditJobStatus(status=state, location=location)
    report_type, report_id = report
    try:
        return AuditJobStatus.model_validate(
            {
                "status": state,
                "location": location,
                "report_type": report_type,
                "report_id": report_id,
            }
        )
    except ValidationError:
        return AuditJobStatus(status=state, location=location, report_id=report_id)


def get_audit_job(job_id: str) -> Operation[AuditJobStatus]:
    """
    Build the report job poll.

    Returns:
        Operation[AuditJobStatus]: The get audit job operation.
    """
    return Operation(
        method="GET",
        path=f"/v1/audit/jobs/{encode_id(job_id)}",
        parse=parse_job_status,
        accept=frozenset({303}),
    )


# -----------------------------------------------------------------------------
# OPERATION: get_audit_report
# -----------------------------------------------------------------------------


def _report_path(report_type: AuditReportType, report_id: str) -> str:
    return f"/v1/audit/{encode_id(report_type)}/{encode_id(report_id)}"


def get_audit_report(
    report_type: AuditReportType,
    report_id: str,
    *,
    offset: int | None = None,
    count: int | None = None,
) -> Operation[AuditReport]:
    """
    Build the JSON report read.

    Returns:
        Operation[AuditReport]: The get audit report operation.
    """
    return Operation(
        method="GET",
        path=_report_path(report_type, report_id),
        params=query(offset=offset, count=count),
        parse=model(AuditReport),
    )


# -----------------------------------------------------------------------------
# OPERATION: download_audit_report
# -----------------------------------------------------------------------------


def download_audit_report(
    report_type: AuditReportType, report_id: str
) -> Operation[bytes]:
    """
    Build the raw report read, as a CSV report needs.

    Returns:
        Operation[bytes]: The download audit report operation.
    """
    return Operation(
        method="GET", path=_report_path(report_type, report_id), parse=content
    )


# -----------------------------------------------------------------------------
# OPERATION: delete_audit_report
# -----------------------------------------------------------------------------


def delete_audit_report(
    report_type: AuditReportType, report_id: str
) -> Operation[None]:
    """
    Build the report delete.

    Returns:
        Operation[None]: The delete audit report operation.
    """
    return Operation(
        method="DELETE", path=_report_path(report_type, report_id), parse=empty
    )


# -----------------------------------------------------------------------------
# OPERATION: stream_audit_events
# -----------------------------------------------------------------------------


def stream_audit_events(
    *,
    start_date: date | datetime | None = None,
    next_cursor: str | None = None,
    audit_types: list[AuditStreamType] | None = None,
    end_date: date | datetime | None = None,
) -> Operation[AuditEventPage]:
    """
    Build one page of the v2 audit stream.

    Returns:
        Operation[AuditEventPage]: The stream operation.
    """
    if (start_date is None) == (next_cursor is None):
        raise ValueError(
            "stream_audit_events takes start_date or next_cursor, not both"
        )

    return Operation(
        method="POST",
        path="/v2/audit/stream",
        body=AuditStreamRequest(
            start_date=_audit_date(start_date) if start_date is not None else None,
            end_date=_audit_date(end_date) if end_date is not None else None,
            next_cursor=next_cursor,
            audit_type=audit_types,
        ),
        parse=model(AuditEventPage),
    )
