from collections.abc import Callable
from typing import Any

import click
from pydantic import BaseModel, TypeAdapter, ValidationError

from egnyte_client.cli.context import ClientContext
from egnyte_client.cli.group import CommonClickGroup
from egnyte_client.cli.options import confirm, exactly_one, parse_json, yes_option
from egnyte_client.cli.output import render
from egnyte_client.schemas.metadata import (
    CreateMetadataKeyRequest,
    MetadataKeyDefinition,
    MetadataKeyValue,
    MetadataValuesRequest,
    UpdateMetadataKeyRequest,
)

KEY_TYPES = click.Choice(
    ["string", "integer", "decimal", "date", "enum", "labels", "multi_value_enum"]
)
SCOPES = click.Choice(["public", "protected", "private"])
SCOPE_TYPES = click.Choice(["GLOBAL", "FOLDER_SCOPE", "DOCUMENT_TYPE"])
DOCUMENT_TYPES = click.Choice(
    [
        "PDF",
        "DOCUMENT",
        "SPREADSHEET",
        "PRESENTATION",
        "IMAGE",
        "AUDIO_VIDEO",
        "TEXT_SOURCE_CODE",
        "GOOGLE_FILE",
        "EMAIL",
        "CAD",
        "ARCHIVE",
    ]
)

_KEY_DEFINITIONS = TypeAdapter(dict[str, MetadataKeyDefinition])
_KEY_VALUES = TypeAdapter(dict[str, list[str]])

# =============================================================================
# FUNCTIONS: Option parsing
# =============================================================================


def _describe(exc: ValidationError) -> str:
    """
    Summarize a validation error as `location: message` pairs on one line.
    """
    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
        if error["loc"]
        else error["msg"]
        for error in exc.errors(include_url=False)
    )


def _parse_keys(
    ctx: click.Context, param: click.Parameter, value: str | None
) -> dict[str, MetadataKeyDefinition] | None:
    """
    Decode `--keys` and check each definition against the request model.
    """
    raw: object = parse_json(value)
    if raw is None:
        return None
    try:
        keys = _KEY_DEFINITIONS.validate_python(raw)
    except ValidationError as exc:
        raise click.BadParameter(_describe(exc)) from exc
    if not keys:
        raise click.BadParameter("a namespace needs at least one key")
    return keys


def _parse_key_values(
    ctx: click.Context, param: click.Parameter, value: str | None
) -> dict[str, list[str]] | None:
    """
    Decode a `{key: [value, ...]}` document of allowed values.
    """
    raw: object = parse_json(value)
    if raw is None:
        return None
    try:
        return _KEY_VALUES.validate_python(raw)
    except ValidationError as exc:
        raise click.BadParameter(_describe(exc)) from exc


def _parse_values(
    ctx: click.Context, param: click.Parameter, value: str | None
) -> dict[str, MetadataKeyValue | None] | None:
    """
    Decode a `{key: value}` document of metadata values.
    """
    raw: object = parse_json(value)
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise click.BadParameter("expected a JSON object of key names to values")
    try:
        return MetadataValuesRequest.model_validate(raw).root
    except ValidationError as exc:
        bad = sorted({str(error["loc"][0]) for error in exc.errors() if error["loc"]})
        raise click.BadParameter(
            f"{', '.join(bad)}: expected text, a number, a list of text, or null"
        ) from exc


def _parse_pairs(
    ctx: click.Context, param: click.Parameter, value: tuple[str, ...]
) -> list[tuple[str, str]]:
    """
    Split repeated `KEY=VALUE` options into pairs.
    """
    pairs: list[tuple[str, str]] = []
    for item in value:
        key, sep, text = item.partition("=")
        if not sep or not key:
            raise click.BadParameter(f"expected KEY=VALUE, got {item!r}")
        pairs.append((key, text))
    return pairs


def _parse_priorities(
    ctx: click.Context, param: click.Parameter, value: tuple[str, ...]
) -> dict[str, int]:
    """
    Read repeated `KEY=PRIORITY` options into a mapping.
    """
    priorities: dict[str, int] = {}
    for key, text in _parse_pairs(ctx, param, value):
        try:
            priorities[key] = int(text)
        except ValueError as exc:
            raise click.BadParameter(
                f"expected KEY=PRIORITY with an integer priority, got {key}={text}"
            ) from exc
    return priorities


