from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

import click

from egnyte_client.cli.context import ClientContext
from egnyte_client.cli.group import CommonClickGroup
from egnyte_client.cli.options import confirm, exactly_one, paging_options, yes_option
from egnyte_client.cli.output import render, write_bytes
from egnyte_client.operations import filesystem as fs_ops
from egnyte_client.schemas.filesystem import ItemReference

MIB = 1024 * 1024

PERMISSIONS = click.Choice(["keep_original", "inherit_from_parent"])
FOLDER_OPTIONS_MODES = click.Choice(["keep_source", "apply_destination"])
PUBLIC_LINKS = click.Choice(["files_folders", "folders", "files", "disabled"])
MOVE_DELETE_RESTRICTIONS = click.Choice(
    ["admins_owners_or_full_access_users", "admins_or_owners", "admins_only"]
)
INHERITANCE_RULES = click.Choice(
    [
        "legacy",
        "this_folder_only",
        "this_folder_and_subfolders_until_overridden",
        "this_folder_and_subfolders",
    ]
)

# =============================================================================
# FUNCTIONS: By-ID targets
# =============================================================================


def _file_id_option[F: Callable[..., Any]](func: F) -> F:
    """
    Add the `--file-id` option, which addresses a file by group ID.

    Returns:
        F: The decorated command.
    """
    return click.option(
        "--file-id",
        default=None,
        help="Address the file by this group ID instead of a path.",
    )(func)


def _folder_id_option[F: Callable[..., Any]](func: F) -> F:
    """
    Add the `--folder-id` option, which addresses a folder by folder ID.

    Returns:
        F: The decorated command.
    """
    return click.option(
        "--folder-id",
        default=None,
        help="Address the folder by this folder ID instead of a path.",
    )(func)


def _describe(path: str | None, file_id: str | None, folder_id: str | None) -> str:
    """
    Name a target for a prompt or a note on stderr.

    Returns:
        str: The path, or `file ID` / `folder ID`.
    """
    if file_id is not None:
        return f"file {file_id}"
    if folder_id is not None:
        return f"folder {folder_id}"
    return str(path)


# =============================================================================
# GROUP: fs
# =============================================================================


@click.group(name="fs", cls=CommonClickGroup)
def group() -> None:
    """
    Browse, upload, download, and manage files and folders.

    Paths are absolute Egnyte paths, such as `/Shared/Projects/plan.pdf`. Most
    commands also take a file's group ID (`--file-id`) or a folder's ID
    (`--folder-id`) in place of the path.
    """


@group.command(name="ls")
@click.argument("path", required=False)
@_folder_id_option
@paging_options
@click.option(
    "--sort-by",
    type=click.Choice(["name", "last_modified", "uploaded_by"]),
    default=None,
    help="Sort the children by this field.",
)
@click.option(
    "--sort-direction",
    type=click.Choice(["ascending", "descending"]),
    default=None,
    help="Sort direction.",
)
@click.pass_obj
def ls(
    ctx: ClientContext,
    path: str | None,
    folder_id: str | None,
    offset: int | None,
    count: int | None,
    sort_by: str | None,
    sort_direction: str | None,
) -> None:
    """
    List a folder's sub-folders and files, by PATH or --folder-id.
    """
    exactly_one(("PATH", path), ("--folder-id", folder_id))
    if folder_id is not None:
        render(
            ctx.client.get_folder_by_id(
                folder_id,
                count=count,
                offset=offset,
                sort_by=sort_by,  # type: ignore[arg-type]
                sort_direction=sort_direction,  # type: ignore[arg-type]
            )
        )
        return
    render(
        ctx.client.get_folder(
            str(path),
            count=count,
            offset=offset,
            sort_by=sort_by,  # type: ignore[arg-type]
            sort_direction=sort_direction,  # type: ignore[arg-type]
        )
    )


