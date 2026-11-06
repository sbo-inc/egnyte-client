from datetime import datetime
from typing import Annotated, Literal

from pydantic import AliasChoices, BeforeValidator, ConfigDict, Field

from egnyte_client.schemas.generic import GenericBaseModel

type AuditReportType = Literal[
    "logins",
    "files",
    "permissions",
    "users",
    "groups",
    "workgroup-settings",
    "workflows",
    "workflow-templates",
    "quality-docs",
    "quality-docs-categories",
    "quality-docs-courses",
    "etmf",
    "snapshot-restore",
    "upload-requests",
]
type AuditReportFormat = Literal["csv", "json"]
type AuditJobState = Literal["running", "completed"]

type LoginAuditEvent = Literal[
    "logins", "logouts", "account_lockouts", "password_resets", "failed_attempts"
]
# The documentation lists `Web, FTP, Mobile`, but Egnyte accepts only lowercase.
type LoginAccessPoint = Literal["web", "ftp", "mobile"]
type FileAuditTransaction = Literal[
    "upload",
    "download",
    "preview",
    "delete",
    "copy",
    "move",
    "create_folder",
    "restore_trash",
    "delete_trash",
    "create_link",
    "delete_link",
    "download_link",
]
type UserAuditAction = Literal[
    "CREATE",
    "UPDATE",
    "DISABLE",
    "ENABLE",
    "DELETE",
    "PASSWORD_RESET",
    "PASSWORD_CHANGE",
]
type GroupAuditAction = Literal[
    "CREATE", "ADD_USERS", "REMOVE_USERS", "RENAME", "DELETE"
]
type WorkflowAuditAction = Literal[
    "WORKFLOW_CREATED",
    "WORKFLOW_CANCELLED",
    "WORKFLOW_COMPLETED",
    "STEP_ACTIVATED",
    "STEP_COMPLETED",
    "STEP_CANCELLED",
    "STEP_REJECTED",
    "STEP_FAILED",
    "WEBHOOK_CALLED",
    "WEBHOOK_COMPLETION_SIGNAL_RECEIVED",
    "WEBHOOK_RETRIED",
    "FILE_MOVED",
    "FILE_MOVE_RETRIED",
    "FILE_CONVERTED",
    "FILE_CONVERT_RETRIED",
    "TODO_TASK_COMPLETED",
    "REVIEW_TASK_COMPLETED",
    "REVIEW_TASK_CANCELLED",
    "APPROVAL_TASK_APPROVED",
    "APPROVAL_TASK_REJECTED",
    "APPROVAL_TASK_CANCELLED",
    "E_SIGNATURE_CAPTURED",
    "COMMENT_ADDED",
    "WORKFLOW_EDITED",
]
type WorkflowAuditType = Literal[
    "REVIEW_APPROVE", "TODO", "APPROVAL", "REVIEW", "MULTISTEP", "TEMPLATE"
]
type WorkflowTemplateAuditAction = Literal[
    "TEMPLATE_CREATED",
    "TEMPLATE_STATUS_CHANGED",
    "TEMPLATE_EDITED",
    "STEP_ADDED",
    "STEP_REMOVED",
    "ITEM_ADDED",
    "ITEM_REMOVED",
]
type QualityDocsAuditAction = Literal[
    "DOCUMENT_ADDED",
    "DOCUMENT_MODIFIED",
    "DOCUMENT_IMPORTED",
    "DOWNLOAD_RENDITION",
    "PREVIEW",
    "DOWNLOAD_ORIGINAL",
    "TRAINING_ASSIGNED",
    "TRAINING_MODIFIED",
    "TRAINING_CANCELED",
    "TRAINING_OVERDUE",
    "TRAINING_COMPLETED",
    "TRAINING_IMPORTED",
    "DRAFT_ADDED",
    "DRAFT_EDITED",
    "DRAFT_DELETED",
]
type QualityDocsStatus = Literal["DRAFT", "EFFECTIVE", "FUTURE_EFFECTIVE", "OBSOLETE"]
type QualityDocsCategoryAuditAction = Literal[
    "CATEGORY_ADDED", "CATEGORY_MODIFIED", "SUBCATEGORY_ADDED", "SUBCATEGORY_MODIFIED"
]
type QualityDocsCourseAuditAction = Literal[
    "COURSE_CREATED",
    "COURSE_MODIFIED",
    "COURSE_STATUS_CHANGED",
    "COURSE_DOCUMENT_STATUS_CHANGED",
]
type QualityDocsCourseParameter = Literal[
    "NAME",
    "DESCRIPTION",
    "DAYS_TO_COMPLETE",
    "MIN_DAYS_BEFORE_OBSOLETE",
    "RECURRENCE_PERIOD",
    "START_DATE",
    "ASSIGNEES",
    "DOCUMENTS",
    "COURSE_STATUS",
    "DOCUMENT_STATUS",
]
type EtmfAuditAction = Literal[
    "STUDY_CREATED",
    "STUDY_UPDATED",
    "TRIAL_UPDATED",
    "COUNTRY_CREATED",
    "COUNTRY_UPDATED",
    "SITE_CREATED",
    "SITE_UPDATED",
    "STUDY_ACTIVATED",
    "STUDY_DEACTIVATED",
    "TRIAL_ACTIVATED",
    "TRIAL_DEACTIVATED",
    "COUNTRY_ACTIVATED",
    "COUNTRY_DEACTIVATED",
    "SITE_ACTIVATED",
    "SITE_DEACTIVATED",
    "DOCUMENT_ADDED",
    "DOCUMENT_DELETED",
    "DOCUMENT_RECLASSIFIED",
    "DOCUMENT_CLASSIFICATION_CHANGED",
    "ARTIFACT_CREATED",
    "ARTIFACT_STATUS_UPDATED",
    "REQUIRED_ARTIFACT_ADDED",
    "REQUIRED_ARTIFACT_REMOVED",
    "STUDY_PERMISSIONS_UPDATED",
    "TRIAL_PERMISSIONS_UPDATED",
    "COUNTRY_PERMISSIONS_UPDATED",
    "SITE_PERMISSIONS_UPDATED",
    "MILESTONE_ADDED",
    "MILESTONE_COMPLETED",
    "MILESTONE_ACTIVATED",
    "MILESTONE_UPDATED",
    "IMPORT_CREATED",
    "IMPORT_FAILED",
    "IMPORT_SUCCEEDED",
    "IMPORT_CONFIRMED",
    "IMPORT_REJECTED",
    "QC_INITIATED",
    "QC_APPROVED",
    "QC_REJECTED",
    "COMMENT_CREATED",
    "ARTIFACT_REQUIREMENT_SETTING_UPDATED",
    "MILESTONE_REQUIREMENT_SETTING_UPDATED",
    "MILESTONE_ACTIVATION_REQUIREMENT_SETTING_UPDATED",
    "ARTIFACT_UNBLINDED",
    "ARTIFACT_BLINDED",
]
type UploadRequestAuditAction = Literal[
    "REQUEST_CREATED",
    "REQUEST_MODIFIED",
    "REQUEST_STATUS_CHANGED",
    "FILE_UPLOADED",
    "FILE_REMOVED",
    "DOCUMENT_SUBMITTED",
    "DOCUMENT_SKIPPED",
    "DOCUMENT_ACCEPTED",
    "DOCUMENT_REJECTED",
    "REQUEST_COMPLETED",
    "REQUEST_CANCELED",
]
type AuditStreamType = Literal[
    "FILE_AUDIT",
    "FOLDER_OPTION_AUDIT",
    "LOGIN_AUDIT",
    "PERMISSION_AUDIT",
    "USER_AUDIT",
    "GROUP_AUDIT",
    "WG_SETTINGS_AUDIT",
    "WORKFLOW_AUDIT",
    "WORKFLOW_TEMPLATES_AUDIT",
    "QUALITY_DOCS_AUDIT",
    "QUALITY_DOCS_CATEGORIES_AUDIT",
    "QUALITY_DOCS_COURSES_AUDIT",
    "ETMF_AUDIT",
    "SNAPSHOT_RESTORE_AUDIT",
    "ESIGNATURE_AUDIT",
    "UPLOAD_REQUESTS_AUDIT",
    "AI_SAFEGUARDS_ENTRY_ALLOWED_AUDIT",
    "AI_SAFEGUARDS_ENTRY_REJECTED_AUDIT",
    "AI_SAFEGUARDS_ENTRY_REPORTED_AUDIT",
    "ANY",
]