def _check[M: BaseModel](model: type[M], **fields: object) -> M:
    """
    Validate flag values against a request model before anything is sent.

    Returns:
        M: The validated request.
    """
    try:
        return model.model_validate(fields)
    except ValidationError as exc:
        raise click.UsageError(_describe(exc)) from exc


def _item(file_id: str | None, folder_id: str | None) -> tuple[str, str]:
    """
    Pick the file or folder a values command acts on; exactly one is given.

    Returns:
        tuple[str, str]: `file` or `folder`, and the ID.
    """
    exactly_one(("--file-id", file_id), ("--folder-id", folder_id))
    return ("file", file_id) if file_id is not None else ("folder", str(folder_id))


def _item_options[F: Callable[..., Any]](func: F) -> F:
    """
    Add the `--file-id` and `--folder-id` options of the values commands.

    Returns:
        F: The decorated command.
    """
    func = click.option(
        "--folder-id", default=None, help="Act on the folder with this ID."
    )(func)
    return click.option(
        "--file-id",
        default=None,
        help="Act on the file with this group ID, or the version with this entry ID.",
    )(func)


# =============================================================================
# GROUP: metadata
# =============================================================================


@click.group(name="metadata", cls=CommonClickGroup)
def group() -> None:
    """
    Define metadata namespaces and keys, and read or set values on items.
    """


# -----------------------------------------------------------------------------
# GROUP: metadata namespaces
# -----------------------------------------------------------------------------


@group.group(name="namespaces", cls=CommonClickGroup)
def namespaces() -> None:
    """
    List, inspect, and manage metadata namespaces.
    """


@namespaces.command(name="list")
@click.option(
    "--folder-associations",
    is_flag=True,
    default=False,
    help="Include the folders each folder-scoped namespace applies to.",
)
@click.pass_obj
def list_(ctx: ClientContext, folder_associations: bool) -> None:
    """
    List the domain's namespaces and their keys.
    """
    render(
        ctx.client.list_metadata_namespaces(
            include_folder_associations=folder_associations or None
        )
    )


@namespaces.command(name="get")
@click.argument("namespace")
@click.pass_obj
def get_namespace(ctx: ClientContext, namespace: str) -> None:
    """
    Show a namespace and its key definitions.
    """
    render(ctx.client.get_metadata_namespace(namespace))


@namespaces.command(name="create")
@click.argument("name")
@click.option(
    "--keys",
    required=True,
    callback=_parse_keys,
    help=(
        'Key definitions as a JSON object, such as \'{"status": {"type": "enum", '
        '"helpText": "...", "data": ["open", "closed"]}}\'.'
    ),
)
@click.option(
    "--scope",
    type=SCOPES,
    default="public",
    show_default=True,
    help="Who sees and edits it: everyone, everyone sees but only this app edits, or only this app.",
)
@click.option("--display-name", default=None, help="Name shown in the UI.")
@click.option(
    "--inheritable/--no-inheritable",
    default=None,
    help="Whether child items inherit the values.",
)
@click.option(
    "--scope-type",
    type=SCOPE_TYPES,
    default=None,
    help="Where it applies; FOLDER_SCOPE needs --folder-id, DOCUMENT_TYPE --document-type.",
)
@click.option(
    "--folder-id",
    "folder_ids",
    multiple=True,
    help="Folder a FOLDER_SCOPE namespace applies to (repeatable).",
)
@click.option(
    "--document-type",
    "document_types",
    type=DOCUMENT_TYPES,
    multiple=True,
    help="Document type a DOCUMENT_TYPE namespace applies to (repeatable).",
)
@click.pass_obj
def create_namespace(
    ctx: ClientContext,
    name: str,
    keys: dict[str, MetadataKeyDefinition],
    scope: str,
    display_name: str | None,
    inheritable: bool | None,
    scope_type: str | None,
    folder_ids: tuple[str, ...],
    document_types: tuple[str, ...],
) -> None:
    """
    Create a namespace with its keys. Needs an admin.
    """
    if scope_type == "DOCUMENT_TYPE" and not document_types:
        raise click.UsageError("--scope-type DOCUMENT_TYPE needs --document-type.")

    ctx.client.create_metadata_namespace(
        name,
        keys=keys,
        scope=scope,  # type: ignore[arg-type]
        display_name=display_name,
        inheritable=inheritable,
        scope_type=scope_type,  # type: ignore[arg-type]
        folder_ids=list(folder_ids) or None,
        document_types=list(document_types) or None,  # type: ignore[arg-type]
    )
    click.echo(f"Created namespace {name}", err=True)