@group.command(name="stat")
@click.argument("path", required=False)
@_file_id_option
@_folder_id_option
@click.option(
    "--versions", is_flag=True, default=False, help="Include a file's versions."
)
@click.pass_obj
def stat(
    ctx: ClientContext,
    path: str | None,
    file_id: str | None,
    folder_id: str | None,
    versions: bool,
) -> None:
    """
    Show a file's or folder's metadata, by PATH, --file-id, or --folder-id.

    A folder is shown with its first page of children.
    """
    exactly_one(("PATH", path), ("--file-id", file_id), ("--folder-id", folder_id))
    if folder_id is not None:
        if versions:
            raise click.UsageError("--versions applies only to files.")
        render(ctx.client.get_folder_by_id(folder_id))
    elif file_id is not None:
        render(ctx.client.get_file_by_id(file_id, include_versions=versions))
    elif versions:
        render(ctx.client.get_file(str(path), include_versions=True))
    else:
        render(ctx.client.get_item(str(path)))


@group.command(name="stats")
@click.argument("path", required=False)
@_folder_id_option
@click.pass_obj
def stats(ctx: ClientContext, path: str | None, folder_id: str | None) -> None:
    """
    Show a folder's total size and file, version, and sub-folder counts.

    The totals include every sub-folder. A PATH costs one extra call to look up
    the folder's ID.
    """
    exactly_one(("PATH", path), ("--folder-id", folder_id))
    if folder_id is None:
        folder_id = ctx.client.get_folder(str(path)).folder_id
    render(ctx.client.get_folder_stats(folder_id))


@group.command(name="mkdir")
@click.argument("path")
@click.pass_obj
def mkdir(ctx: ClientContext, path: str) -> None:
    """
    Create a folder.
    """
    render(ctx.client.create_folder(path))