# =============================================================================
# TYPE: AuditTime
# =============================================================================


def _blank_to_none(value: object) -> object:
    """
    Read the empty string and `N/A` that reports put in unset times as None.
    """
    if isinstance(value, str) and value.strip() in ("", "N/A"):
        return None
    return value


type AuditTime = Annotated[datetime | None, BeforeValidator(_blank_to_none)]


# =============================================================================
# CLASS: AuditJob
# =============================================================================


class AuditJob(GenericBaseModel):
    """
    The job a report create starts; poll it with `get_audit_job`.

    Egnyte documents the ID as a string but sends a number; it is kept as a
    string either way.
    """

    id: str = Field(
        coerce_numbers_to_str=True,
        description="Job ID; once the job completes, also the report ID.",
    )


# =============================================================================
# CLASS: AuditJobStatus
# =============================================================================


class AuditJobStatus(GenericBaseModel):
    """
    Where a report job stands.

    A running job answers 200 with `running`. A finished one answers 303 with
    `completed` and a `Location` pointing at the report, from which
    `report_type` and `report_id` are read; the redirect is not followed.
    """

    status: AuditJobState = Field(
        description="running or completed.",
    )
    location: str | None = Field(
        default=None,
        description="URL of the finished report, from the `Location` header.",
    )
    report_type: AuditReportType | None = Field(
        default=None,
        description="Type of the finished report, as `get_audit_report` takes it.",
    )
    report_id: str | None = Field(
        default=None,
        description="ID of the finished report, as `get_audit_report` takes it.",
    )

    @property
    def is_complete(self) -> bool:
        """
        Whether the report is ready.

        Returns:
            bool: True once the job has completed.
        """
        return self.status == "completed"