@namespaces.command(name="update")
@click.argument("namespace")
@click.option("--display-name", default=None, help="New name shown in the UI.")
@click.option(
    "--priority",
    "priorities",
    multiple=True,
    callback=_parse_priorities,
    metavar="KEY=PRIORITY",
    help="Display priority of a key, higher first (repeatable).",
)
@click.option(
    "--associate-folder",
    "associate_folder_ids",
    multiple=True,
    help="Folder ID to add to a folder-scoped namespace (repeatable).",
)
@click.option(
    "--dissociate-folder",
    "dissociate_folder_ids",
    multiple=True,
    help="Folder ID to remove from a folder-scoped namespace (repeatable).",
)
@click.option(
    "--associate-document-type",
    "associate_document_types",
    type=DOCUMENT_TYPES,
    multiple=True,
    help="Document type to add to a document-type namespace (repeatable).",
)
@click.option(
    "--dissociate-document-type",
    "dissociate_document_types",
    type=DOCUMENT_TYPES,
    multiple=True,
    help="Document type to remove from a document-type namespace (repeatable).",
)
@click.pass_obj
def update_namespace(
    ctx: ClientContext,
    namespace: str,
    display_name: str | None,
    priorities: dict[str, int],
    associate_folder_ids: tuple[str, ...],
    dissociate_folder_ids: tuple[str, ...],
    associate_document_types: tuple[str, ...],
    dissociate_document_types: tuple[str, ...],
) -> None:
    """
    Rename a namespace, reorder its keys, or change where it applies.

    Folder and document type associations cannot change in one call.
    """
    folders = associate_folder_ids or dissociate_folder_ids
    types = associate_document_types or dissociate_document_types
    if folders and types:
        raise click.UsageError(
            "Folder and document type associations cannot change in one call."
        )
    if not (display_name or priorities or folders or types):
        raise click.UsageError("Give at least one change.")

    render(
        ctx.client.update_metadata_namespace(
            namespace,
            display_name=display_name,
            priorities=priorities or None,
            associate_folder_ids=list(associate_folder_ids) or None,
            dissociate_folder_ids=list(dissociate_folder_ids) or None,
            associate_document_types=list(associate_document_types) or None,  # type: ignore[arg-type]
            dissociate_document_types=list(dissociate_document_types) or None,  # type: ignore[arg-type]
        )
    )


@namespaces.command(name="delete")
@click.argument("namespace")
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Delete even if items carry its values (otherwise Egnyte refuses).",
)
@yes_option
@click.pass_obj
def delete_namespace(
    ctx: ClientContext, namespace: str, force: bool, yes: bool
) -> None:
    """
    Delete a namespace, its keys, and their values on every item.
    """
    confirm(yes, f"Delete metadata namespace {namespace} and all its values?")
    ctx.client.delete_metadata_namespace(namespace, force=force)
    click.echo(f"Deleted namespace {namespace}", err=True)