@group.command(name="upload")
@click.argument("source", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("destination", required=False)
@_file_id_option
@click.option(
    "--chunk-size",
    type=click.IntRange(fs_ops.MIN_CHUNK_SIZE // MIB, fs_ops.MAX_CHUNK_SIZE // MIB),
    default=None,
    help=(
        f"Chunk size in MiB ({fs_ops.MIN_CHUNK_SIZE // MIB}-"
        f"{fs_ops.MAX_CHUNK_SIZE // MIB}); a larger file is uploaded in chunks. "
        f"Defaults to {fs_ops.DEFAULT_CHUNK_SIZE // MIB}."
    ),
)
@click.pass_obj
def upload(
    ctx: ClientContext,
    source: Path,
    destination: str | None,
    file_id: str | None,
    chunk_size: int | None,
) -> None:
    """
    Upload a local file to an Egnyte path, or as a new version by --file-id.

    A DESTINATION ending in `/` is treated as a folder, and the local file name
    is appended. A file up to the chunk size (100 MiB by default, Egnyte's
    single-request limit) is sent in one request; a larger one is streamed in
    chunks, never held whole in memory. With --file-id the file's current path
    is looked up first (one extra call) and the new version is uploaded there.
    """
    exactly_one(("DESTINATION", destination), ("--file-id", file_id))
    if destination is not None and destination.endswith("/"):
        destination = destination + source.name

    chunk_bytes = chunk_size * MIB if chunk_size else fs_ops.DEFAULT_CHUNK_SIZE
    size = source.stat().st_size
    if size > chunk_bytes:
        click.echo(f"Uploading {size} bytes in chunks of {chunk_bytes} bytes", err=True)
        with source.open("rb") as stream:
            if file_id is not None:
                render(
                    ctx.client.upload_file_chunked_by_id(
                        file_id, stream, chunk_size=chunk_bytes
                    )
                )
            else:
                render(
                    ctx.client.upload_file_chunked(
                        str(destination), stream, chunk_size=chunk_bytes
                    )
                )
        return

    if file_id is not None:
        destination = ctx.client.get_file_by_id(file_id).path
    render(ctx.client.upload_file(str(destination), source.read_bytes()))


@group.command(name="download")
@click.argument("source", required=False)
@_file_id_option
@click.option(
    "-o",
    "--output",
    type=str,
    default=None,
    help="Local file to write, or `-` for stdout. Defaults to the file name.",
)
@click.option(
    "--entry-id", type=str, default=None, help="Download this version of the file."
)
@click.pass_obj
def download(
    ctx: ClientContext,
    source: str | None,
    file_id: str | None,
    output: str | None,
    entry_id: str | None,
) -> None:
    """
    Download an Egnyte file, by SOURCE path or --file-id.

    With --file-id and no --output, the file's name is looked up first (one
    extra call).
    """
    exactly_one(("SOURCE", source), ("--file-id", file_id))
    if file_id is not None:
        if output is None:
            output = ctx.client.get_file_by_id(file_id).name
        data = ctx.client.download_file_by_id(file_id, entry_id=entry_id)
    else:
        data = ctx.client.download_file(str(source), entry_id=entry_id)
        output = output or PurePosixPath(str(source)).name
    write_bytes(data, output)


def _transfer_options[F: Callable[..., Any]](func: F) -> F:
    """
    Add the arguments and options shared by `cp` and `mv`.

    Returns:
        F: The decorated command.
    """
    func = click.option(
        "--folder-options-mode",
        type=FOLDER_OPTIONS_MODES,
        default=None,
        help="Keep the folder's options or apply the destination's "
        "(with --folder-id); the workgroup setting decides by default.",
    )(func)
    func = click.option(
        "--permissions",
        type=PERMISSIONS,
        default=None,
        help="Keep the item's own permissions or take the destination's.",
    )(func)
    func = click.option(
        "--name",
        default=None,
        help="New name in the destination folder (with --file-id or "
        "--folder-id); the item keeps its name by default.",
    )(func)
    func = _folder_id_option(func)
    func = _file_id_option(func)
    func = click.argument("destination", required=False)(func)
    return click.argument("source", required=False)(func)


def _transfer(
    ctx: ClientContext,
    action: str,
    source: str | None,
    destination: str | None,
    file_id: str | None,
    folder_id: str | None,
    name: str | None,
    permissions: str | None,
    folder_options_mode: str | None,
) -> ItemReference:
    """
    Copy or move an item by path, or by ID into a folder given by ID.

    By path, SOURCE and DESTINATION are full paths. By ID, the one positional
    argument is the destination folder's ID.

    Returns:
        ItemReference: The item's new path and ID.
    """
    client = ctx.client
    if file_id is None and folder_id is None:
        if source is None or destination is None:
            raise click.UsageError(
                "Give SOURCE and DESTINATION paths, or --file-id or --folder-id "
                "and a DEST_FOLDER_ID."
            )
        if name is not None or folder_options_mode is not None:
            raise click.UsageError(
                "--name and --folder-options-mode apply only with --file-id or "
                "--folder-id; give the new name in DESTINATION."
            )
        if action == "copy":
            return client.copy_item(source, destination, permissions=permissions)  # type: ignore[arg-type]
        return client.move_item(source, destination, permissions=permissions)  # type: ignore[arg-type]

    exactly_one(("--file-id", file_id), ("--folder-id", folder_id))
    if source is None or destination is not None:
        raise click.UsageError(
            "With --file-id or --folder-id, give only a DEST_FOLDER_ID, no SOURCE."
        )
    destination_folder_id = source
    if file_id is not None:
        if folder_options_mode is not None:
            raise click.UsageError("--folder-options-mode applies only to folders.")
        transfer = (
            client.copy_file_by_id if action == "copy" else client.move_file_by_id
        )
        return transfer(
            file_id,
            destination_folder_id,
            name=name,
            permissions=permissions,  # type: ignore[arg-type]
        )
    transfer_folder = (
        client.copy_folder_by_id if action == "copy" else client.move_folder_by_id
    )
    return transfer_folder(
        str(folder_id),
        destination_folder_id,
        name=name,
        permissions=permissions,  # type: ignore[arg-type]
        folder_options_mode=folder_options_mode,  # type: ignore[arg-type]
    )


@group.command(name="cp")
@_transfer_options
@click.pass_obj
def cp(
    ctx: ClientContext,
    source: str | None,
    destination: str | None,
    file_id: str | None,
    folder_id: str | None,
    name: str | None,
    permissions: str | None,
    folder_options_mode: str | None,
) -> None:
    """
    Copy a file or folder, by path or by ID.

    By path, give SOURCE and DESTINATION, the full new path including the name.
    By ID, give --file-id or --folder-id and one argument, DEST_FOLDER_ID: the copy goes
    into that folder, keeping its name unless --name gives another.
    """
    render(
        _transfer(
            ctx,
            "copy",
            source,
            destination,
            file_id,
            folder_id,
            name,
            permissions,
            folder_options_mode,
        )
    )


@group.command(name="mv")
@_transfer_options
@click.pass_obj
def mv(
    ctx: ClientContext,
    source: str | None,
    destination: str | None,
    file_id: str | None,
    folder_id: str | None,
    name: str | None,
    permissions: str | None,
    folder_options_mode: str | None,
) -> None:
    """
    Move or rename a file or folder, by path or by ID.

    By path, give SOURCE and DESTINATION, the full new path including the name.
    By ID, give --file-id or --folder-id and one argument, DEST_FOLDER_ID: the item moves
    into that folder, keeping its name unless --name gives another.
    """
    render(
        _transfer(
            ctx,
            "move",
            source,
            destination,
            file_id,
            folder_id,
            name,
            permissions,
            folder_options_mode,
        )
    )


@group.command(name="rm")
@click.argument("path", required=False)
@_file_id_option
@_folder_id_option
@click.option(
    "--entry-id", type=str, default=None, help="Delete only this version of a file."
)
@yes_option
@click.pass_obj
def rm(
    ctx: ClientContext,
    path: str | None,
    file_id: str | None,
    folder_id: str | None,
    entry_id: str | None,
    yes: bool,
) -> None:
    """
    Delete a file or folder (it moves to the trash), by PATH or ID.
    """
    exactly_one(("PATH", path), ("--file-id", file_id), ("--folder-id", folder_id))
    if folder_id is not None and entry_id is not None:
        raise click.UsageError("--entry-id applies only to files.")
    target = _describe(path, file_id, folder_id)
    if entry_id is not None:
        confirm(yes, f"Delete version {entry_id} of {target}?")
    else:
        confirm(yes, f"Delete {target}?")

    if file_id is not None:
        render(ctx.client.delete_file_by_id(file_id, entry_id=entry_id))
    elif folder_id is not None:
        render(ctx.client.delete_folder_by_id(folder_id))
    else:
        render(ctx.client.delete_item(str(path), entry_id=entry_id))


@group.command(name="lock")
@click.argument("path", required=False)
@_file_id_option
@click.option(
    "--lock-token",
    default=None,
    help="Refresh the lock held with this token; Egnyte makes a new one by default.",
)
@click.option(
    "--timeout",
    "lock_timeout",
    type=click.IntRange(1, fs_ops.MAX_LOCK_TIMEOUT),
    default=None,
    help="Seconds until the lock expires (default 3600, at most 604800).",
)
@click.option(
    "--collaboration",
    default=None,
    help="Base64 token of the UI Integration Framework app taking the lock.",
)
@click.pass_obj
def lock(
    ctx: ClientContext,
    path: str | None,
    file_id: str | None,
    lock_token: str | None,
    lock_timeout: int | None,
    collaboration: str | None,
) -> None:
    """
    Lock a file, by PATH or --file-id, and print the lock token.

    The token is needed to unlock the file or to refresh the lock.
    """
    exactly_one(("PATH", path), ("--file-id", file_id))
    if file_id is not None:
        result = ctx.client.lock_file_by_id(
            file_id,
            lock_token=lock_token,
            lock_timeout=lock_timeout,
            collaboration=collaboration,
        )
    else:
        result = ctx.client.lock_file(
            str(path),
            lock_token=lock_token,
            lock_timeout=lock_timeout,
            collaboration=collaboration,
        )
    if result.timeout is not None:
        click.echo(
            f"Locked {_describe(path, file_id, None)} for {result.timeout} seconds",
            err=True,
        )
    render(result.lock_token)


@group.command(name="unlock")
@click.argument("path", required=False)
@_file_id_option
@click.option("--lock-token", required=True, help="The token the file was locked with.")
@click.pass_obj
def unlock(
    ctx: ClientContext, path: str | None, file_id: str | None, lock_token: str
) -> None:
    """
    Unlock a file, by PATH or --file-id, with the token it was locked with.
    """
    exactly_one(("PATH", path), ("--file-id", file_id))
    if file_id is not None:
        ctx.client.unlock_file_by_id(file_id, lock_token)
    else:
        ctx.client.unlock_file(str(path), lock_token)
    click.echo(f"Unlocked {_describe(path, file_id, None)}", err=True)


@group.command(name="options")
@click.argument("path")
@click.option(
    "--description", default=None, help="Folder description (at most 200 characters)."
)
@click.option(
    "--allow-links/--no-allow-links",
    default=None,
    help="Allow links to the folder's content; off disables every link.",
)
@click.option(
    "--allow-upload-links/--no-allow-upload-links",
    default=None,
    help="Allow upload links to the folder.",
)
@click.option(
    "--public-links",
    type=PUBLIC_LINKS,
    default=None,
    help="Which items may have links that anyone can open.",
)
@click.option(
    "--restrict-move-delete/--no-restrict-move-delete",
    default=None,
    help="Restrict who may move or delete the folder.",
)
@click.option(
    "--move-delete-restriction",
    "move_delete_folder_restriction",
    type=MOVE_DELETE_RESTRICTIONS,
    default=None,
    help="Who may move or delete the folder; overrides --restrict-move-delete.",
)
@click.option(
    "--inheritance-rule",
    type=INHERITANCE_RULES,
    default=None,
    help="How far the options reach into sub-folders.",
)
@click.option(
    "--notify-content-updates/--no-notify-content-updates",
    default=None,
    help="Email me when files in the folder are uploaded.",
)
@click.option(
    "--notify-content-accessed/--no-notify-content-accessed",
    default=None,
    help="Email me when files in the folder are downloaded (power users and admins).",
)
@click.pass_obj
def options(
    ctx: ClientContext,
    path: str,
    description: str | None,
    allow_links: bool | None,
    allow_upload_links: bool | None,
    public_links: str | None,
    restrict_move_delete: bool | None,
    move_delete_folder_restriction: str | None,
    inheritance_rule: str | None,
    notify_content_updates: bool | None,
    notify_content_accessed: bool | None,
) -> None:
    """
    Change a folder's description, link, move and delete, and notification options.

    Only the options given change. The move and delete restrictions do not
    apply to top-level folders, and Egnyte does not report the notification
    settings back.
    """
    changes = (
        description,
        allow_links,
        allow_upload_links,
        public_links,
        restrict_move_delete,
        move_delete_folder_restriction,
        inheritance_rule,
        notify_content_updates,
        notify_content_accessed,
    )
    if all(change is None for change in changes):
        raise click.UsageError("Give at least one option to change.")
    render(
        ctx.client.update_folder_options(
            path,
            description=description,
            allow_links=allow_links,
            allow_upload_links=allow_upload_links,
            public_links=public_links,  # type: ignore[arg-type]
            restrict_move_delete=restrict_move_delete,
            move_delete_folder_restriction=move_delete_folder_restriction,  # type: ignore[arg-type]
            inheritance_rule=inheritance_rule,  # type: ignore[arg-type]
            notify_content_updates=notify_content_updates,
            notify_content_accessed=notify_content_accessed,
        )
    )


@group.command(name="recent")
@click.option("--folder", default=None, help="Only files within this folder path.")
@click.pass_obj
def recent(ctx: ClientContext, folder: str | None) -> None:
    """
    List up to ten files you accessed most recently, newest first.
    """
    render(ctx.client.list_recent_files(folder_path=folder))