# =============================================================================
# CLASS: AuditRecord
# =============================================================================


class AuditRecord(GenericBaseModel):
    """
    One row of a JSON audit report.

    Every report type shares this model; each fills the fields its rows carry
    and leaves the rest None. Egnyte documents the rows of the login, file,
    permissions, user, group, and configuration settings reports, which the
    fields below cover. Fields of other report types are kept as extras
    (`model_extra`) rather than dropped. People appear as display name and
    email, such as `Jane Doe ( jdoe@acme.com )`.
    """

    model_config = ConfigDict(extra="allow")

    time: AuditTime = Field(
        default=None,
        description="When it happened (login, file, permissions, group, and settings reports).",
    )
    date_and_time: AuditTime = Field(
        default=None,
        description="When it happened (user report).",
    )
    username: str | None = Field(
        default=None,
        description="Who acted (login and file reports).",
    )
    user_id: int | None = Field(
        default=None,
        description="ID of `username`.",
    )
    event: str | None = Field(
        default=None,
        description="Login, Logout, Failed Attempt, and so on (login report).",
    )
    logout_time: AuditTime = Field(
        default=None,
        description="When the session ended, if it has (login report).",
    )
    details: str | None = Field(
        default=None,
        description="Extra detail on the login event (login report).",
    )
    access: str | None = Field(
        default=None,
        description="Access point, such as Web UI or Mobile (login and file reports).",
    )
    ip_address: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ip_address", "ipAddress"),
        description="Client IP address (login, file, and settings reports).",
    )
    file: str | None = Field(
        default=None,
        description="Path of the file acted on (file report).",
    )
    folder: str | None = Field(
        default=None,
        description="Path of the folder acted on (file and permissions reports).",
    )
    target_path: str | None = Field(
        default=None,
        description="Destination of a move or copy (file report).",
    )
    link: str | None = Field(
        default=None,
        description="Link used, for link activity (file report).",
    )
    transaction: str | None = Field(
        default=None,
        description="What was done, such as Move File (file report).",
    )
    file_checksum: str | None = Field(
        default=None,
        description="Checksum of the file, or N/A (file report).",
    )
    assignee: str | None = Field(
        default=None,
        description="User or group that received the permission (permissions report).",
    )
    assignee_id: int | None = Field(
        default=None,
        description="ID of `assignee`.",
    )
    assigner: str | None = Field(
        default=None,
        description="User who changed the permission (permissions report).",
    )
    assigner_id: int | None = Field(
        default=None,
        description="ID of `assigner`.",
    )
    change: str | None = Field(
        default=None,
        description="The change, such as +Editor or Editor>>Owner (permissions report).",
    )
    performed_by: str | None = Field(
        default=None,
        description="User who made the change (user report).",
    )
    performed_by_id: int | None = Field(
        default=None,
        description="ID of `performed_by`.",
    )
    subject: str | None = Field(
        default=None,
        description="User who was changed (user report).",
    )
    subject_id: int | None = Field(
        default=None,
        description="ID of `subject`.",
    )
    actor: str | None = Field(
        default=None,
        description="User who made the change (group and settings reports).",
    )
    actor_id: int | None = Field(
        default=None,
        description="ID of `actor`.",
    )
    group: str | None = Field(
        default=None,
        description="Group that was changed (group report).",
    )
    action: str | None = Field(
        default=None,
        description="What was done, such as Create or Add Users (user and group reports).",
    )
    action_info: str | None = Field(
        default=None,
        validation_alias=AliasChoices("action_info", "actionInfo"),
        description="Detail on the action (file, user, and group reports).",
    )
    action_source: str | None = Field(
        default=None,
        description="Where the change came from, such as Web UI (user report).",
    )
    source: str | None = Field(
        default=None,
        description="Where the change came from, such as Web UI (group report).",
    )
    setting_screen: str | None = Field(
        default=None,
        description="Settings screen, such as SECURITY (settings report).",
    )
    setting_name: str | None = Field(
        default=None,
        description="Setting that changed (settings report).",
    )
    old_value: str | None = Field(
        default=None,
        description="Value before the change (settings report).",
    )
    new_value: str | None = Field(
        default=None,
        description="Value after the change (settings report).",
    )