@namespaces.command(name="delete-values")
@click.argument("namespace")
@click.option(
    "--values",
    "values_json",
    default=None,
    callback=_parse_key_values,
    help='Allowed values to remove, by key, as JSON, such as \'{"status": ["closed"]}\'.',
)
@click.option(
    "--value",
    "pairs",
    multiple=True,
    callback=_parse_pairs,
    metavar="KEY=VALUE",
    help="An allowed value to remove from a key (repeatable).",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Remove values even if items use them (otherwise Egnyte refuses).",
)
@yes_option
@click.pass_obj
def delete_namespace_values(
    ctx: ClientContext,
    namespace: str,
    values_json: dict[str, list[str]] | None,
    pairs: list[tuple[str, str]],
    force: bool,
    yes: bool,
) -> None:
    """
    Remove allowed values from several enum, multi-value enum, or labels keys.
    """
    values: dict[str, list[str]] = {
        key: list(data) for key, data in (values_json or {}).items()
    }
    for key, value in pairs:
        values.setdefault(key, []).append(value)
    if not any(values.values()):
        raise click.UsageError("Give --values or --value.")

    keys = ", ".join(key for key, data in values.items() if data)
    confirm(yes, f"Remove allowed values of {keys} in namespace {namespace}?")
    ctx.client.delete_metadata_values(namespace, values, force=force)
    click.echo(f"Removed allowed values of {keys} in {namespace}", err=True)


# -----------------------------------------------------------------------------
# GROUP: metadata keys
# -----------------------------------------------------------------------------


@group.group(name="keys", cls=CommonClickGroup)
def keys_group() -> None:
    """
    Add, change, and delete a namespace's keys.
    """


@keys_group.command(name="add")
@click.argument("namespace")
@click.argument("key")
@click.option("--type", "type_", type=KEY_TYPES, required=True, help="Data type.")
@click.option(
    "--help-text",
    required=True,
    help="Guidance shown to users filling in the key (20 to 200 characters).",
)
@click.option("--display-name", default=None, help="Name shown in the UI.")
@click.option(
    "--priority", type=int, default=None, help="Display order; higher is first."
)
@click.option(
    "--data",
    multiple=True,
    help="Allowed value, required for enum and multi_value_enum keys (repeatable).",
)
@click.option(
    "--timezone-independent",
    is_flag=True,
    default=None,
    help="Store a date key as UTC-midnight dates; cannot be undone.",
)
@click.pass_obj
def add_key(
    ctx: ClientContext,
    namespace: str,
    key: str,
    type_: str,
    help_text: str,
    display_name: str | None,
    priority: int | None,
    data: tuple[str, ...],
    timezone_independent: bool | None,
) -> None:
    """
    Add a key to a namespace.
    """
    request = _check(
        CreateMetadataKeyRequest,
        key=key,
        type=type_,
        help_text=help_text,
        display_name=display_name,
        priority=priority,
        data=list(data) or None,
        timezone_independent=timezone_independent,
    )
    ctx.client.add_metadata_key(
        namespace,
        key,
        request.type,
        request.help_text,
        display_name=request.display_name,
        priority=request.priority,
        data=request.data,
        timezone_independent=request.timezone_independent,
    )
    click.echo(f"Added key {key} to {namespace}", err=True)


@keys_group.command(name="update")
@click.argument("namespace")
@click.argument("key")
@click.option("--display-name", default=None, help="New name shown in the UI.")
@click.option(
    "--help-text",
    default=None,
    help="New guidance (20 to 200 characters); required if the key has none.",
)
@click.option(
    "--type",
    "type_",
    type=KEY_TYPES,
    default=None,
    help="Broaden the data type, such as integer to decimal or enum to string.",
)
@click.option(
    "--priority", type=int, default=None, help="Display order; higher is first."
)
@click.option(
    "--data",
    multiple=True,
    help=(
        "Allowed value (repeatable); replaces an enum key's values and appends "
        "to a multi_value_enum or labels key's."
    ),
)
@click.option(
    "--timezone-independent",
    is_flag=True,
    default=None,
    help="Store a date key as UTC-midnight dates; cannot be undone.",
)
@click.pass_obj
def update_key(
    ctx: ClientContext,
    namespace: str,
    key: str,
    display_name: str | None,
    help_text: str | None,
    type_: str | None,
    priority: int | None,
    data: tuple[str, ...],
    timezone_independent: bool | None,
) -> None:
    """
    Change a key's definition; only the options given change.
    """
    request = _check(
        UpdateMetadataKeyRequest,
        display_name=display_name,
        help_text=help_text,
        type=type_,
        priority=priority,
        data=list(data) or None,
        timezone_independent=timezone_independent,
    )
    if not request.model_dump(exclude_none=True):
        raise click.UsageError("Give at least one change.")

    ctx.client.update_metadata_key(
        namespace,
        key,
        display_name=request.display_name,
        help_text=request.help_text,
        type=request.type,
        priority=request.priority,
        data=request.data,
        timezone_independent=request.timezone_independent,
    )
    click.echo(f"Updated key {key} of {namespace}", err=True)


