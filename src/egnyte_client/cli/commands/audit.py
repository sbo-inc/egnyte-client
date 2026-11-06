from collections.abc import Callable
from datetime import datetime
from typing import Any

import click
from pydantic import TypeAdapter, ValidationError

from egnyte_client.cli.context import ClientContext
from egnyte_client.cli.group import CommonClickGroup
from egnyte_client.cli.options import (
    confirm,
    exactly_one,
    paging_options,
    parse_json,
    yes_option,
)
from egnyte_client.cli.output import render, write_bytes
from egnyte_client.schemas.audit import AuditJob, QualityDocsCategoryFilter

REPORT_TYPES = click.Choice(
    [
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
)
FORMATS = click.Choice(["csv", "json"])
LOGIN_EVENTS = click.Choice(
    ["logins", "logouts", "account_lockouts", "password_resets", "failed_attempts"]
)
ACCESS_POINTS = click.Choice(["web", "ftp", "mobile"])
FILE_TRANSACTIONS = click.Choice(
    [
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
)
USER_ACTIONS = click.Choice(
    [
        "CREATE",
        "UPDATE",
        "DISABLE",
        "ENABLE",
        "DELETE",
        "PASSWORD_RESET",
        "PASSWORD_CHANGE",
    ]
)
GROUP_ACTIONS = click.Choice(
    ["CREATE", "ADD_USERS", "REMOVE_USERS", "RENAME", "DELETE"]
)
WORKFLOW_ACTIONS = click.Choice(
    [
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
)
WORKFLOW_TYPES = click.Choice(
    ["REVIEW_APPROVE", "TODO", "APPROVAL", "REVIEW", "MULTISTEP", "TEMPLATE"]
)
WORKFLOW_TEMPLATE_ACTIONS = click.Choice(
    [
        "TEMPLATE_CREATED",
        "TEMPLATE_STATUS_CHANGED",
        "TEMPLATE_EDITED",
        "STEP_ADDED",
        "STEP_REMOVED",
        "ITEM_ADDED",
        "ITEM_REMOVED",
    ]
)
QUALITY_DOCS_ACTIONS = click.Choice(
    [
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
)
QUALITY_DOCS_STATUSES = click.Choice(
    ["DRAFT", "EFFECTIVE", "FUTURE_EFFECTIVE", "OBSOLETE"]
)
QUALITY_DOCS_CATEGORY_ACTIONS = click.Choice(
    ["CATEGORY_ADDED", "CATEGORY_MODIFIED", "SUBCATEGORY_ADDED", "SUBCATEGORY_MODIFIED"]
)
QUALITY_DOCS_COURSE_ACTIONS = click.Choice(
    [
        "COURSE_CREATED",
        "COURSE_MODIFIED",
        "COURSE_STATUS_CHANGED",
        "COURSE_DOCUMENT_STATUS_CHANGED",
    ]
)
QUALITY_DOCS_COURSE_PARAMETERS = click.Choice(
    [
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
)
ETMF_ACTIONS = click.Choice(
    [
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
)
UPLOAD_REQUEST_ACTIONS = click.Choice(
    [
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
)
STREAM_TYPES = click.Choice(
    [
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
)

DATE = click.DateTime()
_CATEGORIES = TypeAdapter(list[QualityDocsCategoryFilter])

# =============================================================================
# FUNCTIONS: Shared options
# =============================================================================


def _report_options[F: Callable[..., Any]](func: F) -> F:
    """
    Add the `START END` arguments and `--format` option every report takes.

    Returns:
        F: The decorated command.
    """
    func = click.option(
        "--format",
        "format_",
        type=FORMATS,
        default="json",
        show_default=True,
        help="Report format; read json with `audit get`, csv with `audit download`.",
    )(func)
    func = click.argument("end_date", metavar="END", type=DATE)(func)
    return click.argument("start_date", metavar="START", type=DATE)(func)


def _users_option(help_text: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Build the repeatable `--user` option, with help naming whose actions it picks.

    Returns:
        Callable: The option decorator.
    """
    return click.option("--user", "users", multiple=True, help=help_text)


def _suppress_emails_option[F: Callable[..., Any]](func: F) -> F:
    """
    Add the `--suppress-emails` flag.

    Returns:
        F: The decorated command.
    """
    return click.option(
        "--suppress-emails",
        is_flag=True,
        default=False,
        help="Skip the email Egnyte sends when the report is ready.",
    )(func)


def _system_actions_option(
    default: str,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Build the `--include-system-actions/--exclude-system-actions` switch.

    Returns:
        Callable: The option decorator.
    """
    return click.option(
        "--include-system-actions/--exclude-system-actions",
        default=None,
        help=f"Whether to report system-initiated actions (Egnyte {default} them by default).",
    )


def _parse_categories(
    ctx: click.Context, param: click.Parameter, value: str | None
) -> list[QualityDocsCategoryFilter] | None:
    """
    Decode `--categories` and check it against the request model.
    """
    raw: object = parse_json(value)
    if raw is None:
        return None
    try:
        return _CATEGORIES.validate_python(raw)
    except ValidationError as exc:
        raise click.BadParameter(
            "; ".join(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors(include_url=False)
            )
        ) from exc


def _categories_options[F: Callable[..., Any]](func: F) -> F:
    """
    Add the `--category` and `--categories` options of the Quality Docs reports.

    Returns:
        F: The decorated command.
    """
    func = click.option(
        "--categories",
        "categories_json",
        default=None,
        callback=_parse_categories,
        help=(
            'Categories with subcategories, as JSON, such as \'[{"id": "c1", '
            '"subcategoryIds": ["s1"]}]\'.'
        ),
    )(func)
    return click.option(
        "--category",
        "category_ids",
        multiple=True,
        help="Category ID to report on, with all its subcategories (repeatable).",
    )(func)


def _categories(
    category_ids: tuple[str, ...], categories: list[QualityDocsCategoryFilter] | None
) -> list[QualityDocsCategoryFilter] | None:
    """
    Merge `--category` IDs and `--categories` filters into one list.

    Returns:
        list[QualityDocsCategoryFilter] | None: The filters, or None for all.
    """
    merged = list(categories or []) + [
        QualityDocsCategoryFilter(id=category_id) for category_id in category_ids
    ]
    return merged or None


def _check_range(start_date: datetime, end_date: datetime) -> None:
    """
    Refuse an empty report range before anything is sent.
    """
    if end_date <= start_date:
        raise click.BadParameter("END must be after START.", param_hint="END")


def _started(job: AuditJob) -> None:
    """
    Print a started report's job, with a hint on what to run next.
    """
    render(job)
    click.echo(f"Started job {job.id}; check it with `audit job {job.id}`.", err=True)


def _file_pattern(file: str | None) -> str | None:
    """
    Refuse a name pattern that starts with the `*` wildcard.

    Returns:
        str | None: The pattern.
    """
    if file is not None and file.startswith("*"):
        raise click.BadParameter(
            "cannot start with the * wildcard", param_hint="--file"
        )
    return file


def _many(values: tuple[str, ...]) -> list[str] | None:
    """
    Turn a repeatable option into the list the client takes, or None if unused.

    Returns:
        list[str] | None: The values.
    """
    return list(values) or None


# =============================================================================
# GROUP: audit
# =============================================================================


@click.group(name="audit", cls=CommonClickGroup)
def group() -> None:
    """
    Run audit reports and read the audit event stream.

    A report is made in three steps: `audit create TYPE` starts a job,
    `audit job JOB_ID` shows when it is done (poll at most every 2 minutes),
    and `audit get` (json) or `audit download` (csv) reads it.
    """


@group.group(name="create", cls=CommonClickGroup)
def create() -> None:
    """
    Start an audit report job. START and END are YYYY-MM-DD or ISO 8601 (UTC).
    """


@create.command(name="logins")
@_report_options
@click.option(
    "--event",
    "events",
    type=LOGIN_EVENTS,
    multiple=True,
    required=True,
    help="Login event to include (repeatable; at least one).",
)
@click.option(
    "--access-point",
    "access_points",
    type=ACCESS_POINTS,
    multiple=True,
    help="Access point to include (repeatable). Defaults to all.",
)
@_users_option("User whose logins to include (repeatable). Defaults to all.")
@_suppress_emails_option
@click.pass_obj
def create_logins(
    ctx: ClientContext,
    start_date: datetime,
    end_date: datetime,
    format_: str,
    events: tuple[str, ...],
    access_points: tuple[str, ...],
    users: tuple[str, ...],
    suppress_emails: bool,
) -> None:
    """
    Report logins, logouts, lockouts, password resets, and failed attempts.
    """
    _check_range(start_date, end_date)
    _started(
        ctx.client.create_login_audit_report(
            start_date,
            end_date,
            events=list(events),  # type: ignore[arg-type]
            format=format_,  # type: ignore[arg-type]
            access_points=_many(access_points),  # type: ignore[arg-type]
            users=_many(users),
            suppress_emails=suppress_emails or None,
        )
    )


@create.command(name="files")
@_report_options
@click.option(
    "--folder",
    "folders",
    multiple=True,
    help="Folder path to report on (repeatable). Needed unless --file is given.",
)
@click.option(
    "--file",
    default=None,
    help="File name pattern; may use the * wildcard, but not first.",
)
@_users_option("User whose actions to include (repeatable). Defaults to all.")
@click.option(
    "--transaction",
    "transaction_types",
    type=FILE_TRANSACTIONS,
    multiple=True,
    help="Transaction type to include (repeatable). Defaults to all.",
)
@_suppress_emails_option
@click.pass_obj
def create_files(
    ctx: ClientContext,
    start_date: datetime,
    end_date: datetime,
    format_: str,
    folders: tuple[str, ...],
    file: str | None,
    users: tuple[str, ...],
    transaction_types: tuple[str, ...],
    suppress_emails: bool,
) -> None:
    """
    Report file and folder actions: uploads, downloads, moves, links, and so on.

    The time of day in START and END is ignored.
    """
    if not folders and not file:
        raise click.UsageError("Give --folder, --file, or both.")
    _check_range(start_date, end_date)
    _started(
        ctx.client.create_file_audit_report(
            start_date,
            end_date,
            folders=_many(folders),
            file=_file_pattern(file),
            format=format_,  # type: ignore[arg-type]
            users=_many(users),
            transaction_types=_many(transaction_types),  # type: ignore[arg-type]
            suppress_emails=suppress_emails or None,
        )
    )


@create.command(name="permissions")
@_report_options
@click.option(
    "--folder",
    "folders",
    multiple=True,
    help="Folder path to report on (repeatable). Defaults to all.",
)
@click.option(
    "--assigner",
    "assigners",
    multiple=True,
    help="User who changed permissions (repeatable). Defaults to all.",
)
@click.option(
    "--assignee-user",
    "assignee_users",
    multiple=True,
    help="User who was granted permissions (repeatable).",
)
@click.option(
    "--assignee-group",
    "assignee_groups",
    multiple=True,
    help="Group that was granted permissions (repeatable).",
)
@_suppress_emails_option
@click.pass_obj
def create_permissions(
    ctx: ClientContext,
    start_date: datetime,
    end_date: datetime,
    format_: str,
    folders: tuple[str, ...],
    assigners: tuple[str, ...],
    assignee_users: tuple[str, ...],
    assignee_groups: tuple[str, ...],
    suppress_emails: bool,
) -> None:
    """
    Report folder permission changes.

    Without --assignee-user only group grants are reported, and without
    --assignee-group only user grants. The time of day in START and END is
    ignored.
    """
    _check_range(start_date, end_date)
    _started(
        ctx.client.create_permissions_audit_report(
            start_date,
            end_date,
            format=format_,  # type: ignore[arg-type]
            folders=_many(folders),
            assigners=_many(assigners),
            assignee_users=_many(assignee_users),
            assignee_groups=_many(assignee_groups),
            suppress_emails=suppress_emails or None,
        )
    )


@create.command(name="users")
@_report_options
@click.option(
    "--action",
    "action_types",
    type=USER_ACTIONS,
    multiple=True,
    help="Account change to include (repeatable). Defaults to all.",
)
@click.option(
    "--performed-by",
    multiple=True,
    help="User who made the change (repeatable). Defaults to all.",
)
@click.option(
    "--subject",
    "subjects",
    multiple=True,
    help="User who was changed (repeatable). Defaults to all.",
)
@_system_actions_option("excludes")
@click.pass_obj
def create_users(
    ctx: ClientContext,
    start_date: datetime,
    end_date: datetime,
    format_: str,
    action_types: tuple[str, ...],
    performed_by: tuple[str, ...],
    subjects: tuple[str, ...],
    include_system_actions: bool | None,
) -> None:
    """
    Report user account changes: creates, updates, disables, deletes, and passwords.

    The time of day in START and END is ignored.
    """
    _check_range(start_date, end_date)
    _started(
        ctx.client.create_user_audit_report(
            start_date,
            end_date,
            format=format_,  # type: ignore[arg-type]
            action_types=_many(action_types),  # type: ignore[arg-type]
            performed_by=_many(performed_by),
            subjects=_many(subjects),
            include_system_actions=include_system_actions,
        )
    )


@create.command(name="groups")
@_report_options
@click.option(
    "--action",
    "action_types",
    type=GROUP_ACTIONS,
    multiple=True,
    help="Group change to include (repeatable). Defaults to all.",
)
@_users_option("User who made the change (repeatable). Defaults to all.")
@click.option(
    "--group",
    "groups",
    multiple=True,
    help="Group name, matched case-insensitively (repeatable). Defaults to all.",
)
@_system_actions_option("excludes")
@click.pass_obj
def create_groups(
    ctx: ClientContext,
    start_date: datetime,
    end_date: datetime,
    format_: str,
    action_types: tuple[str, ...],
    users: tuple[str, ...],
    groups: tuple[str, ...],
    include_system_actions: bool | None,
) -> None:
    """
    Report group changes: creates, membership changes, renames, and deletes.

    The time of day in START and END is ignored.
    """
    _check_range(start_date, end_date)
    _started(
        ctx.client.create_group_audit_report(
            start_date,
            end_date,
            format=format_,  # type: ignore[arg-type]
            action_types=_many(action_types),  # type: ignore[arg-type]
            users=_many(users),
            groups=_many(groups),
            include_system_actions=include_system_actions,
        )
    )


@create.command(name="workgroup-settings")
@_report_options
@_users_option("User who made the change (repeatable). Defaults to all.")
@click.pass_obj
def create_workgroup_settings(
    ctx: ClientContext,
    start_date: datetime,
    end_date: datetime,
    format_: str,
    users: tuple[str, ...],
) -> None:
    """
    Report domain configuration setting changes.

    The time of day in START and END is ignored.
    """
    _check_range(start_date, end_date)
    _started(
        ctx.client.create_workgroup_settings_audit_report(
            start_date,
            end_date,
            format=format_,  # type: ignore[arg-type]
            users=_many(users),
        )
    )


@create.command(name="workflows")
@_report_options
@_users_option("User whose activity to include (repeatable). Defaults to all.")
@click.option(
    "--file",
    default=None,
    help="Workflow name pattern; may use the * wildcard, but not first.",
)
@click.option(
    "--action",
    "workflow_actions",
    type=WORKFLOW_ACTIONS,
    multiple=True,
    help="Workflow action to include (repeatable). Defaults to all.",
)
@click.option(
    "--workflow-type",
    "workflow_types",
    type=WORKFLOW_TYPES,
    multiple=True,
    help="Workflow type to include (repeatable). Defaults to all.",
)
@_suppress_emails_option
@click.pass_obj
def create_workflows(
    ctx: ClientContext,
    start_date: datetime,
    end_date: datetime,
    format_: str,
    users: tuple[str, ...],
    file: str | None,
    workflow_actions: tuple[str, ...],
    workflow_types: tuple[str, ...],
    suppress_emails: bool,
) -> None:
    """
    Report workflow activity: workflows, steps, tasks, and webhooks.
    """
    _check_range(start_date, end_date)
    _started(
        ctx.client.create_workflow_audit_report(
            start_date,
            end_date,
            format=format_,  # type: ignore[arg-type]
            users=_many(users),
            file=_file_pattern(file),
            workflow_actions=_many(workflow_actions),  # type: ignore[arg-type]
            workflow_types=_many(workflow_types),  # type: ignore[arg-type]
            suppress_emails=suppress_emails or None,
        )
    )


@create.command(name="workflow-templates")
@_report_options
@_users_option("User who made the change (repeatable). Defaults to all.")
@click.option(
    "--action",
    "workflow_template_actions",
    type=WORKFLOW_TEMPLATE_ACTIONS,
    multiple=True,
    help="Template change to include (repeatable). Defaults to all.",
)
@_suppress_emails_option
@click.pass_obj
def create_workflow_templates(
    ctx: ClientContext,
    start_date: datetime,
    end_date: datetime,
    format_: str,
    users: tuple[str, ...],
    workflow_template_actions: tuple[str, ...],
    suppress_emails: bool,
) -> None:
    """
    Report workflow template changes.
    """
    _check_range(start_date, end_date)
    _started(
        ctx.client.create_workflow_template_audit_report(
            start_date,
            end_date,
            format=format_,  # type: ignore[arg-type]
            users=_many(users),
            workflow_template_actions=_many(workflow_template_actions),  # type: ignore[arg-type]
            suppress_emails=suppress_emails or None,
        )
    )


@create.command(name="quality-docs")
@_report_options
@_users_option("User whose activity to include (repeatable). Defaults to all.")
@click.option(
    "--document-id",
    "quality_document_id",
    default=None,
    help="Quality document to report on. Defaults to all.",
)
@_categories_options
@click.option(
    "--action",
    "quality_docs_actions",
    type=QUALITY_DOCS_ACTIONS,
    multiple=True,
    help="Action to include (repeatable). Defaults to all.",
)
@click.option(
    "--status",
    "quality_docs_statuses",
    type=QUALITY_DOCS_STATUSES,
    multiple=True,
    help="Document status to include (repeatable). Defaults to all.",
)
@_suppress_emails_option
@click.pass_obj
def create_quality_docs(
    ctx: ClientContext,
    start_date: datetime,
    end_date: datetime,
    format_: str,
    users: tuple[str, ...],
    quality_document_id: str | None,
    category_ids: tuple[str, ...],
    categories_json: list[QualityDocsCategoryFilter] | None,
    quality_docs_actions: tuple[str, ...],
    quality_docs_statuses: tuple[str, ...],
    suppress_emails: bool,
) -> None:
    """
    Report Quality Docs activity: documents, drafts, and training.
    """
    _check_range(start_date, end_date)
    _started(
        ctx.client.create_quality_docs_audit_report(
            start_date,
            end_date,
            format=format_,  # type: ignore[arg-type]
            users=_many(users),
            quality_document_id=quality_document_id,
            quality_docs_categories=_categories(category_ids, categories_json),
            quality_docs_actions=_many(quality_docs_actions),  # type: ignore[arg-type]
            quality_docs_statuses=_many(quality_docs_statuses),  # type: ignore[arg-type]
            suppress_emails=suppress_emails or None,
        )
    )


@create.command(name="quality-docs-categories")
@_report_options
@_users_option("User who made the change (repeatable). Defaults to all.")
@_categories_options
@click.option(
    "--action",
    "quality_docs_categories_actions",
    type=QUALITY_DOCS_CATEGORY_ACTIONS,
    multiple=True,
    help="Category change to include (repeatable). Defaults to all.",
)
@_suppress_emails_option
@click.pass_obj
def create_quality_docs_categories(
    ctx: ClientContext,
    start_date: datetime,
    end_date: datetime,
    format_: str,
    users: tuple[str, ...],
    category_ids: tuple[str, ...],
    categories_json: list[QualityDocsCategoryFilter] | None,
    quality_docs_categories_actions: tuple[str, ...],
    suppress_emails: bool,
) -> None:
    """
    Report Quality Docs category and subcategory changes.
    """
    _check_range(start_date, end_date)
    _started(
        ctx.client.create_quality_docs_categories_audit_report(
            start_date,
            end_date,
            format=format_,  # type: ignore[arg-type]
            users=_many(users),
            quality_docs_categories=_categories(category_ids, categories_json),
            quality_docs_categories_actions=_many(quality_docs_categories_actions),  # type: ignore[arg-type]
            suppress_emails=suppress_emails or None,
        )
    )


@create.command(name="quality-docs-courses")
@_report_options
@_users_option("User who made the change (repeatable). Defaults to all.")
@click.option(
    "--course-id",
    "quality_docs_courses_ids",
    multiple=True,
    help="Training course to report on (repeatable). Defaults to all.",
)
@click.option(
    "--action",
    "quality_docs_courses_actions",
    type=QUALITY_DOCS_COURSE_ACTIONS,
    multiple=True,
    help="Course change to include (repeatable). Defaults to all.",
)
@click.option(
    "--parameter",
    "quality_docs_courses_parameters",
    type=QUALITY_DOCS_COURSE_PARAMETERS,
    multiple=True,
    help="Course setting whose changes to include (repeatable). Defaults to all.",
)
@_suppress_emails_option
@click.pass_obj
def create_quality_docs_courses(
    ctx: ClientContext,
    start_date: datetime,
    end_date: datetime,
    format_: str,
    users: tuple[str, ...],
    quality_docs_courses_ids: tuple[str, ...],
    quality_docs_courses_actions: tuple[str, ...],
    quality_docs_courses_parameters: tuple[str, ...],
    suppress_emails: bool,
) -> None:
    """
    Report Quality Docs training course changes.
    """
    _check_range(start_date, end_date)
    _started(
        ctx.client.create_quality_docs_courses_audit_report(
            start_date,
            end_date,
            format=format_,  # type: ignore[arg-type]
            users=_many(users),
            quality_docs_courses_ids=_many(quality_docs_courses_ids),
            quality_docs_courses_actions=_many(quality_docs_courses_actions),  # type: ignore[arg-type]
            quality_docs_courses_parameters=_many(quality_docs_courses_parameters),  # type: ignore[arg-type]
            suppress_emails=suppress_emails or None,
        )
    )


@create.command(name="etmf")
@_report_options
@_users_option("User whose activity to include (repeatable). Defaults to all.")
@click.option(
    "--action",
    "etmf_actions",
    type=ETMF_ACTIONS,
    multiple=True,
    help="eTMF action to include (repeatable). Defaults to all.",
)
@click.option(
    "--study-id",
    "etmf_study_ids",
    multiple=True,
    help="Study to report on (repeatable). Defaults to all.",
)
@click.option(
    "--artifact-number",
    "etmf_artifact_number",
    default=None,
    help="Artifact number to report on. Defaults to all.",
)
@_suppress_emails_option
@click.pass_obj
def create_etmf(
    ctx: ClientContext,
    start_date: datetime,
    end_date: datetime,
    format_: str,
    users: tuple[str, ...],
    etmf_actions: tuple[str, ...],
    etmf_study_ids: tuple[str, ...],
    etmf_artifact_number: str | None,
    suppress_emails: bool,
) -> None:
    """
    Report eTMF activity: studies, trials, countries, sites, documents, and artifacts.
    """
    _check_range(start_date, end_date)
    _started(
        ctx.client.create_etmf_audit_report(
            start_date,
            end_date,
            format=format_,  # type: ignore[arg-type]
            users=_many(users),
            etmf_actions=_many(etmf_actions),  # type: ignore[arg-type]
            etmf_study_ids=_many(etmf_study_ids),
            etmf_artifact_number=etmf_artifact_number,
            suppress_emails=suppress_emails or None,
        )
    )


@create.command(name="snapshot-restore")
@_report_options
@_users_option("User whose activity to include (repeatable). Defaults to all.")
@_system_actions_option("includes")
@_suppress_emails_option
@click.pass_obj
def create_snapshot_restore(
    ctx: ClientContext,
    start_date: datetime,
    end_date: datetime,
    format_: str,
    users: tuple[str, ...],
    include_system_actions: bool | None,
    suppress_emails: bool,
) -> None:
    """
    Report snapshot mounts, unmounts, previews, and restores.
    """
    _check_range(start_date, end_date)
    _started(
        ctx.client.create_snapshot_restore_audit_report(
            start_date,
            end_date,
            format=format_,  # type: ignore[arg-type]
            users=_many(users),
            include_system_actions=include_system_actions,
            suppress_emails=suppress_emails or None,
        )
    )


@create.command(name="upload-requests")
@_report_options
@_users_option("User whose activity to include (repeatable). Defaults to all.")
@click.option(
    "--action",
    "upload_requests_actions",
    type=UPLOAD_REQUEST_ACTIONS,
    multiple=True,
    help="Upload request action to include (repeatable). Defaults to all.",
)
@_suppress_emails_option
@click.pass_obj
def create_upload_requests(
    ctx: ClientContext,
    start_date: datetime,
    end_date: datetime,
    format_: str,
    users: tuple[str, ...],
    upload_requests_actions: tuple[str, ...],
    suppress_emails: bool,
) -> None:
    """
    Report upload request activity: requests, uploads, submissions, and reviews.
    """
    _check_range(start_date, end_date)
    _started(
        ctx.client.create_upload_requests_audit_report(
            start_date,
            end_date,
            format=format_,  # type: ignore[arg-type]
            users=_many(users),
            upload_requests_actions=_many(upload_requests_actions),  # type: ignore[arg-type]
            suppress_emails=suppress_emails or None,
        )
    )


# -----------------------------------------------------------------------------
# COMMANDS: jobs and reports
# -----------------------------------------------------------------------------


@group.command(name="job")
@click.argument("job_id")
@click.pass_obj
def job(ctx: ClientContext, job_id: str) -> None:
    """
    Show whether a report job has finished, and the report to read once it has.

    Egnyte asks that a job be polled no more than once every 2 minutes.
    """
    render(ctx.client.get_audit_job(job_id))


@group.command(name="get")
@click.argument("report_type", metavar="TYPE", type=REPORT_TYPES)
@click.argument("report_id")
@paging_options
@click.pass_obj
def get(
    ctx: ClientContext,
    report_type: str,
    report_id: str,
    offset: int | None,
    count: int | None,
) -> None:
    """
    Show a finished JSON report, whole or one page of rows.
    """
    render(
        ctx.client.get_audit_report(
            report_type,  # type: ignore[arg-type]
            report_id,
            offset=offset,
            count=count,
        )
    )


@group.command(name="download")
@click.argument("report_type", metavar="TYPE", type=REPORT_TYPES)
@click.argument("report_id")
@click.option(
    "-o",
    "--output",
    default="-",
    show_default=True,
    help="Local file to write, or `-` for stdout.",
)
@click.pass_obj
def download(ctx: ClientContext, report_type: str, report_id: str, output: str) -> None:
    """
    Download a finished report as Egnyte serves it: CSV, or raw JSON.
    """
    write_bytes(
        ctx.client.download_audit_report(report_type, report_id),  # type: ignore[arg-type]
        output,
    )


@group.command(name="delete")
@click.argument("report_type", metavar="TYPE", type=REPORT_TYPES)
@click.argument("report_id")
@yes_option
@click.pass_obj
def delete(ctx: ClientContext, report_type: str, report_id: str, yes: bool) -> None:
    """
    Delete a report.
    """
    confirm(yes, f"Delete {report_type} audit report {report_id}?")
    ctx.client.delete_audit_report(report_type, report_id)  # type: ignore[arg-type]
    click.echo(f"Deleted {report_type} audit report {report_id}", err=True)


# -----------------------------------------------------------------------------
# COMMAND: stream
# -----------------------------------------------------------------------------


@group.command(name="stream")
@click.option(
    "--start-date",
    type=DATE,
    default=None,
    help="Read from this time, within the last 7 days (YYYY-MM-DD or ISO 8601, UTC).",
)
@click.option(
    "--cursor",
    default=None,
    help="Continue from a previous page's `next_cursor` instead of --start-date.",
)
@click.option(
    "--end-date",
    type=DATE,
    default=None,
    help="Read up to this time (YYYY-MM-DD or ISO 8601, UTC).",
)
@click.option(
    "--type",
    "audit_types",
    type=STREAM_TYPES,
    multiple=True,
    help="Event type to include (repeatable). Defaults to ANY.",
)
@click.pass_obj
def stream(
    ctx: ClientContext,
    start_date: datetime | None,
    cursor: str | None,
    end_date: datetime | None,
    audit_types: tuple[str, ...],
) -> None:
    """
    Print one page of the audit event stream.

    Start with --start-date, then pass each page's `next_cursor` as --cursor.
    While `more_events` is true more events are ready; pages over quiet
    periods may be empty. Egnyte allows 10 calls a minute and 100 an hour.
    """
    exactly_one(("--start-date", start_date), ("--cursor", cursor))

    render(
        ctx.client.stream_audit_events(
            start_date=start_date,
            next_cursor=cursor,
            audit_types=_many(audit_types),  # type: ignore[arg-type]
            end_date=end_date,
        )
    )