# =============================================================================
# CLASS: AuditReport
# =============================================================================


class AuditReport(GenericBaseModel):
    """
    A JSON audit report, or one page of it.

    Without `offset` and `count` on the request the whole report arrives;
    Egnyte then reports `count` as 0 rather than the number of rows.
    """

    total_count: int = Field(
        default=0,
        description="Rows in the whole report.",
    )
    offset: int = Field(
        default=0,
        description="Index of the first row in this page.",
    )
    count: int = Field(
        default=0,
        description="Rows requested for this page; 0 when the whole report was asked for.",
    )
    events: list[AuditRecord] = Field(
        default_factory=list,
        description="The rows.",
    )


# =============================================================================
# CLASS: AuditEvent
# =============================================================================


class AuditEvent(GenericBaseModel):
    """
    One event from the v2 audit stream.

    The fields carried depend on `audit_source`. Egnyte documents file, user,
    and group events, which the fields below cover; fields of other event
    types are kept as extras (`model_extra`) rather than dropped.
    """

    model_config = ConfigDict(extra="allow")

    date: datetime = Field(
        description="When it happened.",
    )
    audit_source: str = Field(
        alias="auditSource",
        description="Event type, such as FILE_AUDIT or USER_AUDIT.",
    )
    action: str | None = Field(
        default=None,
        description="What was done, such as Upload, Disable, or Create.",
    )
    action_info: str | None = Field(
        default=None,
        alias="actionInfo",
        description="Detail on the action.",
    )
    user: str | None = Field(
        default=None,
        description="Who acted, as name and email (file events).",
    )
    user_id: str | None = Field(
        default=None,
        alias="userId",
        description="ID of `user` (file events).",
    )
    source_path: str | None = Field(
        default=None,
        alias="sourcePath",
        description="Path acted on (file events).",
    )
    target_path: str | None = Field(
        default=None,
        alias="targetPath",
        description="Destination of a move or copy, or N/A (file events).",
    )
    access: str | None = Field(
        default=None,
        description="Access method, such as Web UI or Desktop App (file events).",
    )
    ip_address: str | None = Field(
        default=None,
        alias="ipAddress",
        description="Client IP address (file events).",
    )
    actor: str | None = Field(
        default=None,
        description="Who made the change, as name and email (user and group events).",
    )
    subject: str | None = Field(
        default=None,
        description="User who was changed, as name and email (user events).",
    )
    group: str | None = Field(
        default=None,
        description="Group that was changed (group events).",
    )
    source: str | None = Field(
        default=None,
        description="Where the change came from, such as Web UI or API (user and group events).",
    )


# =============================================================================
# CLASS: AuditEventPage
# =============================================================================


class AuditEventPage(GenericBaseModel):
    """
    One page of the v2 audit stream.

    Pass `next_cursor` to the next call; `more_events` turns false once the
    stream has caught up with the present, after which polling with the
    latest cursor picks up new events.
    """

    events: list[AuditEvent] = Field(
        default_factory=list,
        description="Up to 5,000 events, spanning at most 30 minutes.",
    )
    next_cursor: str | None = Field(
        default=None,
        alias="nextCursor",
        description="Cursor for the next page; expires after 7 days.",
    )
    more_events: bool = Field(
        default=False,
        alias="moreEvents",
        description="Whether more events are available now.",
    )
    cursor_expired: bool | None = Field(
        default=None,
        alias="cursorExpired",
        description="Whether the cursor given has expired (sent live, undocumented).",
    )


# =============================================================================
# CLASSES: Report requests
# =============================================================================


class QualityDocsCategoryFilter(GenericBaseModel):
    """
    A Quality Docs category to report on, optionally narrowed to subcategories.
    """

    id: str
    subcategory_ids: list[str] | None = Field(default=None, alias="subcategoryIds")