@keys_group.command(name="delete")
@click.argument("namespace")
@click.argument("key")
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Delete even if items carry its values (otherwise Egnyte refuses).",
)
@yes_option
@click.pass_obj
def delete_key(
    ctx: ClientContext, namespace: str, key: str, force: bool, yes: bool
) -> None:
    """
    Delete a key and its values on every item.
    """
    confirm(yes, f"Delete key {key} of namespace {namespace} and all its values?")
    ctx.client.delete_metadata_key(namespace, key, force=force)
    click.echo(f"Deleted key {key} of {namespace}", err=True)


@keys_group.command(name="delete-values")
@click.argument("namespace")
@click.argument("key")
@click.argument("values", nargs=-1, required=True)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Remove values even if items use them (otherwise Egnyte refuses).",
)
@yes_option
@click.pass_obj
def delete_key_values(
    ctx: ClientContext,
    namespace: str,
    key: str,
    values: tuple[str, ...],
    force: bool,
    yes: bool,
) -> None:
    """
    Remove allowed values from an enum, multi-value enum, or labels key.
    """
    confirm(yes, f"Remove {', '.join(values)} from key {key} of namespace {namespace}?")
    ctx.client.delete_metadata_key_values(namespace, key, list(values), force=force)
    click.echo(f"Removed {len(values)} allowed values from {key}", err=True)


# -----------------------------------------------------------------------------
# COMMANDS: values on files and folders
# -----------------------------------------------------------------------------


@group.command(name="get")
@click.argument("namespace")
@_item_options
@click.pass_obj
def get(
    ctx: ClientContext, namespace: str, file_id: str | None, folder_id: str | None
) -> None:
    """
    Show a namespace's values on a file or folder; dates are epoch milliseconds.
    """
    kind, item_id = _item(file_id, folder_id)
    if kind == "file":
        render(ctx.client.get_file_metadata(item_id, namespace))
    else:
        render(ctx.client.get_folder_metadata(item_id, namespace))


@group.command(name="set")
@click.argument("namespace")
@_item_options
@click.option(
    "--values",
    "values_json",
    default=None,
    callback=_parse_values,
    help=(
        "Values by key as a JSON object: text, numbers, lists of text, dates as "
        "epoch milliseconds, or null to remove."
    ),
)
@click.option(
    "--value",
    "pairs",
    multiple=True,
    callback=_parse_pairs,
    metavar="KEY=VALUE",
    help="Set KEY to the text VALUE (repeatable); use --values for other types.",
)
@click.option(
    "--remove",
    "removed",
    multiple=True,
    metavar="KEY",
    help="Remove KEY's value (repeatable).",
)
@click.pass_obj
def set_(
    ctx: ClientContext,
    namespace: str,
    file_id: str | None,
    folder_id: str | None,
    values_json: dict[str, MetadataKeyValue | None] | None,
    pairs: list[tuple[str, str]],
    removed: tuple[str, ...],
) -> None:
    """
    Set a namespace's values on a file or folder.

    Keys not given are left alone. Enum values replace, while labels and
    multi-value enum values are added.
    """
    kind, item_id = _item(file_id, folder_id)
    values: dict[str, MetadataKeyValue | None] = dict(values_json or {})
    given = [key for key, _ in pairs] + list(removed)
    duplicates = sorted({key for key in given if given.count(key) > 1 or key in values})
    if duplicates:
        raise click.UsageError(f"Key given more than once: {', '.join(duplicates)}")
    values.update(pairs)
    values.update(dict.fromkeys(removed))
    if not values:
        raise click.UsageError("Give --values, --value, or --remove.")

    if kind == "file":
        ctx.client.set_file_metadata(item_id, namespace, values)
    else:
        ctx.client.set_folder_metadata(item_id, namespace, values)
    click.echo(f"Set {len(values)} values of {namespace} on {kind} {item_id}", err=True)