class AuditReportRequest(GenericBaseModel):
    """
    The fields every report create takes.
    """

    format: AuditReportFormat
    date_start: str
    date_end: str


class _Users(GenericBaseModel):
    users: list[str] | None = None


class _SuppressEmails(GenericBaseModel):
    suppress_emails: bool | None = None


class _SystemActions(GenericBaseModel):
    include_system_actions: bool | None = None


class LoginAuditRequest(AuditReportRequest, _Users, _SuppressEmails):
    """
    Request body for the login audit report.
    """

    events: list[LoginAuditEvent]
    access_points: list[LoginAccessPoint] | None = None


class FileAuditRequest(AuditReportRequest, _Users, _SuppressEmails):
    """
    Request body for the file audit report.
    """

    folders: list[str] | None = None
    file: str | None = None
    transaction_type: list[FileAuditTransaction] | None = None


class PermissionsAuditRequest(AuditReportRequest, _SuppressEmails):
    """
    Request body for the permissions audit report.
    """

    folders: list[str] | None = None
    assigners: list[str] | None = None
    assignee_users: list[str] | None = None
    assignee_groups: list[str] | None = None


class UserAuditRequest(AuditReportRequest, _SystemActions):
    """
    Request body for the user provisioning audit report.
    """

    action_type: list[UserAuditAction] | None = None
    performed_by: list[str] | None = None
    subject: list[str] | None = None


class GroupAuditRequest(AuditReportRequest, _Users, _SystemActions):
    """
    Request body for the group provisioning audit report.
    """

    action_type: list[GroupAuditAction] | None = None
    groups: list[str] | None = None


class WorkgroupSettingsAuditRequest(AuditReportRequest, _Users):
    """
    Request body for the configuration settings audit report.
    """


class WorkflowAuditRequest(AuditReportRequest, _Users, _SuppressEmails):
    """
    Request body for the workflow audit report.
    """

    file: str | None = None
    workflow_actions: list[WorkflowAuditAction] | None = None
    workflow_types: list[WorkflowAuditType] | None = None


class WorkflowTemplateAuditRequest(AuditReportRequest, _Users, _SuppressEmails):
    """
    Request body for the workflow templates audit report.
    """

    workflow_template_actions: list[WorkflowTemplateAuditAction] | None = None


class QualityDocsAuditRequest(AuditReportRequest, _Users, _SuppressEmails):
    """
    Request body for the Quality Docs audit report.
    """

    quality_document_id: str | None = None
    quality_docs_categories: list[QualityDocsCategoryFilter] | None = None
    quality_docs_actions: list[QualityDocsAuditAction] | None = None
    quality_docs_statuses: list[QualityDocsStatus] | None = None


class QualityDocsCategoriesAuditRequest(AuditReportRequest, _Users, _SuppressEmails):
    """
    Request body for the Quality Docs categories audit report.
    """

    quality_docs_categories: list[QualityDocsCategoryFilter] | None = None
    quality_docs_categories_actions: list[QualityDocsCategoryAuditAction] | None = None


class QualityDocsCoursesAuditRequest(AuditReportRequest, _Users, _SuppressEmails):
    """
    Request body for the Quality Docs courses audit report.
    """

    quality_docs_courses_ids: list[str] | None = None
    quality_docs_courses_actions: list[QualityDocsCourseAuditAction] | None = None
    quality_docs_courses_parameters: list[QualityDocsCourseParameter] | None = None


class EtmfAuditRequest(AuditReportRequest, _Users, _SuppressEmails):
    """
    Request body for the eTMF audit report.
    """

    etmf_actions: list[EtmfAuditAction] | None = None
    etmf_study_ids: list[str] | None = None
    etmf_artifact_number: str | None = None


class SnapshotRestoreAuditRequest(
    AuditReportRequest, _Users, _SystemActions, _SuppressEmails
):
    """
    Request body for the snapshot restore audit report.
    """


class UploadRequestsAuditRequest(AuditReportRequest, _Users, _SuppressEmails):
    """
    Request body for the upload requests audit report.
    """

    upload_requests_actions: list[UploadRequestAuditAction] | None = None


class AuditStreamRequest(GenericBaseModel):
    """
    Request body for the v2 audit stream.
    """

    start_date: str | None = Field(default=None, alias="startDate")
    end_date: str | None = Field(default=None, alias="endDate")
    next_cursor: str | None = Field(default=None, alias="nextCursor")
    audit_type: list[AuditStreamType] | None = Field(default=None, alias="auditType")
